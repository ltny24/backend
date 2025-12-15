from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import List, Optional
import pandas as pd
import os
from datetime import datetime
import sys
import time

# Import function từ predict module
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
try:
    from predict.seven_days_predict import generate_forecast_for_location
except ImportError as e:
    print(f"Warning: Could not import forecast generator: {e}")
    generate_forecast_for_location = None

router = APIRouter()

# Simple in-memory cache for generated forecasts to avoid repeated slow API calls
_forecast_cache = {}
# cache structure: {(lat,lon): (timestamp_seconds, dataframe)}
# TTL in seconds
_FORECAST_CACHE_TTL = 600

# Đường dẫn tới file dữ liệu dự đoán 7 ngày (fallback)
FORECAST_DATA_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "final_7day_forecast.csv"
)

# ============= MODELS (Pydantic) =============

class ForecastDay(BaseModel):
    """Model cho mỗi ngày dự đoán"""
    date: str
    temp_avg: float
    temp_min: Optional[float] = None
    temp_max: Optional[float] = None
    humidity: Optional[float] = None
    overall_hazard: str
    rain_hazard: str
    wind_hazard: str
    storm_hazard: str
    flood_hazard: str
    earthquake_hazard: str

class ForecastResponse(BaseModel):
    """Response tổng hợp dữ liệu dự đoán 7 ngày"""
    success: bool
    message: str
    count: int
    data: List[ForecastDay]
    location: Optional[dict] = None

# ============= HÀM HỖ TRỢ =============

def load_forecast_data() -> pd.DataFrame:
    """Đọc dữ liệu dự đoán từ CSV"""
    if not os.path.exists(FORECAST_DATA_PATH):
        raise FileNotFoundError(f"Dữ liệu dự đoán không tìm thấy: {FORECAST_DATA_PATH}")
    
    df = pd.read_csv(FORECAST_DATA_PATH)
    return df

# ============= API ENDPOINTS =============

@router.get("/", response_model=ForecastResponse, tags=["Forecast"])
async def get_7day_forecast(
    lat: Optional[float] = Query(None, description="Latitude"),
    lon: Optional[float] = Query(None, description="Longitude"),
) -> ForecastResponse:
    """
    Lấy dữ liệu dự đoán 7 ngày (Nhiệt độ, Độ ẩm, Mức độ nguy hiểm)
    
    **Query Parameters:**
    - `lat` (optional): Vĩ độ để generate dữ liệu
    - `lon` (optional): Kinh độ để generate dữ liệu
    
    **Response:**
    - Danh sách 7 ngày với nhiệt độ, độ ẩm, mức độ nguy hiểm (Mưa, Gió, Bão, Lụt, Động đất)
    """
    try:
        # Nếu có tọa độ, generate forecast cho tọa độ đó
        if lat is not None and lon is not None:
            if generate_forecast_for_location is None:
                raise HTTPException(status_code=500, detail="Forecast generator không khả dụng")
            
            print(f"🎯 Generating forecast for: {lat}, {lon}")
            # Check in-memory cache first
            key = (round(float(lat), 5), round(float(lon), 5))
            now_ts = time.time()
            cached = _forecast_cache.get(key)
            if cached and (now_ts - cached[0] < _FORECAST_CACHE_TTL):
                print("🔁 Using cached forecast")
                df = cached[1]
            else:
                df = generate_forecast_for_location(lat, lon)
                try:
                    _forecast_cache[key] = (now_ts, df)
                except Exception:
                    pass
        else:
            # Fallback: đọc từ CSV
            print("📂 Using fallback CSV data")
            if not os.path.exists(FORECAST_DATA_PATH):
                raise FileNotFoundError(f"Dữ liệu dự đoán không tìm thấy: {FORECAST_DATA_PATH}")
            df = pd.read_csv(FORECAST_DATA_PATH)
        
        if df.empty:
            raise HTTPException(status_code=404, detail="Không có dữ liệu dự đoán")
        
        # Sắp xếp theo ngày
        df = df.sort_values('date')
        
        # Chuyển đổi sang format response
        forecast_days = []
        for _, row in df.iterrows():
            forecast_days.append(ForecastDay(
                date=str(row['date']),
                temp_avg=float(row['temp_avg']),
                temp_min=float(row['temp_min']) if 'temp_min' in row and pd.notna(row['temp_min']) else None,
                temp_max=float(row['temp_max']) if 'temp_max' in row and pd.notna(row['temp_max']) else None,
                humidity=float(row['humidity']) if pd.notna(row['humidity']) else None,
                overall_hazard=str(row['overall_hazard_ml']),  # Dùng ML model predictions
                rain_hazard=str(row['rain_label_rule']),
                wind_hazard=str(row['wind_label_rule']),
                storm_hazard=str(row['storm_label_rule']),
                flood_hazard=str(row['flood_label_rule']),
                earthquake_hazard=str(row['earthquake_label_rule']),
            ))
        
        return ForecastResponse(
            success=True,
            message="Lấy dữ liệu dự đoán 7 ngày thành công",
            count=len(forecast_days),
            data=forecast_days,
            location={
                "latitude": float(df.iloc[0]['lat']),
                "longitude": float(df.iloc[0]['lon'])
            }
        )
    
    except FileNotFoundError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        print(f"❌ Error in forecast endpoint: {e}")
        raise HTTPException(status_code=500, detail=f"Lỗi khi lấy dữ liệu: {str(e)}")

@router.get("/summary", response_model=dict, tags=["Forecast"])
async def get_7day_forecast_summary() -> dict:
    """
    Lấy thông tin tóm tắt dự đoán 7 ngày
    
    **Response:**
    - Thống kê mức độ nguy hiểm, ngày nguy hiểm nhất
    """
    try:
        df = load_forecast_data()
        
        if df.empty:
            raise HTTPException(status_code=404, detail="Không có dữ liệu dự đoán")
        
        # Tìm ngày nguy hiểm nhất (dựa trên mức độ nguy hiểm)
        hazard_priority = {"high": 4, "mid-high": 3, "mid": 2, "low": 1, "no": 0}
        df['max_hazard_score'] = df[[
            'rain_label_rule', 'wind_label_rule', 'storm_label_rule', 
            'flood_label_rule', 'earthquake_label_rule'
        ]].applymap(lambda x: hazard_priority.get(str(x).lower(), 0)).max(axis=1)
        
        worst_day_idx = df['max_hazard_score'].idxmax()
        worst_row = df.loc[worst_day_idx]
        
        return {
            "success": True,
            "message": "Lấy thông tin tóm tắt thành công",
            "worst_day": {
                "date": str(worst_row['date']),
                "temp_avg": float(worst_row['temp_avg']),
                "rain_hazard": str(worst_row['rain_label_rule']),
                "wind_hazard": str(worst_row['wind_label_rule']),
                "storm_hazard": str(worst_row['storm_label_rule']),
                "flood_hazard": str(worst_row['flood_label_rule']),
                "earthquake_hazard": str(worst_row['earthquake_label_rule']),
            },
            "hazards_count": {
                "high": len(df[df['max_hazard_score'] == 4]),
                "mid-high": len(df[df['max_hazard_score'] == 3]),
                "mid": len(df[df['max_hazard_score'] == 2]),
                "low": len(df[df['max_hazard_score'] == 1]),
                "no": len(df[df['max_hazard_score'] == 0]),
            }
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi khi lấy thông tin tóm tắt: {str(e)}")

@router.get("/chart-data", tags=["Forecast"])
async def get_7day_forecast_chart_data():
    """
    Lấy dữ liệu dự đoán 7 ngày trong format phù hợp để vẽ biểu đồ
    
    **Response:**
    - Các mảng dữ liệu (dates, temp, hazards) để vẽ Chart
    """
    try:
        df = load_forecast_data()
        
        if df.empty:
            raise HTTPException(status_code=404, detail="Không có dữ liệu dự đoán")
        
        # Chuẩn bị dữ liệu cho biểu đồ
        chart_data = {
            "dates": df['date'].astype(str).tolist(),
            "temperature": df['temp_avg'].tolist(),
            "temp_min": df['temp_min'].tolist() if 'temp_min' in df.columns else [],
            "temp_max": df['temp_max'].tolist() if 'temp_max' in df.columns else [],
            "hazards": {
                "rain": df['rain_label_rule'].astype(str).tolist(),
                "wind": df['wind_label_rule'].astype(str).tolist(),
                "storm": df['storm_label_rule'].astype(str).tolist(),
                "flood": df['flood_label_rule'].astype(str).tolist(),
                "earthquake": df['earthquake_label_rule'].astype(str).tolist(),
            }
        }
        
        return {
            "success": True,
            "message": "Lấy dữ liệu biểu đồ thành công",
            "data": chart_data
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi khi lấy dữ liệu biểu đồ: {str(e)}")

@router.get("/hazard-levels", tags=["Forecast"])
async def get_7day_hazard_levels():
    """
    Lấy mức độ nguy hiểm của 7 ngày dự đoán
    
    **Response:**
    - Mức độ nguy hiểm (No, Low, Mid, Mid-High, High) cho mỗi loại nguy hiểm
    """
    try:
        df = load_forecast_data()
        
        if df.empty:
            raise HTTPException(status_code=404, detail="Không có dữ liệu dự đoán")
        
        hazard_levels = {
            "by_date": [],
        }
        
        # Chi tiết theo ngày
        for idx, row in df.iterrows():
            hazard_levels["by_date"].append({
                "date": str(row['date']),
                "rain": str(row['rain_label_rule']),
                "wind": str(row['wind_label_rule']),
                "storm": str(row['storm_label_rule']),
                "flood": str(row['flood_label_rule']),
                "earthquake": str(row['earthquake_label_rule']),
            })
        
        return {
            "success": True,
            "message": "Lấy mức độ nguy hiểm thành công",
            "data": hazard_levels
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi khi lấy mức độ nguy hiểm: {str(e)}")
