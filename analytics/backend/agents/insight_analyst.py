"""
Enhanced InsightAnalyst - Intelligent Chart Generation System
4-Layer Zero-Error Architecture:
  Layer 1: Data Exploration (autonomous SQL by LLM)
  Layer 2: Chart Planning (LLM generates Data Contracts)
  Layer 3: Data Contractor (validates, transforms, shapes)
  Layer 4: Legacy Fallback (ChartSelector + ChartRenderer if all else fails)
"""

from backend.core.llm_client import LLMClient
from backend.core.logger import logger
from backend.config import Config
from backend.agents.chart_selector import ChartSelector
from backend.agents.chart_planner import ChartPlanner
from backend.agents.chart_renderer import ChartRenderer
from backend.agents.data_contractor import DataContractor, FulfilledChart

import pandas as pd
import json
import os
from typing import Dict, Any, List, Optional


def _parse_json_safe(text: str, default=None):
    """Safely parse JSON, returning default on any error."""
    if default is None:
        default = []
    try:
        text = text.strip()
        if "```" in text:
            parts = text.split("```")
            for part in parts:
                stripped = part.strip()
                if stripped.lower().startswith("json"):
                    stripped = stripped[4:].strip()
                if stripped.startswith("[") or stripped.startswith("{"):
                    text = stripped
                    break
        return json.loads(text)
    except Exception:
        return default


class InsightAnalyst:
    """
    Orchestrates the 4-layer zero-error visualization pipeline.
    """

    def __init__(self, llm_client: LLMClient, db_manager=None):
        self.llm = llm_client
        self.db = db_manager

        # Load business context for domain-aware chart generation
        self.business_context = self._load_business_context()

        # Layer 2: Chart Planner (LLM-driven spec generation)
        self.chart_planner = ChartPlanner(llm_client)

        # Layer 3: Data Contractor (validation + transformation)
        self.data_contractor = DataContractor()

        # Layer 4 fallback: Legacy rule-based system
        self.chart_selector = ChartSelector()
        self.chart_renderer = ChartRenderer()

        logger.info("InsightAnalyst initialized — 4-layer zero-error visualization engine")

    def _load_business_context(self) -> str:
        """Load business context for domain-aware chart generation."""
        try:
            context_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                'business_context.json'
            )
            if os.path.exists(context_path):
                with open(context_path, 'r') as f:
                    data = json.load(f)
                desc = data.get('description', '')
                if desc:
                    logger.info(f"InsightAnalyst: Loaded business context ({len(desc)} chars)")
                    return desc
        except Exception as e:
            logger.error(f"InsightAnalyst: Error loading business context: {e}")
        return ""

    def generate_insights(
        self,
        user_query: str,
        sql_query: str,
        results_df: pd.DataFrame,
        schema_context: str = "",
        chat_history: List[Dict] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Main entry point. Runs the full 4-layer pipeline.

        Returns:
            Chart configuration dict with charts ready for frontend rendering,
            or None if no meaningful visualization is possible.
        """
        if results_df.empty:
            logger.info("InsightAnalyst: Empty results, skipping visualization")
            return None

        logger.info(f"InsightAnalyst: Starting pipeline for {len(results_df)} rows, {len(results_df.columns)} cols")

        try:
            # ── LAYER 1: Data Exploration ──────────────────────────────────────────────
            logger.info("InsightAnalyst: Layer 1 — Data Exploration")
            exploration_findings = self._explore_data(user_query, sql_query, results_df, schema_context)
            if exploration_findings:
                logger.info(f"InsightAnalyst: Exploration findings ({len(exploration_findings)} chars)")

            # ── LAYER 2: Chart Planning (LLM Data Contracts) ──────────────────────────
            logger.info("InsightAnalyst: Layer 2 — Chart Planning")
            chart_specs = self.chart_planner.plan_charts(
                user_query=user_query,
                sql_query=sql_query,
                results_df=results_df,
                max_charts=3,
                chat_history=chat_history or [],
                business_context=self.business_context,
                schema_context=schema_context,
                exploration_findings=exploration_findings
            )

            if not chart_specs:
                logger.info("InsightAnalyst: ChartPlanner returned no specs — falling back to legacy")
                return self._fallback_to_legacy(user_query, sql_query, results_df, schema_context)

            # ── LAYER 3: Data Contractor (validate + transform + shape) ────────────────
            logger.info("InsightAnalyst: Layer 3 — Data Contractor")
            fulfilled_charts = self.data_contractor.fulfill_contracts(chart_specs, results_df)

            if not fulfilled_charts:
                logger.info("InsightAnalyst: DataContractor produced no valid charts — falling back to legacy")
                return self._fallback_to_legacy(user_query, sql_query, results_df, schema_context)

            # ── Build Final Config ─────────────────────────────────────────────────────
            charts = self._build_chart_configs(fulfilled_charts)

            # Generate summary
            summary = self._generate_summary(user_query, results_df, chart_specs, charts)

            final_config = {
                'should_visualize': True,
                'summary': summary,
                'charts': charts,
                'generation_method': 'llm_contract'
            }

            logger.info(
                f"InsightAnalyst: ✅ Generated {len(charts)} chart(s) via LLM contract pipeline "
                f"[types: {[c['chart_type'] for c in charts]}]"
            )
            return final_config

        except Exception as e:
            logger.error(f"InsightAnalyst: Pipeline error ({e}) — falling back to legacy")
            return self._fallback_to_legacy(user_query, sql_query, results_df, schema_context)

    def _explore_data(
        self,
        user_query: str,
        sql_query: str,
        results_df: pd.DataFrame,
        schema_context: str
    ) -> str:
        """
        Layer 1: LLM autonomously explores the data by writing + executing follow-up SQL.
        Returns a findings string injected into the chart planning prompt.
        """
        if self.db is None:
            # No DB access — still produce quick statistical profile
            return self._quick_statistical_profile(results_df)

        # Build a quick profile without SQL first
        quick_profile = self._build_quick_profile(results_df, sql_query)

        # Ask LLM: what lightweight SQL queries would help you choose the right chart?
        prompt = f"""You are about to choose the best charts for this data.

USER QUESTION: "{user_query}"
SQL EXECUTED: {sql_query[:500]}

CURRENT DATA PROFILE:
{json.dumps(quick_profile, indent=2, default=str)}

Write UP TO 2 simple, fast SQL queries that would help you choose chart types more accurately.
Good reasons to write an exploration query:
- Checking whether a distribution is uniform or skewed
- Checking actual date range or time granularity
- Seeing exact category counts when unique_count is large
- Understanding min/max/avg of a metric before picking chart scale

Return ONLY JSON array: [{{"sql": "SELECT ...", "purpose": "..."}}]
If no additional queries are needed (data profile is sufficient), return: []"""

        try:
            response = self.llm.call_agent(
                system_prompt=prompt,
                user_query="Generate exploration queries or return []",
                model=Config.INSIGHT_MODEL,
                temperature=0.0,
                timeout=20,
                agent_name="InsightAnalyst-Explorer"
            )

            explore_specs = _parse_json_safe(response, default=[])
            findings = [f"STATISTICAL PROFILE:\n{json.dumps(quick_profile, indent=2, default=str)}"]

            for spec in explore_specs[:2]:
                sql = spec.get("sql", "").strip()
                purpose = spec.get("purpose", "")
                if not sql:
                    continue
                try:
                    # Safety: only allow SELECT
                    if not sql.upper().startswith("SELECT"):
                        logger.warning(f"InsightAnalyst: Rejected non-SELECT exploration query")
                        continue
                    explore_df = self.db.execute_query_safe(sql)
                    if explore_df is not None and not explore_df.empty:
                        findings.append(
                            f"EXPLORATION ({purpose}):\n{explore_df.head(10).to_string(index=False)}"
                        )
                        logger.info(f"InsightAnalyst: Exploration query ran ok ({purpose})")
                    else:
                        findings.append(f"EXPLORATION ({purpose}): returned no data")
                except Exception as e:
                    findings.append(f"EXPLORATION ({purpose}): FAILED — {e}")

            return "\n\n".join(findings)

        except Exception as e:
            logger.warning(f"InsightAnalyst: Data exploration LLM call failed: {e}")
            return self._quick_statistical_profile(results_df)

    def _build_quick_profile(self, df: pd.DataFrame, sql_query: str = "") -> Dict:
        """Build a quick statistical profile for the data exploration prompt."""
        profile = {
            "total_rows": len(df),
            "is_pre_aggregated": "GROUP BY" in sql_query.upper(),
            "columns": {}
        }
        for col in df.columns:
            dtype = str(df[col].dtype)
            if "int" in dtype or "float" in dtype:
                profile["columns"][col] = {
                    "type": "numeric",
                    "min": float(df[col].min()) if not df[col].empty else None,
                    "max": float(df[col].max()) if not df[col].empty else None,
                    "avg": round(float(df[col].mean()), 2) if not df[col].empty else None,
                    "nulls": int(df[col].isna().sum()),
                }
            else:
                profile["columns"][col] = {
                    "type": "text",
                    "unique_count": int(df[col].nunique()),
                    "sample": df[col].dropna().head(3).tolist(),
                    "nulls": int(df[col].isna().sum()),
                }
        return profile

    def _quick_statistical_profile(self, df: pd.DataFrame) -> str:
        """Profile string without any SQL queries (fallback for no-DB mode)."""
        profile = self._build_quick_profile(df)
        return f"STATISTICAL PROFILE:\n{json.dumps(profile, indent=2, default=str)}"

    def _build_chart_configs(self, fulfilled_charts: List[FulfilledChart]) -> List[Dict[str, Any]]:
        """Convert FulfilledChart objects to the JSON config expected by the frontend."""
        configs = []
        for fc in fulfilled_charts:
            config = {
                'chart_type': fc.viz_type,
                'title': fc.title,
                'description': fc.description,
                'x_key': fc.x_key,
                'y_key': fc.y_key,
                'x_axis_title': fc.x_axis_title,
                'y_axis_title': fc.y_axis_title,
                'format': fc.format,
                'data_override': fc.data if fc.data is not None else None,
                'is_advanced': fc.is_advanced,
                'reasoning': fc.reasoning,
            }
            # Add chart-type-specific fields
            if fc.series_by:
                config['series_by'] = fc.series_by
            if fc.group_by:
                config['group_by'] = fc.group_by
            if fc.size_key:
                config['size_key'] = fc.size_key
            if fc.was_downgraded:
                config['was_downgraded'] = True
                config['original_type'] = fc.original_viz_type
            configs.append(config)
        return configs

    def _generate_summary(
        self,
        user_query: str,
        df: pd.DataFrame,
        chart_specs: list,
        charts: List[Dict]
    ) -> str:
        """Generate a concise natural language summary of the key insights."""
        chart_desc = ", ".join([f"{c['chart_type']}: {c['title']}" for c in charts])
        data_summary = f"{len(df)} rows, {len(df.columns)} columns. Charts: {chart_desc}"
        sample = df.head(3).to_string(index=False)

        # Collect reasoning from specs
        spec_reasoning = " | ".join([
            f"{getattr(s, 'viz_type', '?')}: {getattr(s, 'reasoning', '')[:80]}"
            for s in chart_specs
        ])

        prompt = f"""You are a data analyst. Answer the user's question in 1-2 sentences using the data insight.

BUSINESS CONTEXT: {self.business_context[:300] if self.business_context else 'N/A'}
USER QUESTION: "{user_query}"
DATA: {data_summary}
SAMPLE:\n{sample}
CHART REASONING: {spec_reasoning}

Write a concise, actionable insight that directly answers the user's question. Use real numbers."""

        try:
            summary = self.llm.call_agent(
                system_prompt=prompt,
                user_query=user_query,
                model=Config.INSIGHT_MODEL,
                timeout=20,
                agent_name="InsightAnalyst-Summary"
            )
            return summary.strip()
        except Exception as e:
            logger.error(f"InsightAnalyst: Summary generation failed: {e}")
            return f"Analysis of {len(df)} records across {len(charts)} visualization(s)."

    def _fallback_to_legacy(
        self,
        user_query: str,
        sql_query: str,
        results_df: pd.DataFrame,
        schema_context: str
    ) -> Optional[Dict[str, Any]]:
        """
        Legacy fallback: uses rule-based ChartSelector + ChartRenderer.
        Only runs if the full 4-layer pipeline fails.
        """
        logger.info("InsightAnalyst: Running legacy fallback pipeline")
        try:
            analysis = self.chart_selector.analyze_data_pattern(results_df)
            if not analysis.get('has_numeric_metrics'):
                return None

            recs = self.chart_selector.select_chart_types(results_df, user_query, sql=sql_query)
            if not recs:
                return None

            charts = self._create_legacy_charts(recs, results_df, user_query)
            if not charts:
                return None

            summary = f"Analysis of {len(results_df)} records."
            try:
                summary_prompt = f"Summarize this data in 1-2 sentences: user asked '{user_query}', got {len(results_df)} rows."
                summary = self.llm.call_agent(summary_prompt, user_query, model=Config.INSIGHT_MODEL, timeout=15).strip()
            except Exception:
                pass

            return {
                'should_visualize': True,
                'summary': summary,
                'charts': charts,
                'generation_method': 'legacy_fallback'
            }
        except Exception as e:
            logger.error(f"InsightAnalyst: Legacy fallback also failed: {e}")
            return None

    def _create_legacy_charts(self, recs, df, user_query) -> List[Dict]:
        """Build legacy chart configs from ChartSelector recommendations."""
        charts = []
        for rec in recs[:3]:
            chart_type = rec.get('chart_type', 'bar')
            x_key = rec.get('suggested_x')
            y_key = rec.get('suggested_y')

            if not y_key:
                continue

            chart_df = df.copy()
            if rec.get('needs_top_n'):
                top_n = rec.get('top_n_limit', 15)
                if y_key in chart_df.columns:
                    chart_df = chart_df.nlargest(top_n, y_key)

            if rec.get('is_aggregation') and x_key:
                chart_df = df.groupby(x_key).size().reset_index(name='count')
                y_key = 'count'

            charts.append({
                'chart_type': chart_type,
                'title': f"{(y_key or '').replace('_', ' ').title()} by {(x_key or '').replace('_', ' ').title()}",
                'description': rec.get('reason', ''),
                'x_key': x_key,
                'y_key': y_key,
                'data_override': chart_df.to_dict(orient='records') if rec.get('needs_top_n') or rec.get('is_aggregation') else None,
                'is_advanced': False,
            })
        return charts
