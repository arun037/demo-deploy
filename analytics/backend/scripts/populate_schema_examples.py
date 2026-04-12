"""
populate_schema_examples.py
===========================
One-time (and re-runnable) offline script that enriches db_schema.json with
pre-computed example_values for every column.

Strategy per column type
------------------------
 DATE / DATETIME / TIMESTAMP            → detect_date_range  (min / max stored)
 INT columns that are FK IDs            → follow the FK graph and sample the
                                          human-readable name column from the
                                          referenced table instead of returning
                                          raw integers
 Categorical VARCHAR / CHAR / ENUM      → SELECT DISTINCT col LIMIT 10  (no COUNT,
                                          no GROUP BY — fast)
 TEXT / LONGTEXT / BLOB / JSON / BINARY → skip entirely  (not groupable)
 Plain numerics (INT, FLOAT, etc.)
   that are NOT FK IDs                  → skip  (values like 1,2,3 are useless)

Everything is 100% driven by db_schema.json — zero hardcoding of table or
column names.  Re-run whenever data changes or new tables are added.

Usage
-----
    cd /home/abhishek/analytics
    python -m backend.scripts.populate_schema_examples
"""

import json
import re
import sys
import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Bootstrap so this script can import backend.*  when run as __main__
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[2]   # project root
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(dotenv_path=ROOT / ".env")

from backend.config import Config
from backend.core.database import DatabaseManager

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
SCHEMA_FILE = Path(Config.SCHEMA_FILE)

UNSAMPLEABLE_TYPES = {
    "TEXT", "LONGTEXT", "MEDIUMTEXT", "TINYTEXT",
    "BLOB", "LONGBLOB", "MEDIUMBLOB", "TINYBLOB",
    "JSON", "BIT", "BINARY", "VARBINARY",
}

DATE_TYPES = {"DATE", "DATETIME", "TIMESTAMP"}

# VARCHAR / CHAR / ENUM / SET are categorical
CATEGORICAL_TYPES = {"VARCHAR", "CHAR", "ENUM", "SET"}

MAX_SAMPLES = 10   # top-N distinct values to store per column
MAX_VAL_LEN = 80   # max character length of any single value (filters HTML / long text)

# Column name substrings that indicate the column holds technical / tracking data,
# PII, or free-text with no business filter value — skip sampling for these.
SKIP_COL_SUBSTRINGS = {
    # Identifiers / hashes / sessions
    "ip_address", "ip_addr", "cart_id", "session", "uuid", "token",
    "hash", "gclid", "msclkid", "mlclkid", "landing_id", "web_id",
    "local_id", "cc_email", "act_on", "accounting_id", "ein",
    # URLs
    "_url", "url_",
    # PII — never expose as example values
    "email", "first_name", "last_name", "street_address", "address",
    "phone", "city", "zip", "postal",
    # Free-text / long labels with no filter use
    "message", "subject", "description", "top_html", "bottom_html",
    "stylesheet", "js_include", "h1_title", "meta_",
    "status_message", "processed_message",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def base_type(col_type: str) -> str:
    """Strip size suffix and return upper-case base type — e.g. 'varchar(45)' → 'VARCHAR'."""
    return col_type.upper().split("(")[0].strip()


def qualified(db: str, table: str) -> str:
    return f"`{db}`.`{table}`"


def run_query(db: DatabaseManager, sql: str):
    """Execute SQL and return list of single-column values (or None on error)."""
    try:
        df = db.execute_query_safe(sql)
        if df.empty:
            return []
        return [str(v) for v in df.iloc[:, 0].dropna().tolist() if str(v).strip() not in ("", "None")]
    except Exception as e:
        print(f"    [WARN] query failed: {e}")
        return None


def _is_useful_values(vals: list[str]) -> bool:
    """
    Return True only if vals look like real business labels, not system data.

    Rejects:
      - Values that are all-numeric strings  (e.g. source column storing '4','5')
      - Values longer than MAX_VAL_LEN chars  (HTML fragments, long messages)
      - Values that look like IP addresses    (e.g. '67.8.87.122')
      - Values that look like hex hashes      (long hex strings)
      - Lists that still only contain 1 value after filtering (not useful)
    """
    if not vals:
        return False

    ip_re    = re.compile(r'^\d{1,3}(\.\d{1,3}){3}$')
    hash_re  = re.compile(r'^[0-9a-f]{16,}$', re.IGNORECASE)

    clean = []
    for v in vals:
        if len(v) > MAX_VAL_LEN:
            continue           # too long — HTML, free-text message, etc.
        if ip_re.match(v):
            continue           # IP address
        if hash_re.match(v):
            continue           # hex hash / session token
        if v.replace('.', '').replace(',', '').isdigit():
            continue           # all-numeric string (e.g. source='4')
        if '<' in v and '>' in v:
            continue           # HTML tags
        clean.append(v)

    return len(clean) >= 1  and clean != vals or len(clean) > 0


# ---------------------------------------------------------------------------
# FK resolution
# ---------------------------------------------------------------------------

def _find_name_col(schema_data: list[dict], ref_table: str) -> str | None:
    """
    Find the best human-readable label column in ref_table.

    Priority:
        1. Any VARCHAR/CHAR column whose name ends with _name, _abbr, _label,
           _title, _code, _slug (in that order)
        2. First VARCHAR/CHAR column that is NOT an id/numeric column
    """
    tdata = next((t for t in schema_data if t["table_name"] == ref_table), None)
    if not tdata:
        return None

    name_suffixes = ("display_name", "_name", "_abbr", "_label", "_title", "_code", "_slug")
    char_cols = [
        c["name"] for c in tdata["columns"]
        if base_type(c.get("type", "")) in CATEGORICAL_TYPES
        and not c["name"].lower().endswith("_id")
        and c["name"].lower() != "id"
    ]

    # priority 1 – suffix match
    for suffix in name_suffixes:
        for col in char_cols:
            if col.lower().endswith(suffix):
                return col

    # priority 2 – first non-id varchar col
    return char_cols[0] if char_cols else None


def _parse_fk_ref(ref_str: str):
    """
    Parse 'database.table(col)' or 'table(col)' → (db_or_None, table, col).
    Returns None if parsing fails.
    """
    # Handle composite FK strings like "franchises.concepts(fbo_id + site_id) — ..."
    # We only process simple single-column FK refs
    if "+" in ref_str or "—" in ref_str:
        return None
    m = re.match(r"(?:([^.(]+)\.)?([^.(]+)\(([^)]+)\)", ref_str.strip())
    if not m:
        return None
    return m.group(1), m.group(2).strip(), m.group(3).strip()


# ---------------------------------------------------------------------------
# Per-column sampling
# ---------------------------------------------------------------------------

def sample_column(db: DatabaseManager, schema_data: list[dict],
                  db_name: str, table_name: str, col: dict,
                  fk_map: dict) -> list[str] | None:
    """
    Return example values for a single column, or None to skip.

    fk_map: dict mapping column_name → (ref_db, ref_table, ref_col)
             for the current table.
    """
    col_name = col["name"]
    btype = base_type(col.get("type", ""))

    # --- skip columns that hold technical / tracking values ---------------
    col_lower_full = col_name.lower()
    if any(skip in col_lower_full for skip in SKIP_COL_SUBSTRINGS):
        return None

    # --- skip unsampleable types ----------------------------------------
    if btype in UNSAMPLEABLE_TYPES:
        return None

    # --- skip bare PK 'id' (meaningless integers) ------------------------
    if col_name.lower() == "id":
        return None

    # --- date / datetime columns → range detection -----------------------
    if btype in DATE_TYPES:
        sql = (
            f"SELECT MIN(`{col_name}`), MAX(`{col_name}`) "
            f"FROM {qualified(db_name, table_name)} "
            f"WHERE `{col_name}` IS NOT NULL LIMIT 1"
        )
        try:
            df = db.execute_query_safe(sql)
            if not df.empty:
                mn = str(df.iloc[0, 0])
                mx = str(df.iloc[0, 1])
                if mn not in ("None", "NaT", "") and mx not in ("None", "NaT", ""):
                    return [f"range:{mn} → {mx}"]
        except Exception as e:
            print(f"    [WARN] date-range failed for {col_name}: {e}")
        return None

    # --- FK ID integer column → resolve to human-readable name -----------
    if col_name in fk_map and btype.startswith("INT"):
        ref_db, ref_table, _ref_col = fk_map[col_name]
        name_col = _find_name_col(schema_data, ref_table)
        if name_col:
            ref_db_actual = ref_db or db_name
            sql = (
                f"SELECT DISTINCT `{name_col}` "
                f"FROM {qualified(ref_db_actual, ref_table)} "
                f"WHERE `{name_col}` IS NOT NULL AND `{name_col}` != '' "
                f"LIMIT {MAX_SAMPLES}"
            )
            vals = run_query(db, sql)
            if vals:
                print(f"    [FK] {col_name} → {ref_table}.{name_col}: {vals}")
                return vals
        # FK but no name column found → skip (raw ints not useful)
        return None

    # --- plain numeric non-FK → skip ------------------------------------
    if btype.startswith("INT") or btype in ("FLOAT", "DOUBLE", "DECIMAL",
                                             "TINYINT", "SMALLINT", "BIGINT",
                                             "MEDIUMINT"):
        return None

    # --- categorical VARCHAR / CHAR / ENUM → simple DISTINCT ------------
    if btype in CATEGORICAL_TYPES:
        sql = (
            f"SELECT DISTINCT `{col_name}` "
            f"FROM {qualified(db_name, table_name)} "
            f"WHERE `{col_name}` IS NOT NULL AND `{col_name}` != '' "
            f"LIMIT {MAX_SAMPLES}"
        )
        vals = run_query(db, sql)
        if vals and _is_useful_values(vals):
            # Keep only clean values
            ip_re   = re.compile(r'^\d{1,3}(\.\d{1,3}){3}$')
            hash_re = re.compile(r'^[0-9a-f]{16,}$', re.IGNORECASE)
            clean = [
                v for v in vals
                if len(v) <= MAX_VAL_LEN
                and not ip_re.match(v)
                and not hash_re.match(v)
                and not (v.replace('.', '').replace(',', '').isdigit())
                and not ('<' in v and '>' in v)
            ]
            if clean:
                print(f"    [VAL] {col_name}: {clean}")
                return clean
        return None

    return None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print(f"\n{'='*60}")
    print("  Populate schema example_values")
    print(f"  Schema: {SCHEMA_FILE}")
    print(f"{'='*60}\n")

    # Load schema
    with open(SCHEMA_FILE, "r") as f:
        schema_data: list[dict] = json.load(f)

    # Connect to DB
    db = DatabaseManager()

    total_cols = 0
    populated_cols = 0

    for table in schema_data:
        table_name = table["table_name"]
        db_name = table["database_name"]
        columns = table.get("columns", [])
        foreign_keys = table.get("foreign_keys", [])

        # Build FK map for this table: col_name → (ref_db, ref_table, ref_col)
        fk_map: dict[str, tuple] = {}
        for fk in foreign_keys:
            parsed = _parse_fk_ref(fk.get("references", ""))
            if parsed:
                fk_map[fk["column"]] = parsed

        print(f"\nTable: {db_name}.{table_name} ({len(columns)} columns, {len(fk_map)} FKs)")

        for col in columns:
            total_cols += 1
            examples = sample_column(db, schema_data, db_name, table_name, col, fk_map)
            if examples:
                col["example_values"] = examples
                populated_cols += 1
            else:
                # Remove stale values if re-running
                col.pop("example_values", None)

    # Save updated schema
    with open(SCHEMA_FILE, "w") as f:
        json.dump(schema_data, f, indent=2, ensure_ascii=False)

    print(f"\n{'='*60}")
    print(f"  Done. Populated {populated_cols}/{total_cols} columns.")
    print(f"  Saved → {SCHEMA_FILE}")
    print(f"{'='*60}\n")

    db.close()


if __name__ == "__main__":
    main()
