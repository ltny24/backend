from fastapi import APIRouter
from pydantic import BaseModel
import requests
import random  # <--- Import thư viện random
from app.core.database import get_active_risks
from app.core.config import OWM_API_KEYS_LIST # <--- Import danh sách Key

router = APIRouter()

class UserLocationReq(BaseModel):
    lat: float
    lon: float

@router.post("/update-location")
async def get_live_data(data: UserLocationReq):
    """
    Trả về dữ liệu tổng hợp:
    1. Thời tiết Live (Dùng Random Key để tránh lỗi 429 Too Many Requests).
    2. Cảnh báo thiên tai từ DB.
    """
    
    # 1. Gọi OWM API (Live Weather)
    weather_info = {}
    try:
        # --- LOGIC MỚI: Chọn ngẫu nhiên 1 key ---
        current_api_key = random.choice(OWM_API_KEYS_LIST)
        
        url = f"https://api.openweathermap.org/data/2.5/weather?lat={data.lat}&lon={data.lon}&appid={current_api_key}&units=metric&lang=vi"
        
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            d = resp.json()
            weather_info = {
                "temp": d["main"]["temp"],
                "desc": d["weather"][0]["description"],
                "icon": d["weather"][0]["icon"],
                "humidity": d["main"]["humidity"],
                "wind": d["wind"]["speed"],
                "name": d.get("name", "") # Lấy tên địa điểm từ OWM nếu có
            }
        else:
            print(f"⚠️ OWM Error {resp.status_code}: {resp.text}")
            
    except Exception as e:
        print(f"❌ Lỗi kết nối OWM: {e}")

    # 2. Lấy cảnh báo từ DB (Giữ nguyên)
    alerts = get_active_risks(lat=data.lat, lon=data.lon, radius_km=50)

    return {
        "status": "success",
        "live_weather": weather_info,
        "nearby_alerts": alerts,
        "alert_count": len(alerts)
    }