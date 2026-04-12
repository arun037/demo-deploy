from backend.core.llm_client import LLMClient
from backend.config import Config
import json
from typing import Dict, Any, List

class InsightPlanner:
    """
    Virtual Data Scientist Agent. 
    Analyzes schema, data profile, and quality to propose a high-value predictive task.
    """
    
    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client

    def plan_insight(self, table_name: str, schema_description: str, data_profile: Dict[str, Any], strategic_hint: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Stage 2: The Data Scientist.
        Generates a semantic training recipe, guided by Stage 1 Strategy
        and enriched with data quality + target recommendations.
        """
        
        hint_text = ""
        if strategic_hint:
            hint_text = f"""
            STRATEGIC GUIDANCE FROM STAGE 1:
            - Proposed Goal: {strategic_hint.get('strategy')}
            - Suggested Target: {strategic_hint.get('discovery_target')}
            Use this guidance to prioritize your modeling choices.
            """

        # Build target recommendation context from enriched profiler
        target_recs = data_profile.get("target_recommendations", {})
        rec_text = ""
        if target_recs:
            cls_recs = target_recs.get("classification", [])
            reg_recs = target_recs.get("regression", [])
            if cls_recs:
                rec_text += "\nCLASSIFICATION TARGETS DETECTED:\n"
                for r in cls_recs[:3]:
                    rec_text += f"  - {r['column']}: {r['reason']}\n"
            if reg_recs:
                rec_text += "\nREGRESSION TARGETS DETECTED:\n"
                for r in reg_recs[:3]:
                    rec_text += f"  - {r['column']}: {r['reason']} (skew={r.get('skew', 'N/A')})\n"

        # Data quality context
        quality = data_profile.get("data_quality", {})
        quality_text = ""
        if quality:
            quality_text = f"\nDATA QUALITY: Score={quality.get('score', '?')}/100"
            if quality.get("constant_columns"):
                quality_text += f", Constant columns (EXCLUDE these): {quality['constant_columns']}"
            if quality.get("id_like_columns"):
                quality_text += f", ID-like columns (EXCLUDE these): {quality['id_like_columns']}"

        # Top correlations context
        correlations = data_profile.get("top_correlations", [])
        corr_text = ""
        if correlations:
            corr_text = "\nTOP CORRELATIONS:\n"
            for c in correlations[:5]:
                corr_text += f"  - {c['feature_1']}  {c['feature_2']}: {c['correlation']}\n"

        system_prompt = f"""You are a Lead Data Scientist.
        Your goal is to discover ONE high-value predictive modeling task for the given dataset, strictly following the provided Business Logic.
        {hint_text}
        
        STRICT OPERATING RULES:
        1. NO EXTERNAL ASSUMPTIONS: Do not assume the system type. Use only the provided logic.
        2. BUSINESS LOGIC IS TRUTH: The "Business Logic" provided below is your definitive source of truth. 
        3. DATA-DRIVEN VALIDATION: Use the "Data Profile" to ensure the logic and statistics align.
        4. EXCLUDE constant columns and ID-like columns from features.
        5. Prefer targets with higher business value and sufficient data quality.
        
        INPUTS:
        1. Table Name: {table_name}
        2. Business Logic (Schema Context): {schema_description}
        3. Data Profile (Statistical Summary): JSON provided in user query.
        
        YOUR REASONING PROCESS:
        1. Review the TARGET RECOMMENDATIONS from the data profiler  these are statistically validated candidates.
        2. Cross-reference with the "Business Logic" to pick the most valuable target.
        3. Identify "Features" (drivers) that are logically related according to the schema.
        4. Exclude ID columns, constant columns, and any potential leakage.
        
        OUTPUT FORMAT:
        Return ONLY valid JSON with this structure:
        {{
            "task_name": "Predicting [Target] based on [Drivers]",
            "task_description": "We will train a model to forecast...",
            "task_type": "regression" OR "classification",
            "target_column": "exact_column_name",
            "hypothesis": "I suspect that [Feature X] will negatively correlate with [Target] because [Business Reason]",
            "feature_columns": ["col1", "col2", ...],
            "reasoning": "I chose this target because..."
        }}
        """
        # We limit the profile size to avoid context window issues, focusing on column stats
        profile_snippet = json.dumps(data_profile.get("columns", {}), default=str)[:10000]
        
        user_query = f"""
        Here is the Data Profile for table '{table_name}':
        {profile_snippet}
        {rec_text}
        {quality_text}
        {corr_text}
        
        Propose the best predictive task.
        """
        
        response = self.llm.call_agent(
            system_prompt=system_prompt,
            user_query=user_query,
            model=Config.INSIGHT_MODEL,
            agent_name="InsightPlanner",
            temperature=0.1 # low temp for valid JSON
        )
        
        try:
            # Clean markdown code blocks if present
            clean_response = response.replace("```json", "").replace("```", "").strip()
            return json.loads(clean_response)
        except json.JSONDecodeError:
            # Fallback simple plan if LLM fails (should be rare with low temp)
            return {
                "error": "Failed to parse AI plan", 
                "raw_response": response
            }

    def discover_opportunities(self, schema: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Stage 1: The Consultant.
        Scans only schema (tables/columns) to find the best business opportunities.
        """
        system_prompt = """You are an Expert Strategic Analyst.
        Your goal is to analyze the provided DATABASE SCHEMA and BUSINESS LOGIC to identify the TOP 3 modeling opportunities.
        
        STRICT OPERATING RULES:
        1. NO EXTERNAL ASSUMPTIONS: Do not assume this is a CRM, ERP, or any other generic system. 
        2. SCHEMA-ONLY: You must ONLY use tables and columns listed in the input. 
        3. PURPOSE-DRIVEN: Use the "Purpose" and "Column Descriptions" provided to understand the domain. If a table says its purpose is "Franchise Contracts", treat it as such.
        4. BUSINESS IMPACT: Focus on predicting outcomes that directly follow from the "Purpose" fields (e.g., predicting status in 'contracts' to manage agreement lifecycles).
        
        OUTPUT FORMAT:
        Return ONLY valid JSON list:
        [
            {
                "table_name": "exact_name_from_input",
                "discovery_target": "exact_column_from_input", 
                "task_type": "regression" OR "classification",
                "strategy": "Strategic explanation based on the 'Purpose' description of why this is valuable."
            },
            ...
        ]
        """
        
        # summarizing schema with purpose/descriptions for richer context
        schema_summary = ""
        for table in schema:
            schema_summary += f"### TABLE: {table.get('table_name')}\n"
            schema_summary += f"BUSINESS LOGIC (PURPOSE): {table.get('purpose', 'N/A')}\n"
            schema_summary += f"COLUMNS: {', '.join(table.get('columns', []))}\n"
            if "column_descriptions" in table:
                schema_summary += f"FIELD DATA LOGIC: {'; '.join(table.get('column_descriptions', []))}\n"
            schema_summary += "---\n"

        user_query = f"""
        Analyze this SCHEMA and BUSINESS LOGIC:
        {schema_summary[:20000]}
        
        Propose the top 3 modeling opportunities. MANDATORY: Stick strictly to the names and logic provided above.
        """
        
        response = self.llm.call_agent(
            system_prompt=system_prompt,
            user_query=user_query,
            model=Config.INSIGHT_MODEL,
            agent_name="InsightPlanner_Consultant",
            temperature=0.1
        )
        
        try:
            clean_response = response.replace("```json", "").replace("```", "").strip()
            return json.loads(clean_response)
        except:
             return []
