"""
DataContractor — Zero-Error Data Validation & Transformation Layer

This is the critical safety layer between ChartPlanner and ChartRenderer.
For every chart specification, it:
1. Applies aggregation (GROUP BY) if specified
2. Fuzzy-matches column names (handles case, spaces, underscores)
3. Validates & auto-casts column types against the Data Contract
4. Automatically downgrades chart type if contract cannot be fulfilled
5. Shapes data to the exact format each chart type expects
6. Applies sort + limit

GUARANTEE: Returns only renderable, validated chart configs. Never raises exceptions.
"""

import json
import pandas as pd
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from backend.agents.chart_planner import (
    ChartSpecification, CHART_COLUMN_REQUIREMENTS, FALLBACK_CHAIN,
    STANDARD_CHART_TYPES, ADVANCED_CHART_TYPES
)
from backend.core.logger import logger


@dataclass
class FulfilledChart:
    """A chart specification where data has been validated and pre-shaped for the frontend."""
    viz_type: str           # Final chart type (may differ from original if downgraded)
    title: str
    description: str
    y_key: str
    format: str
    data: Any               # Pre-shaped data (list of dicts, pivot dict, or scalar)
    reasoning: str
    
    # Optional / default fields
    x_key: Optional[str] = None
    x_axis_title: Optional[str] = None  # NEW
    y_axis_title: Optional[str] = None  # NEW
    was_downgraded: bool = False
    original_viz_type: str = ""
    series_by: Optional[str] = None   # For multi_line charts
    group_by: Optional[str] = None    # For multi_bar charts
    size_key: Optional[str] = None    # For bubble charts
    is_advanced: bool = False          # True = use Plotly renderer


class DataContractor:
    """
    Validates, transforms, and shapes DataFrames to match ChartSpecification contracts.
    All operations are wrapped in try/except — this class NEVER crashes.
    """

    DEFAULT_LIMIT = 20    # Default max bars/points
    HARD_LIMIT = 50       # Absolute maximum for any chart

    def __init__(self):
        logger.info("DataContractor initialized — zero-error data contract validation")

    def fulfill_contracts(
        self,
        specs: List[ChartSpecification],
        df: pd.DataFrame
    ) -> List[FulfilledChart]:
        """
        Process all chart specifications against the source DataFrame.
        Returns only successfully fulfilled charts.
        """
        results = []
        for spec in specs:
            try:
                fulfilled = self._fulfill_single(spec, df.copy())
                if fulfilled is not None:
                    results.append(fulfilled)
                    logger.info(f"DataContractor: ✅ Fulfilled '{fulfilled.title}' ({fulfilled.viz_type})"
                                + (" [DOWNGRADED]" if fulfilled.was_downgraded else ""))
                else:
                    logger.warning(f"DataContractor: ⚠️ Could not fulfill '{spec.title}' — skipped")
            except Exception as e:
                logger.error(f"DataContractor: 💥 Critical failure for '{spec.title}': {e}")
        return results

    def _fulfill_single(
        self,
        spec: ChartSpecification,
        df: pd.DataFrame
    ) -> Optional[FulfilledChart]:
        """Process a single chart specification end-to-end."""

        original_viz_type = spec.viz_type

        # STEP 1: Apply aggregation first (before any column resolution)
        df = self._apply_aggregation(df, spec)
        if df is None or df.empty:
            logger.warning(f"DataContractor: Aggregation produced empty data for '{spec.title}'")
            return None

        # STEP 2: Fuzzy-resolve column names
        spec = self._resolve_columns(spec, df)

        # STEP 3: Try the primary viz_type — downgrade if it fails
        for attempt_type in self._get_downgrade_chain(spec.viz_type):
            spec.viz_type = attempt_type
            req_types = CHART_COLUMN_REQUIREMENTS.get(attempt_type, {})

            # Validate and auto-cast types
            df_valid, type_ok, violations = self._validate_and_cast_types(df.copy(), spec, req_types)

            if type_ok:
                df = df_valid
                break
            else:
                logger.warning(f"DataContractor: '{spec.title}' failed as {attempt_type}: {violations} — trying fallback")
        else:
            logger.error(f"DataContractor: '{spec.title}' failed all fallback chart types — skipping")
            return None

        # STEP 4: Apply sort + limit
        df, was_limited, limit_applied, total_rows = self._apply_sort_limit(df, spec)
        if df.empty:
            return None

        # If data was truncated, annotate the description so users aren't misled.
        if was_limited:
            limit_note = f" (Showing top {limit_applied:,} of {total_rows:,} rows)"
            if not spec.description.endswith(limit_note):
                spec.description = spec.description.rstrip() + limit_note

        # STEP 5: Handle multi-series chart pivoting
        if spec.viz_type in ('multi_line', 'multi_bar') and spec.series_column:
            df = self._pivot_multi_series(df, spec)
            if df is None:
                spec.viz_type = FALLBACK_CHAIN.get(spec.viz_type, 'bar_chart')

        # STEP 6: Shape data for this specific chart type
        shaped_data = self._shape_data(df, spec)
        if shaped_data is None:
            logger.warning(f"DataContractor: Could not shape data for '{spec.title}'")
            return None

        return FulfilledChart(
            viz_type=spec.viz_type,
            title=spec.title,
            description=spec.description,
            x_key=spec.x_column,
            y_key=spec.y_column,
            x_axis_title=spec.x_axis_title,
            y_axis_title=spec.y_axis_title,
            format=spec.format,
            data=shaped_data,
            reasoning=spec.reasoning,
            was_downgraded=(spec.viz_type != original_viz_type),
            original_viz_type=original_viz_type,
            series_by=spec.series_column if spec.viz_type == 'multi_line' else None,
            group_by=spec.series_column if spec.viz_type == 'multi_bar' else None,
            size_key=spec.size_column,
            is_advanced=(spec.viz_type in ADVANCED_CHART_TYPES),
        )

    def _get_downgrade_chain(self, viz_type: str) -> List[str]:
        """Build a downgrade chain starting from viz_type, ending at bar_chart/kpi_card."""
        chain = [viz_type]
        current = viz_type
        seen = {current}
        while True:
            fallback = FALLBACK_CHAIN.get(current)
            if not fallback or fallback in seen:
                break
            chain.append(fallback)
            seen.add(fallback)
            current = fallback
        return chain

    def _apply_aggregation(self, df: pd.DataFrame, spec: ChartSpecification) -> pd.DataFrame:
        """Apply GROUP BY + aggregation function as specified in the Data Contract."""
        if not spec.aggregation or spec.aggregation == 'none':
            return df

        # Resolve group_by column
        group_col = spec.group_by
        if group_col and group_col not in df.columns:
            group_col = self._fuzzy_find_column(group_col, df.columns)
        if not group_col or group_col not in df.columns:
            logger.warning(f"DataContractor: group_by column '{spec.group_by}' not found — skipping aggregation")
            return df

        try:
            if spec.aggregation == 'count':
                result = df.groupby(group_col).size().reset_index(name='count')
                # Update spec references
                spec.y_column = 'count'
                return result

            # Resolve y_column for other aggregations
            y_col = spec.y_column
            if y_col not in df.columns:
                y_col = self._fuzzy_find_column(y_col, df.columns)
            if not y_col or y_col not in df.columns:
                logger.warning(f"DataContractor: y_column '{spec.y_column}' not found for aggregation")
                return df

            agg_map = {'sum': 'sum', 'avg': 'mean', 'min': 'min', 'max': 'max'}
            agg_func = agg_map.get(spec.aggregation, 'sum')

            # Carry along other useful columns (series_column, etc.)
            extra_cols = []
            if spec.series_column and spec.series_column in df.columns:
                extra_cols.append(spec.series_column)

            group_cols = [group_col] + extra_cols
            result = df.groupby(group_cols, dropna=False)[y_col].agg(agg_func).reset_index()

            # Update the y_column name in spec to match result
            new_y_name = f"{spec.aggregation}_{y_col}"
            result.rename(columns={y_col: new_y_name}, inplace=True)
            spec.y_column = new_y_name

            logger.info(f"DataContractor: Applied {spec.aggregation} on '{y_col}' grouped by {group_cols} → {len(result)} groups")
            return result

        except Exception as e:
            logger.error(f"DataContractor: Aggregation failed: {e}")
            return df

    def _resolve_columns(self, spec: ChartSpecification, df: pd.DataFrame) -> ChartSpecification:
        """Fuzzy-match column names against the actual DataFrame columns."""
        for attr in ['x_column', 'y_column', 'series_column', 'size_column', 'color_column', 'group_by']:
            requested = getattr(spec, attr, None)
            if requested and requested not in df.columns:
                match = self._fuzzy_find_column(requested, df.columns)
                if match:
                    logger.info(f"DataContractor: Column resolved '{requested}' → '{match}' for {attr}")
                    setattr(spec, attr, match)
        return spec

    def _fuzzy_find_column(self, requested: str, available) -> Optional[str]:
        """Case-insensitive, space/underscore-insensitive column matching."""
        def normalize(s):
            return str(s).lower().replace('_', '').replace(' ', '').replace('-', '')

        norm_req = normalize(requested)
        # Exact normalized match
        for col in available:
            if normalize(col) == norm_req:
                return col
        # Partial match
        for col in available:
            norm_col = normalize(col)
            if norm_req in norm_col or norm_col in norm_req:
                return col
        return None

    def _validate_and_cast_types(
        self,
        df: pd.DataFrame,
        spec: ChartSpecification,
        req_types: Dict[str, str]
    ) -> Tuple[pd.DataFrame, bool, List[str]]:
        """
        Validate column types against requirements. Auto-casts where possible.
        Returns (modified_df, success, list_of_violations).
        """
        violations = []

        for col_attr, expected_type in req_types.items():
            if expected_type == 'optional':
                continue
            if expected_type == 'any':
                # Just check the column exists
                col_name = getattr(spec, col_attr, None)
                if col_name and col_name not in df.columns:
                    violations.append(f"{col_attr} column '{col_name}' not found")
                continue

            col_name = getattr(spec, col_attr, None)
            if not col_name:
                violations.append(f"Required field '{col_attr}' is empty")
                continue

            if col_name not in df.columns:
                violations.append(f"Column '{col_name}' not in data")
                continue

            if expected_type == 'numeric':
                if not pd.api.types.is_numeric_dtype(df[col_name]):
                    # Try to cast (handle "$1,234.56" style strings)
                    try:
                        cleaned = (df[col_name].astype(str)
                                   .str.replace(',', '', regex=False)
                                   .str.replace('$', '', regex=False)
                                   .str.replace('%', '', regex=False)
                                   .str.strip())
                        cast_col = pd.to_numeric(cleaned, errors='coerce')
                        if cast_col.notna().sum() > 0:
                            df[col_name] = cast_col
                            logger.info(f"DataContractor: Cast '{col_name}' to numeric")
                        else:
                            violations.append(f"'{col_name}' could not be cast to numeric")
                    except Exception:
                        violations.append(f"'{col_name}' is not numeric")

            elif expected_type == 'text':
                if pd.api.types.is_numeric_dtype(df[col_name]):
                    # Numeric used as label — cast to string
                    df[col_name] = df[col_name].astype(str)
                    logger.info(f"DataContractor: Cast '{col_name}' to string for labels")

        return df, (len(violations) == 0), violations

    def _apply_sort_limit(
        self, df: pd.DataFrame, spec: ChartSpecification
    ):
        """
        Sort by y_column and apply the specified limit (or default safety cap).

        KPI cards are exempt from limiting — the full dataset must be used so
        that count/sum/avg are computed correctly.

        Returns a 4-tuple:
            (df, was_limited: bool, limit_applied: int, total_rows: int)
        """
        total_rows = len(df)
        try:
            # KPI cards: skip truncation entirely — wrong to limit before aggregation
            if spec.viz_type == 'kpi_card':
                return df, False, total_rows, total_rows

            # Sort
            if spec.y_column and spec.y_column in df.columns:
                if pd.api.types.is_numeric_dtype(df[spec.y_column]):
                    ascending = (spec.sort_order == 'asc')
                    df = df.sort_values(by=spec.y_column, ascending=ascending)

            # Limit: use specified limit, cap at HARD_LIMIT, default to DEFAULT_LIMIT
            limit = spec.limit if spec.limit is not None else self.DEFAULT_LIMIT
            limit = min(limit, self.HARD_LIMIT)
            limited_df = df.head(limit)

            was_limited = len(limited_df) < total_rows
            return limited_df, was_limited, limit, total_rows

        except Exception as e:
            logger.error(f"DataContractor: Sort/limit failed: {e}")
            fallback = df.head(self.DEFAULT_LIMIT)
            return fallback, len(fallback) < total_rows, self.DEFAULT_LIMIT, total_rows

    def _sanitize_numeric_data(self, df: pd.DataFrame, spec: ChartSpecification) -> pd.DataFrame:
        """
        Remove rows with extreme outlier y-values that would distort charts.
        Uses IQR-based filtering: keeps rows within [Q1 - 3*IQR, Q3 + 3*IQR].
        Only applied when outliers would dominate the chart scale.
        """
        if not spec.y_column or spec.y_column not in df.columns:
            return df
        col = df[spec.y_column]
        if not pd.api.types.is_numeric_dtype(col) or len(df) < 4:
            return df
        try:
            q1 = col.quantile(0.25)
            q3 = col.quantile(0.75)
            iqr = q3 - q1
            if iqr == 0:
                return df  # All same value — no filtering needed
            lower = q1 - 3 * iqr
            upper = q3 + 3 * iqr
            n_before = len(df)
            df_clean = df[(col >= lower) & (col <= upper)]
            n_removed = n_before - len(df_clean)
            if n_removed > 0:
                logger.info(
                    f"DataContractor: Removed {n_removed} extreme outlier rows "
                    f"(outside [{lower:.1f}, {upper:.1f}]) for '{spec.title}'"
                )
            # Only apply if there's actual meaningful data left
            return df_clean if len(df_clean) >= 1 else df
        except Exception as e:
            logger.error(f"DataContractor: Sanitize failed: {e}")
            return df

    def _pivot_multi_series(self, df: pd.DataFrame, spec: ChartSpecification) -> Optional[pd.DataFrame]:
        """Pivot data for multi_line / multi_bar charts."""
        try:
            if not spec.x_column or not spec.series_column:
                return None

            # Ensure datetime columns are strings
            for col in [spec.x_column, spec.series_column]:
                if col in df.columns and pd.api.types.is_datetime64_any_dtype(df[col]):
                    df[col] = df[col].dt.strftime('%Y-%m-%d')

            pivot = df.pivot_table(
                index=spec.x_column,
                columns=spec.series_column,
                values=spec.y_column,
                aggfunc='sum',
                fill_value=0
            ).reset_index()

            # Limit rows
            if len(pivot) > self.HARD_LIMIT:
                numeric_cols = [c for c in pivot.columns if c != spec.x_column]
                pivot['__total'] = pivot[numeric_cols].sum(axis=1)
                pivot = pivot.nlargest(self.DEFAULT_LIMIT, '__total').drop(columns=['__total'])

            return pivot

        except Exception as e:
            logger.error(f"DataContractor: Pivot failed: {e}")
            return None

    def _shape_data(self, df: pd.DataFrame, spec: ChartSpecification) -> Any:
        """
        Produce the exact data format each chart type expects.
        Returns None if the required columns aren't present.
        """
        # Ensure datetime columns are serializable
        for col in df.columns:
            if pd.api.types.is_datetime64_any_dtype(df[col]):
                df[col] = df[col].dt.strftime('%Y-%m-%d')

        viz = spec.viz_type

        try:
            if viz == 'bubble_chart':
                required = [spec.x_column, spec.y_column, spec.size_column]
                if not all(r and r in df.columns for r in required):
                    logger.warning(f"DataContractor: bubble_chart missing columns: {required}")
                    return None
                return df[[spec.x_column, spec.y_column, spec.size_column]].rename(
                    columns={spec.x_column: 'x', spec.y_column: 'y', spec.size_column: 'z'}
                ).to_dict(orient='records')

            elif viz == 'histogram':
                if not spec.x_column or spec.x_column not in df.columns:
                    return None
                return df[[spec.x_column]].dropna().to_dict(orient='records')

            elif viz == 'heatmap':
                # Needs: x_column (row labels), y_column (col labels), size_column (values)
                # OR: x_column (row), size_column (numeric values), pivoted
                if spec.color_column and spec.color_column in df.columns and spec.x_column in df.columns:
                    try:
                        pivot = df.pivot_table(
                            index=spec.x_column,
                            columns=spec.color_column,
                            values=spec.size_column or spec.y_column,
                            aggfunc='sum',
                            fill_value=0
                        )
                        return {
                            'type': 'pivot',
                            'z': pivot.values.tolist(),
                            'x_labels': list(pivot.columns.astype(str)),
                            'y_labels': list(pivot.index.astype(str))
                        }
                    except Exception:
                        pass
                return None

            elif viz == 'kpi_card':
                # ALWAYS check if df is exactly 1 row before assuming we need to aggregate
                # LLMs often mistakenly specify aggregation="count" for pre-aggregated scalar rows
                if len(df) == 1 and spec.y_column and spec.y_column in df.columns:
                    col = df[spec.y_column]
                    value = col.iloc[0]
                    logger.info(f"DataContractor: KPI '{spec.title}' → found literal scalar {value} (ignoring aggregation='{spec.aggregation}')")
                elif spec.aggregation == 'count':
                    value = len(df)
                    agg_name = 'count'
                    logger.info(f"DataContractor: KPI '{spec.title}' → count={value} (aggregation='count')")
                else:
                    if not spec.y_column or spec.y_column not in df.columns:
                        return None
                    col = df[spec.y_column]
                    
                    if len(df) == 1:
                        value = col.iloc[0]
                        agg_name = 'literal'
                    elif pd.api.types.is_numeric_dtype(col):
                        if spec.aggregation in ('avg', 'mean'):
                            value = col.mean()
                            agg_name = 'mean'
                        elif spec.aggregation == 'min':
                            value = col.min()
                            agg_name = 'min'
                        elif spec.aggregation == 'max':
                            value = col.max()
                            agg_name = 'max'
                        elif spec.aggregation == 'sum':
                            value = col.sum()
                            agg_name = 'sum'
                        else:
                            # Fallback if 'none' or unknown: try semantics, default to sum
                            col_lower = spec.y_column.lower()
                            is_avg_column = any(k in col_lower for k in ['avg', 'average', 'mean', 'rate', 'ratio', 'pct', 'percent'])
                            value = col.mean() if is_avg_column else col.sum()
                            agg_name = 'mean (fallback)' if is_avg_column else 'sum (fallback)'
                    else:
                        value = col.iloc[0]
                        agg_name = 'fallback_literal'
                        
                    logger.info(
                        f"DataContractor: KPI '{spec.title}' → "
                        f"{agg_name}={value} "
                        f"(column='{spec.y_column}', aggregation='{spec.aggregation}')"
                    )
                return {'value': self._format_value(value, spec.format)}

            elif viz in ('multi_line', 'multi_bar'):
                # After pivot, data is already in correct format
                return df.to_dict(orient='records')

            else:
                # Standard: list of records
                return df.to_dict(orient='records')

        except Exception as e:
            logger.error(f"DataContractor: Shape failed for {viz}: {e}")
            return None

    def _format_value(self, value, format_type: str) -> str:
        """Format a single value for KPI display."""
        try:
            if pd.isna(value):
                return "N/A"
            num = float(value)
            if format_type == 'currency':
                return f"${num:,.2f}"
            elif format_type == 'percentage':
                return f"{num:.1f}%"
            else:
                if num >= 1_000_000:
                    return f"{num/1_000_000:.1f}M"
                elif num >= 1_000:
                    return f"{num:,.0f}"
                return f"{num:.2f}"
        except Exception:
            return str(value)
