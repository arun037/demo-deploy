"""
Adaptive Coverage Engine - Intelligent Scaling for Any Schema Size

Automatically adjusts planning strategy based on table count:
- Small schemas (1-20 tables): Comprehensive analysis of all tables
- Medium schemas (21-100 tables): Tiered prioritization with multi-pass
- Large schemas (101-500 tables): Strategic sampling with clustering
- Enterprise schemas (500+ tables): Domain-based partitioning with intelligent selection

Key Features:
- Adaptive table prioritization using multi-factor scoring
- Dynamic insight allocation based on table importance
- Intelligent clustering for related tables
- Domain detection and categorization
"""

import math
from typing import List, Dict, Any, Tuple
from collections import defaultdict
from backend.core.logger import logger


class TableImportanceScorer:
    """
    Multi-dimensional scoring system for table prioritization
    
    Scoring Factors:
    1. Data Volume Score (0-20 points) - Based on row count
    2. Temporal Relevance Score (0-25 points) - Has date columns for filtering
    3. Relational Connectivity Score (0-20 points) - Foreign key relationships
    4. Business Criticality Score (0-25 points) - Domain keywords and patterns
    5. Data Quality Score (0-10 points) - Completeness and freshness
    
    Total: 0-100 points per table
    """
    
    # Business domain keywords by priority
    CRITICAL_KEYWORDS = ['customer', 'order', 'transaction', 'payment', 'invoice', 'contract', 'sale']
    HIGH_PRIORITY_KEYWORDS = ['lead', 'product', 'inventory', 'user', 'account', 'revenue']
    MEDIUM_PRIORITY_KEYWORDS = ['category', 'vendor', 'supplier', 'employee', 'department']
    
    def __init__(self, schema_analysis: Dict, data_exploration: Dict, json_schema: Dict):
        self.schema_analysis = schema_analysis
        self.data_exploration = data_exploration
        self.json_schema = json_schema
    
    def score_table(self, table: str) -> Tuple[float, Dict[str, float]]:
        """
        Calculate comprehensive importance score for a table
        
        Returns: (total_score, score_breakdown)
        """
        breakdown = {}
        
        # Factor 1: Data Volume Score (0-20)
        breakdown['data_volume'] = self._score_data_volume(table)
        
        # Factor 2: Temporal Relevance Score (0-25)
        breakdown['temporal_relevance'] = self._score_temporal_relevance(table)
        
        # Factor 3: Relational Connectivity Score (0-20)
        breakdown['relational_connectivity'] = self._score_relational_connectivity(table)
        
        # Factor 4: Business Criticality Score (0-25)
        breakdown['business_criticality'] = self._score_business_criticality(table)
        
        # Factor 5: Data Quality Score (0-10)
        breakdown['data_quality'] = self._score_data_quality(table)
        
        total_score = sum(breakdown.values())
        
        return total_score, breakdown
    
    def _score_data_volume(self, table: str) -> float:
        """Score based on row count (log scale)"""
        row_count = self.data_exploration.get("row_counts", {}).get(table, 0)
        
        if row_count == 0:
            return 0.0
        
        # Log scale: 1 row = 0, 10 rows = 5, 100 rows = 10, 1M rows = 20
        score = min(math.log10(row_count) * 3.33, 20.0)
        return round(score, 2)
    
    def _score_temporal_relevance(self, table: str) -> float:
        """Score based on date column presence and quality"""
        time_dims = self.schema_analysis.get("time_dimensions", {})
        
        if table not in time_dims:
            return 0.0
        
        date_columns = time_dims[table]
        
        # Base score for having date columns
        score = 15.0
        
        # Bonus for multiple date columns (created, updated, etc.)
        if len(date_columns) > 1:
            score += 5.0
        
        # Bonus for standard naming (create_date, updated_at, etc.)
        standard_names = ['create_date', 'created_at', 'updated_at', 'last_update', 'transaction_date']
        if any(col.lower() in standard_names for col in date_columns):
            score += 5.0
        
        return min(score, 25.0)
    
    def _score_relational_connectivity(self, table: str) -> float:
        """Score based on foreign key relationships"""
        table_key = table.split(".")[-1]
        
        if table_key not in self.json_schema:
            return 0.0
        
        table_def = self.json_schema[table_key]
        fk_count = len(table_def.get("foreign_keys", []))
        
        # Score: 5 points per FK, max 20
        score = min(fk_count * 5.0, 20.0)
        
        return score
    
    def _score_business_criticality(self, table: str) -> float:
        """Score based on business domain keywords"""
        table_lower = table.lower()
        score = 0.0
        
        # Critical keywords: 15 points
        if any(kw in table_lower for kw in self.CRITICAL_KEYWORDS):
            score += 15.0
        # High priority: 10 points
        elif any(kw in table_lower for kw in self.HIGH_PRIORITY_KEYWORDS):
            score += 10.0
        # Medium priority: 5 points
        elif any(kw in table_lower for kw in self.MEDIUM_PRIORITY_KEYWORDS):
            score += 5.0
        
        # Bonus for table purpose description
        table_key = table.split(".")[-1]
        if table_key in self.json_schema:
            purpose = self.json_schema[table_key].get("purpose", "").lower()
            if any(kw in purpose for kw in self.CRITICAL_KEYWORDS):
                score += 10.0
        
        return min(score, 25.0)
    
    def _score_data_quality(self, table: str) -> float:
        """Score based on data quality indicators"""
        # Check if table has data
        row_count = self.data_exploration.get("row_counts", {}).get(table, 0)
        
        if row_count == 0:
            return 0.0
        
        score = 5.0  # Base score for having data
        
        # Bonus for reasonable data volume (not too sparse)
        if row_count > 100:
            score += 5.0
        
        return score


class AdaptiveCoverageEngine:
    """
    Adaptive engine that scales dashboard generation based on schema size
    """
    
    # Schema size thresholds
    SMALL_SCHEMA_THRESHOLD = 20
    MEDIUM_SCHEMA_THRESHOLD = 100
    LARGE_SCHEMA_THRESHOLD = 500
    
    def __init__(self, schema_analysis: Dict, data_exploration: Dict, json_schema: Dict):
        self.schema_analysis = schema_analysis
        self.data_exploration = data_exploration
        self.json_schema = json_schema
        self.scorer = TableImportanceScorer(schema_analysis, data_exploration, json_schema)
    
    def determine_strategy(self, tables_with_data: List[str]) -> Dict[str, Any]:
        """
        Determine optimal coverage strategy based on table count
        
        Returns strategy configuration with:
        - strategy_type: 'comprehensive', 'tiered', 'strategic', or 'partitioned'
        - table_batches: List of table batches to process
        - insight_allocation: How many insights per batch
        - reasoning: Explanation of strategy choice
        """
        table_count = len(tables_with_data)
        
        logger.info(f" Schema Analysis: {table_count} tables with data")
        
        if table_count <= self.SMALL_SCHEMA_THRESHOLD:
            return self._comprehensive_strategy(tables_with_data)
        elif table_count <= self.MEDIUM_SCHEMA_THRESHOLD:
            return self._tiered_strategy(tables_with_data)
        elif table_count <= self.LARGE_SCHEMA_THRESHOLD:
            return self._strategic_sampling_strategy(tables_with_data)
        else:
            return self._domain_partitioned_strategy(tables_with_data)
    
    def _comprehensive_strategy(self, tables: List[str]) -> Dict[str, Any]:
        """
        Small schemas (1-20 tables): Analyze all tables thoroughly
        """
        logger.info(" Strategy: COMPREHENSIVE (analyzing all tables)")
        
        # Score and sort all tables
        scored_tables = self._score_and_rank_tables(tables)
        
        return {
            "strategy_type": "comprehensive",
            "table_batches": [
                {
                    "name": "all_tables",
                    "tables": [t[0] for t in scored_tables],
                    "priority": "high"
                }
            ],
            "insight_allocation": {
                "kpi": 8,
                "trend": 6,
                "distribution": 6,
                "alert": 5
            },
            "reasoning": f"Small schema ({len(tables)} tables) - comprehensive analysis of all tables"
        }
    
    def _tiered_strategy(self, tables: List[str]) -> Dict[str, Any]:
        """
        Medium schemas (21-100 tables): Tiered prioritization with multi-pass
        """
        logger.info(" Strategy: TIERED (multi-pass with prioritization)")
        
        scored_tables = self._score_and_rank_tables(tables)
        
        # Tier 1: Top 25% (critical tables)
        tier1_count = max(10, len(tables) // 4)
        tier1_tables = [t[0] for t in scored_tables[:tier1_count]]
        
        # Tier 2: Next 25% (important tables)
        tier2_count = max(10, len(tables) // 4)
        tier2_tables = [t[0] for t in scored_tables[tier1_count:tier1_count + tier2_count]]
        
        # Tier 3: Remaining high-scoring tables
        tier3_tables = [t[0] for t in scored_tables[tier1_count + tier2_count:] if t[1] > 30]
        
        return {
            "strategy_type": "tiered",
            "table_batches": [
                {
                    "name": "tier1_critical",
                    "tables": tier1_tables,
                    "priority": "critical"
                },
                {
                    "name": "tier2_important",
                    "tables": tier2_tables,
                    "priority": "high"
                },
                {
                    "name": "tier3_supplementary",
                    "tables": tier3_tables,
                    "priority": "medium"
                }
            ],
            "insight_allocation": {
                "tier1_critical": {"kpi": 5, "trend": 4, "distribution": 4, "alert": 3},
                "tier2_important": {"kpi": 3, "trend": 2, "distribution": 2, "alert": 2},
                "tier3_supplementary": {"kpi": 0, "trend": 0, "distribution": 0, "alert": 0}
            },
            "reasoning": f"Medium schema ({len(tables)} tables) - tiered approach with {len(tier1_tables)} critical, {len(tier2_tables)} important, {len(tier3_tables)} supplementary tables"
        }
    
    def _strategic_sampling_strategy(self, tables: List[str]) -> Dict[str, Any]:
        """
        Large schemas (101-500 tables): Strategic sampling with clustering
        """
        logger.info(" Strategy: STRATEGIC SAMPLING (intelligent clustering)")
        
        scored_tables = self._score_and_rank_tables(tables)
        
        # Cluster tables by domain/purpose
        clusters = self._cluster_tables_by_domain(scored_tables)
        
        # Select representatives from each cluster
        batches = []
        for cluster_name, cluster_tables in clusters.items():
            # Take top 5 from each cluster
            top_tables = [t[0] for t in cluster_tables[:5]]
            if top_tables:
                batches.append({
                    "name": f"cluster_{cluster_name}",
                    "tables": top_tables,
                    "priority": "high" if cluster_tables[0][1] > 60 else "medium"
                })
        
        return {
            "strategy_type": "strategic_sampling",
            "table_batches": batches,
            "insight_allocation": {
                "per_cluster": {"kpi": 2, "trend": 1, "distribution": 1, "alert": 1}
            },
            "reasoning": f"Large schema ({len(tables)} tables) - clustered into {len(clusters)} domains, sampling top tables from each"
        }
    
    def _domain_partitioned_strategy(self, tables: List[str]) -> Dict[str, Any]:
        """
        Enterprise schemas (500+ tables): Domain-based partitioning
        """
        logger.info(" Strategy: DOMAIN PARTITIONED (enterprise-scale)")
        
        scored_tables = self._score_and_rank_tables(tables)
        
        # Group by database/schema
        domains = defaultdict(list)
        for table, score in scored_tables:
            if "." in table:
                domain = table.split(".")[0]
            else:
                domain = "default"
            domains[domain].append((table, score))
        
        # Select top tables from each domain
        batches = []
        for domain_name, domain_tables in domains.items():
            # Take top 10 from each domain
            top_tables = [t[0] for t in sorted(domain_tables, key=lambda x: x[1], reverse=True)[:10]]
            if top_tables:
                batches.append({
                    "name": f"domain_{domain_name}",
                    "tables": top_tables,
                    "priority": "high"
                })
        
        return {
            "strategy_type": "domain_partitioned",
            "table_batches": batches,
            "insight_allocation": {
                "per_domain": {"kpi": 2, "trend": 1, "distribution": 1, "alert": 1}
            },
            "reasoning": f"Enterprise schema ({len(tables)} tables) - partitioned into {len(domains)} domains, analyzing top tables from each"
        }
    
    def _score_and_rank_tables(self, tables: List[str]) -> List[Tuple[str, float]]:
        """Score all tables and return sorted by score descending"""
        scored = []
        for table in tables:
            score, breakdown = self.scorer.score_table(table)
            scored.append((table, score))
            logger.debug(f"Table {table}: score={score:.2f}, breakdown={breakdown}")
        
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored
    
    def _cluster_tables_by_domain(self, scored_tables: List[Tuple[str, float]]) -> Dict[str, List[Tuple[str, float]]]:
        """Cluster tables by business domain based on naming patterns"""
        clusters = defaultdict(list)
        
        for table, score in scored_tables:
            table_lower = table.lower()
            
            # Determine cluster based on keywords
            if any(kw in table_lower for kw in ['customer', 'client', 'user', 'account']):
                cluster = 'customer_management'
            elif any(kw in table_lower for kw in ['order', 'purchase', 'sale', 'transaction']):
                cluster = 'sales_transactions'
            elif any(kw in table_lower for kw in ['product', 'item', 'inventory', 'stock']):
                cluster = 'inventory_products'
            elif any(kw in table_lower for kw in ['invoice', 'payment', 'billing', 'revenue']):
                cluster = 'financial'
            elif any(kw in table_lower for kw in ['lead', 'campaign', 'marketing']):
                cluster = 'marketing_leads'
            elif any(kw in table_lower for kw in ['employee', 'staff', 'department', 'hr']):
                cluster = 'human_resources'
            else:
                cluster = 'operational'
            
            clusters[cluster].append((table, score))
        
        return clusters
