import pandas as pd
import traceback
import os
import json
from typing import Dict, Any, Optional, List

from backend.core import DatabaseManager, LLMClient
from backend.core.logger import logger
from backend.ai_insights.job_store import JobStore
from backend.ai_insights.data_profiler import DataProfiler
from backend.ai_insights.insight_planner import InsightPlanner
from backend.ai_insights.feature_engineer import FeatureEngineer
from backend.ai_insights.model_trainer import ModelTrainer
from backend.ai_insights.model_registry import ModelRegistry
from backend.ai_insights.explainability import ExplainabilityService
from backend.ai_insights.narrative_generator import NarrativeGenerator


class InsightOrchestrator:
    """
    Manages the background execution of Insight Jobs.
    Uses a cached schema for consistent, efficient lookups.
    """

    SCHEMA_PATH = "backend/db_schema.json"

    def __init__(self, db_manager: DatabaseManager, llm_client: LLMClient):
        self.db_manager = db_manager
        self.llm_client = llm_client
        self.registry = ModelRegistry()
        self._schema_cache = self._load_schema()

    def _load_schema(self) -> List[Dict]:
        """Load schema once, cache it."""
        if os.path.exists(self.SCHEMA_PATH):
            try:
                with open(self.SCHEMA_PATH, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load schema: {e}")
        return []

    def _get_table_info(self, table_name: str) -> Dict[str, Any]:
        """Get table info from cached schema."""
        for t in self._schema_cache:
            if t.get("table_name") == table_name:
                return t
        return {}

    def _get_qualified_table(self, table_name: str) -> str:
        """Get fully qualified table name from schema."""
        info = self._get_table_info(table_name)
        db_name = info.get("database_name")
        return f"`{db_name}`.`{table_name}`" if db_name else f"`{table_name}`"

    def start_job(self, table_name: str, background_tasks) -> str:
        """Creates a job record and schedules the background task."""
        job_id = JobStore.create_job(job_type="model_training")
        JobStore.update_job(job_id, artifacts={"table": table_name})
        background_tasks.add_task(self.run_pipeline, job_id, table_name)
        return job_id

    def start_autonomous_discovery(self, background_tasks) -> List[str]:
        """
        Two-Stage Discovery:
        Stage 1: Consultant analyzing schema strategy.
        Stage 2: Targeted deep-dive modeling for top opportunities.
        """
        schema_outline = []

        if self._schema_cache:
            for table in self._schema_cache:
                schema_outline.append({
                    "table_name": table.get("table_name"),
                    "purpose": table.get("purpose"),
                    "columns": [c.get("name") for c in table.get("columns", [])],
                    "column_descriptions": [
                        f"{c.get('name')}: {c.get('description')}"
                        for c in table.get("columns", [])[:15]
                    ]
                })
            logger.info(f"Using cached schema for Strategic Discovery ({len(schema_outline)} tables).")

        # Fallback to dynamic scan if schema JSON missing
        if not schema_outline:
            all_tables = self.db_manager.get_table_names()
            for t in all_tables:
                try:
                    cols = self.db_manager.get_column_names(t)
                    schema_outline.append({"table_name": t, "columns": cols})
                except:
                    continue

        # Stage 1: Identify Strategies (Consultant)
        planner = InsightPlanner(self.llm_client)
        opportunities = planner.discover_opportunities(schema_outline)

        # Stage 2: Launch Jobs
        job_ids = []
        for opp in opportunities:
            table = opp.get("table_name")
            if not table:
                continue

            job_id = JobStore.create_job(job_type="model_training")
            JobStore.update_job(job_id, artifacts={
                "table": table,
                "strategic_hint": opp
            })
            background_tasks.add_task(self.run_pipeline, job_id, table)
            job_ids.append(job_id)

        return job_ids

    def run_pipeline(self, job_id: str, table_name: str):
        """
        The main intelligent pipeline:
        1. Load Data  2. Profile  3. Plan  4. Engineer  5. Train  6. Explain  7. Narrative
        """
        try:
            # ========== 1. LOAD DATA ==========
            JobStore.update_job(job_id, status="loading_data", progress=10, message="Loading data from database...")

            qualified_table = self._get_qualified_table(table_name)
            
            # Use up to 50K rows for accuracy (user prioritizes accuracy over speed)
            df = self.db_manager.execute_query_safe(f"SELECT * FROM {qualified_table} LIMIT 50000")

            if df.empty:
                raise ValueError(f"Table {table_name} is empty")

            logger.info(f"Pipeline [{job_id[:8]}]: Loaded {len(df)} rows from {qualified_table}")

            # ========== 2. PROFILE DATA ==========
            JobStore.update_job(job_id, status="profiling", progress=25, message="Analyzing data structure & quality...")
            profiler = DataProfiler()
            profile = profiler.profile_dataframe(df)
            JobStore.update_job(job_id, artifacts={"profile": profile})

            # ========== 3. PLAN INSIGHT (LLM) ==========
            JobStore.update_job(job_id, status="planning", progress=40, message="AI reasoning about best prediction targets...")

            table_info = self._get_table_info(table_name)
            schema_desc = table_info.get("purpose", "Auto-detected schema")

            # Get Strategic Hint from Stage 1
            job = JobStore.get_job(job_id)
            strategic_hint = job.get("artifacts", {}).get("strategic_hint")

            planner = InsightPlanner(self.llm_client)
            plan = planner.plan_insight(table_name, schema_desc, profile, strategic_hint=strategic_hint)

            if "error" in plan:
                raise ValueError(f"Planning failed: {plan.get('raw_response', 'Unknown error')}")

            JobStore.update_job(job_id, artifacts={"plan": plan})

            # ========== 4. FEATURE ENGINEERING ==========
            JobStore.update_job(job_id, status="engineering", progress=55, message="Engineering features adaptively...")
            target = plan["target_column"]

            if target not in df.columns:
                raise ValueError(f"AI selected target '{target}' not found in dataset columns")

            # Filter to only suggested columns + target
            feature_cols = plan.get("feature_columns", [])
            cols_to_use = feature_cols + [target]
            valid_cols = [c for c in cols_to_use if c in df.columns]
            df_model = df[valid_cols].copy()

            fe = FeatureEngineer()
            X, y, fe_meta = fe.fit_transform(df_model, target)
            JobStore.update_job(job_id, artifacts={"feature_metadata": fe_meta})

            # ========== 5. TRAIN MODEL (INTELLIGENT) ==========
            JobStore.update_job(job_id, status="training", progress=70, message=f"Training & evaluating models ({plan['task_type']})...")
            trainer = ModelTrainer(task_type=plan["task_type"])
            train_results = trainer.train_auto(X, y)

            if "error" in train_results:
                JobStore.update_job(job_id, status="failed", error=train_results["error"],
                                    message="Training skipped: insufficient data")
                return

            # ========== 6. SAVE MODEL ==========
            metadata = {
                "target": target,
                "metrics": train_results,
                "plan": plan,
                "feature_metadata": fe_meta,
                "input_features": feature_cols
            }
            self.registry.save_model(job_id, trainer.best_model, fe, metadata)

            # ========== 7. EXPLAINABILITY & NARRATIVE ==========
            JobStore.update_job(job_id, status="explaining", progress=90, message="Generating business insights...")

            # Use hold-out test set from trainer (stored on instance, not in dict for JSON safety)
            X_test, y_test = getattr(trainer, '_test_set', (X, y))

            # Feature Importance (permutation-based)
            feature_imp = ExplainabilityService.calculate_feature_importance(
                trainer.best_model, X_test, y_test, fe_meta["feature_names"]
            )

            # Target Distribution
            dist_plot = ExplainabilityService.calculate_distribution(df, target)

            # Confusion Matrix (classification only)  now returns {labels, matrix}
            confusion = {"labels": [], "matrix": []}
            if plan["task_type"] == "classification":
                y_pred_test = trainer.best_model.predict(X_test)
                confusion = ExplainabilityService.calculate_confusion_matrix(y_test, y_pred_test)

            # Executive Narrative (LLM-based)
            narrator = NarrativeGenerator(self.llm_client)
            metrics_for_narrative = {
                "test_metrics": train_results.get("test_metrics", {}),
                "validation_scores": train_results.get("validation_scores", {}),
                "data_analysis": train_results.get("data_analysis", {}),
                "best_model_name": train_results.get("best_model_name", "Unknown"),
                "algorithms_tried": train_results.get("algorithms_tried", 0)
            }

            executive_summary = narrator.generate_executive_summary(
                plan=plan,
                metrics=metrics_for_narrative,
                feature_importance=feature_imp,
                profile=profile,
                strategic_hint=strategic_hint,
                schema_description=schema_desc
            )

            # ========== BUILD FINAL RESULT ==========
            final_result = {
                "job_id": job_id,
                "metrics": train_results,
                "target": target,
                "recommended_features": fe_meta["feature_names"],
                "input_features": feature_cols,
                "narrative": executive_summary,
                "data_quality": profile.get("data_quality", {}),
                "charts": {
                    "feature_importance": feature_imp,
                    "distribution": dist_plot,
                    "confusion_matrix": confusion
                }
            }

            JobStore.update_job(job_id, status="completed", progress=100,
                                message="Analysis complete!", result=final_result)
            logger.info(f"Pipeline [{job_id[:8]}]: Completed  Best: {train_results.get('best_model_name')}")

        except Exception as e:
            traceback.print_exc()
            logger.error(f"Pipeline [{job_id[:8]}] FAILED: {e}")
            JobStore.update_job(job_id, status="failed", error=str(e), message="Pipeline failed")
