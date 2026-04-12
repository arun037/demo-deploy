
from backend.core.llm_client import LLMClient
from backend.config import Config
from typing import Dict, Any, List
import json

class NarrativeGenerator:
    """
    Synthesizes technical metrics into a business narrative.
    Now enriched with algorithm competition data and data analysis intelligence.
    """
    
    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client

    def generate_executive_summary(self, 
                                   plan: Dict[str, Any], 
                                   metrics: Dict[str, Any], 
                                   feature_importance: List[Dict[str, Any]],
                                   profile: Dict[str, Any],
                                   strategic_hint: Dict[str, Any] = None,
                                   schema_description: str = None) -> str:
        """
        Writes a CEO-level summary linking model results to business value.
        Includes algorithm selection rationale and data quality context.
        """
        
        system_prompt = """You are a Senior Strategic Analytics Officer.
        Your goal is to explain a predictive model's results to a CEO, linking technical performance back to the provided BUSINESS LOGIC.
        
        STRICT RULES:
        1. NO GENERIC ASSUMPTIONS: Do not assume system type. Use only the provided Business Logic and Schema Context.
        2. BUSINESS LOGIC IS TRUTH: The "Definitive Business Logic" provided below is your single source of truth for what this table represents.
        
        NARRATIVE STRUCTURE:
        1. The Strategic Recap: Why this analysis was performed according to the Stage 1 Strategy.
        2. The Core Discovery: What the model found across the data drivers.
        3. Algorithm Intelligence: Why a specific algorithm was chosen (briefly mention the competition).
        4. Business Guidance: How this impacts the specific business area described in the Logic.
        5. Performance Confidence: Explain accuracy/R2 in layman's terms.
        
        CONSTRAINTS:
        - Concise (max 6-7 sentences).
        - Focus on strategic value (risk mitigation, efficiency, growth).
        - Mention the winning algorithm by name.
        """
        
        # Prepare context
        strategy = strategic_hint.get("strategy", "General business optimization.") if strategic_hint else "General business optimization."
        hypothesis = plan.get("hypothesis", "No initial hypothesis provided.")
        target = plan.get("target_column")
        task = plan.get("task_type")
        
        # Format Top 3 Features
        top_drivers = ", ".join([f"{f['feature']} ({round(f['importance'], 3)})" for f in feature_importance[:3]])
        
        # Format Performance
        perf_text = ""
        test_metrics = metrics.get("test_metrics", {})
        if test_metrics:
            if "accuracy" in test_metrics:
                perf_text = f"Accuracy: {round(test_metrics['accuracy']*100, 1)}%"
                if "f1" in test_metrics:
                    perf_text += f", F1: {round(test_metrics['f1']*100, 1)}%"
            elif "r2" in test_metrics:
                perf_text = f"Predictive Power (R): {round(test_metrics['r2']*100, 1)}%"
                if "rmse" in test_metrics:
                    perf_text += f", RMSE: {test_metrics['rmse']}"
        
        # Algorithm competition context
        best_model = metrics.get("best_model_name", "Unknown")
        algorithms_tried = metrics.get("algorithms_tried", 0)
        algo_text = f"{best_model} (selected from {algorithms_tried} candidate algorithms)"
        
        # Data quality context
        data_quality = profile.get("data_quality", {})
        quality_text = f"Data Quality Score: {data_quality.get('score', 'N/A')}/100" if data_quality else ""
        
        # Data analysis context
        data_analysis = metrics.get("data_analysis", {})
        analysis_notes = []
        if data_analysis.get("is_imbalanced"):
            analysis_notes.append(f"Imbalanced classes detected (ratio: {data_analysis.get('imbalance_ratio', 'N/A')})")
        if data_analysis.get("has_strong_linear"):
            analysis_notes.append("Strong linear correlations found in features")
        if data_analysis.get("is_sparse"):
            analysis_notes.append("High sparsity in features")
        analysis_text = "; ".join(analysis_notes) if analysis_notes else "Standard data characteristics"
        
        user_query = f"""
        DEFINITIVE BUSINESS LOGIC (From Schema):
        "{schema_description or 'No logic metadata provided.'}"

        STRATEGIC CONTEXT (STAGE 1):
        "{strategy}"

        MODEL HYPOTHESIS:
        "{hypothesis}"
        
        TARGET: {target} ({task})
        
        WINNING ALGORITHM: {algo_text}
        
        MODEL PERFORMANCE: {perf_text}
        
        TOP DATA DRIVERS: {top_drivers}
        
        DATA INTELLIGENCE: {analysis_text}
        {quality_text}
        
        Write a professional, meaningful executive summary. Include one clear "Strategic Recommendation" at the end.
        """
        
        response = self.llm.call_agent(
            system_prompt=system_prompt,
            user_query=user_query,
            model=Config.INSIGHT_MODEL,
            agent_name="NarrativeGenerator",
            temperature=0.1
        )
        
        return response.strip()
