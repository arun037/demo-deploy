"""
Hierarchical Schema Embedding Retriever
Two-stage: Table retrieval → Column semantic ranking

Document types:
  table_schema  : one per table (purpose + column names + FKs — no descriptions)
  column_schema : one per column (table + column name + full description)
  relationship  : common multi-hop FK join paths
  business_rule : critical business logic (concept visibility, revenue calc, etc.)
  sql_example   : representative question → SQL pairs
"""
import json
import os
import re
import chromadb
from backend.core.logger import logger
from backend.config import Config


class EmbeddingRetriever:
    def __init__(self, schema_path=None):
        if not schema_path:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            schema_path = os.path.join(base_dir, "db_schema.json")

        self.schema_path = schema_path
        self.schema_data = self._load_schema()

        try:
            self.client = chromadb.CloudClient(
                api_key=Config.CHROMA_API_KEY,
                tenant=Config.CHROMA_TENANT,
                database=Config.CHROMA_DB_NAME
            )
            logger.info("Connected to Chroma Cloud successfully")
        except Exception as e:
            logger.error(f"Failed to connect to Chroma Cloud: {e}")
            raise

        if self._needs_rebuild():
            logger.info("Collection needs rebuild for hierarchical architecture. Deleting...")
            try:
                self.client.delete_collection(name=Config.CHROMA_COLLECTION_NAME)
                logger.info(f"Deleted collection: {Config.CHROMA_COLLECTION_NAME}")
            except Exception as e:
                logger.warning(f"Could not delete collection: {e}")

        self.collection = self.client.get_or_create_collection(
            name=Config.CHROMA_COLLECTION_NAME,
            metadata={"description": "Hierarchical schema embeddings", "version": "hierarchical_v1"}
        )
        self._initialize_embeddings()

    # ─────────────────────────────────────────────────────────────────────────
    # Schema Loading
    # ─────────────────────────────────────────────────────────────────────────

    def _load_schema(self):
        try:
            if os.path.exists(self.schema_path):
                with open(self.schema_path, 'r') as f:
                    data = json.load(f)
                logger.info(f"Loaded schema definition for {len(data)} tables.")
                return data
            logger.warning(f"Schema file not found at {self.schema_path}")
            return []
        except Exception as e:
            logger.error(f"Failed to load schema: {e}")
            return []

    # ─────────────────────────────────────────────────────────────────────────
    # Rebuild Detection
    # ─────────────────────────────────────────────────────────────────────────

    def _needs_rebuild(self):
        """
        Rebuild if:
          - collection uses old col_ IDs (original column-level chunks), or
          - collection uses CSR-RAG format but has no column_schema docs (v1 CSR-RAG), or
          - collection is empty (no rebuild needed, just empty)
        """
        try:
            col = self.client.get_or_create_collection(name=Config.CHROMA_COLLECTION_NAME)
            count = col.count()
            if count == 0:
                return False

            sample = col.get(limit=20, include=["metadatas"])
            ids = sample.get("ids", [])
            metadatas = sample.get("metadatas", [])

            # Old column-level format: IDs start with "col_" (but not the new "col_schema" format)
            for doc_id in ids:
                if str(doc_id).startswith("col_") and not str(doc_id).startswith("col_schema"):
                    logger.info("Detected old column-level embeddings. Rebuild needed.")
                    return True

            # CSR-RAG v1 format: has table_schema but no column_schema docs
            types_found = {m.get("type", "") for m in metadatas if m}
            if "table_schema" in types_found and "column_schema" not in types_found:
                logger.info("Detected CSR-RAG v1 (no column_schema). Rebuild needed.")
                return True

            # Check for new table format containing Column Summaries
            try:
                sample_docs = col.get(limit=20, include=["documents"])
                docs = sample_docs.get("documents", [])
                for doc in docs:
                    if "TYPE: table_schema" in str(doc) and "Column Summaries:" not in str(doc):
                        logger.info("Detected old table_schema format (no column summaries). Rebuild needed.")
                        return True
            except Exception as e:
                logger.warning(f"Error checking document contents: {e}")

            return False
        except Exception:
            return False

    # ─────────────────────────────────────────────────────────────────────────
    # Embedding Initialization
    # ─────────────────────────────────────────────────────────────────────────

    def _initialize_embeddings(self):
        if not self.schema_data:
            logger.warning("No schema data to embed.")
            return

        count = self.collection.count()
        if count > 0:
            logger.info(f"Collection has {count} docs. Skipping re-embed.")
            return

        logger.info("Building hierarchical schema embeddings...")
        documents, metadatas, ids = [], [], []

        # 1. TABLE_SCHEMA — one per table, column names only (no descriptions)
        ts_docs, ts_meta, ts_ids = self._generate_table_schema_docs()
        documents.extend(ts_docs); metadatas.extend(ts_meta); ids.extend(ts_ids)

        # 2. COLUMN_SCHEMA — one per column, full description
        #    Business rules and SQL patterns are embedded here via db_schema.json descriptions.
        col_docs, col_meta, col_ids = self._generate_column_schema_docs()
        documents.extend(col_docs); metadatas.extend(col_meta); ids.extend(col_ids)

        # 3. RELATIONSHIP — multi-hop FK join paths (auto-derived from FK graph)
        rel_docs, rel_meta, rel_ids = self._generate_relationship_docs()
        documents.extend(rel_docs); metadatas.extend(rel_meta); ids.extend(rel_ids)

        logger.info(f"Total docs to embed: {len(documents)}")
        logger.info(f"  table_schema={len(ts_docs)}, column_schema={len(col_docs)}, relationship={len(rel_docs)}")


        try:
            batch_size = 200
            for i in range(0, len(documents), batch_size):
                self.collection.add(
                    documents=documents[i:i + batch_size],
                    metadatas=metadatas[i:i + batch_size],
                    ids=ids[i:i + batch_size]
                )
            logger.info(f"✓ Embedding complete. Total docs: {self.collection.count()}")
        except Exception as e:
            logger.error(f"Failed to add documents to Chroma: {e}")
            raise

    # ─────────────────────────────────────────────────────────────────────────
    # Document Builders
    # ─────────────────────────────────────────────────────────────────────────

    def _generate_table_schema_docs(self):
        """
        One doc per table. Contains purpose, column NAMES and short summaries.
        Full descriptions still live in column_schema docs for precise column ranking, 
        but table_schema docs get summaries to ensure Table Gravity works semantically.
        """
        documents, metadatas, ids = [], [], []

        for table in self.schema_data:
            table_name = table['table_name']
            db_name = table.get('database_name', 'unknown')
            purpose = table.get('purpose', '')
            columns = table.get('columns', [])
            foreign_keys = table.get('foreign_keys', [])

            col_names = [c.get('name', '') for c in columns]
            
            # Extract first sentence of description for semantic table-level matching
            col_descriptions = [f"{c.get('name', '')}: {str(c.get('description', '')).split('.')[0]}" for c in columns if c.get('description')]

            fk_lines = []
            for fk in foreign_keys:
                fk_col = fk.get('column', '')
                fk_ref = fk.get('references', '')
                fk_lines.append(f"  {table_name}.{fk_col} → {fk_ref}")

            lines = [
                "TYPE: table_schema",
                f"Database: {db_name}",
                f"Table: {table_name}",
                "",
                "Purpose:",
                purpose,
                "",
                "Columns:",
                "  " + ", ".join(col_names),
            ]
            
            if col_descriptions:
                lines += ["", "Column Summaries:"] + [f"  - {cd}" for cd in col_descriptions]

            if fk_lines:
                lines += ["", "Foreign Keys:"] + fk_lines

            documents.append("\n".join(lines))
            metadatas.append({
                "type": "table_schema",
                "table": table_name,
                "database": db_name,
                "source": "schema"
            })
            ids.append(f"table_schema_{db_name}_{table_name}")

        return documents, metadatas, ids

    def _generate_column_schema_docs(self):
        """
        One doc per column. Contains table name, column name, and full description.
        Used for semantic column ranking after table retrieval.
        """
        documents, metadatas, ids = [], [], []

        for table in self.schema_data:
            table_name = table['table_name']
            db_name = table.get('database_name', 'unknown')
            fk_set = {fk.get('column', '') for fk in table.get('foreign_keys', [])}
            pk_set = set(table.get('primary_keys', []))

            for col in table.get('columns', []):
                col_name = col.get('name', '')
                col_type = col.get('type', '')
                col_desc = col.get('description', '')

                # Build role annotations for FK/PK — helps ranking find join columns
                role_notes = []
                if col_name in pk_set or col_name == 'id':
                    role_notes.append("Primary key.")
                if col_name in fk_set:
                    fk_ref = next(
                        (fk.get('references', '') for fk in table.get('foreign_keys', [])
                         if fk.get('column') == col_name), ''
                    )
                    role_notes.append(f"Foreign key → {fk_ref}")

                lines = [
                    "TYPE: column_schema",
                    f"Database: {db_name}",
                    f"Table: {table_name}",
                    f"Column: {col_name} ({col_type})",
                    "",
                    "Description:",
                    col_desc,
                ]
                if role_notes:
                    lines += ["", "Role: " + " ".join(role_notes)]

                documents.append("\n".join(lines))
                metadatas.append({
                    "type": "column_schema",
                    "table": table_name,
                    "database": db_name,
                    "column": col_name,
                    "column_type": col_type,
                    "is_fk": "true" if col_name in fk_set else "false",
                    "is_pk": "true" if (col_name in pk_set or col_name == 'id') else "false",
                    "source": "schema"
                })
                ids.append(f"col_schema_{db_name}_{table_name}_{col_name}")

        return documents, metadatas, ids

    def _generate_relationship_docs(self):
        """Auto-generate 2-hop and 3-hop FK join path documents."""
        documents, metadatas, ids = [], [], []

        fk_index = {}
        for table in self.schema_data:
            table_name = table['table_name']
            fk_index[table_name] = []
            for fk in table.get('foreign_keys', []):
                fk_col = fk.get('column', '')
                refs = fk.get('references', '')
                match = re.search(r'(?:[^.]+\.)?([^.(]+)\(([^)]+)\)', refs)
                if match:
                    fk_index[table_name].append(
                        (fk_col, match.group(1).strip(), match.group(2).strip())
                    )

        generated_paths = set()

        for table in self.schema_data:
            src_table = table['table_name']
            src_db = table.get('database_name', 'unknown')

            for fk_col, ref_table, ref_col in fk_index.get(src_table, []):
                path_key = tuple(sorted([src_table, ref_table]))
                if path_key not in generated_paths:
                    generated_paths.add(path_key)
                    ref_data = next((t for t in self.schema_data if t['table_name'] == ref_table), None)
                    ref_purpose = ref_data.get('purpose', '')[:120] if ref_data else ''

                    doc = "\n".join([
                        "TYPE: RELATIONSHIP",
                        f"Path: {src_table} → {ref_table}",
                        "Joins:",
                        f"  {src_table}.{fk_col} = {ref_table}.{ref_col}",
                        f"Source: {table.get('purpose', '')[:120]}",
                        f"Target: {ref_purpose}",
                        f"Used for: Queries linking {src_table} with {ref_table}.",
                    ])
                    documents.append(doc)
                    metadatas.append({
                        "type": "relationship", "table": src_table,
                        "database": src_db, "tables": f"{src_table},{ref_table}", "source": "schema"
                    })
                    ids.append(f"rel_{src_table}__{ref_table}")

                for fk_col2, ref2_table, ref2_col in fk_index.get(ref_table, []):
                    chain_key = (src_table, ref_table, ref2_table)
                    chain_key_r = (ref2_table, ref_table, src_table)
                    if chain_key not in generated_paths and chain_key_r not in generated_paths:
                        generated_paths.add(chain_key)
                        doc = "\n".join([
                            "TYPE: RELATIONSHIP",
                            f"Path: {src_table} → {ref_table} → {ref2_table}",
                            "Joins:",
                            f"  {src_table}.{fk_col} = {ref_table}.{ref_col}",
                            f"  {ref_table}.{fk_col2} = {ref2_table}.{ref2_col}",
                            f"Used for: Multi-hop queries joining {src_table} through {ref_table} to {ref2_table}.",
                        ])
                        documents.append(doc)
                        metadatas.append({
                            "type": "relationship", "table": src_table,
                            "database": src_db,
                            "tables": f"{src_table},{ref_table},{ref2_table}", "source": "schema"
                        })
                        ids.append(f"rel_{src_table}__{ref_table}__{ref2_table}")

        return documents, metadatas, ids

    # ─────────────────────────────────────────────────────────────────────────
    # Stage 1 — Table Retrieval (Table Gravity)
    # ─────────────────────────────────────────────────────────────────────────

    def retrieve_relevant_tables(self, user_query, max_tables=5):
        """
        Retrieve top-K tables using Table Gravity scoring:
          1. Query table_schema docs (primary signal)
          2. Query relationship docs (small additive boost for relevant join paths)
          3. Aggregate scores per table, sort, take top max_tables
          4. Add FK parent tables (capped at 2)
        """
        try:
            table_scores = {}

            # ── Table-level search ──────────────────────────────────────────
            ts_n = min(len(self.schema_data) * 2, max(9, self.collection.count() // 4))
            ts_results = self.collection.query(
                query_texts=[user_query],
                n_results=ts_n,
                where={"type": "table_schema"}
            )
            if ts_results and ts_results.get('ids') and ts_results['ids'][0]:
                for i in range(len(ts_results['ids'][0])):
                    meta = ts_results['metadatas'][0][i]
                    distance = ts_results['distances'][0][i] if ts_results.get('distances') else 2.0
                    table_name = meta.get('table', '')
                    if table_name:
                        table_scores[table_name] = table_scores.get(table_name, 0) + (-distance)
                        logger.debug(f"[TABLE] {table_name} distance={distance:.3f}")

            # ── Relationship boost (small, capped) ─────────────────────────
            try:
                rel_results = self.collection.query(
                    query_texts=[user_query],
                    n_results=10,
                    where={"type": "relationship"}
                )
                if rel_results and rel_results.get('ids') and rel_results['ids'][0]:
                    for i in range(len(rel_results['ids'][0])):
                        meta = rel_results['metadatas'][0][i]
                        distance = rel_results['distances'][0][i] if rel_results.get('distances') else 2.0
                        if distance > 1.5:
                            continue  # only use clearly relevant paths
                        for t in meta.get('tables', '').split(','):
                            t = t.strip()
                            if t:
                                table_scores[t] = table_scores.get(t, 0) + 0.05
            except Exception as e:
                logger.warning(f"Relationship boost failed (non-critical): {e}")

            # ── Sort by gravity, take top-N ────────────────────────────────
            sorted_tables = sorted(table_scores.items(), key=lambda x: x[1], reverse=True)
            top_table_names = [t for t, _ in sorted_tables[:max_tables]]
            logger.info(f"[TABLE GRAVITY] Top tables: {top_table_names}")

            # ── Materialize from schema ────────────────────────────────────
            seen_tables = set(top_table_names)
            retrieved_tables = []
            for rank, table_name in enumerate(top_table_names):
                table_data = next((t for t in self.schema_data if t['table_name'] == table_name), None)
                if not table_data:
                    continue
                retrieved_tables.append({
                    "table": table_name,
                    "database": table_data.get('database_name', 'unknown'),
                    "description": table_data.get('purpose', ''),
                    "foreign_keys": table_data.get('foreign_keys', []),
                    "similarity_score": max(0.1, 1.0 - rank * 0.15)
                })

            # ── FK parent resolution (max 2) ───────────────────────────────
            fk_parents_added = 0
            for t in list(retrieved_tables):
                if fk_parents_added >= 2:
                    break
                for fk in t.get('foreign_keys', []):
                    if fk_parents_added >= 2:
                        break
                    refs = fk.get('references', '')
                    match = re.search(r'(?:[^.]+\.)?([^.(]+)\(([^)]+)\)', refs)
                    if match:
                        parent_name = match.group(1).strip()
                        if parent_name not in seen_tables:
                            parent_data = next(
                                (pt for pt in self.schema_data if pt['table_name'] == parent_name), None
                            )
                            if parent_data:
                                seen_tables.add(parent_name)
                                retrieved_tables.append({
                                    "table": parent_name,
                                    "database": parent_data.get('database_name', 'unknown'),
                                    "description": parent_data.get('purpose', ''),
                                    "foreign_keys": parent_data.get('foreign_keys', []),
                                    "similarity_score": 0.1
                                })
                                fk_parents_added += 1
                                logger.info(f"[FK PARENT] Added: {parent_name}")

            logger.info(f"[RETRIEVAL] Final tables: {[t['table'] for t in retrieved_tables]}")
            return retrieved_tables

        except Exception as e:
            logger.error(f"Failed to retrieve tables: {e}")
            return []

    # ─────────────────────────────────────────────────────────────────────────
    # Stage 2 — Column Semantic Ranking
    # ─────────────────────────────────────────────────────────────────────────

    def rank_columns(self, user_query, top_table_names, top_n=15):
        """
        Rank columns from retrieved tables using column_schema embeddings.
        FK/PK columns get a -0.2 distance boost (prefer them for JOINs) but
        semantic relevance still wins — e.g. lead_status beats a distant FK.

        Returns: list of dicts {table, column, column_type, distance,
                                boosted_distance, is_fk, is_pk}
                 sorted by boosted_distance ascending (best match first).
        """
        if not top_table_names:
            return []

        try:
            total_col_count = sum(
                len(t.get('columns', []))
                for t in self.schema_data
                if t['table_name'] in top_table_names
            )
            n_results = min(max(top_n * 3, total_col_count), self.collection.count())

            results = self.collection.query(
                query_texts=[user_query],
                n_results=n_results,
                where={
                    "$and": [
                        {"type": {"$eq": "column_schema"}},
                        {"table": {"$in": list(top_table_names)}}
                    ]
                }
            )

            ranked = []
            if results and results.get('ids') and results['ids'][0]:
                for i in range(len(results['ids'][0])):
                    meta = results['metadatas'][0][i]
                    raw_dist = results['distances'][0][i] if results.get('distances') else 2.0
                    is_fk = meta.get('is_fk', 'false') == 'true'
                    is_pk = meta.get('is_pk', 'false') == 'true'
                    # FK/PK get a distance boost: they rank higher than non-FK columns
                    # at the same semantic distance, but a very relevant non-FK column
                    # (e.g. lead_status when query mentions "failed leads") can still win.
                    boost = -0.2 if (is_fk or is_pk) else 0.0
                    ranked.append({
                        "table": meta.get('table', ''),
                        "column": meta.get('column', ''),
                        "column_type": meta.get('column_type', ''),
                        "is_fk": is_fk,
                        "is_pk": is_pk,
                        "distance": raw_dist,
                        "boosted_distance": raw_dist + boost,
                    })

            # Sort by boosted distance (lower = better match)
            ranked.sort(key=lambda x: x['boosted_distance'])
            top_ranked = ranked[:top_n]

            logger.info(
                f"[COLUMN RANK] Top {len(top_ranked)} from {list(top_table_names)}: "
                f"{[(c['table'], c['column'], round(c['boosted_distance'],3)) for c in top_ranked[:6]]}"
            )
            return top_ranked

        except Exception as e:
            logger.error(f"Column ranking failed: {e}")
            return []

    # ─────────────────────────────────────────────────────────────────────────
    # Stage 3 — Schema String Generation
    # ─────────────────────────────────────────────────────────────────────────

    def _get_fk_annotation(self, col_name, foreign_keys):
        """Inline FK annotation: '  JOIN db.table.col'"""
        for fk in foreign_keys:
            if fk.get('column', '') == col_name:
                refs = fk.get('references', '')
                match = re.search(r'(?:([^.]+)\.)?([^.(]+)\(([^)]+)\)', refs)
                if match:
                    ref_db = match.group(1) or ''
                    ref_table = match.group(2).strip()
                    ref_col = match.group(3).strip()
                    return f"  JOIN {ref_db + '.' if ref_db else ''}{ref_table}.{ref_col}"
        return ""

    def _get_distinct_values(self, col: dict) -> str:
        """
        Return '[VALUES: ...]' annotation string from pre-computed example_values
        in db_schema.json — zero live DB queries.

        The populate_schema_examples.py script must have been run at least once
        to populate the example_values field.  If the field is absent, an empty
        string is returned gracefully.

        Skips raw integer ID columns (ends with _id) — their FK-resolved names
        are already stored by the script in the referenced table's column entry.
        """
        col_name = col.get("name", "")
        col_type = col.get("type", "")
        example_values = col.get("example_values", [])

        if not example_values:
            return ""

        # Skip bare integer PKs that are just raw IDs with no display value
        col_lower = col_name.lower()
        btype = col_type.upper().split("(")[0].strip()
        if col_lower == "id" or (col_lower.endswith("_id") and btype.startswith("INT")):
            # FK IDs whose referenced name was NOT resolved by the script are useless
            # (the script stores resolved name values in example_values, not raw ints)
            if all(str(v).isdigit() for v in example_values):
                return ""

        # Format the values list
        # Date-range entries look like "range:2020-01-01 → 2025-12-31"
        display_vals = [str(v) for v in example_values if v is not None]
        if not display_vals:
            return ""

        return f" [VALUES: {', '.join(display_vals)}]"

    def get_full_schema_string(self, relevant_context, data_sampler=None, user_query=""):
        """
        Build the schema string sent to the LLM.

        Two-tier column display:
          TOP (semantically ranked, top-15 + FK/PK boosted)
            → full detail: type, FK annotation, [VALUES: ...], description
          OTHER (remaining columns in retrieved tables)
            → brief: type + [VALUES: ...] if pre-computed, no description

        [VALUES: ...] are read directly from the pre-computed example_values
        field in db_schema.json — NO live DB queries at request time.
        Run backend/scripts/populate_schema_examples.py once (or after schema
        changes) to populate/refresh those values.

        Args:
            relevant_context : list of table dicts from retrieve_relevant_tables()
            data_sampler     : kept for API compatibility — no longer used in this path
            user_query       : user's natural-language query (drives column ranking)
        """
        if not relevant_context:
            return "=== AVAILABLE DATABASE SCHEMA ===\n\nNo relevant tables found.\n"

        top_table_names = [t['table'] for t in relevant_context]

        # Rank columns semantically
        ranked_columns = []
        if user_query:
            ranked_columns = self.rank_columns(user_query, top_table_names, top_n=15)

        # Build a lookup: (table, column) → rank position
        ranked_col_lookup = {(c['table'], c['column']): i for i, c in enumerate(ranked_columns)}

        schema_text = "=== AVAILABLE DATABASE SCHEMA ===\n\n"

        for table in relevant_context:
            table_name = table['table']
            database = table.get('database', 'unknown')
            description = table.get('description', '')

            # Get full table data from schema JSON
            table_data = next((t for t in self.schema_data if t['table_name'] == table_name), None)
            if not table_data:
                continue

            foreign_keys = table_data.get('foreign_keys', [])

            schema_text += f"DATABASE: {database}\n"
            schema_text += f"TABLE: {table_name}\n"
            schema_text += f"PURPOSE: {description}\n"

            top_cols = []   # (rank, col_str)  — semantically ranked
            other_cols = [] # col_str           — remaining columns

            for c in table_data['columns']:
                col_name = c['name']
                col_type = c.get('type', '')
                in_ranked = (table_name, col_name) in ranked_col_lookup

                # [VALUES: ...] annotation — reads from pre-computed JSON field
                values_ann = self._get_distinct_values(c)

                if in_ranked:
                    # ── Full detail: type, FK JOIN hint, values, description ──
                    col_str = f"{col_name} ({col_type})"
                    fk_ann = self._get_fk_annotation(col_name, foreign_keys)
                    if fk_ann:
                        col_str += fk_ann
                    if values_ann:
                        col_str += values_ann
                    if c.get('description'):
                        desc = c['description'].split('.')[0].split('(')[0].strip()
                        if desc:
                            col_str += f" - {desc}"
                    top_cols.append((ranked_col_lookup[(table_name, col_name)], col_str))
                else:
                    # ── Brief: type + values only (no full description) ──────
                    col_str = f"{col_name} ({col_type})"
                    if values_ann:
                        col_str += values_ann
                    other_cols.append(col_str)

            # Sort top columns by semantic rank
            top_cols.sort(key=lambda x: x[0])

            schema_text += "TOP COLUMNS (Detailed):\n"
            for _, col_str in top_cols:
                schema_text += f"  - {col_str}\n"
            if other_cols:
                schema_text += "OTHER COLUMNS:\n"
                for col_str in other_cols:
                    schema_text += f"  - {col_str}\n"

            schema_text += "\n" + "=" * 50 + "\n\n"

        schema_text += (
            "CRITICAL: TOP COLUMNS have full context including descriptions. "
            "OTHER COLUMNS exist and can be SELECTed but have less detail. "
            "Do NOT reference columns not listed above.\n"
        )
        return schema_text
