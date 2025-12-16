import sys
import os
import logging
import uvicorn
import warnings
from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

# --- 1. IMPORT DATABASE & MODELS ---
from app.database import engine, Base
from app.models import User, EmergencyContact, MedicalInfo, SavedLocation, UserLog

# --- TẮT CẢNH BÁO RÁC ---
warnings.filterwarnings("ignore")

logger = logging.getLogger(__name__)

# --- Cấu hình đường dẫn ---
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# --- Import các router cũ ---
from app.routers import (
    map_risk,
    ai_score,
    login_register,
    ai_hazard,
    rescue,
    live_data,
    system,
    alerts,
    user_alerts,
    forecast_7day,
    sos,
    past_hazards
)

# --- Import router mới (Import riêng để tránh lỗi vòng lặp) ---
from app.profile_data import router as profile_router
# --- 2. TẠO BẢNG ---
Base.metadata.create_all(bind=engine)

# --- Khởi tạo App ---
app = FastAPI(
    title="Travel Safety Integrated System",
    description="Backend hợp nhất GIS (Bản đồ), AI (Dự báo) và Live Data",
    version="2.0.0"
)

# --- CẤU HÌNH MIDDLEWARE ---
app.add_middleware(SessionMiddleware, secret_key="your-secret-key-change-in-production")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "https://travel-safety.vercel.app",
        "https://travel-safety-nhom3.vercel.app",
    ],
    allow_origin_regex=r"https://.*\.vercel\.app", 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Xử lý lỗi ---
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    logger.error(f"Validation error: {exc}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": exc.errors(), "body": str(exc)},
    )

# --- Đăng ký Router ---
app.include_router(map_risk.router, prefix="/api/v1/map", tags=["Map & GIS"])
app.include_router(ai_score.router, prefix="/api/v1/ai", tags=["AI Safety Prediction"])
app.include_router(ai_hazard.router, prefix="/api/v1/hazard", tags=["AI Hazard Prediction"])
app.include_router(login_register.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(rescue.router, prefix="/api/v1/rescue", tags=["Rescue Finder"])
app.include_router(live_data.router, prefix="/api/v1/live", tags=["Live Data"])
app.include_router(system.router, prefix="/api/v1/system", tags=["System Operations"])
app.include_router(alerts.router, prefix="/api/v1/alerts", tags=["Alert Hub"])
app.include_router(user_alerts.router, prefix="/api/user", tags=["User Alerts & Preferences"])
app.include_router(forecast_7day.router, prefix="/api/v1/forecast", tags=["7-Day Forecast"])
app.include_router(sos.router, prefix="/api/v1/sos", tags=["SOS & Emergency"])
app.include_router(past_hazards.router, prefix="/api/v1/hazards/past", tags=["Past Hazards Statistics"])

# --- SỬA DÒNG NÀY (Dùng biến profile_router) ---
app.include_router(profile_router, prefix="/api/v1/profile", tags=["User Profile Data"])

@app.get("/")
def health_check():
    return {"status": "ok", "message": "Travel Safety Backend is Running 🚀"}

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)