"""
Enhanced Context Manager

Provides unified context handling for all queries.
Replaces the need for separate FOLLOW_UP classification.
"""

import logging
from typing import Dict, List, Optional, Any
from backend.core.session_manager import SessionManager
from backend.core.context_intelligence import ContextIntelligence

logger = logging.getLogger(__name__)


class EnhancedContextManager:
    """
    Manages comprehensive conversation context for intelligent query processing.
    
    Provides full context to all agents, enabling:
    - Dynamic schema reuse
    - Conversation continuity
    - Meta-question handling
    - Natural conversation flow
    """
    
    def __init__(self, session_manager: SessionManager):
        """
        Initialize Enhanced Context Manager.
        
        Args:
            session_manager: Session manager for accessing conversation history
        """
        self.session_manager = session_manager
        self.context_intelligence = ContextIntelligence()  # NEW: Intelligent context extraction
        self.context_cache = {}  # Future: cache for performance
    
    def get_full_context(self, session_id: str, current_query: str) -> Dict[str, Any]:
        """
        Build comprehensive context for any query.
        
        Args:
            session_id: Current session ID
            current_query: Current user query
            
        Returns:
            Dictionary with full conversation context including:
            - conversation_history: Recent messages
            - previous_query: Last user query
            - previous_sql: Last generated SQL
            - previous_schema: Last schema context
            - previous_result_summary: Summary of last results
            - last_error: Last error if any
            - active_filters: Inferred active filters
            - conversation_topic: Current topic
        """
        
        # Default empty context
        empty_context = {
            'conversation_history': [],
            'previous_query': None,
            'previous_sql': None,
            'previous_schema': None,
            'previous_result_summary': None,
            'previous_tables': [],
            'last_error': None,
            'active_filters': [],
            'conversation_topic': None,
            'has_previous_context': False
        }
        
        if not session_id:
            return empty_context
        
        # Load session
        session = self.session_manager.get_session(session_id)
        if not session or not session.get('messages'):
            return empty_context
        
        messages = session['messages']
        
        # Build context with FULL PIPELINE AWARENESS
        # Use 12 raw messages: a single full exchange with clarification takes ~4 messages
        # (user question + clarification Q + clarification A + final answer),
        # so 12 messages covers ~3 complete exchanges reliably.
        HISTORY_WINDOW = 12
        context = {
            # Conversation
            'conversation_history': messages[-HISTORY_WINDOW:],
            'previous_query': None,
            'conversation_topic': self._extract_topic(messages),
            'has_previous_context': False,
            
            # Schema & Tables
            'previous_schema': None,
            'previous_tables': [],
            'schema_hash': None,
            
            # SQL & Execution
            'previous_sql': None,
            'previous_plan': None,
            'previous_intent': None,
            'previous_result_summary': None,
            
            # Pipeline Workflow (NEW - tracks agent decisions)
            'pipeline_context': {
                'clarification_asked': False,
                'clarification_questions': [],
                'clarification_for_query': None,  # Which query had clarification
                'clarification_for_topic': None,  # Which topic had clarification
                'planning_steps': None,
                'sql_validation_attempts': 0,
                'sql_fixes_applied': [],
                'execution_successful': None,
                'insights_generated': False
            },
            
            # Error Tracking
            'last_error': None,
            'error_history': [],
            # Filters & Context (NEW - intelligent extraction)
            'active_filters': [],
            'active_groupings': [],
            
            # NEW: Extracted context from query & history
            'extracted_context': self.context_intelligence.extract_query_context(
                current_query,
                messages[-HISTORY_WINDOW:]  # Match the expanded history window
            )
        }
        
        # Find last assistant message WITH responseMeta (actual query result, not clarification)
        # Also find the very last assistant message for error checking
        last_assistant_with_meta = None
        last_assistant_msg = None
        last_user_msg = None
        
        for msg in reversed(messages):
            if msg.get('role') == 'assistant':
                if not last_assistant_msg:
                    last_assistant_msg = msg
                # Look specifically for the last message with responseMeta (real query result)
                if not last_assistant_with_meta and msg.get('responseMeta'):
                    last_assistant_with_meta = msg
            elif msg.get('role') == 'user' and not last_user_msg:
                last_user_msg = msg
            
            # Stop once we have both  
            if last_assistant_with_meta and last_user_msg:
                break
        
        # Extract context from last assistant message with actual query results
        # Use last_assistant_with_meta (has responseMeta) for SQL/schema/table context
        # Fall back to last_assistant_msg for basic context
        context_source = last_assistant_with_meta or last_assistant_msg
        
        if context_source:
            context['has_previous_context'] = True
            
            # Extract from responseMeta (ENHANCED - capture full pipeline)
            if context_source.get('responseMeta'):
                meta = context_source['responseMeta']
                
                # Core data
                context['previous_sql'] = meta.get('generatedSql')
                context['previous_schema'] = meta.get('schemaContext')
                context['previous_tables'] = meta.get('tablesUsed', [])
                context['previous_plan'] = meta.get('plan')
                context['previous_intent'] = meta.get('intent')
                context['schema_hash'] = meta.get('schemaHash')
                
                # Results
                context['previous_result_summary'] = {
                    'row_count': meta.get('rowCount', 0),
                    'execution_time_ms': meta.get('executionTimeMs', 0),
                    'columns': meta.get('columns', [])
                }
                
                # Pipeline workflow tracking (NEW)
                pipeline = context['pipeline_context']
                
                # Clarification tracking (QUERY-SPECIFIC)
                # Only mark as asked if it was for the SAME query/topic
                if meta.get('clarificationAsked'):
                    pipeline['clarification_asked'] = True
                    pipeline['clarification_questions'] = meta.get('clarificationQuestions', [])
                    pipeline['clarification_for_query'] = context.get('previous_query')  # Track which query
                    pipeline['clarification_for_topic'] = context.get('conversation_topic')  # Track topic
                
                # Planning
                if meta.get('plan'):
                    pipeline['planning_steps'] = meta.get('plan')
                
                # SQL validation & fixes
                if meta.get('validationAttempts'):
                    pipeline['sql_validation_attempts'] = meta.get('validationAttempts', 0)
                if meta.get('sqlFixes'):
                    pipeline['sql_fixes_applied'] = meta.get('sqlFixes', [])
                
                # Execution status
                pipeline['execution_successful'] = meta.get('executionSuccessful', True)
                
                # Insights
                if meta.get('insightsGenerated'):
                    pipeline['insights_generated'] = True
                
                # Infer active filters from SQL (intelligent extraction)
                if context['previous_sql']:
                    context['active_filters'] = self._extract_filters_from_sql(context['previous_sql'])
                    context['active_groupings'] = self._extract_groupings_from_sql(context['previous_sql'])
            
            # Check for errors (use the most recent assistant message for this)
            if last_assistant_msg and last_assistant_msg.get('error'):
                error_info = {
                    'message': last_assistant_msg['error'],
                    'query': last_user_msg.get('content') if last_user_msg else None,
                    'sql': context.get('previous_sql'),
                    'timestamp': last_assistant_msg.get('timestamp')
                }
                context['last_error'] = error_info
                context['error_history'].append(error_info)
        
        # Get previous user query
        if last_user_msg:
            context['previous_query'] = last_user_msg.get('content')
        
        logger.info(f"S Built intelligent context: has_previous={context['has_previous_context']}, "
                   f"tables={context['previous_tables']}, "
                   f"topic={context['conversation_topic']}, "
                   f"clarification_asked={context['pipeline_context']['clarification_asked']}, "
                   f"sql_fixes={len(context['pipeline_context']['sql_fixes_applied'])}")
        
        return context
    
    def _extract_topic(self, messages: List[Dict]) -> Optional[str]:
        """
        Extract conversation topic from messages.
        
        Simple heuristic: look for common entities/tables mentioned.
        Future: Use LLM for better topic extraction.
        
        Args:
            messages: List of conversation messages
            
        Returns:
            Topic string or None
        """
        if not messages:
            return None
        
        # Simple heuristic: get most recent data query topic
        for msg in reversed(messages):
            if msg.get('role') == 'assistant' and msg.get('responseMeta'):
                tables = msg['responseMeta'].get('tablesUsed', [])
                if tables:
                    # Return first table as topic (simplified)
                    return tables[0].split('.')[-1] if '.' in tables[0] else tables[0]
        
        return None
    
    def should_fetch_schema(self, user_query: str, context: Dict[str, Any], intent: str, is_follow_up: bool = False) -> bool:
        """
        Dynamically decide if we need to fetch fresh schema.
        Reuses previous schema if the LLM router flagged it as a follow up, or if
        it looks like a short conversational continuation.
        
        Args:
            user_query: Current user query
            context: Full context from get_full_context()
            intent: Classified intent
            is_follow_up: Boolean flag from Router indicating if this is a follow up
            
        Returns:
            True if should fetch schema, False if should reuse from context
        """
        # META_QUESTION doesn't need schema
        if intent == "META_QUESTION":
            return False
            
        # No previous context? Must fetch
        if not context.get('has_previous_context') or not context.get('previous_schema'):
            logger.info(" Fetching schema: No previous context")
            return True
            
        query_lower = user_query.lower().strip()
        
        # If the LLM router explicitly classified this as a follow-up to the previous query, reuse schema
        if is_follow_up:
            logger.info(" Reusing schema: LLM classified query as a follow-up")
            return False
            
        # Fallback: Short queries (<= 5 words) are highly likely to be follow-ups/refinements
        word_count = len(query_lower.split())
        if word_count <= 5 and context.get('conversation_topic'):
             logger.info(f" Reusing schema: Short query ({word_count} words) with existing topic context")
             return False

        # Default: fetch fresh schema for every new query
        logger.info(" Fetching schema: Query appears to be new analysis  fetching fresh")
        return True
    
    def _extract_filters_from_sql(self, sql: str) -> List[str]:
        """
        Extract active filters from SQL WHERE clause.
        
        Args:
            sql: SQL query string
            
        Returns:
            List of filter descriptions
        """
        if not sql:
            return []
        
        filters = []
        sql_upper = sql.upper()
        
        # Find WHERE clause
        if 'WHERE' in sql_upper:
            try:
                where_start = sql_upper.index('WHERE') + 5
                where_end = len(sql)
                
                # Find end of WHERE clause (GROUP BY, ORDER BY, LIMIT, etc.)
                for keyword in ['GROUP BY', 'ORDER BY', 'LIMIT', 'HAVING']:
                    if keyword in sql_upper[where_start:]:
                        where_end = min(where_end, sql_upper.index(keyword, where_start))
                
                where_clause = sql[where_start:where_end].strip()
                
                # Simple extraction: split by AND/OR
                conditions = where_clause.replace(' OR ', ' AND ').split(' AND ')
                for condition in conditions:
                    condition = condition.strip()
                    if condition and len(condition) > 3:
                        filters.append(condition[:100])  # Limit length
            except Exception as e:
                logger.debug(f"Error extracting filters: {e}")
        
        return filters[:5]  # Limit to 5 most important filters
    
    def _extract_groupings_from_sql(self, sql: str) -> List[str]:
        """
        Extract active GROUP BY columns from SQL.
        
        Args:
            sql: SQL query string
            
        Returns:
            List of grouping column names
        """
        if not sql:
            return []
        
        groupings = []
        sql_upper = sql.upper()
        
        # Find GROUP BY clause
        if 'GROUP BY' in sql_upper:
            try:
                group_start = sql_upper.index('GROUP BY') + 8
                group_end = len(sql)
                
                # Find end of GROUP BY clause
                for keyword in ['ORDER BY', 'LIMIT', 'HAVING']:
                    if keyword in sql_upper[group_start:]:
                        group_end = min(group_end, sql_upper.index(keyword, group_start))
                
                group_clause = sql[group_start:group_end].strip()
                
                # Extract column names
                columns = group_clause.split(',')
                for col in columns:
                    col = col.strip()
                    if col and len(col) > 0:
                        # Remove table prefixes (database.table.column -> column)
                        if '.' in col:
                            col = col.split('.')[-1]
                        groupings.append(col[:50])  # Limit length
            except Exception as e:
                logger.debug(f"Error extracting groupings: {e}")
        
        return groupings[:5]  # Limit to 5 grouping columns
    
    def is_clarification_relevant(self, current_query: str, full_context: Dict[str, Any]) -> bool:
        """
        Determine if previous clarification is relevant to current query.
        
        Args:
            current_query: Current user query
            full_context: Full context from get_full_context()
            
        Returns:
            True if previous clarification should be considered, False if new clarification may be needed
        """
        pipeline = full_context.get('pipeline_context', {})
        
        # No previous clarification? Not relevant
        if not pipeline.get('clarification_asked'):
            return False
        
        # Get what the clarification was for
        clarification_query = pipeline.get('clarification_for_query')
        clarification_topic = pipeline.get('clarification_for_topic')
        
        if not clarification_query:
            # Old format, assume not relevant for safety
            return False
        
        # Check if current query is similar to the one that had clarification
        current_lower = current_query.lower().strip()
        previous_lower = clarification_query.lower().strip()
        
        # Simple heuristics for query similarity
        # 1. Very short refinement (likely same context)
        if len(current_query.split()) < 5:
            # Check if it's a refinement keyword
            refinement_keywords = ['only', 'just', 'exclude', 'without', 'above', 'below', 'more', 'less']
            if any(kw in current_lower for kw in refinement_keywords):
                logger.info("S Previous clarification relevant: Short refinement query")
                return True
        
        # 2. Same topic continuation
        current_topic = full_context.get('conversation_topic')
        if current_topic and clarification_topic and current_topic == clarification_topic:
            # Same topic, check if query is similar enough
            # Simple word overlap check
            current_words = set(current_lower.split())
            previous_words = set(previous_lower.split())
            common_words = current_words & previous_words
            
            if len(common_words) >= 2:  # At least 2 words in common
                logger.info(f"S Previous clarification relevant: Same topic ({current_topic}) with word overlap")
                return True
        
        # 3. Completely different query - clarification NOT relevant
        logger.info("F Previous clarification NOT relevant: New query/topic")
        return False
    
    def get_messages(self, session_id: str, last_n: int = 10) -> List[Dict[str, Any]]:
        """
        Get recent chat messages from session for context-aware chat handling.
        
        This is a convenience method that delegates to session_manager.get_session_context()
        for retrieval of conversation history for chat responses.
        
        Args:
            session_id: Session ID
            last_n: Number of recent messages to return (default 10)
            
        Returns:
            List of message dicts with 'role' and 'content' keys
        """
        if not session_id:
            return []
        
        try:
            return self.session_manager.get_session_context(session_id, last_n=last_n)
        except Exception as e:
            logger.warning(f"Error retrieving messages from session {session_id}: {e}")
            return []
