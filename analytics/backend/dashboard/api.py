"""
Dashboard API Routes

FastAPI routes for dashboard operations.
"""

import json
from datetime import datetime
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from typing import Dict, Any

from .schema_graph_analyzer import SchemaGraphAnalyzer
from backend.agents.embedding_retriever import EmbeddingRetriever
from .rag_retriever import RAGRetriever
from .dashboard_intelligence import DashboardIntelligence
from .config_manager import ConfigManager
from .query_cache_manager import QueryCacheManager
from .filters import (
    PeriodCalculator,
    DateColumnDetector,
    SQLFilterInjector,
    ComparisonEngine
)

from backend.core.logger import logger


# Create router
router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

# Global instances (will be initialized in startup)
config_mgr = None
cache_mgr = None
llm_client = None
db_manager = None

# Filter components
period_calc = None
date_detector = None
sql_injector = None
comparison_engine = None


def init_dashboard(llm_client_instance, db_manager_instance):
    """Initialize dashboard components"""
    global config_mgr, cache_mgr, llm_client, db_manager
    global period_calc, date_detector, sql_injector, comparison_engine
    
    config_mgr = ConfigManager()
    cache_mgr = QueryCacheManager()
    llm_client = llm_client_instance
    db_manager = db_manager_instance
    
    # Initialize filter components
    period_calc = PeriodCalculator()
    sql_injector = SQLFilterInjector()
    
    logger.info("S Dashboard system initialized")
    logger.info("S Filter components initialized")
    
    return config_mgr, cache_mgr



@router.get("/config")
async def get_config():
    """Check if dashboard config exists and return it"""
    try:
        if not config_mgr.exists():
            return {"exists": False}
        
        config = config_mgr.load()
        return {"exists": True, "config": config}
    except Exception as e:
        logger.error(f"Error getting config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate")
async def generate_dashboard(schema_file: str = "db_schema.json"):
    """Generate new dashboard configuration"""
    try:
        logger.info("=" * 80)
        logger.info(" DASHBOARD GENERATION STARTED")
        logger.info("=" * 80)
        
        # 1. Load schema
        import os
        base_dir = os.path.dirname(os.path.abspath(__file__))
        schema_path = os.path.join(os.path.dirname(base_dir), schema_file)
        
        with open(schema_path, 'r') as f:
            schema = json.load(f)
        
        logger.info(f"S Loaded schema: {len(schema)} tables")
        
        # 2. Graph analysis
        logger.info(" Analyzing schema graph...")
        graph_analyzer = SchemaGraphAnalyzer()
        graph_analysis = graph_analyzer.analyze(schema)
        
        logger.info(f"S Found {len(graph_analysis['fact_tables'])} fact tables")
        logger.info(f"S Found {len(graph_analysis['dimension_tables'])} dimension tables")
        
        # 3. Initialize shared EmbeddingRetriever (same as chat uses)
        logger.info(" Initializing shared EmbeddingRetriever...")
        embedding_retriever = EmbeddingRetriever()  # Uses same collection as chat
        logger.info("S EmbeddingRetriever initialized (shared with chat)")
        
        # 4. Initialize RAG with shared embeddings
        logger.info(" Initializing RAG retriever...")
        rag = RAGRetriever(embedding_retriever, llm_client)
        
        # 5. Generate insights
        logger.info(" Generating dashboard insights...")
        intelligence = DashboardIntelligence(llm_client, rag, graph_analysis, db_manager)
        config = intelligence.generate_dashboard(schema)
        
        # 6. Validate we got insights
        if not config.get("insights") or len(config["insights"]) == 0:
            raise Exception("Failed to generate insights - LLM returned empty results")
        
        # 7. Save config
        logger.info(" Saving dashboard configuration...")
        config_mgr.save(config)
        
        logger.info("=" * 80)
        logger.info(f"[OK] DASHBOARD GENERATION COMPLETE: {len(config['insights'])} insights")
        logger.info("=" * 80)
        
        return {"success": True, "config": config}
    
    except Exception as e:
        logger.error(f"[FAIL] Dashboard generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _inject_filter_condition(sql: str, condition: str) -> str:
    """
    Safely inject an AND condition into the outermost WHERE clause of a SQL statement.
    Parenthesis-depth aware to avoid injecting into subqueries.
    """
    depth = 0
    insert_pos = None
    n = len(sql)
    upper = sql.upper()
    i = 0
    while i < n:
        ch = sql[i]
        if ch == '(':
            depth += 1
        elif ch == ')':
            depth -= 1
        elif depth == 0:
            tail = upper[i:]
            for kw in ('GROUP BY', 'ORDER BY', 'LIMIT ', 'HAVING '):
                if tail.startswith(kw):
                    insert_pos = i
                    break
            if insert_pos is not None:
                break
        i += 1

    if insert_pos is not None:
        return sql[:insert_pos].rstrip() + f' AND {condition} ' + sql[insert_pos:]
    else:
        return sql.rstrip() + f' AND {condition}'


@router.get("/data/{insight_id}")
async def get_insight_data(insight_id: str, period: str = "all", compare: bool = False,
                           refresh: bool = False,
                           site_id: str = None,
                           lead_status_filter: str = None,
                           lead_category_filter: str = None,
                           lead_source_filter: str = None):
    """
    Get data for specific insight with optional filtering and comparison.

    Parameters:
    - insight_id           : ID of the insight
    - period               : Time period (7d, 30d, 3m, 12m, ytd, all)
    - compare              : Whether to include period-over-period comparison
    - refresh              : Whether to bypass cache
    - site_id              : Site filter (e.g. "4" for FG, "all" to clear)
    - lead_status_filter   : Lead status filter (SUCCESS / FAIL / DUPLICATE / all)
    - lead_category_filter : Franchise category filter (Food / Retail / ... / all)
    """
    try:
        # ── Collect all dimensional filter values by their API param name ──
        raw_dim_filters = {
            "site_id":               site_id,
            "lead_status_filter":    lead_status_filter,
            "lead_category_filter":  lead_category_filter,
            "lead_source_filter":    lead_source_filter,
        }
        # Only keep non-null, non-"all" values
        active_dim_filters = {k: v for k, v in raw_dim_filters.items() if v and v != "all"}

        # Build cache key
        cache_parts = [insight_id, period] + [f"{k}={v}" for k, v in sorted(active_dim_filters.items())]
        cache_key = "_".join(cache_parts)
        
        # Check cache (skip if refresh=True)
        if not refresh:
            cached_data = cache_mgr.get(cache_key)
            if cached_data:
                logger.info(f" Cache hit for {cache_key}")
                return {"success": True, "data": cached_data, "from_cache": True}
        
        # Load config
        config = config_mgr.load()
        if not config:
            raise HTTPException(status_code=404, detail="Dashboard config not found")
        
        # Find insight
        insight = next((i for i in config["insights"] if i["id"] == insight_id), None)
        if not insight:
            raise HTTPException(status_code=404, detail="Insight not found")
        
        # Get original SQL and template (if available)
        original_sql = insight["sql"]
        sql_template  = insight.get("sql_template", "")

        # Map frontend period codes → MySQL INTERVAL strings
        PERIOD_TO_INTERVAL = {
            "7d":  "7 DAY",
            "30d": "30 DAY",
            "3m":  "3 MONTH",
            "6m":  "6 MONTH",
            "12m": "12 MONTH",
            "all": "100 YEAR",   # Effectively "all time" without stripping the clause
        }

        date_info = None  # kept for comparison_engine below

        # Check if this insight requires/supports date filtering
        requires_date = insight.get("requires_date_filter", True)
        filter_metadata = insight.get("filter_metadata", {})
        supports_time = filter_metadata.get("supports_time_filter", requires_date)
        
        if sql_template and "{period}" in sql_template:
            # ── Template-based replacement (accurate, no double-injection) ──────
            if requires_date and supports_time:
                interval = PERIOD_TO_INTERVAL.get(period, "30 DAY")
                filtered_sql = sql_template.replace("{period}", interval)
                logger.info(f" Template period replacement: {period} → {interval} for {insight_id}")
            else:
                # No date filter needed - use template as-is (shouldn't have {period} but handle gracefully)
                filtered_sql = sql_template.replace("{period}", "100 YEAR")  # Effectively all time
                logger.info(f" Template without date filter for {insight_id} (requires_date_filter=false)")
        elif period != "all" and requires_date and supports_time and period_calc and sql_injector:
            # ── Fallback: injector for non-template SQL ──────────────────────────
            global date_detector, comparison_engine
            if not date_detector:
                import os
                base_dir = os.path.dirname(os.path.abspath(__file__))
                schema_path = os.path.join(os.path.dirname(base_dir), "db_schema.json")
                with open(schema_path, 'r') as f:
                    schema = json.load(f)
                date_detector = DateColumnDetector(llm_client, schema)
                comparison_engine = ComparisonEngine(db_manager, sql_injector, period_calc)

            date_info = date_detector.detect(original_sql, insight_id)
            if date_info and sql_injector.can_inject(original_sql):
                date_range   = period_calc.calculate(period)
                filtered_sql = sql_injector.inject_filter(original_sql, date_info, date_range)
                logger.info(f" Injector period filter applied: {period} for {insight_id}")
            else:
                filtered_sql = original_sql
                logger.info(f"[WARN]  Could not apply period filter to {insight_id} — using original SQL")
        elif sql_template and "{period}" not in sql_template:
            # Template exists but no {period} placeholder - use as-is
            filtered_sql = sql_template
            logger.info(f" Using SQL template as-is (no period placeholder) for {insight_id}")
        else:
            # No date filtering needed or period is "all" - use original SQL
            filtered_sql = original_sql
            if not requires_date or not supports_time:
                logger.info(f" Skipping date filter for {insight_id} (requires_date_filter={requires_date}, supports_time={supports_time})")

        # ── Apply dimensional filters generically ────────────────────────────
        # Load filter_definitions once so we can map param→filter_ref
        import os as _os
        _bc_path = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..', 'business_context.json')
        _filter_defs = {}
        try:
            with open(_bc_path) as _f:
                _bc = json.load(_f)
            _filter_defs = _bc.get('dashboard', {}).get('filter_definitions', {})
        except Exception:
            pass

        # Build param→filter_ref mapping (e.g. "site_id" → "site")
        _param_to_ref = {fd['param']: ref_key for ref_key, fd in _filter_defs.items()}

        card_filters = insight.get("card_filters", [])
        for param, value in active_dim_filters.items():
            filter_ref = _param_to_ref.get(param)
            if not filter_ref:
                logger.info(f"[WARN]  Unknown filter param '{param}', skipping")
                continue
            card_filter_def = next((cf for cf in card_filters if cf.get("filter_ref") == filter_ref), None)
            if card_filter_def and card_filter_def.get("sql_fragment"):
                condition = card_filter_def["sql_fragment"].replace("{value}", value)
                filtered_sql = _inject_filter_condition(filtered_sql, condition)
                logger.info(f" Applied {param}={value} filter to {insight_id}: {condition}")
                logger.debug(f" SQL after filter injection: {filtered_sql[:200]}...")
            else:
                logger.info(f"[WARN]  No '{filter_ref}' filter defined for {insight_id}, skipping")
        
        # Execute SQL
        logger.info(f" Executing query for {insight_id} (period={period}, refresh={refresh})")
        logger.info(f"SQL: {filtered_sql}")
        results = db_manager.execute_query_safe(filtered_sql)
        
        row_count = len(results)
        logger.info(f" Query returned {row_count} rows")
        
        if row_count == 0:
            logger.warning(f"[WARN]  Result is empty for {insight_id}!")
        else:
            first_row = results.iloc[0].to_dict()
            logger.info(f"S First row sample: {first_row}")
        
        # Handle NaN and Inf values before JSON serialization
        import numpy as np
        import math
        
        # Convert to dict first, then handle NaN/Inf in the dict
        results_dict = results.to_dict(orient="records")
        
        # Replace NaN and Inf in the dictionary
        def clean_value(val):
            if isinstance(val, float):
                if math.isnan(val) or math.isinf(val):
                    return None
            return val
        
        cleaned_rows = []
        for row in results_dict:
            cleaned_row = {k: clean_value(v) for k, v in row.items()}
            cleaned_rows.append(cleaned_row)
        
        data = {
            "rows": cleaned_rows,
            "columns": results.columns.tolist(),
            "row_count": row_count,
            "last_updated": datetime.now().isoformat(),
            "refresh_interval": insight.get("refresh_interval", "hourly"),
            "period": period
        }
        
        # Add comparison if requested
        if compare and comparison_engine and date_info and insight.get("viz_type") == "kpi_card":
            try:
                date_range = period_calc.calculate(period)
                comparison = comparison_engine.compare(original_sql, date_info, date_range)
                if comparison:
                    data["comparison"] = comparison
                    logger.info(f" Added comparison for {insight_id}: {comparison['trend']} {comparison['change_percent']}%")
            except Exception as e:
                logger.error(f"Error calculating comparison: {e}")
        
        # Cache result
        cache_mgr.put(cache_key, data, insight.get("refresh_interval", "hourly"))
        
        return {"success": True, "data": data, "from_cache": False}
    
    except Exception as e:
        logger.error(f"Error getting insight data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


from fastapi import BackgroundTasks

@router.post("/regenerate")
async def regenerate_dashboard(background_tasks: BackgroundTasks):
    """
    Delete config and regenerate in background to prevent timeouts.
    Returns immediately with status.
    """
    try:
        logger.info(" Dashboard regeneration request received")
        
        # Define background task function
        async def run_regeneration():
            try:
                logger.info("background_task: Starting regeneration...")
                # Delete config
                config_mgr.delete()
                # Clear cache
                cache_mgr.clear()
                # Regenerate (this is the heavy step)
                await generate_dashboard()
                logger.info("background_task: Regeneration complete")
            except Exception as e:
                logger.error(f"background_task failed: {e}")

        # Add to background tasks
        background_tasks.add_task(run_regeneration)
        
        return {
            "success": True, 
            "message": "Dashboard regeneration started in background. Please refresh in a minute."
        }
    
    except Exception as e:
        logger.error(f"Error starting regeneration: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/insight/{insight_id}/title")
async def update_insight_title(insight_id: str, new_title: Dict[str, str]):
    """
    Update the title of a specific insight in the dashboard config
    
    Parameters:
    - insight_id: ID of the insight to update
    - new_title: JSON body with {"title": "New Title"}
    """
    try:
        title = new_title.get("title", "").strip()
        if not title:
            raise HTTPException(status_code=400, detail="Title cannot be empty")
        
        # Load current config
        config = config_mgr.load()
        if not config:
            raise HTTPException(status_code=404, detail="Dashboard config not found")
        
        # Find and update the insight
        insight_found = False
        for insight in config.get("insights", []):
            if insight["id"] == insight_id:
                old_title = insight["title"]
                insight["title"] = title
                insight_found = True
                logger.info(f"  Updated insight '{insight_id}' title: '{old_title}'  '{title}'")
                break
        
        if not insight_found:
            raise HTTPException(status_code=404, detail=f"Insight '{insight_id}' not found")
        
        # Save updated config
        config_mgr.save(config)
        
        # Clear cache for this insight (since title is part of cached data)
        cache_mgr.delete(insight_id)
        
        return {
            "success": True,
            "message": f"Title updated successfully",
            "insight_id": insight_id,
            "new_title": title
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating insight title: {e}")
        raise HTTPException(status_code=500, detail=str(e))

