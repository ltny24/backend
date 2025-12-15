import os
from fastapi import APIRouter, HTTPException, Header, Request, Depends, status
from fastapi.responses import RedirectResponse, JSONResponse
from pydantic import BaseModel, EmailStr
from typing import Optional
from sqlalchemy.orm import Session

# --- IMPORT DATABASE & UTILS MỚI ---
from app.database import get_db  # Hàm lấy kết nối DB
from app.auth.auth_utils import (
    get_user_by_email, 
    create_new_user, 
    verify_password, 
    create_oauth_user
)

# Thử import oauth, nếu chưa cấu hình thì bỏ qua để tránh lỗi sập web
try:
    from app.auth.oauth_config import oauth
except ImportError:
    oauth = None

router = APIRouter()

# ---- 1. MODELS (Dữ liệu đầu vào/ra) ----
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
    user: Optional[dict] = None

# ---- 2. API ĐĂNG KÝ (SIGN UP) ----
@router.post("/signup", response_model=AuthResponse)
async def signup(request: SignUpRequest, db: Session = Depends(get_db)):
    """
    Đăng ký tài khoản mới và lưu vào PostgreSQL.
    """
    try:
        # 1. Kiểm tra email đã tồn tại chưa
        if get_user_by_email(db, request.email):
            raise HTTPException(status_code=400, detail="Email này đã được đăng ký")

        # 2. Tạo user mới vào Database
        new_user = create_new_user(
            db=db,
            email=request.email,
            password=request.password,
            first_name=request.first_name,
            last_name=request.last_name,
            phone=request.phone_number
        )
        
        return AuthResponse(
            success=True,
            message="Đăng ký thành công",
            user={
                "id": new_user.id,
                "email": new_user.email,
                "name": f"{new_user.first_name} {new_user.last_name}"
            }
        )
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi đăng ký: {str(e)}")

# ---- 3. API ĐĂNG NHẬP (SIGN IN) ----
@router.post("/signin", response_model=AuthResponse)
async def signin(data: SignInRequest, request: Request, db: Session = Depends(get_db)):
    """
    Đăng nhập và lưu trạng thái vào Cookie Session.
    """
    try:
        # 1. Tìm user trong DB
        user = get_user_by_email(db, data.email)
        
        # 2. Kiểm tra mật khẩu
        if not user or not user.password_hash or not verify_password(data.password, user.password_hash):
            raise HTTPException(status_code=401, detail="Email hoặc mật khẩu không đúng")
        
        # 3. Lưu thông tin vào Cookie (SessionMiddleware)
        # Cái này thay thế cho việc tạo token và lưu vào file json
        request.session["user_id"] = user.id
        request.session["user_email"] = user.email
        request.session["user_name"] = f"{user.first_name} {user.last_name}"
        
        return AuthResponse(
            success=True,
            message="Đăng nhập thành công",
            user={
                "id": user.id,
                "email": user.email,
                "name": f"{user.first_name} {user.last_name}"
            }
        )
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi đăng nhập: {str(e)}")

# ---- 4. API ĐĂNG XUẤT ----
@router.post("/logout")
async def logout(request: Request):
    """
    Xóa session cookie.
    """
    request.session.clear()
    return {"success": True, "message": "Đã đăng xuất"}

# ---- 5. API LẤY THÔNG TIN USER (ME) ----
@router.get("/me")
async def get_current_user(request: Request, db: Session = Depends(get_db)):
    """
    Lấy thông tin user từ Cookie Session hiện tại.
    """
    user_email = request.session.get("user_email")
    
    if not user_email:
        raise HTTPException(status_code=401, detail="Bạn chưa đăng nhập")
        
    user = get_user_by_email(db, user_email)
    if not user:
        request.session.clear()
        raise HTTPException(status_code=401, detail="User không tồn tại")
        
    return {
        "success": True,
        "user": {
            "id": user.id,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "phone": user.phone_number
        }
    }

# ---- 6. OAUTH ENDPOINTS (GOOGLE) ----
@router.get("/google/login")
async def google_login(request: Request):
    if not oauth:
        raise HTTPException(status_code=500, detail="OAuth chưa được cấu hình")
    
    # Redirect URI phải trùng với cái đã khai báo trên Google Cloud Console
    # Ví dụ: https://travel-safety-backend.onrender.com/api/auth/google/callback
    redirect_uri = request.url_for('google_callback')
    return await oauth.google.authorize_redirect(request, redirect_uri)

@router.get("/google/callback")
async def google_callback(request: Request, db: Session = Depends(get_db)):
    if not oauth:
        raise HTTPException(status_code=500, detail="OAuth lỗi")
        
    try:
        token = await oauth.google.authorize_access_token(request)
        user_info = token.get('userinfo')
        
        if not user_info:
            raise HTTPException(status_code=400, detail="Không lấy được thông tin từ Google")
        
        # Lấy thông tin
        email = user_info.get('email')
        first_name = user_info.get('given_name', '')
        last_name = user_info.get('family_name', '')
        
        # 1. Tìm hoặc Tạo user trong Database
        user = get_user_by_email(db, email)
        if not user:
            user = create_oauth_user(
                db=db,
                email=email,
                first_name=first_name,
                last_name=last_name
            )
        
        # 2. Lưu session đăng nhập
        request.session["user_id"] = user.id
        request.session["user_email"] = user.email
        request.session["user_name"] = f"{user.first_name} {user.last_name}"
        
        # 3. Redirect về Frontend (Vercel)
        # Thay link này bằng link Vercel của bạn nếu cần
        frontend_url = os.getenv('FRONTEND_URL', 'https://travel-safety.vercel.app')
        return RedirectResponse(url=f"{frontend_url}/home")
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Lỗi đăng nhập Google: {str(e)}")