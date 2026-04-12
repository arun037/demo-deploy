"""
Chart Planner Agent - LLM-Driven, Data-Contract-Based Visualization Intelligence

This agent:
1. Receives a full data profile (statistical analysis of the result set)
2. Receives data exploration findings (from autonomous SQL by InsightAnalyst)
3. Outputs a structured Data Contract per chart — specifying chart type, columns,
   required data types, aggregation method, and a fallback chart type.
4. Supports ANY chart type: standard (Recharts) and advanced (Plotly).
"""

import json
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
import pandas as pd
from backend.core.llm_client import LLMClient
from backend.core.logger import logger
from backend.config import Config


@dataclass
class ChartSpecification:
    """
    Declarative chart specification with full Data Contract.
    The DataContractor uses this to validate, transform, and shape data
    before it reaches the frontend renderer.
    """
    viz_type: str           # Chart type (see FULL_CHART_REGISTRY below)
    title: str
    description: str
    y_column: str
    format: str             # 'currency', 'percentage', 'number'
    reasoning: str
    priority: int           # 1-10, higher = more important
    
    # Optional / default fields
    x_column: Optional[str] = None
    x_axis_title: Optional[str] = None  # Human-readable label for X axis
    y_axis_title: Optional[str] = None  # Human-readable label for Y axis
    series_column: Optional[str] = None
    sort_order: str = 'desc'
    limit: Optional[int] = None

    # DATA CONTRACT FIELDS — critical for zero-error rendering
    aggregation: str = 'none'            # 'sum', 'count', 'avg', 'min', 'max', 'none'
    group_by: Optional[str] = None       # Column to group by before aggregation
    size_column: Optional[str] = None    # For bubble charts: the size/z axis
    color_column: Optional[str] = None   # For heatmap/treemap: the color dimension
    required_column_types: dict = field(default_factory=dict)  # {"x_column": "text", "y_column": "numeric"}
    fallback_viz_type: str = 'bar_chart' # Simpler chart to use if this type fails validation


# All supported chart types across Recharts (standard) and Plotly (advanced)
STANDARD_CHART_TYPES = {
    'kpi_card', 'line_chart', 'bar_chart', 'pie_chart',
    'multi_line', 'multi_bar', 'area_chart'
}

ADVANCED_CHART_TYPES = {
    'scatter_chart', 'bubble_chart', 'histogram', 'heatmap',
    'funnel_chart', 'waterfall_chart', 'treemap', 'candlestick', 'gauge'
}

FULL_CHART_REGISTRY = STANDARD_CHART_TYPES | ADVANCED_CHART_TYPES

# Required column types per chart type (for DataContractor validation)
CHART_COLUMN_REQUIREMENTS = {
    'kpi_card':       {'y_column': 'numeric'},
    'bar_chart':      {'x_column': 'text', 'y_column': 'numeric'},
    'line_chart':     {'x_column': 'any', 'y_column': 'numeric'},
    'area_chart':     {'x_column': 'any', 'y_column': 'numeric'},
    'pie_chart':      {'x_column': 'text', 'y_column': 'numeric'},
    'multi_line':     {'x_column': 'any', 'y_column': 'numeric', 'series_column': 'text'},
    'multi_bar':      {'x_column': 'any', 'y_column': 'numeric', 'series_column': 'text'},
    'scatter_chart':  {'x_column': 'numeric', 'y_column': 'numeric'},
    'bubble_chart':   {'x_column': 'numeric', 'y_column': 'numeric', 'size_column': 'numeric'},
    'histogram':      {'x_column': 'numeric'},
    'heatmap':        {'x_column': 'text', 'y_column': 'text', 'size_column': 'numeric'},
    'funnel_chart':   {'x_column': 'text', 'y_column': 'numeric'},
    'waterfall_chart':{'x_column': 'text', 'y_column': 'numeric'},
    'treemap':        {'x_column': 'text', 'y_column': 'numeric'},
    'gauge':          {'y_column': 'numeric'},
}

# Downgrade chain: if a chart type fails, try this simpler one
FALLBACK_CHAIN = {
    'bubble_chart':    'scatter_chart',
    'scatter_chart':   'bar_chart',
    'heatmap':         'bar_chart',
    'treemap':         'bar_chart',
    'waterfall_chart': 'bar_chart',
    'funnel_chart':    'bar_chart',
    'candlestick':     'line_chart',
    'gauge':           'kpi_card',
    'histogram':       'bar_chart',
    'multi_line':      'line_chart',
    'multi_bar':       'bar_chart',
    'area_chart':      'line_chart',
    'pie_chart':       'bar_chart',
    'line_chart':      'bar_chart',
    'bar_chart':       'kpi_card',
    'kpi_card':        'kpi_card',  # terminal
}


class ChartPlanner:
    """
    LLM-driven chart planner that generates Data Contract specifications.
    Supports any chart type; uses DataContractor to validate + transform data.
    """

    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client
        logger.info("ChartPlanner initialized — open chart registry, data contract mode")

    def plan_charts(
        self,
        user_query: str,
        sql_query: str,
        results_df: pd.DataFrame,
        max_charts: int = 3,
        chat_history: List[Dict] = None,
        business_context: str = "",
        schema_context: str = "",
        exploration_findings: str = ""  # NEW: findings from InsightAnalyst._explore_data()
    ) -> List[ChartSpecification]:
        """
        Generate Data Contract chart specifications using LLM intelligence.

        Args:
            user_query: Original user question
            sql_query: Executed SQL query
            results_df: Query results
            max_charts: Maximum number of charts
            chat_history: Conversation context
            business_context: Business domain context
            schema_context: DB schema information
            exploration_findings: Autonomous SQL exploration results from InsightAnalyst

        Returns:
            List of validated ChartSpecification objects
        """
        if results_df.empty:
            logger.info("ChartPlanner: Empty results, no charts to plan")
            return []

        logger.info(f"ChartPlanner: Planning charts for {len(results_df)} rows, {len(results_df.columns)} columns")

        # Build full data context
        data_context = self._prepare_data_context(results_df, sql_query)

        # Generate specs with LLM
        chart_specs = self._generate_chart_specs_with_llm(
            user_query=user_query,
            sql_query=sql_query,
            data_context=data_context,
            max_charts=max_charts,
            chat_history=chat_history or [],
            business_context=business_context,
            schema_context=schema_context,
            exploration_findings=exploration_findings
        )

        # Validate specs
        validated_specs = self._validate_specs(chart_specs, results_df)

        logger.info(f"ChartPlanner: Generated {len(validated_specs)} validated chart specifications")
        return validated_specs

    def _prepare_data_context(self, df: pd.DataFrame, sql_query: str = "") -> Dict[str, Any]:
        """
        Build a full statistical profile of the dataframe.
        This is the primary input for the LLM's chart planning decisions.
        """
        is_pre_aggregated = "GROUP BY" in sql_query.upper()
        is_large = len(df) > 500

        columns_info = []
        for col in df.columns:
            dtype = str(df[col].dtype)
            unique_count = int(df[col].nunique())

            col_info = {
                'name': col,
                'dtype': dtype,
                'unique_count': unique_count,
                'has_nulls': bool(df[col].isnull().any()),
            }

            # Detect column role
            is_id = col.lower() == 'id' or col.lower().endswith('_id') or col.lower().endswith('id')
            is_name = any(k in col.lower() for k in ['name', 'title', 'label', 'description'])
            is_date = any(k in col.lower() for k in ['date', 'time', 'year', 'month', 'day', 'period'])

            if 'int' in dtype or 'float' in dtype:
                col_info['type'] = 'numeric'
                col_info['logical_type'] = 'id' if is_id else 'metric'
                col_info['min'] = float(df[col].min()) if not df[col].empty else None
                col_info['max'] = float(df[col].max()) if not df[col].empty else None
                col_info['avg'] = float(df[col].mean()) if not df[col].empty else None
                col_info['sample'] = df[col].dropna().head(3).tolist()

                # Distribution hints
                if col_info['logical_type'] == 'metric' and len(df) > 5:
                    try:
                        sorted_vals = df[col].dropna().sort_values(ascending=False)
                        total = sorted_vals.sum()
                        if total > 0:
                            col_info['top3_concentration_pct'] = round(sorted_vals.head(3).sum() / total * 100, 1)
                    except Exception:
                        pass

            elif 'datetime' in dtype:
                col_info['type'] = 'datetime'
                col_info['logical_type'] = 'time'
                col_info['sample'] = df[col].dropna().head(3).astype(str).tolist()

            elif is_date:
                col_info['type'] = 'date_string'
                col_info['logical_type'] = 'time'
                col_info['sample'] = df[col].dropna().head(3).tolist()

            else:
                col_info['type'] = 'categorical'
                col_info['logical_type'] = 'name' if is_name else 'category'
                col_info['sample'] = df[col].dropna().head(3).tolist()
                if unique_count <= 20:
                    col_info['top_values'] = df[col].value_counts().head(5).to_dict()

            columns_info.append(col_info)

        return {
            'row_count': len(df),
            'column_count': len(df.columns),
            'is_large_dataset': is_large,
            'is_pre_aggregated': is_pre_aggregated,
            'columns': columns_info,
            'sample_data': df.head(5).to_dict(orient='records'),
        }

    def _generate_chart_specs_with_llm(
        self,
        user_query: str,
        sql_query: str,
        data_context: Dict[str, Any],
        max_charts: int,
        chat_history: List[Dict],
        business_context: str,
        schema_context: str,
        exploration_findings: str
    ) -> List[Dict[str, Any]]:
        """Use LLM to generate Data Contract chart specifications."""

        # Build column descriptions
        col_parts = []
        for col in data_context['columns']:
            log_type = col.get('logical_type', 'unknown')
            desc = f"  - {col['name']} ({col['type']} / {log_type}): {col['unique_count']} unique values"
            if col['type'] == 'numeric' and 'min' in col:
                desc += f", range [{col['min']:.2f} → {col['max']:.2f}], avg={col.get('avg', 0):.2f}"
                if 'top3_concentration_pct' in col:
                    desc += f", top-3 = {col['top3_concentration_pct']}% of total"
            elif col['type'] == 'categorical' and 'top_values' in col:
                top_vals = list(col['top_values'].items())[:3]
                desc += f", top: {', '.join([f'{k}({v})' for k, v in top_vals])}"
            desc += f", sample: {col['sample'][:3]}"
            col_parts.append(desc)

        columns_desc = "\n".join(col_parts)
        sample_str = json.dumps(data_context['sample_data'][:3], indent=2, default=str)

        history_str = ""
        if chat_history:
            history_str = "\nCONVERSATIONAL CONTEXT:\n"
            for msg in chat_history[-6:]:
                role = msg.get('role', '').upper()
                content = str(msg.get('content', ''))[:150]
                history_str += f"- {role}: {content}\n"

        exploration_str = ""
        if exploration_findings:
            exploration_str = f"\n\nDATA EXPLORATION FINDINGS (from autonomous SQL queries):\n{exploration_findings}"

        system_prompt = f"""You are an Elite Business Intelligence Analyst and Data Visualization Expert.

USER'S QUESTION: "{user_query}"
{history_str}

SQL QUERY EXECUTED:
{sql_query}

DATA PROFILE ({data_context['row_count']} rows, {data_context['column_count']} columns):
- is_pre_aggregated: {data_context['is_pre_aggregated']} (True = SQL had GROUP BY, data is already summarized)
- is_large_dataset: {data_context['is_large_dataset']} (True = more than 500 rows)

COLUMNS:
{columns_desc}

SAMPLE DATA (first 3 rows):
{sample_str}
{exploration_str}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔴 MANDATORY: DATASET SIZE RULES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

A) Large raw data (row_count > 500, is_pre_aggregated = False):
   → NEVER plot individual rows. You MUST specify aggregation.
   → First chart MUST be a kpi_card (total/count).
   → Other charts must aggregate: set "aggregation" + "group_by" field.
   → Limit: max 20 bars/points per chart.
   → BANNED: scatter_chart (too many points), histogram on large data.

B) Pre-aggregated data (is_pre_aggregated = True):
   → Data is already summarized. Plot directly (aggregation = "none").
   → Full freedom on chart type. Limit to top 20-50 for visual clarity.

C) Small data (row_count <= 50):
   → Full freedom on chart type and complexity.
   → No aggregation needed unless user asks for it.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🟡 MANDATORY: AGGREGATION FIELDS (always include)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

"aggregation": "sum" | "count" | "avg" | "min" | "max" | "none"
"group_by": column name to group by (or null if no grouping needed)

Examples:
- "Show vendor spend"    → aggregation="sum",   group_by="Vendor_Name"
- "Count of orders"     → aggregation="count",  group_by="Status"
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🧠 CREATIVE & INTELLIGENT STORYTELLING
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Your job is to act like a Senior Data Scientist and extract the MOST MEANINGFUL, "Aha!" insights from the data to WOW the user.
- NEVER just dump raw data into a boring chart. Ask yourself: "What is the most interesting story hidden in this data?"
- Be highly creative. Favor impactful visualizations: if you see stages, build a `funnel_chart`. If you see two metrics, build a `scatter_chart`. If you see time and categories, use a `heatmap` or `area_chart`.
- You ARE ENCOURAGED to use aggregation (sum, mean, count) or focus on "Top 10" / "Bottom 5" to highlight extremes or trends.
- You have FULL FREEDOM to choose among the 16 chart types to tell the best visual story.
- MAXIMIZE VISUAL DIVERSITY: Never generate visually repetitive charts in the same response. If you generate a bar chart, the next chart must be a completely different visual representation (like a pie chart, line chart, or KPI card). Do not output plain, repetitive bar charts.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🟢 USER-REQUESTED CHART TYPE — OVERRIDE ALL DEFAULTS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

If the user explicitly asked for a specific chart type (e.g., "bubble chart", "histogram",
"waterfall chart"), YOU MUST use that type. Set required_column_types and size_column
accordingly. Never ignore a user's explicit chart request.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔵 AVAILABLE CHART TYPES (any is valid)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

STANDARD (Recharts):
- kpi_card: Single number (total, count). Needs: y_column (numeric)
- bar_chart: Category comparison. Needs: x_column (text), y_column (numeric)
- line_chart: Trend over time. Needs: x_column (date/text), y_column (numeric)
- area_chart: Cumulative trend. Needs: x_column (date/text), y_column (numeric)
- pie_chart: Part of whole (max 8 slices). Needs: x_column (text), y_column (numeric)
- multi_line: Multiple series over time. Needs: x, y, series_column (text)
- multi_bar: Grouped bars. Needs: x, y, series_column (text)

ADVANCED (Plotly — full power):
- scatter_chart: Correlation between 2 numeric cols. Needs: x, y (both numeric)
- bubble_chart: Correlation + size. Needs: x, y (numeric), size_column (numeric)
- histogram: Distribution of 1 numeric col. Needs: x_column (numeric)
- heatmap: Matrix of values. Needs: x_column (text), y_column (text), size_column (numeric)
- funnel_chart: Conversion/stages. Needs: x_column (text), y_column (numeric)
- waterfall_chart: Running total. Needs:- x_column: The exact column name for the X-axis (if applicable, else null)
- y_column: The exact column name for the Y-axis/value (required)
- x_axis_title: Human-readable, clear title for the X-axis (e.g. "Contract Duration (Days)", "Site Name")
- y_axis_title: Human-readable, clear title for the Y-axis (e.g. "Total Customers", "Revenue ($)")
- series_column: For multi_line/multi_bar, the exact column name to split series by
- format: "currency", "percentage", or "number"
- reasoning: Briefly explain why this chart is useful
- priority: Integer 1-10 (high impact = 10)
- sort_order: "asc" or "desc"
- limit: Integer (e.g., 5, 10, 20) or null

DATA CONTRACT FIELDS (MANDATORY):
- aggregation: "sum", "count", "avg", "min", "max", or "none" (default)
- group_by: The column to group by before aggregating (usually same as x_column)
- required_column_types: dict of column roles mapping to expected types e.g. {{"x_column": "text", "y_column": "numeric"}}
- fallback_viz_type: A simpler chart type to try if this one fails validation (e.g. "bar_chart", "kpi_card")

Return a JSON array of objects. Example:
[
  {{
    "title": "Vendor Spend by Category",
    "description": "Shows the distribution of vendor spending across different categories.",
    "viz_type": "bar_chart",
    "x_column": "Category_Name",
    "y_column": "Total_Spend",
    "x_axis_title": "Expense Category",
    "y_axis_title": "Total Spend ($)",
    "series_column": null,
    "format": "currency",
    "reasoning": "Identifies where the most capital is being allocated.",
    "priority": 9,
    "sort_order": "desc",
    "limit": 10,
    "aggregation": "sum",
    "group_by": "Category_Name",
    "required_column_types": {{"x_column": "text", "y_column": "numeric"}},
    "fallback_viz_type": "kpi_card"
  }}
]

NO markdown, NO explanations. ONLY the JSON array.

**CRITICAL RULES FOR `kpi_card`:** 
1. The `aggregation` MUST make logical sense for the metric. If counting IDs or rows, use `"count"`. If summarizing revenue/spend, use `"sum"`. If looking at performance ratios, use `"avg"`.
2. NEVER set a `description` to a plain number like "1". Descriptions MUST be full sentence fragments answering "What does this number mean?" (e.g. "Total accumulated revenue for the period").
3. NEVER generate a KPI that just shows an arbitrary ID number. KPIs must be counts, sums, or averages of meaningful metrics.

Generate UP TO {max_charts} charts. Each chart must reveal a genuinely different insight or perspective.
- NEVER generate the same viz_type with the same x_column AND y_column — that is a true duplicate.
- Different viz_types on the same columns ARE valid (e.g. bar_chart + pie_chart both show distribution but from different angles)."""


        user_prompt = f"Generate UP TO {max_charts} chart Data Contracts. Quality over quantity — only create charts that genuinely add insight."

        try:
            response = self.llm.call_agent(
                system_prompt=system_prompt,
                user_query=user_prompt,
                model=Config.CHART_PLANNER_MODEL,
                temperature=0.1,
                timeout=45,
                agent_name="ChartPlanner"
            )

            specs = self._parse_json_response(response)
            logger.info(f"ChartPlanner: LLM generated {len(specs)} chart specifications")
            return specs

        except Exception as e:
            logger.error(f"ChartPlanner: LLM generation failed: {e}")
            return []

    def _parse_json_response(self, response: str) -> List[Dict[str, Any]]:
        """Parse JSON from LLM response, handling markdown code blocks."""
        try:
            text = response.strip()

            # Remove markdown code blocks
            if "```" in text:
                parts = text.split("```")
                for part in parts:
                    stripped = part.strip()
                    if stripped.lower().startswith("json"):
                        stripped = stripped[4:].strip()
                    if stripped.startswith("[") or stripped.startswith("{"):
                        text = stripped
                        break

            specs = json.loads(text.strip())

            if isinstance(specs, list):
                return specs
            elif isinstance(specs, dict):
                return [specs]
            return []

        except Exception as e:
            logger.error(f"ChartPlanner: JSON parse error: {e}")
            logger.error(f"Raw response was: {response[:500]}")
            return []

    def _validate_specs(
        self,
        specs: List[Dict[str, Any]],
        df: pd.DataFrame
    ) -> List[ChartSpecification]:
        """
        Validate and create ChartSpecification objects.
        Enriches specs with required_column_types from the registry if not provided.
        """
        validated = []

        for spec in specs:
            try:
                # Check required top-level fields
                if not all(k in spec for k in ['viz_type', 'title', 'y_column']):
                    logger.warning(f"ChartPlanner: Skipping spec missing required fields: {spec.get('title', 'unknown')}")
                    continue

                viz_type = spec['viz_type']

                # Accept any known chart type; warn on unknown
                if viz_type not in FULL_CHART_REGISTRY:
                    logger.warning(f"ChartPlanner: Unknown viz_type '{viz_type}' — treating as bar_chart")
                    viz_type = 'bar_chart'

                # Auto-fill required_column_types from registry if not specified
                req_types = spec.get('required_column_types') or CHART_COLUMN_REQUIREMENTS.get(viz_type, {})

                # Determine fallback
                fallback = spec.get('fallback_viz_type') or FALLBACK_CHAIN.get(viz_type, 'bar_chart')

                # For kpi_card: skip column existence check (DataContractor will handle)
                x_col = spec.get('x_column')
                y_col = spec.get('y_column')

                # Log what we're building
                chart_spec = ChartSpecification(
                    viz_type=viz_type,
                    title=spec.get('title', 'Chart'),
                    description=spec.get('description', ''),
                    x_column=x_col,
                    y_column=y_col,
                    series_column=spec.get('series_column'),
                    size_column=spec.get('size_column'),
                    color_column=spec.get('color_column'),
                    format=spec.get('format', 'number'),
                    reasoning=spec.get('reasoning', ''),
                    priority=spec.get('priority', 5),
                    sort_order=spec.get('sort_order', 'desc'),
                    limit=spec.get('limit'),
                    aggregation=spec.get('aggregation', 'none'),
                    group_by=spec.get('group_by'),
                    required_column_types=req_types,
                    fallback_viz_type=fallback,
                )

                validated.append(chart_spec)
                logger.info(
                    f"ChartPlanner: Validated '{chart_spec.title}' "
                    f"({chart_spec.viz_type}) [agg={chart_spec.aggregation}, "
                    f"group_by={chart_spec.group_by}, limit={chart_spec.limit}, "
                    f"fallback={chart_spec.fallback_viz_type}]"
                )

            except Exception as e:
                logger.error(f"ChartPlanner: Error validating spec: {e}")
                continue

        # Sort by priority (highest first)
        validated.sort(key=lambda x: x.priority, reverse=True)

        # Deduplicate: only drop charts with the SAME viz_type AND same (x_column, y_column)
        # Different chart types on same columns are VALID (e.g. bar + pie = different perspectives)
        seen_type_axis = set()
        deduped = []
        for spec in validated:
            key = (spec.viz_type, spec.x_column, spec.y_column)
            if key in seen_type_axis:
                logger.warning(
                    f"ChartPlanner: Dropping true duplicate '{spec.title}' "
                    f"({spec.viz_type} x={spec.x_column} y={spec.y_column})"
                )
                continue
            seen_type_axis.add(key)
            deduped.append(spec)

        return deduped

