import os
import json
from fastapi import APIRouter, HTTPException

router = APIRouter()

# Đường dẫn file JSON đã xử lý
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
JSON_FILE_PATH = os.path.join(BASE_DIR, "data", "processed", "processed_risk_zones.json")

@router.get("/zones")
async def get_risk_zones():
    """
    Trả về dữ liệu bản đồ từ file JSON tĩnh đã được xử lý bởi AI Backend.
    """
    if not os.path.exists(JSON_FILE_PATH):
        # Nếu chưa có file, trả về rỗng hoặc gọi hàm xử lý ngay lập tức (tuỳ chọn)
        return {"type": "FeatureCollection", "features": [], "message": "Data not ready yet"}

    try:
        with open(JSON_FILE_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading map data: {e}")