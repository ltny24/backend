import sys
import os
import logging
import uvicorn
import warnings # <--- Thêm thư viện này để tắt cảnh báo rác
from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from app.models import User, EmergencyContact, MedicalInfo, SavedLocation 

# ...

# Lệnh này sẽ kiểm tra: Bảng nào chưa có thì tạo mới ngay lập tức
Base.metadata.create_all(bind=engine)
# --- IMPORT DATABASE ---
from app.database import engine, Base
from app.models import User

# --- TẮT CẢNH BÁO PHIÊN BẢN (Để Log sạch đẹp hơn) ---
warnings.filterwarnings("ignore") 

logger = logging.getLogger(__name__)

# --- Cấu hình đường dẫn ---
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# --- Import các router ---
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

# --- TẠO BẢNG TRONG DATABASE ---
# Lệnh này tự động tạo bảng 'users' và các bảng khác nếu chưa có
Base.metadata.create_all(bind=engine)

# --- Khởi tạo App ---
app = FastAPI(
    title="Travel Safety Integrated System",
    description="Backend hợp nhất GIS (Bản đồ), AI (Dự báo) và Live Data",
    version="2.0.0"
)

# --- CẤU HÌNH MIDDLEWARE ---

# 1. Session (Cookie)
app.add_middleware(SessionMiddleware, secret_key="your-secret-key-change-in-production")

# 2. CORS (QUAN TRỌNG: Đã nâng cấp để chấp nhận mọi link Vercel)
app.add_middleware(
    CORSMiddleware,
    # Danh sách các tên miền cụ thể (Localhost và Domain chính)
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "https://travel-safety.vercel.app",
        "https://travel-safety-nhom3.vercel.app", # Thêm link nhóm cho chắc ăn
    ],
    # QUAN TRỌNG: Dòng này cho phép mọi subdomain của vercel (ví dụ: travel-safety-git-main...)
    # Giúp bạn không bao giờ bị lỗi CORS khi deploy bản thử nghiệm
    allow_origin_regex=r"https://.*\.vercel\.app", 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Xử lý lỗi (Exception Handler) ---
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    logger.error(f"Validation error: {exc}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": exc.errors(), "body": str(exc)},
    )

# --- Đăng ký Router ---

# 1. Router Bản đồ
app.include_router(map_risk.router, prefix="/api/v1/map", tags=["Map & GIS"])

# 2. Router AI Safety Score
app.include_router(ai_score.router, prefix="/api/v1/ai", tags=["AI Safety Prediction"])

# 3. Router AI Hazard Prediction
app.include_router(ai_hazard.router, prefix="/api/v1/hazard", tags=["AI Hazard Prediction"])

# 4. Router Authentication
app.include_router(login_register.router, prefix="/api/auth", tags=["Authentication"])

# 5. Router Cứu hộ
app.include_router(rescue.router, prefix="/api/v1/rescue", tags=["Rescue Finder"])

# 6. Router Live Data
app.include_router(live_data.router, prefix="/api/v1/live", tags=["Live Data"])

# 7. Router System
app.include_router(system.router, prefix="/api/v1/system", tags=["System Operations"])

# 8. Router Alert Hub
app.include_router(alerts.router, prefix="/api/v1/alerts", tags=["Alert Hub"])

# 9. Router User Alerts
app.include_router(user_alerts.router, prefix="/api/user", tags=["User Alerts & Preferences"])

# 10. Router 7-Day Forecast
app.include_router(forecast_7day.router, prefix="/api/v1/forecast", tags=["7-Day Forecast"])

# 11. Router SOS
app.include_router(sos.router, prefix="/api/v1/sos", tags=["SOS & Emergency"])

# 12. Router Past Hazards
app.include_router(past_hazards.router, prefix="/api/v1/hazards/past", tags=["Past Hazards Statistics"])

@app.get("/")
def health_check():
    return {"status": "ok", "message": "Travel Safety Backend is Running 🚀"}

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)