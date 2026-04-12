from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from typing import Dict, Any, List
from pydantic import BaseModel

from backend.core import DatabaseManager, LLMClient
from backend.ai_insights.orchestrator import InsightOrchestrator
from backend.ai_insights.job_store import JobStore
from backend.ai_insights.predictions import PredictionService

router = APIRouter(prefix="/api/insights", tags=["AI Insights"])

# Dependencies
# In a real app, use Dependency Injection properly. Here we instantiate for simplicity or use globals from main if available.
# But orchestrator needs db_manager and llm_client. 
# We'll use a helper to get them (or just instantiate new ones which is fine for Stateless LLM, but DB manager should be shared).
# For now, let's assume we can import the global instances from main, but circular imports are bad.
# Solution: Dependency injection via app state or just new instances for now (DB manager handles connection pooling).

def get_orchestrator():
    # Factory check
    db = DatabaseManager()
    llm = LLMClient()
    return InsightOrchestrator(db, llm)

def get_predictor():
    return PredictionService()

class InsightRequest(BaseModel):
    table_name: str

class PredictionRequest(BaseModel):
    input_data: Dict[str, Any]

@router.post("/generate", status_code=202)
def generate_insight(background_tasks: BackgroundTasks):
    """
    Starts the Autonomous AI Analysis in the background.
    Scans entire project and launches multiple jobs.
    """
    orchestrator = get_orchestrator()
    job_ids = orchestrator.start_autonomous_discovery(background_tasks)
    return {
        "message": "AI Chief Data Officer is scanning project for opportunities...",
        "jobs_started": len(job_ids), 
        "job_ids": job_ids
    }

@router.get("/jobs")
def list_jobs():
    """
    List recent insight jobs.
    """
    return JobStore.list_jobs()

@router.get("/jobs/{job_id}")
def get_job_status(job_id: str):
    """
    Get detailed status of a specific job.
    """
    job = JobStore.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job

@router.post("/predict/{job_id}")
def predict(job_id: str, request: PredictionRequest):
    """
    Run inference on a trained model.
    """
    predictor = get_predictor()
    result = predictor.predict(job_id, request.input_data)
    
    if result.get("status") == "failed":
        raise HTTPException(status_code=500, detail=result.get("error"))
        
    return result
