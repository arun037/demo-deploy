"""
RAG Retriever using EmbeddingRetriever
Retrieves relevant schema context using the same embedding system as chat.
"""

from typing import List, Dict, Any
from backend.core.logger import logger


class RAGRetriever:
    """Retrieves relevant tables for each insight category using EmbeddingRetriever"""
    
    def __init__(self, embedding_retriever, llm_client=None):
        """
        Initialize RAG retriever with shared EmbeddingRetriever instance
        
        Args:
            embedding_retriever: Instance of EmbeddingRetriever (same as used by chat)
            llm_client: LLM client (optional, for future use)
        """
        self.embedding_retriever = embedding_retriever
        self.llm_client = llm_client
        self.dynamic_queries = None  # Will be set by caller for AI-generated queries
        logger.info("RAGRetriever: Initialized with shared EmbeddingRetriever")
    
    def set_dynamic_queries(self, queries: dict):
        """
        Set AI-generated dynamic queries for each category
        
        Args:
            queries: Dict mapping category -> optimized query string
                    e.g. {"kpi": "franchise contract revenue...", "trend": "..."}
        """
        self.dynamic_queries = queries
        logger.info(f"S Using AI-generated dynamic queries for {len(queries)} categories")
    
    def retrieve_for_category(self, category: str, top_k: int = 10) -> List[Dict]:
        """
        Retrieve relevant tables for insight category
        
        Categories:
        - kpi: Total spend, order counts, inventory value
        - trend: Time-series analysis, growth rates
        - distribution: Top vendors, categories, departments
        - alert: Low stock, pending items, overdue
        """
        # Use dynamic queries if available, otherwise fallback to static
        if self.dynamic_queries and category in self.dynamic_queries:
            query_text = self.dynamic_queries[category]
            logger.info(f" Using AI-generated query for {category}: {query_text[:60]}...")
        else:
            # Fallback to static queries
            static_queries = {
                "kpi": "financial metrics totals counts aggregates summary statistics monetary amounts quantities revenue cost investment",
                "trend": "date fields time series monthly quarterly yearly temporal analysis growth changes trends over time",
                "distribution": "categories groups rankings top performers distributions breakdowns segments",
                "alert": "status pending low stock thresholds warnings critical items overdue issues problems"
            }
            query_text = static_queries.get(category, "")
            logger.warning(f"[WARN] Using static fallback query for {category}")
        
        try:
            # Use EmbeddingRetriever to get relevant tables
            results = self.embedding_retriever.retrieve_relevant_tables(
                user_query=query_text,
                max_tables=top_k
            )
            
            # Convert EmbeddingRetriever format to RAG format
            retrieved = []
            for result in results:
                retrieved.append({
                    "table_name": result.get("table", ""),
                    "database": result.get("database", ""),
                    "text": result.get("description", ""),
                    "columns": result.get("columns", []),
                    "foreign_keys": result.get("foreign_keys", []),
                    "similarity": result.get("similarity_score", 0),
                    # Dashboard-specific fields (set defaults)
                    "is_fact": False,  # Can be enhanced later with graph analysis
                    "priority_score": result.get("similarity_score", 0)
                })
            
            logger.info(f"Retrieved {len(retrieved)} tables for category '{category}'")
            return retrieved[:top_k]
            
        except Exception as e:
            logger.error(f"Failed to retrieve from EmbeddingRetriever: {e}")
            return []
