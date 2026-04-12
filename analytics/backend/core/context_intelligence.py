"""
Context Intelligence Module

Intelligently extracts and manages conversation context.
Prevents redundant clarification questions by understanding what's already specified.
"""

import re
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class ContextIntelligence:
    """
    Intelligently extracts context from queries and conversation history.
    Identifies what's already specified to avoid redundant questions.
    """
    
    def __init__(self):
        """Initialize Context Intelligence."""
        # Time-related keywords
        self.time_keywords = {
            'last_n_days': r'last (\d+) days?',
            'last_n_months': r'last (\d+) months?',
            'last_n_years': r'last (\d+) years?',
            'this_month': r'this month',
            'this_year': r'this year',
            'last_month': r'last month',
            'last_year': r'last year',
            'today': r'today',
            'yesterday': r'yesterday',
            'specific_month': r'(january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{4}',
            'year': r'\b(20\d{2})\b',
            'ytd': r'year.to.date|ytd',
            'mtd': r'month.to.date|mtd',
            'q1': r'q1|first quarter',
            'q2': r'q2|second quarter',
            'q3': r'q3|third quarter',
            'q4': r'q4|fourth quarter'
        }
        
        # Status/filter keywords
        self.status_keywords = ['active', 'inactive', 'pending', 'completed', 'cancelled', 'approved', 'rejected']
        
        # Aggregation keywords
        self.aggregation_keywords = ['total', 'sum', 'count', 'average', 'avg', 'max', 'min', 'top', 'bottom']
        
        # Grouping keywords
        self.grouping_keywords = ['by', 'per', 'each', 'grouped by', 'broken down by', 'split by']
    
    def extract_query_context(self, query: str, chat_history: List[Dict] = None) -> Dict[str, Any]:
        """
        Extract what's already specified in the query and recent conversation.
        
        Args:
            query: Current user query
            chat_history: Recent conversation messages
            
        Returns:
            Dictionary with extracted context
        """
        query_lower = query.lower()
        
        # Combine query with recent user messages for context
        combined_text = query_lower
        if chat_history:
            # Get last 3 user messages
            recent_user_messages = [
                msg.get('content', '').lower() 
                for msg in chat_history[-6:] 
                if msg.get('role') == 'user'
            ][-3:]
            combined_text = ' '.join(recent_user_messages + [query_lower])
        
        context = {
            'time_scope': self._extract_time_scope(combined_text),
            'filters': self._extract_filters(combined_text),
            'entities': self._extract_entities(query_lower),
            'metrics': self._extract_metrics(query_lower),
            'groupings': self._extract_groupings(query_lower),
            'has_aggregation': self._has_aggregation(query_lower),
            'is_comparison': self._is_comparison(query_lower)
        }
        
        logger.info(f"Extracted context: {context}")
        return context
    
    def _extract_time_scope(self, text: str) -> Optional[str]:
        """Extract time scope from text."""
        for time_type, pattern in self.time_keywords.items():
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(0)
        return None
    
    def _extract_filters(self, text: str) -> List[str]:
        """Extract filter conditions from text."""
        filters = []
        
        # Status filters
        for status in self.status_keywords:
            if status in text:
                filters.append(f"status:{status}")
        
        # Site/location filters
        site_match = re.search(r'site\s+(\d+|[a-z]+)', text, re.IGNORECASE)
        if site_match:
            filters.append(f"site:{site_match.group(1)}")
        
        # Region filters
        region_match = re.search(r'region\s+([a-z\s]+)', text, re.IGNORECASE)
        if region_match:
            filters.append(f"region:{region_match.group(1)}")
        
        # Category filters
        category_match = re.search(r'category\s+([a-z\s]+)', text, re.IGNORECASE)
        if category_match:
            filters.append(f"category:{category_match.group(1)}")
        
        return filters
    
    def _extract_entities(self, text: str) -> List[str]:
        """Extract business entities mentioned."""
        entities = []
        
        # Common business entities
        entity_patterns = {
            'sales': r'\b(sales?|revenue|orders?)\b',
            'customers': r'\b(customers?|clients?|buyers?)\b',
            'products': r'\b(products?|items?|skus?)\b',
            'leads': r'\b(leads?|inquiries?|prospects?)\b',
            'sites': r'\b(sites?|locations?|stores?)\b',
            'regions': r'\b(regions?|territories?|areas?)\b',
            'categories': r'\b(categor(y|ies)|types?)\b'
        }
        
        for entity, pattern in entity_patterns.items():
            if re.search(pattern, text, re.IGNORECASE):
                entities.append(entity)
        
        return entities
    
    def _extract_metrics(self, text: str) -> List[str]:
        """Extract metrics/aggregations mentioned."""
        metrics = []
        
        for keyword in self.aggregation_keywords:
            if keyword in text:
                metrics.append(keyword)
        
        return metrics
    
    def _extract_groupings(self, text: str) -> List[str]:
        """Extract grouping dimensions."""
        groupings = []
        
        # Look for "by X" patterns
        by_matches = re.findall(r'by\s+([a-z_]+)', text, re.IGNORECASE)
        groupings.extend(by_matches)
        
        # Look for "per X" patterns
        per_matches = re.findall(r'per\s+([a-z_]+)', text, re.IGNORECASE)
        groupings.extend(per_matches)
        
        return groupings
    
    def _has_aggregation(self, text: str) -> bool:
        """Check if query involves aggregation."""
        return any(keyword in text for keyword in self.aggregation_keywords)
    
    def _is_comparison(self, text: str) -> bool:
        """Check if query is a comparison."""
        comparison_keywords = ['compare', 'vs', 'versus', 'difference', 'between']
        return any(keyword in text for keyword in comparison_keywords)
    
    def get_missing_context(self, extracted_context: Dict[str, Any], intent: str) -> List[str]:
        """
        Identify what critical information is missing.
        
        Args:
            extracted_context: Context extracted from query
            intent: Query intent
            
        Returns:
            List of missing context items
        """
        missing = []
        
        # Time-sensitive queries need time scope
        time_sensitive_intents = ['RANKING', 'TRENDS', 'AGGREGATION', 'COMPARISON']
        if intent in time_sensitive_intents and not extracted_context.get('time_scope'):
            missing.append('time_scope')
        
        # Aggregation queries might need grouping
        if extracted_context.get('has_aggregation') and not extracted_context.get('groupings'):
            missing.append('grouping')
        
        # Comparison queries need what to compare
        if extracted_context.get('is_comparison') and len(extracted_context.get('entities', [])) < 2:
            missing.append('comparison_entities')
        
        return missing
    
    def build_context_summary(self, extracted_context: Dict[str, Any]) -> str:
        """
        Build human-readable summary of extracted context.
        
        Args:
            extracted_context: Extracted context dictionary
            
        Returns:
            Formatted context summary
        """
        summary_parts = []
        
        if extracted_context.get('time_scope'):
            summary_parts.append(f"Time: {extracted_context['time_scope']}")
        
        if extracted_context.get('filters'):
            summary_parts.append(f"Filters: {', '.join(extracted_context['filters'])}")
        
        if extracted_context.get('groupings'):
            summary_parts.append(f"Grouped by: {', '.join(extracted_context['groupings'])}")
        
        if extracted_context.get('entities'):
            summary_parts.append(f"Entities: {', '.join(extracted_context['entities'])}")
        
        return ' | '.join(summary_parts) if summary_parts else 'No context extracted'
