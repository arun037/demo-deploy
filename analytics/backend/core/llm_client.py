"""
LLM Client - Handles all LLM API calls via Novita AI or OpenRouter
Supports both Novita AI (preferred) and OpenRouter (fallback)
"""
import os
import requests
import json
from backend.config import Config
from backend.core.logger import logger

class LLMClient:
    def __init__(self):
        # Prioritize Novita API if available and enabled
        self.use_novita = Config.USE_NOVITA and bool(Config.NOVITA_API_KEY)
        
        if self.use_novita:
            self.api_key = Config.NOVITA_API_KEY
            base_url = Config.NOVITA_BASE_URL.rstrip('/')
            logger.info("Using Novita AI for LLM calls")
        else:
            self.api_key = Config.OPENROUTER_API_KEY
            base_url = Config.OPENROUTER_BASE_URL.rstrip('/')
            logger.info("Using OpenRouter for LLM calls")
            
        if not self.api_key:
            logger.warning("No API key set. LLM calls will fail.")
        
        self.endpoint = f"{base_url}/chat/completions"
        
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        
        # Add OpenRouter-specific headers if using OpenRouter
        if not self.use_novita:
            self.headers.update({
                "HTTP-Referer": os.getenv("OPENROUTER_REFERRER", ""),
                "X-Title": os.getenv("OPENROUTER_APP_NAME", "data-analytics")
            })
        
    def call_chat(self, messages, model=None, temperature=0.1, max_tokens=2000, timeout=60, return_usage=False):
        """
        Generic call to chat completion using requests.
        Supports both Novita AI and OpenRouter
        
        Args:
            return_usage: If True, returns (content, usage_dict). If False, returns just content.
        """
        if not self.api_key:
             return "Error: API key not configured." if not return_usage else ("Error: API key not configured.", None)

        payload = {
            "model": model or Config.MODEL_NAME,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False
        }

        try:
            logger.info(f"Sending request to {payload['model']}...")
            response = requests.post(self.endpoint, headers=self.headers, json=payload, timeout=timeout)
            
            response.raise_for_status()
            data = response.json()
            
            content = data['choices'][0]['message']['content']
            usage = data.get('usage', {})
            
            if return_usage:
                return content, usage
            return content
            
        except requests.exceptions.Timeout:
            logger.error(f"LLM call timed out after {timeout}s for model {payload['model']}")
            error_msg = f"Error: Request timed out after {timeout}s. Try simplifying your question."
            return error_msg if not return_usage else (error_msg, None)
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP Error: {e.response.status_code} - {e.response.text}")
            error_msg = f"Error calling LLM: {e.response.text}"
            return error_msg if not return_usage else (error_msg, None)
        except Exception as e:
            logger.error(f"LLM Call Failed: {e}")
            error_msg = f"Error: {str(e)}"
            return error_msg if not return_usage else (error_msg, None)

    def call_agent(self, system_prompt, user_query, temperature=0.1, model=None, timeout=60, agent_name=None, log_file=None, max_tokens=4000):
        """
        Convenience method for agent calls.
        agent_name is optional and used for logging/debugging purposes.
        log_file is optional path to CSV file for usage tracking. Defaults to logs/llm_usage.csv
        """
        if agent_name:
            logger.info(f"Agent call from: {agent_name}")
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_query}
        ]
        
        # Get response with usage data
        content, usage = self.call_chat(messages, model=model, temperature=temperature, max_tokens=max_tokens, timeout=timeout, return_usage=True)
        
        # Log usage if we have valid usage data
        if usage and agent_name:
            self._log_usage(
                agent_name=agent_name,
                model=model or Config.MODEL_NAME,
                usage=usage,
                log_file=log_file
            )
        
        return content
    
    def _log_usage(self, agent_name, model, usage, log_file=None):
        """
        Log token usage to CSV file.
        
        Args:
            agent_name: Name of the agent making the call
            model: Model name used
            usage: Usage dict from API response with prompt_tokens, completion_tokens, total_tokens
            log_file: Optional custom log file path. Defaults to logs/llm_usage.csv
        """
        import csv
        from datetime import datetime
        
        # Default log file
        if log_file is None:
            log_file = "logs/llm_usage.csv"
        
        # Ensure logs directory exists
        log_dir = os.path.dirname(log_file)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)
        
        # Check if file exists to determine if we need to write header
        file_exists = os.path.exists(log_file)
        
        try:
            with open(log_file, 'a', newline='') as f:
                writer = csv.writer(f)
                
                # Write header if file is new
                if not file_exists:
                    writer.writerow(['Timestamp', 'Agent', 'Model', 'Prompt Tokens', 'Completion Tokens', 'Total Tokens'])
                
                # Write usage data
                writer.writerow([
                    datetime.utcnow().isoformat(),
                    agent_name,
                    model,
                    usage.get('prompt_tokens', 0),
                    usage.get('completion_tokens', 0),
                    usage.get('total_tokens', 0)
                ])
                
            logger.debug(f"Logged usage: {agent_name} - {usage.get('total_tokens', 0)} tokens")
        except Exception as e:
            logger.error(f"Failed to log usage: {e}")
    
    def create_embedding(self, text, model=None):
        """
        Create embedding for text using Novita or OpenRouter embeddings API
        """
        if not self.api_key:
            logger.error("API key not configured")
            return []
        
        # Use configured embedding model if not specified
        if model is None:
            model = Config.EMBEDDING_MODEL if hasattr(Config, 'EMBEDDING_MODEL') else "text-embedding-3-small"
        
        # Determine base URL based on which API is being used
        if self.use_novita:
            base_url = Config.NOVITA_BASE_URL.rstrip('/')
        else:
            base_url = Config.OPENROUTER_BASE_URL.rstrip('/')
            
        embeddings_endpoint = f"{base_url}/embeddings"
        
        payload = {
            "model": model,
            "input": text
        }
        
        try:
            response = requests.post(embeddings_endpoint, headers=self.headers, json=payload, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            # Return embedding vector
            return data['data'][0]['embedding']
        except Exception as e:
            logger.error(f"Embedding creation failed: {e}")
            return []

