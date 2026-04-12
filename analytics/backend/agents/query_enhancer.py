"""
Query Enhancer — Pre-retrieval LLM step.

Rewrites the raw user query into a meaningful 2-3 sentence business-domain
description that semantically matches the column/table embeddings stored in
ChromaDB (which are written as full natural language descriptions).

Used ONLY for vector retrieval — the raw user query is unchanged everywhere else.
"""
import json
import os
import re
from backend.core.logger import logger
from backend.config import Config


# Removed hardcoded _BUSINESS_SUMMARY - now relying exclusively on dynamic business_context.json


class QueryEnhancer:
    """
    Lightweight pre-retrieval query expansion.

    Takes a user query + recent conversation and produces a meaningful
    2-3 sentence description the vector retriever can match against
    embedded column/table descriptions.
    """

    def __init__(self, llm_client, business_context_path: str = None):
        self.llm_client = llm_client

        # Try to load business_context.json for richer domain signal
        self._extra_context = ""
        if business_context_path and os.path.exists(business_context_path):
            try:
                with open(business_context_path, "r") as f:
                    bc = json.load(f)
                # Pull the main description — first 1500 chars is enough
                desc = bc.get("description", "")
                self._extra_context = desc[:1500] if desc else ""
            except Exception as e:
                logger.warning(f"[ENHANCER] Could not load business_context.json: {e}")

        logger.info("[ENHANCER] QueryEnhancer initialized")

    # ──────────────────────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────────────────────

    def enhance(self, user_query: str, conversation_context: list = None) -> str:
        """
        Produce a retrieval-optimised description for the user query.

        Returns enriched text on success, raw user_query on any failure.
        """
        try:
            prompt = self._build_prompt(user_query, conversation_context or [])
            model = getattr(Config, "QUERY_ENHANCER_MODEL", Config.MODEL_NAME)

            messages = [
                {"role": "system", "content": "You are a database retrieval expert."},
                {"role": "user", "content": prompt}
            ]

            response = self.llm_client.call_chat(
                messages=messages,
                model=model,
                max_tokens=300,
                temperature=0.1,
                timeout=5,          # hard 5-second budget — never blocks pipeline
                return_usage=False
            )

            enhanced = self._extract_text(response)
            if not enhanced or len(enhanced.strip()) < 20:
                logger.debug("[ENHANCER] Empty/short response — using raw query")
                return user_query

            logger.info(f"[ENHANCER] Enriched: {enhanced[:160]}")
            return enhanced.strip()

        except Exception as e:
            logger.warning(f"[ENHANCER] Failed ({type(e).__name__}: {e}) — using raw query")
            return user_query         # Silent fallback — pipeline unaffected

    # ──────────────────────────────────────────────────────────────────────────
    # Internal helpers
    # ──────────────────────────────────────────────────────────────────────────

    def _build_prompt(self, user_query: str, conversation_context: list) -> str:
        # Recent conversation snippet (last 2 turns)
        ctx_lines = ""
        for msg in conversation_context[-4:]:        # up to 4 messages = 2 Q&A pairs
            role = msg.get("role", "")
            content = str(msg.get("content", ""))[:200]
            if role and content:
                ctx_lines += f"{role.upper()}: {content}\n"

        convo_block = ""
        return f"""{self._extra_context}

{convo_block}

User question: "{user_query}"

TASK: Rewrite the user's question as a 2-3 sentence business-domain description
that explains WHAT data is needed and captures the business meaning behind it.
Focus on:
- What kind of records are being queried (leads, contracts, concepts, customers, revenue, categories)
- What filtering or time range is implied (active status, successful leads, this month, by site)
- What aggregation or relationship is needed (totals, counts, grouped by, joined across tables)

Write in plain English describing the business question — do NOT use SQL syntax or raw column names.
Do NOT include any explanation or preamble — only output the descriptive sentences.
"""

    @staticmethod
    def _extract_text(response) -> str:
        """Extract plain text from LLM response (handles str or dict shapes)."""
        if isinstance(response, str):
            return response.strip()
        if isinstance(response, dict):
            # OpenAI-style response
            choices = response.get("choices", [])
            if choices:
                msg = choices[0].get("message", {}) or choices[0].get("delta", {})
                return (msg.get("content") or "").strip()
            # Direct content key
            return (response.get("content") or response.get("text") or "").strip()
        return ""
