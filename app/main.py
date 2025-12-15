import sys
import os
from fastapi import FastAPI
import uvicorn
from pydantic import BaseModel, EmailStr
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from typing import Optional
from fastapi.exceptions import RequestValidationError
from fastapi import status
from fastapi.responses import JSONResponse
import logging

logger = logging.getLogger(__name__)

# --- Cấu hình đường dẫn ---
# Giúp Python nhìn thấy thư mục gốc 'backend' để import module
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# --- Import các router ---
# LƯU Ý: Phải đảm bảo tất cả các file này đều tồn tại trong thư mục app/routers/
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
    user_alerts,
    past_hazards
)

# --- Các Class Model (Có thể giữ lại hoặc chuyển sang schemas.py) ---
class SignUpRequest(BaseModel):
    email: EmailStr
    password: str
    first_name: str
    last_name: str
    phone_number: str

class SignInRequest(BaseModel):
    email: EmailStr
    password: str

class AuthResponse(BaseModel):
    success: bool
    message: str
    access_token: Optional[str] = None
    user: Optional[dict] = None

# --- Khởi tạo App ---
app = FastAPI(
    title="Travel Safety Integrated System",
    description="Backend hợp nhất GIS (Bản đồ), AI (Dự báo) và Live Data",
    version="2.0.0"
)

app.add_middleware(SessionMiddleware, secret_key="your-secret-key-change-in-production")

# Cấu hình CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Exception handler for validation errors
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    logger.error(f"Validation error: {exc}")
    logger.error(f"Request body: {request.body if hasattr(request, 'body') else 'N/A'}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": exc.errors(),
            "body": str(exc)
        },
    )

# --- Đăng ký Router (Gắn API vào App) ---

# 1. Router Bản đồ -> /api/v1/map/...
app.include_router(map_risk.router, prefix="/api/v1/map", tags=["Map & GIS"])

# 2. Router AI Safety Score -> /api/v1/ai/...
app.include_router(ai_score.router, prefix="/api/v1/ai", tags=["AI Safety Prediction"])

# 3. Router AI Hazard Prediction -> /api/v1/hazard/...
app.include_router(ai_hazard.router, prefix="/api/v1/hazard", tags=["AI Hazard Prediction"])

# 4. Router Authentication -> /api/auth/...
app.include_router(login_register.router, prefix="/api/auth", tags=["Authentication"])

# 5. Router Cứu hộ -> /api/v1/rescue/...
app.include_router(rescue.router, prefix="/api/v1/rescue", tags=["Rescue Finder"])

# 6. Router Live Data (Thời tiết thật + Cảnh báo) -> /api/v1/live/... 
# [QUAN TRỌNG] Cái này cần cho trang Home
app.include_router(live_data.router, prefix="/api/v1/live", tags=["Live Data"])

# 7. Router System (Trigger xử lý dữ liệu) -> /api/v1/system/...
# Dùng để Data Collector gọi sau khi thu thập xong
app.include_router(system.router, prefix="/api/v1/system", tags=["System Operations"])

# 8. Router Alert Hub -> /api/v1/alerts/...
app.include_router(alerts.router, prefix="/api/v1/alerts", tags=["Alert Hub"])

# 9. Router User Alerts Management -> /api/user/...
app.include_router(user_alerts.router, prefix="/api/user", tags=["User Alerts & Preferences"])
# 10. Router 7-Day Forecast -> /api/v1/forecast/...
app.include_router(forecast_7day.router, prefix="/api/v1/forecast", tags=["7-Day Forecast"])
# 11. Router SOS -> /api/v1/sos/...
app.include_router(sos.router, prefix="/api/v1/sos", tags=["SOS & Emergency"])
# 12. User alert preferences -> /api/user/...
app.include_router(user_alerts.router, prefix="/api/user", tags=["User Alerts & Preferences"])
# 13. Router Past Hazards -> /api/v1/hazards/...
app.include_router(past_hazards.router, prefix="/api/v1/hazards/past", tags=["Past Hazards Statistics"])

@app.get("/")
def health_check():
    return {"status": "ok", "message": "Travel Safety Backend is Running 🚀"}

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)