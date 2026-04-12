import uuid
from datetime import datetime
from threading import Lock
from typing import Dict, Optional, Any

class JobStore:
    """
    Thread-safe in-memory store for AI Insight Jobs.
    Statuses: 'queued', 'profiling', 'planning', 'training', 'completed', 'failed'
    """
    _jobs: Dict[str, Dict[str, Any]] = {}
    _lock = Lock()

    @classmethod
    def create_job(cls, job_type: str = "insight_generation") -> str:
        job_id = str(uuid.uuid4())
        with cls._lock:
            cls._jobs[job_id] = {
                "id": job_id,
                "type": job_type,
                "status": "queued",
                "progress": 0,
                "message": "Job initialized",
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "result": None,
                "error": None,
                "artifacts": {}
            }
        return job_id

    @classmethod
    def update_job(cls, job_id: str, status: Optional[str] = None, 
                   progress: Optional[int] = None, 
                   message: Optional[str] = None,
                   result: Optional[Any] = None,
                   error: Optional[str] = None,
                   artifacts: Optional[Dict] = None):
        with cls._lock:
            if job_id not in cls._jobs:
                return # Or raise error
            
            job = cls._jobs[job_id]
            if status: job["status"] = status
            if progress is not None: job["progress"] = progress
            if message: job["message"] = message
            if result: job["result"] = result
            if error: job["error"] = error
            if artifacts: job["artifacts"].update(artifacts)
            
            job["updated_at"] = datetime.now().isoformat()

    @classmethod
    def get_job(cls, job_id: str) -> Optional[Dict[str, Any]]:
        with cls._lock:
            return cls._jobs.get(job_id)

    @classmethod
    def list_jobs(cls, limit: int = 10):
        with cls._lock:
            # Sort by created_at desc
            sorted_jobs = sorted(cls._jobs.values(), key=lambda x: x["created_at"], reverse=True)
            return sorted_jobs[:limit]
