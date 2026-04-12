import logging
import sys
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

# Suppress noisy third-party loggers
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

logger = logging.getLogger("SQL_Swarm")

class WebSocketLogger:
    """Logger that sends messages to WebSocket clients"""
    
    def __init__(self, websocket=None):
        self.websocket = websocket
        self.logs = []
    
    async def log(self, phase, message, data=None, level="info"):
        """Log a message and optionally send to WebSocket"""
        
        # Define colors for different phases
        COLORS = {
            "INTENT": "\033[95m",   # Purple
            "SCHEMA": "\033[96m",   # Cyan
            "PLANNER": "\033[94m",  # Blue
            "SQL": "\033[93m",      # Yellow
            "EXECUTION": "\033[92m", # Green
            "RESPONSE": "\033[97m", # White
            "INSIGHTS": "\033[91m", # Red (for visibility)
            "RESET": "\033[0m"
        }
        
        color = COLORS.get(phase.upper(), COLORS["RESET"])
        
        log_entry = {
            "type": "log",
            "phase": phase,
            "message": message,
            "data": data or {},
            "timestamp": datetime.utcnow().isoformat(),
            "level": level
        }
        
        self.logs.append(log_entry)
        
        # Also log to console with color
        try:
            # Check if this is a "structured" log with a specific phase prefix
            prefix = f"{color}[{phase}]{COLORS['RESET']}"
            logger.info(f"{prefix} {message}")
        except:
             logger.info(f"[{phase}] {message}")
        
        # Send to WebSocket if available
        if self.websocket:
            try:
                await self.websocket.send_json(log_entry)
            except Exception as e:
                logger.error(f"Failed to send WebSocket message: {e}")
    
    def get_logs(self):
        """Get all collected logs"""
        return self.logs
