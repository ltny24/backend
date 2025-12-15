# backend/app/routers/system.py
from fastapi import APIRouter, BackgroundTasks
from process_data_integrated import run_processing_pipeline

router = APIRouter()

@router.post("/trigger-processing")
async def trigger_ai_processing(background_tasks: BackgroundTasks):
    """
    API để Data Collector gọi sau khi thu thập xong.
    Nó sẽ chạy script xử lý AI dưới nền (Background).
    """
    background_tasks.add_task(run_processing_pipeline)
    return {"status": "success", "message": "AI Processing started in background"}