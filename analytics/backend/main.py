"""
Production SQL Swarm Backend - Dual Support (Streaming + Legacy)
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel
from typing import Optional, Dict, Any
import time
import json
import hashlib
import asyncio
from datetime import datetime, date
from decimal import Decimal
from cachetools import TTLCache
from hashlib import md5

from backend.config import Config
from backend.core import DatabaseManager, LLMClient, logger
from backend.core.history_manager import HistoryManager
from backend.core.session_manager import SessionManager
from backend.core.enhanced_context_manager import EnhancedContextManager  # NEW: Unified context handling
from backend.agents import (
    Router, EmbeddingRetriever, QueryArchitect, # Replaced Planner, Synthesizer
    Validator, Fixer, ResponseGenerator, SchemaAnalyzer,
    TypeAnalyzer, InsightAnalyst, ClarificationAgent, FollowUpHandler, QueryEnhancer
)

from backend.utils.data_sampler import DataSampler
from backend.utils.date_format_detector import DateFormatDetector
from backend.utils.report_classifier import classify_report_result, extract_metadata, ReportType


from backend.models.report import (
    save_report, list_reports, regenerate_report, execute_report,
    delete_report, rename_report, save_filtered_version, generate_report_name
)
import uuid


# Dashboard module
# Dashboard module
from backend.dashboard import api as dashboard_api
# AI Insights module
from backend.ai_insights import api as insights_api



# Initialize FastAPI app
app = FastAPI(title="SQL Swarm API", version="1.0.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=Config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global instances
db_manager = None
llm_client = None
router_agent = None
retriever_agent = None
architect_agent = None # Replaced planner_agent and synthesizer_agent
validator_agent = None
fixer_agent = None
response_agent = None
schema_analyzer = None
type_analyzer = None
insight_analyst = None
data_sampler = None
date_format_detector = None
clarification_agent = None

history_manager = None
session_manager = None
followup_handler = None
enhanced_context_manager = None  # NEW: Unified context manager
query_enhancer = None            # Pre-retrieval query expansion

# Query result cache for report execution (5 minute TTL)
query_result_cache = TTLCache(maxsize=100, ttl=300)

class CustomJSONEncoder(json.JSONEncoder):
    """
    Custom JSON Encoder to handle:
    - datetime.date -> ISO string
    - datetime.datetime -> ISO string
    - decimal.Decimal -> float
    - NaN/Infinity -> null (to prevent invalid JSON)
    """
    def default(self, obj):
        if isinstance(obj, (date, datetime)):
            return obj.isoformat()
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)
    
    def encode(self, obj):
        """Override encode to handle NaN and Infinity in nested structures"""
        import math
        
        def sanitize(o):
            """Recursively sanitize NaN and Infinity values"""
            if isinstance(o, float):
                if math.isnan(o) or math.isinf(o):
                    return None  # Convert NaN/Infinity to null
                return o
            elif isinstance(o, dict):
                return {k: sanitize(v) for k, v in o.items()}
            elif isinstance(o, (list, tuple)):
                return [sanitize(item) for item in o]
            return o
        
        return super().encode(sanitize(obj))

class QueryRequest(BaseModel):
    query: str
    session_id: Optional[str] = None
    # NEW: Fields for clarification follow-up
    clarification_context: Optional[Dict[str, Any]] = None
    clarification_answer: Optional[str] = None
    clarification_question_id: Optional[str] = None

@app.on_event("startup")
async def startup_event():
    """Initialize all agents"""
    global db_manager, llm_client, router_agent, retriever_agent
    global architect_agent, validator_agent, fixer_agent, response_agent # Replaced planner_agent, synthesizer_agent
    global schema_analyzer, type_analyzer, insight_analyst
    global data_sampler, date_format_detector, clarification_agent, history_manager, session_manager, followup_handler, enhanced_context_manager, query_enhancer
    
    try:
        logger.info("="*80)
        logger.info(" Initializing SQL Swarm Backend (Production)")
        logger.info("="*80)
        
        Config.validate()
        
        db_manager = DatabaseManager()
        
        # Verify multi-database access for cross-database queries
        accessible_dbs, inaccessible_dbs = db_manager.verify_multi_database_access()
        if len(accessible_dbs) > 1:
            logger.info(f" Multi-database queries enabled across {len(accessible_dbs)} databases")
        
        llm_client = LLMClient()
        
        router_agent = Router(llm_client)
        retriever_agent = EmbeddingRetriever(Config.SCHEMA_FILE)
        architect_agent = QueryArchitect(llm_client) # Initialize QueryArchitect
        validator_agent = Validator(db_manager)
        fixer_agent = Fixer(llm_client)
        response_agent = ResponseGenerator(llm_client)
        schema_analyzer = SchemaAnalyzer()
        type_analyzer = TypeAnalyzer()
        insight_analyst = InsightAnalyst(llm_client, db_manager)  # Pass db_manager for autonomous queries

        history_manager = HistoryManager()
        session_manager = SessionManager(sessions_dir="sessions")
        followup_handler = FollowUpHandler(llm_client)
        enhanced_context_manager = EnhancedContextManager(session_manager)  # NEW: Unified context handling
        logger.info("S Enhanced context manager initialized")

        query_enhancer = QueryEnhancer(llm_client, Config.BUSINESS_CONTEXT_FILE)
        logger.info("S QueryEnhancer initialized")
        
        
        # Initialize clarification system if enabled
        if Config.ENABLE_CLARIFICATION:
            logger.info("Initializing clarification system...")
            
            # Initialize data sampler and date detector with retriever reference
            data_sampler = DataSampler(db_manager, retriever=retriever_agent)
            date_format_detector = DateFormatDetector(db_manager, retriever=retriever_agent)
            
            # Initialize clarification agent
            clarification_agent = ClarificationAgent(
                llm_client=llm_client,
                data_sampler=data_sampler,
                date_format_detector=date_format_detector
            )
            
            logger.info("S Clarification system enabled")
        else:
            logger.info("[WARN] Clarification system disabled")
        
        # Initialize dashboard (AFTER llm_client and db_manager are ready)
        logger.info("Initializing dashboard system...")
        dashboard_api.init_dashboard(llm_client, db_manager)
        
        logger.info("S All agents initialized successfully")
        logger.info("="*80 + "\n")
        
    except Exception as e:
        logger.error(f"Failed to initialize: {e}")
        raise

@app.on_event("shutdown")
async def shutdown_event():
    if db_manager:
        db_manager.close()

@app.get("/")
async def root():
    return {"service": "SQL Swarm API", "status": "running"}

@app.get("/api/health")
async def health_check():
    try:
        tables = db_manager.get_table_names() if db_manager else []
        return {
            "status": "healthy",
            "database": "connected" if tables else "disconnected",
            "schema_tables": len(retriever_agent.schema_data) if retriever_agent else 0
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Include dashboard router
# Include dashboard router
app.include_router(dashboard_api.router)
# Include AI Insights router
app.include_router(insights_api.router)



async def query_processor(user_query: str, skip_clarification: bool = False, session_id: Optional[str] = None, track_history: bool = True, clarification_context: Optional[Dict[str, Any]] = None, clarification_answer: Optional[str] = None, clarification_question_id: Optional[str] = None):
    """
    Shared async generator for processing queries.
    Yields dicts of events.
    
    Args:
        user_query: The user's query string
        skip_clarification: If True, skip clarification step (used for refined queries)
        track_history: If True, track the query in history manager.
        session_id: Optional session ID for loading conversation context
        clarification_context: Context from a previous clarification request.
        clarification_answer: The user's answer to a clarification question.
        clarification_question_id: The ID of the question being answered.
    """
    start_time = time.time()
    
    try:
        logger.info("\n" + "="*80)
        logger.info(f" QUERY: {user_query}")
        logger.info("="*80)
        
        # Track history (fire and forget)
        try:
            if history_manager and track_history:
                history_manager.add_query(user_query, query_type='normal')
        except Exception as e:
            logger.error(f"Failed to track history: {e}")
        
        # Load session history early — used by the CHAT response for context awareness
        early_chat_history = []
        if session_id and session_manager:
            try:
                early_session = session_manager.get_session(session_id)
                if early_session and early_session.get('messages'):
                    early_chat_history = early_session['messages']
            except Exception:
                pass
        
        # Step 1: Request Gating (Chat vs Data)
        logger.info("\n STEP 1: REQUEST GATING")
        t0 = time.time()
        
        # Check if conversational or data
        # Pass simplified chat history so router understands follow-up queries
        simplified_history = []
        for msg in early_chat_history[-6:]:
            simplified_history.append({
                'role': msg.get('role', ''),
                'content': str(msg.get('content', ''))[:300]
            })
        request_type = router_agent.classify_request_type(user_query, chat_history=simplified_history)
        t1 = time.time()

        logger.info(f"S Request Type: {request_type} ({(t1-t0)*1000:.0f}ms)")
        
        yield {
            'type': 'log', 
            'phase': 'ROUTER', 
            'message': f'Request Type: {request_type}', 
            'data': {'request_type': request_type, 'time_ms': (t1-t0)*1000}
        }
        await asyncio.sleep(0.01)
        
        # HANDLE CHAT REQUESTS
        if request_type == "CHAT":
            logger.info(" CHAT RESPONSE GENERATION")
            t0 = time.time()
            
            ai_response = response_agent.generate_conversational_response(user_query, chat_history=early_chat_history)
            t1 = time.time()
            
            result = {
                'type': 'result',
                'success': True,
                'sql': None,
                'data': [],
                'row_count': 0,
                'ai_response': ai_response,
                'metadata': {
                    'intent': 'CHAT',
                    'is_chat': True,
                    'total_time_ms': (time.time() - start_time) * 1000
                }
            }
            yield result
            return

        # HANDLE DATA REQUESTS -> Proceed to Intent Classification

        
        # Step 1.5: Load Chat History (needed for intent classification)
        logger.info("\n STEP 1.5: LOADING CHAT HISTORY")
        conversation_context = []
        if session_id and session_manager:
            try:
                context_messages = session_manager.get_session_context(session_id, last_n=10)  # ENHANCED: Expanded from 5 to 10 for better context
                
                # FIX: Filter out the current message if it was already saved to the session
                # This prevents the Router from seeing the current query as "history" and classifying it as a follow-up to itself
                if context_messages:
                    last_msg = context_messages[-1]
                    if last_msg.get('role') == 'user' and last_msg.get('content', '').strip() == user_query.strip():
                        logger.info("Ignoring current query found in session context (preventing self-follow-up)")
                        context_messages.pop()
                
                if context_messages:
                    logger.info(f"S Loaded {len(context_messages)} messages from session context")
                    conversation_context = context_messages
            except Exception as e:
                logger.error(f"Failed to load session context: {e}")
        
        # Step 1.6: Intent Classification (with chat history for follow-up detection)
        logger.info("\n STEP 1.6: INTENT CLASSIFICATION")
        t0 = time.time()
        intent_data = router_agent.classify_intent(user_query, chat_history=conversation_context)
        intent = intent_data.get("intent", "DETAIL_RETRIEVAL")
        is_follow_up = intent_data.get("is_follow_up", False)
        t1 = time.time()
        logger.info(f"S Intent: {intent}, Follow-up: {is_follow_up} ({(t1-t0)*1000:.0f}ms)")
        
        log_data = {
            'type': 'log', 
            'phase': 'ROUTER', 
            'message': f'Intent: {intent}{" (Follow-up)" if is_follow_up else ""}', 
            'data': {'intent': intent, 'is_follow_up': is_follow_up, 'time_ms': (t1-t0)*1000}
        }
        yield log_data
        await asyncio.sleep(0.01)

        
        # Step 2: Schema Retrieval
        logger.info("\n STEP 2: SCHEMA RETRIEVAL")
        t0 = time.time()
        # Enhance query for better semantic retrieval (enriched text used ONLY for ChromaDB lookup)
        enriched_query = query_enhancer.enhance(user_query, conversation_context) if query_enhancer else user_query
        relevant_tables_dicts = retriever_agent.retrieve_relevant_tables(enriched_query)
        t1 = time.time()
        table_names = [t['table'] for t in relevant_tables_dicts]
        logger.info(f"S Found: {', '.join(table_names)} ({(t1-t0)*1000:.0f}ms)")
        
        # Prepare log data for retriever
        # Extract matched columns specifically to show users exactly what triggered the match
        matched_cols = []
        for t in relevant_tables_dicts:
            if t.get('matched_columns'):
                matched_cols.extend(t['matched_columns'])
        
        display_msg = f"Found: {', '.join(table_names)}"
        if matched_cols:
            display_msg += f" (Matched columns: {', '.join(matched_cols[:5])})"
            if len(matched_cols) > 5:
                display_msg += "..."
                
        log_data = {
            'type': 'log', 
            'phase': 'RETRIEVER', 
            'message': display_msg, 
            'data': {'tables': table_names, 'columns': matched_cols, 'time_ms': (t1-t0)*1000}
        }
        yield log_data
        await asyncio.sleep(0.01)

        # Enhance Schema Context
        basic_context = retriever_agent.get_full_schema_string(relevant_tables_dicts, data_sampler=data_sampler, user_query=user_query)
        relationships = schema_analyzer.analyze_schema_relationships(relevant_tables_dicts)
        schema_context = schema_analyzer.enhance_schema_context(basic_context, relationships)
        
        # Load full context EARLY (needed for clarification)
        full_context = enhanced_context_manager.get_full_context(session_id, user_query)
        
        # Step 2.5: Intelligent Clarification (if enabled)
        if clarification_agent and intent != "FOLLOW_UP" and not skip_clarification:
            logger.info("\n STEP 2.5: CLARIFICATION ANALYSIS")
            t0 = time.time()
            
            # Enhance schema with date formats
            if date_format_detector:
                date_formats = date_format_detector.get_all_date_formats(relevant_tables_dicts, retriever_agent.schema_data)
                if date_formats:
                    date_info = "\n=== DATE FORMAT INFORMATION ===\n"
                    for col, fmt in date_formats.items():
                        date_info += f"{col}: {fmt}\n"
                    schema_context += date_info
            
            # Call clarification agent with FULL CONTEXT for intelligent decisions
            needs_clarification, questions, clarification_context = clarification_agent.analyze_query_conversational(
                user_query, 
                schema_context, 
                intent, 
                conversation_context,
                full_context=full_context  # NEW: Pass full pipeline context
            )
            t1 = time.time()
            
            if needs_clarification and questions:
                # Check if any questions are critical/high importance
                has_important_questions = any(
                    q.get('importance', 'medium') in ('critical', 'high') 
                    for q in questions
                )
                best_guess = clarification_context.get('best_guess_assumptions', '')
                
                if not has_important_questions and best_guess:
                    # Only skip questions if they're ALL low/medium importance
                    logger.info(f" Skipping low-priority questions, using assumption: {best_guess}")
                    yield {'type': 'log', 'phase': 'CLARIFICATION', 'message': f'Assumption made: {best_guess}', 'data': {'time_ms': (t1-t0)*1000}}
                    
                    # Store the assumption so the Planner sees it
                    schema_context += f"\n\n=== CLARIFICATION ASSUMPTION ===\n{best_guess}\n==============================\n"
                    await asyncio.sleep(0.01)
                else:
                    logger.info(f"[WARN] Clarification needed ({(t1-t0)*1000:.0f}ms)  sending first question only")
                    
                    # Send ONLY the first question  backend will decide next question after each answer
                    first_question = questions[0]
                    
                    yield {
                        'type': 'clarification_needed',
                        'questions': [first_question],  # Only the first question
                        'context': clarification_context,
                        'original_query': user_query,
                        'intent': intent,
                        'schema_context': schema_context,
                        'session_id': session_id,
                        'time_ms': (t1-t0)*1000
                    }
                    
                    # Exit generator - frontend will call /api/query/clarify/next for each answer
                    return
            else:
                logger.info(f"S Query is clear ({(t1-t0)*1000:.0f}ms)")
                yield {'type': 'log', 'phase': 'CLARIFICATION', 'message': 'Query is clear S', 'data': {'time_ms': (t1-t0)*1000}}
                await asyncio.sleep(0.01)
        
        # Step 2: Load Full Context & Dynamic Schema Retrieval
        # UNIFIED APPROACH: Every query gets full context, no special FOLLOW_UP handling
        logger.info("\n STEP 2: CONTEXT LOADING & SCHEMA RETRIEVAL")
        t0 = time.time()
        
        # full_context already loaded before clarification step
        
        # Dynamically decide if we need to fetch schema
        should_fetch = enhanced_context_manager.should_fetch_schema(user_query, full_context, intent, is_follow_up=is_follow_up)
        
        if should_fetch:
            # Schema already fetched in Step 2 above  reuse it (no duplicate retrieval)
            # relevant_tables_dicts, table_names, schema_context are already set
            logger.info(f" Using schema from Step 2: {', '.join(table_names)}")
        elif full_context.get('previous_schema') and full_context.get('previous_tables'):
            # Reuse schema from previous session context
            schema_context = full_context['previous_schema']
            table_names = full_context['previous_tables']
            logger.info(f" Reused schema from session: {', '.join(table_names)}")
            relevant_tables_dicts = [{'table': t} for t in table_names]  # Reconstruct format
        else:
            # Safety fallback: no previous schema available, force fresh fetch
            logger.info("[WARN] No previous schema available  fetching fresh")
            enriched_fallback = query_enhancer.enhance(user_query, conversation_context) if query_enhancer else user_query
            relevant_tables_dicts = retriever_agent.retrieve_relevant_tables(enriched_fallback)
            table_names = [t.get('table', 'unknown') for t in relevant_tables_dicts]
            basic_context = retriever_agent.get_full_schema_string(relevant_tables_dicts, data_sampler=data_sampler, user_query=user_query)
            relationships = schema_analyzer.analyze_schema_relationships(relevant_tables_dicts)
            schema_context = schema_analyzer.enhance_schema_context(basic_context, relationships)
            logger.info(f" Fresh schema fetched: {', '.join(table_names)}")
        
        t1 = time.time()
        
        yield {
            'type': 'log',
            'phase': 'CONTEXT',
            'message': f"{'Fetched' if should_fetch else 'Reused'} schema: {', '.join(table_names)}",
            'data': {
                'tables': table_names,
                'reused_schema': not should_fetch,
                'has_previous_context': full_context['has_previous_context'],
                'time_ms': (t1-t0)*1000
            }
        }
        await asyncio.sleep(0.01)
        
        
        # Step 3: Query Architecture (Planning & SQL Generation)
        logger.info("\n STEP 3: SQL GENERATION")
        t0 = time.time()
        
        # --- Follow-Up Rewrite Path ---
        # If we have previous SQL AND the query looks like a follow-up refinement,
        # route through FollowUpHandler (modify existing SQL) instead of regenerating.
        previous_sql = full_context.get('previous_sql')
        is_followup_rewrite = False
        
        if followup_handler and previous_sql and full_context.get('has_previous_context'):
            # Detect if query is a follow-up refinement (not a completely new topic)
            followup_signals = [
                'only', 'exclude', 'without', 'except', 'remove',
                'sort by', 'order by', 'order it by',
                'more than', 'less than', 'greater than', 'above', 'below',
                'show me more', 'show more', 'filter by', 'add filter',
                'now show', 'also show', 'and also', 'just show',
                'instead', 'change it to', 'make it'
            ]
            query_lower_check = user_query.lower()
            has_followup_signal = any(kw in query_lower_check for kw in followup_signals)
            
            if has_followup_signal:
                logger.info(" Follow-up signal detected  rewriting existing SQL via FollowUpHandler")
                yield {'type': 'log', 'phase': 'FOLLOWUP', 'message': 'Refining previous query...', 'data': {}}
                
                followup_type = followup_handler.detect_followup_type(user_query, full_context)
                rewritten_sql = followup_handler.rewrite_sql(
                    original_sql=previous_sql,
                    user_instruction=user_query,
                    followup_type=followup_type,
                    schema_context=schema_context,
                    previous_intent=full_context.get('previous_intent', 'UNKNOWN')
                )
                
                # Validate rewrite is safe
                is_valid_rewrite, rewrite_error = followup_handler.validate_rewrite(
                    previous_sql, rewritten_sql, full_context.get('previous_intent', 'UNKNOWN')
                )
                
                if is_valid_rewrite and rewritten_sql:
                    sql = rewritten_sql
                    is_followup_rewrite = True
                    logger.info(f"S SQL rewritten via FollowUpHandler ({followup_type})")
                else:
                    logger.warning(f"FollowUpHandler rewrite failed ({rewrite_error}), falling back to QueryArchitect")
        
        if not is_followup_rewrite:
            # Standard path: generate SQL from scratch with QueryArchitect
            sql = architect_agent.generate_sql(
                user_query, 
                intent, 
                schema_context, 
                full_context=full_context
            )
        
        t1 = time.time()
        logger.info(f"S SQL generated ({(t1-t0)*1000:.0f}ms) [{'rewrite' if is_followup_rewrite else 'fresh'}]")
        logger.info(f"SQL:\n{sql}")
        
        # Step 5: Validation, Execution & Fixing Loop
        logger.info("\n STEP 5: VALIDATION & EXECUTION")
        
        valid = False
        attempts = 0
        max_attempts = 3
        error_msg = ""
        results_df = None
        exec_time_ms = 0
        
        while attempts < max_attempts:
            # 5a. Syntax Validation
            t0 = time.time()
            valid_syntax, syntax_error = validator_agent.validate(sql)
            t1 = time.time()
            
            if not valid_syntax:
                logger.warning(f"F Syntax Invalid ({(t1-t0)*1000:.0f}ms): {syntax_error}")
                yield {'type': 'log', 'phase': 'VALIDATOR', 'message': 'Syntax Invalid', 'data': {'status': 'invalid', 'error': syntax_error, 'time_ms': (t1-t0)*1000}}
                
                # Fix Syntax
                logger.info("\n FIXING SQL (Syntax)")
                sql = fixer_agent.fix_sql(user_query, None, schema_context, syntax_error, sql)
                attempts += 1
                continue

            logger.info(f"S Syntax Valid ({(t1-t0)*1000:.0f}ms)")
            yield {'type': 'log', 'phase': 'VALIDATOR', 'message': 'Syntax Valid', 'data': {'status': 'valid', 'time_ms': (t1-t0)*1000}}
            
            # 5b. Execution
            try:
                t0 = time.time()
                results_df = db_manager.execute_query_safe(sql)
                t1 = time.time()
                exec_time_ms = (t1 - t0) * 1000
                
                # 5c. Result Validation (Duplicate Check & Suspicious Patterns)
                valid_result, result_issue, fix_hint = validator_agent.validate_results(results_df, user_query, sql)
                
                if valid_result:
                    logger.info(f"S Query executed successfully ({len(results_df)} rows)")
                    yield {'type': 'log', 'phase': 'EXECUTOR', 'message': f'Query executed ({len(results_df)} rows)', 'data': {'row_count': len(results_df), 'time_ms': exec_time_ms}}
                    break # Success!
                else:
                    logger.warning(f"F Result Issue: {result_issue}")
                    yield {'type': 'log', 'phase': 'VALIDATOR', 'message': 'Result Issue Detected', 'data': {'status': 'invalid_result', 'error': result_issue, 'time_ms': 0}}
                    
                    if attempts < max_attempts - 1:
                        logger.info("\n FIXING SQL (Result Quality)")
                        # Fix Result Issue
                        sql = fixer_agent.fix_sql(user_query, None, schema_context, result_issue + "\n" + (fix_hint or ""), sql)
                        yield {'type': 'log', 'phase': 'FIXER', 'message': 'Fixing result quality', 'data': {'sql': sql, 'time_ms': 0}}
                    attempts += 1
            except Exception as e:
                # Catch runtime SQL execution errors (e.g. invalid column, wrong type)
                error_msg = str(e)
                logger.warning(f"F Execution Error: {error_msg}")
                yield {'type': 'log', 'phase': 'EXECUTOR', 'message': 'Execution Error', 'data': {'status': 'execution_failed', 'error': error_msg, 'time_ms': 0}}
                
                if attempts < max_attempts - 1:
                    logger.info("\n FIXING SQL (Runtime Execution)")
                    sql = fixer_agent.fix_sql(user_query, None, schema_context, f"Runtime Execution Error: {error_msg}", sql)
                    yield {'type': 'log', 'phase': 'FIXER', 'message': 'Fixing runtime error', 'data': {'sql': sql, 'time_ms': 0}}
                attempts += 1
                continue
        
        if attempts >= max_attempts and (results_df is None or results_df.empty):
             yield {'type': 'error', 'message': f'Failed to generate valid results after {max_attempts} attempts'}
             return

        # Step 7: Response Generation
        logger.info("\n STEP 7: AI RESPONSE GENERATION")
        t0 = time.time()
        results_summary = results_df.head(5).to_string(index=False) if not results_df.empty else "No results"
        ai_response = response_agent.generate_response(user_query, sql, results_summary, len(results_df), intent)
        t1 = time.time()
        
        yield {'type': 'log', 'phase': 'RESPONSE', 'message': 'Generated explanation', 'data': {'response': ai_response, 'time_ms': (t1-t0)*1000}}
        await asyncio.sleep(0.01)

        total_time = (time.time() - start_time) * 1000
        logger.info("\n" + "="*80)
        logger.info(f"[OK] QUERY COMPLETED SUCCESSFULLY (Total: {total_time:.0f}ms)")
        
        # Step 6: Result Classification
        classification = "NON_REPORT" # Default fallback
        try:
            metadata = extract_metadata(results_df, sql, intent)
            classification = classify_report_result(results_df, metadata)
            logger.info(f"S Result Classification: {classification}")
        except Exception as e:
            logger.error(f"Classification failed: {e}")
        
        # Generate suggested report title (only for report-classified results)
        suggested_title = None
        if classification != "NON_REPORT" and not results_df.empty:
            try:
                columns = results_df.columns.tolist()
                suggested_title = generate_report_name(
                    original_question=user_query,
                    columns=columns,
                    row_count=len(results_df),
                    classification=classification,
                    llm_client=llm_client
                )
                logger.info(f"Generated suggested report title: {suggested_title}")
            except Exception as e:
                logger.error(f"Failed to generate suggested title: {e}")
                # Fallback to user query
                suggested_title = user_query[:60] if len(user_query) <= 60 else user_query[:57] + "..."
        
        # Send final result IMMEDIATELLY (User requirement: don't block)
        limited_data = results_df.head(1000).to_dict(orient='records')
        
        query_id = str(uuid.uuid4())
        
        result = {
            "type": "result",
            "success": True,
            "sql": sql,
            "data": limited_data,
            "row_count": len(results_df),
            "is_truncated": len(results_df) > 1000,
            "ai_response": ai_response,
            "classification": classification,
            "query_id": query_id,
            "metadata": {
                "query_id": query_id,
                "classification": classification,
                "intent": intent,
                "tables_used": table_names,
                "plan": None,
                "total_time_ms": total_time,
                #  FULL CONTEXT for conversational intelligence (auto-stored by frontend)
                "schemaContext": schema_context,
                "schemaHash": hashlib.md5(schema_context.encode()).hexdigest(),
                "tablesUsed": table_names,
                "rowCount": len(results_df),
                "executionTimeMs": int(total_time),
                "suggested_title": suggested_title  # NEW: Suggested report name
            }
        }
        yield result
        
        # Give frontend a moment to render the main response before starting insights
        await asyncio.sleep(0.1)

        # Step 8: Auto-Insights (Background - Post Response)
        logger.info("\n STEP 8: AUTO INSIGHTS (Background)")
        yield {'type': 'log', 'phase': 'INSIGHTS', 'message': 'Initializing insight engine...', 'data': {'status': 'analyzing'}}
        await asyncio.sleep(0.5)

        if not results_df.empty:
            yield {'type': 'log', 'phase': 'INSIGHTS', 'message': 'Analyzing data structure & content...', 'data': {'status': 'processing'}}
            
            # We need to manually log from inside the agent if we want streams, 
            # or we simulate progress here for the user benefit
            yield {'type': 'log', 'phase': 'INSIGHTS', 'message': f'Sending {len(results_df)} rows to Analyst Agent...', 'data': {'status': 'processing'}}
            
            insight_config = insight_analyst.generate_insights(
                user_query, 
                sql, 
                results_df, 
                schema_context,
                chat_history=conversation_context
            )
            
            if insight_config:
                 yield {'type': 'log', 'phase': 'INSIGHTS', 'message': ' Visualization generated successfully!', 'data': {'status': 'complete'}}
                 logger.info("S Insights generated (Async)")
                 yield {'type': 'insight', 'data': insight_config}
                 await asyncio.sleep(0.5)  # Ensure insight event is transmitted before stream closes
                 

            else:
                 yield {'type': 'log', 'phase': 'INSIGHTS', 'message': 'No robust visualization patterns found.', 'data': {'status': 'complete'}}
                 # Yield empty insight to clear the frontend loader
                 yield {'type': 'insight', 'data': {'should_visualize': False, 'charts': []}}
                 await asyncio.sleep(0.5)  # Ensure insight event is transmitted before stream closes
        else:
            yield {'type': 'log', 'phase': 'INSIGHTS', 'message': 'Skipping insights (No data returned).', 'data': {'status': 'complete'}}
            yield {'type': 'insight', 'data': {'should_visualize': False, 'charts': []}}
            await asyncio.sleep(0.5)  # Ensure insight event is transmitted before stream closes
        
    except Exception as e:
        logger.error(f"\n[FAIL] Pipeline error: {e}")
        yield {'type': 'error', 'message': str(e)}

@app.post("/api/query")
async def process_query_legacy(request: QueryRequest):
    """
    Legacy endpoint returns full JSON response (blocks until complete)
    """
    steps = []
    final_result = None
    
    async for event in query_processor(request.query):
        if event['type'] == 'log':
            steps.append(event)
        elif event['type'] == 'result':
            final_result = event
        elif event['type'] == 'error':
            return {"success": False, "error": event['message'], "steps": steps}
        elif event['type'] == 'clarification':
            return {
                "success": True,
                "type": "clarification",
                "questions": event['questions'],
                "context": event['context'],
                "original_query": event['original_query'],
                "intent": event['intent'],
                "schema_context": event['schema_context'],
                "session_id": event['session_id'],
                "steps": steps
            }
        elif event['type'] == 'insight':
            continue # Stream only feature, ignore in legacy
            
    if final_result:
        # Construct legacy response format matching old main.py
        return {
            "success": True,
            "result": {
                "success": True,
                "sql": final_result['sql'],
                "data": final_result['data'],
                "row_count": final_result['row_count'],
                "ai_response": final_result['ai_response'],
                "steps": steps,
                "metadata": final_result.get('metadata', None)
            }
        }
    return {"success": False, "error": "Unknown dispatch error"}

@app.post("/api/query/stream")
async def process_query_stream(request: QueryRequest):
    """
    Stream query processing with Server-Sent Events
    """
    async def event_generator():
        async for event in query_processor(request.query, session_id=request.session_id):
            yield f"data: {json.dumps(event, cls=CustomJSONEncoder)}\n\n"
            
    return StreamingResponse(
        event_generator(), 
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # Critical for Nginx to stream properly
            "Connection": "keep-alive"
        }
    )

class ClarificationResponse(BaseModel):
    original_query: str
    clarifications: Dict[str, Any]
    context: Dict[str, Any]
    session_id: Optional[str] = None

@app.post("/api/query/clarify")
async def process_clarified_query(request: ClarificationResponse):
    """
    Process query after user provides clarifications.
    Refines the query and continues with normal pipeline.
    """
    try:
        # Build refined query using clarification agent
        refined_query = clarification_agent.build_refined_query_conversational(
            request.original_query,
            request.clarifications,
            request.context
        )
        
        logger.info(f"\n{'='*80}")
        logger.info(f" CLARIFIED QUERY")
        logger.info(f"Original: {request.original_query}")
        logger.info(f"Refined: {refined_query}")
        logger.info(f"{'='*80}")
        
        # logger.info(f"Refined history tracking skipped per user request")
        
        # Continue with normal streaming pipeline using refined query
        async def event_generator():
            # First, yield the refined query info
            refined_query_event = {
                'type': 'log', 
                'phase': 'CLARIFIED', 
                'message': f'Refined Query: {refined_query}',
                'data': {'original': request.original_query, 'refined': refined_query}
            }
            yield f"data: {json.dumps(refined_query_event, cls=CustomJSONEncoder)}\n\n"
            await asyncio.sleep(0.1)
            
            # Then stream events from processor (DON'T track history again as 'normal')
            async for event in query_processor(refined_query, skip_clarification=True, session_id=request.session_id, track_history=False):
                yield f"data: {json.dumps(event, cls=CustomJSONEncoder)}\n\n"
        
        return StreamingResponse(
            event_generator(), 
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
                "Connection": "keep-alive"
            }
        )
    
    except Exception as e:
        logger.error(f"Clarification processing error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

class NextClarificationRequest(BaseModel):
    """Request body for the sequential clarification flow."""
    original_query: str
    answered_pairs: list  # [{"question": ..., "answer": ..., "category": ...}]
    context: Dict[str, Any]
    intent: str = "AGGREGATION"
    schema_context: str = ""
    session_id: Optional[str] = None

@app.post("/api/query/clarify/next")
async def process_next_clarification(request: NextClarificationRequest):
    """
    Sequential clarification: evaluate if another question is needed.
    
    Flow:
    1. Frontend sends answered Q&A pairs
    2. Backend calls generate_next_question() with all answers
    3. If more needed  returns next question
    4. If done  builds refined query and runs pipeline (streaming)
    """
    try:
        # Load conversation context for the agent
        conversation_context = []
        if request.session_id and session_manager:
            try:
                conversation_context = session_manager.get_session_context(request.session_id, last_n=4)
            except Exception as e:
                logger.warning(f"Failed to load session context: {e}")
        
        # Load full context
        full_context = None
        if request.session_id and enhanced_context_manager:
            try:
                full_context = enhanced_context_manager.get_full_context(request.session_id, request.original_query)
            except Exception as e:
                logger.warning(f"Failed to load full context: {e}")
        
        # Get schema context  use what was passed or re-fetch
        schema_context = request.schema_context
        if not schema_context:
            relevant_tables = retriever_agent.retrieve_relevant_tables(request.original_query)
            basic_context = retriever_agent.get_full_schema_string(relevant_tables, data_sampler=data_sampler, user_query=request.original_query)
            relationships = schema_analyzer.analyze_schema_relationships(relevant_tables)
            schema_context = schema_analyzer.enhance_schema_context(basic_context, relationships)
        
        # Ask the agent if another question is needed
        needs_more, next_question, ctx = clarification_agent.generate_next_question(
            user_query=request.original_query,
            schema_context=schema_context,
            intent=request.intent,
            answered_pairs=request.answered_pairs,
            chat_history=conversation_context,
            full_context=full_context
        )
        
        if needs_more and next_question:
            # Return next question  frontend will show it
            logger.info(f" Next clarification question: {next_question.get('question', '')[:80]}")
            return JSONResponse(content={
                "type": "next_question",
                "question": next_question,
                "answered_count": len(request.answered_pairs)
            })
        else:
            # All done  build refined query and run pipeline
            logger.info(f"[OK] Clarification complete ({len(request.answered_pairs)} answers)  running pipeline")
            
            # Build clarifications dict from answered pairs
            clarifications = {}
            for pair in request.answered_pairs:
                category = pair.get('category', f"q{pair.get('id', 0)}")
                clarifications[category] = pair.get('answer', '')
            
            # Build refined query
            refined_query = clarification_agent.build_refined_query_conversational(
                request.original_query,
                clarifications,
                request.context
            )
            
            logger.info(f" Refined query: {refined_query}")
            
            # Stream the pipeline
            async def event_generator():
                refined_event = {
                    'type': 'log',
                    'phase': 'CLARIFIED',
                    'message': f'Refined Query: {refined_query}',
                    'data': {'original': request.original_query, 'refined': refined_query}
                }
                yield f"data: {json.dumps(refined_event, cls=CustomJSONEncoder)}\n\n"
                await asyncio.sleep(0.1)
                
                async for event in query_processor(refined_query, skip_clarification=True, session_id=request.session_id, track_history=False):
                    yield f"data: {json.dumps(event, cls=CustomJSONEncoder)}\n\n"
            
            return StreamingResponse(
                event_generator(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "X-Accel-Buffering": "no",
                    "Connection": "keep-alive"
                }
            )
    
    except Exception as e:
        logger.error(f"Next clarification error: {e}")
        raise HTTPException(status_code=500, detail=str(e))



class SaveReportFromSqlRequest(BaseModel):
    sql: str
    user_query: str
    columns: Optional[list[str]] = None
    classification: Optional[str] = "STRONG_REPORT"
    custom_title: Optional[str] = None
    user_id: Optional[str] = "default_user"
    charts: Optional[list] = []

@app.post("/api/reports/save-from-sql")
async def api_save_report_from_sql(request: SaveReportFromSqlRequest):
    """
    Save report using SQL from session history (no ResultCache needed).
    Re-executes the SQL to get fresh rows for the summary/row_count.
    Also works as a permanent fallback when the ResultCache has expired.
    """
    if not db_manager:
        raise HTTPException(status_code=500, detail="Database manager not initialized")

    try:
        results_df = db_manager.execute_query_safe(request.sql)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"SQL execution failed: {e}")

    columns = request.columns or results_df.columns.tolist()

    result = await run_in_threadpool(
        save_report,
        query_context={
            "original_question": request.user_query,
            "classification": request.classification,
        },
        sql_context={
            "base_sql": request.sql,
            "base_params": {},
        },
        result_cache={
            "rows": results_df.to_dict(orient="records"),
            "columns": columns,
        },
        user_id=request.user_id,
        llm_client=llm_client,
        charts=request.charts or [],
        custom_title=request.custom_title,
        date_detector=date_format_detector,
    )

    if result["status"] == "error":
        raise HTTPException(status_code=500, detail=result["message"])

    return result


@app.get("/api/reports")
async def api_list_reports():
    """
    Get list of saved reports.
    """
    try:
        reports = list_reports()
        return {"success": True, "reports": reports}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class RegenerateReportRequest(BaseModel):
    filters: Dict[str, Any]
    temporary: bool = False

@app.post("/api/reports/{report_id}/regenerate")
async def api_regenerate_report(report_id: str, request: RegenerateReportRequest):
    """
    Regenerate report with new filters.
    """
    if not llm_client or not db_manager:
        raise HTTPException(status_code=500, detail="Services not initialized")
        
    result = await run_in_threadpool(
        regenerate_report,
        report_id=report_id,
        filters=request.filters,
        user_id="default_user",
        llm_client=llm_client,
        db_manager=db_manager,
        date_detector=date_format_detector,
        temporary=request.temporary,
        insight_analyst=insight_analyst  # Pass InsightAnalyst to use same logic as Chat
    )
    
    if result["status"] == "error":
        raise HTTPException(status_code=500, detail=result["message"])
        
    return result

class RenameReportRequest(BaseModel):
    new_title: str

@app.post("/api/reports/{report_id}/rename")
async def api_rename_report(report_id: str, request: RenameReportRequest):
    """
    Rename a saved report.
    """
    result = rename_report(report_id, request.new_title)
    
    if result["status"] == "error":
        raise HTTPException(status_code=500, detail=result["message"])
        
    return result

@app.delete("/api/reports/{report_id}")
async def api_delete_report(report_id: str):
    """
    Delete a saved report.
    """
    from backend.models.report import delete_report
    
    result = delete_report(report_id)
    
    if result["status"] == "error":
        raise HTTPException(status_code=404 if "not found" in result["message"].lower() else 500, detail=result["message"])
        
    return result


class SaveFilteredVersionRequest(BaseModel):
    filters: Dict[str, Any]
    title: str
    user_id: Optional[str] = "default_user"

@app.post("/api/reports/{report_id}/save-version")
async def api_save_filtered_version(report_id: str, request: SaveFilteredVersionRequest):
    """
    Save the currently applied filtered view of a report as a new standalone report.
    The filtered SQL becomes the new report's base_sql.
    """
    if not db_manager:
        raise HTTPException(status_code=500, detail="Database manager not initialized")

    result = await run_in_threadpool(
        save_filtered_version,
        report_id=report_id,
        filters=request.filters,
        new_title=request.title,
        user_id=request.user_id,
        db_manager=db_manager,
        llm_client=llm_client,
        date_detector=date_format_detector
    )

    if result["status"] == "error":
        raise HTTPException(status_code=500, detail=result["message"])

    return result


@app.get("/api/history")
async def api_get_history():
    """
    Get query history sorted by frequency.
    """
    try:
        if not history_manager:
              return {"success": False, "history": []}
              
        history = history_manager.get_history(limit=50)
        return {"success": True, "history": history}
    except Exception as e:
        logger.error(f"Failed to get history: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=Config.API_HOST, port=Config.API_PORT, reload=Config.API_RELOAD)

@app.post("/api/reports/{report_id}/execute")
async def api_execute_report(report_id: str, params: Optional[Dict[str, Any]] = None):
    """
    Execute a saved report's SQL query and return fresh data.
    Uses caching to improve performance.
    """
    if not db_manager:
        raise HTTPException(status_code=500, detail="Database manager not initialized")
    
    # Generate cache key
    cache_key_str = f"{report_id}:{json.dumps(params or {}, sort_keys=True)}"
    cache_key = md5(cache_key_str.encode()).hexdigest()
    
    # Check cache
    if cache_key in query_result_cache:
        logger.info(f"Cache hit for report {report_id}")
        cached_result = query_result_cache[cache_key]
        cached_result["cached"] = True
        return cached_result
    
    # Execute report
    logger.info(f"Received execution request for report {report_id}")
    
    result = await run_in_threadpool(
        execute_report,
        report_id=report_id,
        params=params,
        db_manager=db_manager,
        regenerate_charts=True,
        insight_analyst=insight_analyst  # Pass InsightAnalyst to use same logic as Chat
    )
    
    if result["status"] == "error":
        logger.error(f"Report execution failed: {result.get('message')}")
        raise HTTPException(status_code=500, detail=result["message"])
    
    # Cache result
    query_result_cache[cache_key] = result
    logger.info(f"Execution successful for {report_id}. Rows: {len(result.get('data', []))}. Caching result.")
    
    return result


# ============================================================================
# SESSION MANAGEMENT ENDPOINTS
# ============================================================================

class CreateSessionRequest(BaseModel):
    title: Optional[str] = None

class AddMessageRequest(BaseModel):
    message: Dict[str, Any]

class UpdateTitleRequest(BaseModel):
    title: str

@app.post("/api/sessions/create")
async def create_session(request: CreateSessionRequest = None):
    """
    Create a new chat session.
    """
    try:
        title = request.title if request else None
        session = session_manager.create_session(title=title)
        return {"success": True, **session}
    except Exception as e:
        logger.error(f"Failed to create session: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/sessions")
async def list_sessions(page: int = 1, limit: int = 20):
    """
    List chat sessions with pagination support.
    
    Args:
        page: Page number (1-indexed)
        limit: Number of sessions per page (default 20)
    
    Returns:
        {
            "success": True,
            "sessions": [...],
            "total": total_count,
            "page": current_page,
            "has_more": boolean
        }
    """
    try:
        all_sessions = session_manager.list_sessions(limit=None)  # Get all sessions
        total = len(all_sessions)
        
        # Calculate pagination
        start = (page - 1) * limit
        end = start + limit
        paginated_sessions = all_sessions[start:end]
        
        return {
            "success": True,
            "sessions": paginated_sessions,
            "total": total,
            "page": page,
            "has_more": end < total
        }
    except Exception as e:
        logger.error(f"Failed to list sessions: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/sessions/{session_id}")
async def get_session(session_id: str):
    """
    Get a specific session with all messages.
    """
    try:
        session = session_manager.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        return {"success": True, **session}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get session: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/sessions/{session_id}/messages")
async def add_message_to_session(session_id: str, request: AddMessageRequest):
    """
    Add a message to a session.
    """
    try:
        success = session_manager.add_message(session_id, request.message)
        if not success:
            raise HTTPException(status_code=404, detail="Session not found or failed to add message")
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to add message: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/sessions/{session_id}/title")
async def update_session_title(session_id: str, request: UpdateTitleRequest):
    """
    Update a session's title.
    """
    try:
        success = session_manager.update_session_title(session_id, request.title)
        if not success:
            raise HTTPException(status_code=404, detail="Session not found")
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update title: {e}")
@app.delete("/api/sessions/{session_id}")
async def delete_session(session_id: str):
    """
    Delete a specific session.
    """
    try:
        success = session_manager.delete_session(session_id)
        if not success:
            raise HTTPException(status_code=404, detail="Session not found")
        return {"success": True, "message": "Session deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete session: {e}")
        raise HTTPException(status_code=500, detail=str(e))

class UpdateSessionRequest(BaseModel):
    title: str

@app.patch("/api/sessions/{session_id}")
async def update_session(session_id: str, request: UpdateSessionRequest):
    """
    Update a session's title.
    
    Args:
        session_id: Session ID to update
        request: Request body containing new title
    
    Returns:
        {"success": True, "message": "Session updated successfully"}
    """
    try:
        success = session_manager.update_session_title(session_id, request.title)
        if not success:
            raise HTTPException(status_code=404, detail="Session not found")
        return {"success": True, "message": "Session updated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update session: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/sessions/{session_id}/context")
async def get_session_context(session_id: str):
    """
    Get the last query context for debugging/display.
    Returns the most recent assistant message's full context including SQL, schema, intent, etc.
    """
    try:
        context = session_manager.get_last_query_context(session_id)
        if not context:
            return {"success": True, "context": None, "message": "No context found"}
        return {"success": True, "context": context}
    except Exception as e:
        logger.error(f"Failed to get context: {e}")
        raise HTTPException(status_code=500, detail=str(e))


