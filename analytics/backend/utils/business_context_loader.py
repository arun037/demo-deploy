"""
Business Context Loader Utility
Loads business context from JSON configuration file
"""
import json
import os
from backend.core.logger import logger

class BusinessContextLoader:
    """Loads and caches business context from configuration file."""
    
    _context_cache = None
    _config_path = None
    
    @classmethod
    def load_context(cls, config_path: str = None) -> str:
        """
        Load business context from JSON file.
        
        Args:
            config_path: Path to business_context.json file. 
                        If None, uses default path in backend directory.
        
        Returns:
            str: Business context description in human-readable format
        """
        # Use default path if not specified
        if config_path is None:
            backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            config_path = os.path.join(backend_dir, 'business_context.json')
        
        # Return cached context if already loaded and path hasn't changed
        if cls._context_cache is not None and cls._config_path == config_path:
            return cls._context_cache
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            context_parts = []
            
            # Phase 3 JSON Support: Parse structured sections
            if "domain_summary" in data:
                context_parts.append(f"DOMAIN SUMMARY:\n{data['domain_summary']}\n")
                
            if "kpi_definitions" in data and isinstance(data["kpi_definitions"], dict):
                context_parts.append("KPI DEFINITIONS:")
                for k, v in data["kpi_definitions"].items():
                    context_parts.append(f"- {k}: {v}")
                context_parts.append("")
                
            if "business_facts" in data and isinstance(data["business_facts"], list):
                context_parts.append("BUSINESS FACTS & DOMAIN KNOWLEDGE:")
                for rule in data["business_facts"]:
                    context_parts.append(f"- {rule}")
                context_parts.append("")

            # Fallback to old format if new fields don't exist
            if not context_parts and "description" in data:
                context_parts.append(data.get('description', ''))

            context = "\n".join(context_parts).strip()

            if not context:
                logger.warning("Business context is empty or unparsable")
                return ""

            # Cache the context
            cls._context_cache = context
            cls._config_path = config_path

            logger.info(f"Business context loaded successfully ({len(context)} chars)")
            return context
            
        except FileNotFoundError:
            logger.error(f"Business context file not found: {config_path}")
            return ""
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in business context file: {e}")
            return ""
        except Exception as e:
            logger.error(f"Error loading business context: {e}")
            return ""
    
    @classmethod
    def reload_context(cls, config_path: str = None) -> str:
        """
        Force reload of business context (clears cache).
        
        Args:
            config_path: Path to business_context.json file
        
        Returns:
            str: Reloaded business context
        """
        cls._context_cache = None
        cls._config_path = None
        return cls.load_context(config_path)
