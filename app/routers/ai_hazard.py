from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from app.ml.predictor_hazard import HazardPredictor
from app.core.database import fetch_latest_weather_data # Hàm lấy dữ liệu thật

router = APIRouter()

# Khởi tạo model một lần duy nhất
try:
    model = HazardPredictor()
except Exception as e:
    print(f"⚠️ Model init failed: {e}")
    model = None

# --- Input: Chỉ cần tọa độ ---
class LocationReq(BaseModel):
    lat: float
    lon: float

# --- Output: Kết quả dự báo ---
class HazardResponse(BaseModel):
    overall_hazard: str # Kết quả dự báo (Storm, Rain...)
    confidence: str     # Độ tin cậy (High/Medium...)
    real_data_used: Optional[dict] = None # Trả về dữ liệu thật đã dùng để debug

@router.post("/predict", response_model=HazardResponse)
async def predict_hazard(req: LocationReq):
    """
    1. Nhận toạ độ từ Frontend.
    2. Lấy dữ liệu thời tiết MỚI NHẤT từ Database (bảng events).
    3. Đưa vào Model XGBoost để dự đoán.
    """
    if not model:
        raise HTTPException(status_code=500, detail="AI Model chưa được tải.")

    # BƯỚC 1: Lấy dữ liệu thật từ DB
    db_data = fetch_latest_weather_data(req.lat, req.lon)
    
    if not db_data:
        # Nếu chưa có dữ liệu trong DB (vùng này chưa được Data Collector quét)
        return HazardResponse(
            overall_hazard="Unknown", 
            confidence="Low (No Data)",
            real_data_used={}
        )

    try:
        # BƯỚC 2: Gọi Model dự đoán
        # db_data chính là raw_data từ DB, chứa: temperature, humidity, wind_speed...
        # Class HazardPredictor sẽ tự lọc các trường cần thiết.
        prediction = model.predict_overall_hazard(db_data)
        
        # BƯỚC 3: Trả về kết quả
        return HazardResponse(
            overall_hazard=prediction, 
            confidence="High", # Model XGBoost thường có độ tin cậy cao nếu có data
            real_data_used=db_data # Show dữ liệu thật cho Frontend biết
        )

    except Exception as e:
        print(f"Prediction Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))