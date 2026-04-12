"""
Session Manager for Chat Persistence

Manages chat sessions with JSON file storage.
Each session is stored as a separate JSON file in the sessions/ directory.
"""

import os
import json
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class SessionManager:
    """Manages chat sessions with JSON file-based storage."""
    
    def __init__(self, sessions_dir: str = "sessions"):
        """
        Initialize SessionManager.
        
        Args:
            sessions_dir: Directory to store session JSON files
        """
        self.sessions_dir = Path(sessions_dir)
        self.sessions_dir.mkdir(exist_ok=True)
        logger.info(f"SessionManager initialized with directory: {self.sessions_dir}")
    
    def _get_session_path(self, session_id: str) -> Path:
        """Get the file path for a session, ensuring directory exists."""
        if not self.sessions_dir.exists():
            self.sessions_dir.mkdir(exist_ok=True)
            logger.info(f"Re-created sessions directory: {self.sessions_dir}")
        return self.sessions_dir / f"{session_id}.json"
    
    def create_session(self, title: Optional[str] = None) -> Dict[str, Any]:
        """
        Create a new chat session.
        
        Args:
            title: Optional session title (auto-generated if not provided)
            
        Returns:
            Session metadata dict
        """
        session_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat() + "Z"
        
        session = {
            "session_id": session_id,
            "title": title or "New Chat",
            "created_at": now,
            "updated_at": now,
            "message_count": 0,
            "messages": []
        }
        
        # Save to file
        session_path = self._get_session_path(session_id)
        with open(session_path, 'w') as f:
            json.dump(session, f, indent=2)
        
        logger.info(f"Created new session: {session_id}")
        return {
            "session_id": session["session_id"],
            "title": session["title"],
            "created_at": session["created_at"],
            "updated_at": session["updated_at"],
            "message_count": session["message_count"]
        }
    
    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Load a session from storage.
        
        Args:
            session_id: Session ID to load
            
        Returns:
            Full session dict with messages, or None if not found
        """
        session_path = self._get_session_path(session_id)
        
        if not session_path.exists():
            logger.warning(f"Session not found: {session_id}")
            return None
        
        try:
            with open(session_path, 'r') as f:
                session = json.load(f)
            return session
        except Exception as e:
            logger.error(f"Error loading session {session_id}: {e}")
            return None
    
    def list_sessions(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        List all sessions, sorted by most recently updated.
        
        Args:
            limit: Maximum number of sessions to return
            
        Returns:
            List of session metadata dicts (without full messages)
        """
        sessions = []
        
        for session_file in self.sessions_dir.glob("*.json"):
            try:
                with open(session_file, 'r') as f:
                    session = json.load(f)
                
                # Filter out empty sessions
                msg_count = session.get("message_count", 0)
                messages = session.get("messages", [])
                
                # Logic: Skip if 0 messages OR if title is "New Chat" and it's empty
                if msg_count == 0 or (len(messages) == 0):
                    continue
                
                # Return metadata only (no messages)
                sessions.append({
                    "session_id": session["session_id"],
                    "title": session["title"],
                    "created_at": session["created_at"],
                    "updated_at": session["updated_at"],
                    "message_count": msg_count
                })
            except Exception as e:
                logger.error(f"Error reading session file {session_file}: {e}")
                continue
        
        # Sort by updated_at (most recent first)
        sessions.sort(key=lambda x: x["updated_at"], reverse=True)
        
        # Return all sessions if limit is None, otherwise apply limit
        if limit is None:
            return sessions
        return sessions[:limit]
    
    def add_message(self, session_id: str, message: Dict[str, Any]) -> bool:
        """
        Add a message to a session.
        
        Args:
            session_id: Session ID
            message: Message dict to add
            
        Returns:
            True if successful, False otherwise
        """
        session = self.get_session(session_id)
        
        if not session:
            logger.error(f"Cannot add message - session not found: {session_id}")
            return False
        
        # Check for duplicate/update based on query_id in responseMeta
        incoming_query_id = message.get("responseMeta", {}).get("query_id")
        updated_existing = False
        
        if incoming_query_id:
            # Iterate backwards to find matching message
            for i in range(len(session["messages"]) - 1, -1, -1):
                existing_msg = session["messages"][i]
                existing_query_id = existing_msg.get("responseMeta", {}).get("query_id")
                
                if existing_query_id and existing_query_id == incoming_query_id:
                    # Found match - update it!
                    session["messages"][i] = message
                    updated_existing = True
                    logger.info(f"Updated existing message with query_id {incoming_query_id} in session {session_id}")
                    break
        
        if not updated_existing:
            # Add new message
            session["messages"].append(message)
            session["message_count"] = len(session["messages"])
        
        session["updated_at"] = datetime.utcnow().isoformat() + "Z"
        
        # Auto-generate title from first user message if still "New Chat"
        if session["title"] == "New Chat" and message.get("role") == "user":
            # Use first 50 chars of user message as title
            content = message.get("content", "")
            session["title"] = content[:50] + ("..." if len(content) > 50 else "")
        
        # Save to file
        session_path = self._get_session_path(session_id)
        try:
            with open(session_path, 'w') as f:
                json.dump(session, f, indent=2)
            return True
        except Exception as e:
            logger.error(f"Error saving session {session_id}: {e}")
            return False
    
    def update_session_title(self, session_id: str, title: str) -> bool:
        """
        Update a session's title.
        
        Args:
            session_id: Session ID
            title: New title
            
        Returns:
            True if successful, False otherwise
        """
        session = self.get_session(session_id)
        
        if not session:
            logger.error(f"Cannot update title - session not found: {session_id}")
            return False
        
        session["title"] = title
        session["updated_at"] = datetime.utcnow().isoformat() + "Z"
        
        # Save to file
        session_path = self._get_session_path(session_id)
        try:
            with open(session_path, 'w') as f:
                json.dump(session, f, indent=2)
            return True
        except Exception as e:
            logger.error(f"Error updating session title {session_id}: {e}")
            return False
    
    def get_session_context(self, session_id: str, last_n: int = 5) -> List[Dict[str, Any]]:
        """
        Get the last N messages from a session for LLM context.
        
        This returns a simplified version of messages suitable for passing to LLM:
        - User messages: role + content
        - Assistant messages: role + content + SQL (from responseMeta)
        
        Args:
            session_id: Session ID
            last_n: Number of recent messages to return
            
        Returns:
            List of message dicts for context
        """
        session = self.get_session(session_id)
        
        if not session:
            return []
        
        messages = session.get("messages", [])
        recent_messages = messages[-last_n:] if len(messages) > last_n else messages
        
        # Simplify messages for context
        context_messages = []
        for msg in recent_messages:
            context_msg = {
                "role": msg.get("role"),
                "content": msg.get("content")
            }
            
            # Include SQL for assistant messages (for follow-up understanding)
            if msg.get("role") == "assistant" and msg.get("responseMeta"):
                sql = msg["responseMeta"].get("generatedSql")
                if sql:
                    context_msg["sql"] = sql
            
            context_messages.append(context_msg)
        
        return context_messages
    
    def delete_session(self, session_id: str) -> bool:
        """
        Delete a session.
        
        Args:
            session_id: Session ID to delete
            
        Returns:
            True if successful, False otherwise
        """
        session_path = self._get_session_path(session_id)
        
        if not session_path.exists():
            logger.warning(f"Cannot delete - session not found: {session_id}")
            return False
        
        try:
            session_path.unlink()
            logger.info(f"Deleted session: {session_id}")
            return True
        except Exception as e:
            logger.error(f"Error deleting session {session_id}: {e}")
            return False
    
    def get_last_query_context(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the most recent assistant message's full context for follow-up processing.
        
        Args:
            session_id: Session ID
            
        Returns:
            Dict containing responseMeta from last assistant message, or None if not found
        """
        session = self.get_session(session_id)
        
        if not session:
            return None
        
        messages = session.get("messages", [])
        
        # Find last assistant message
        for msg in reversed(messages):
            if msg.get("role") == "assistant" and msg.get("responseMeta"):
                context = msg["responseMeta"].copy()
                # Add the original user query for reference
                context["original_user_query"] = msg.get("content", "")
                return context
        
        logger.warning(f"No assistant message with context found in session {session_id}")
        return None
    
    def get_context_for_followup(self, session_id: str, user_query: str, max_lookback: int = 5) -> Optional[Dict[str, Any]]:
        """
        Intelligently retrieve relevant context for a follow-up query.
        Uses keyword matching to find the most relevant previous query.
        
        Args:
            session_id: Session ID
            user_query: Current follow-up query from user
            max_lookback: Maximum number of messages to analyze
            
        Returns:
            Dict with keys: 'context' (responseMeta), 'original_query', 'message_index'
            Returns None if no relevant context found
        """
        session = self.get_session(session_id)
        
        if not session:
            return None
        
        messages = session.get("messages", [])
        
        if len(messages) == 0:
            return None
        
        # Get recent messages (limit lookback)
        recent_messages = messages[-max_lookback*2:] if len(messages) > max_lookback*2 else messages
        
        # Extract keywords from user query for relevance matching
        query_lower = user_query.lower()
        keywords = []
        
        # Extract potential filter keywords
        for word in ['2024', '2023', '2022', 'category', 'department', 'vendor', 'item', 'cancelled', 'open', 'closed']:
            if word in query_lower:
                keywords.append(word)
        
        # Find most relevant assistant message
        best_match = None
        best_score = 0
        
        for i, msg in enumerate(reversed(recent_messages)):
            if msg.get("role") == "assistant" and msg.get("responseMeta"):
                score = 0
                
                # Score based on keyword overlap in original query and SQL
                msg_content = (msg.get("content", "") + " " + 
                              msg.get("responseMeta", {}).get("generatedSql", "")).lower()
                
                for keyword in keywords:
                    if keyword in msg_content:
                        score += 1
                
                # Boost score for most recent message (recency bias)
                if i == 0:
                    score += 0.5
                
                if score > best_score:
                    best_score = score
                    best_match = {
                        "context": msg["responseMeta"],
                        "original_query": msg.get("content", ""),
                        "message_index": len(recent_messages) - i - 1
                    }
        
        # If no keyword matches, just return the last assistant message
        if not best_match:
            for msg in reversed(messages):
                if msg.get("role") == "assistant" and msg.get("responseMeta"):
                    return {
                        "context": msg["responseMeta"],
                        "original_query": msg.get("content", ""),
                        "message_index": 0
                    }
        
        return best_match
    
    def update_last_message_feedback(self, session_id: str, feedback: str) -> bool:
        """
        Store user feedback/corrections in the last assistant message.
        
        Args:
            session_id: Session ID
            feedback: User feedback or correction text
            
        Returns:
            True if successful, False otherwise
        """
        session = self.get_session(session_id)
        
        if not session:
            logger.error(f"Cannot update feedback - session not found: {session_id}")
            return False
        
        messages = session.get("messages", [])
        
        # Find last assistant message
        for i in range(len(messages) - 1, -1, -1):
            if messages[i].get("role") == "assistant":
                # Initialize responseMeta if it doesn't exist
                if "responseMeta" not in messages[i]:
                    messages[i]["responseMeta"] = {}
                
                # Add user feedback
                messages[i]["responseMeta"]["userFeedback"] = feedback
                
                # Save updated session
                session["updated_at"] = datetime.utcnow().isoformat() + "Z"
                session_path = self._get_session_path(session_id)
                
                try:
                    with open(session_path, 'w') as f:
                        json.dump(session, f, indent=2)
                    logger.info(f"Updated feedback for session {session_id}")
                    return True
                except Exception as e:
                    logger.error(f"Error saving feedback for session {session_id}: {e}")
                    return False
        
        logger.warning(f"No assistant message found to update in session {session_id}")
        return False
    

