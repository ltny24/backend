import os
from fastapi import APIRouter, HTTPException, Header, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, EmailStr
from typing import Optional
# Import các hàm tiện ích
from app.auth.auth_utils import create_user, authenticate_user, generate_token, save_session, get_user_from_token, delete_session, create_or_get_oauth_user
from app.auth.oauth_config import oauth

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
router = APIRouter()
# ---- 3. AUTHENTICATION ENDPOINTS ----
@router.post("/signup", response_model=AuthResponse)
async def signup(request: SignUpRequest):
    """
    Đăng ký tài khoản mới.
    Lưu thông tin user vào file CSV.
    """
    try:
        # Tạo user mới
        user_data = create_user(
            email=request.email,
            password=request.password,
            first_name=request.first_name,
            last_name=request.last_name,
            phone_number=request.phone_number
        )
        
        # Tạo access token
        token = generate_token()
        save_session(token, user_data)
        
        return AuthResponse(
            success=True,
            message="Account created successfully",
            access_token=token,
            user=user_data
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Registration failed: {str(e)}")

@router.post("/signin", response_model=AuthResponse)
async def signin(request: SignInRequest):
    """
    Đăng nhập với email và password.
    Trả về access token nếu thành công.
    """
    try:
        # Xác thực user
        user_data = authenticate_user(request.email, request.password)
        
        if not user_data:
            raise HTTPException(status_code=401, detail="Invalid email or password")
        
        # Tạo access token
        token = generate_token()
        save_session(token, user_data)
        
        return AuthResponse(
            success=True,
            message="Login successful",
            access_token=token,
            user=user_data
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Login failed: {str(e)}")

@router.post("/logout")
async def logout(authorization: Optional[str] = Header(None)):
    """
    Đăng xuất - xóa session token.
    Header: Authorization: Bearer <token>
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid authorization header")
    
    token = authorization.replace("Bearer ", "")
    delete_session(token)
    
    return {"success": True, "message": "Logged out successfully"}

# ---- OAUTH ENDPOINTS ----
@router.get("/google/login")
async def google_login(request: Request):
    """
    Redirect to Google OAuth login page
    """
    redirect_uri = request.url_for('google_callback')
    return await oauth.google.authorize_redirect(request, redirect_uri)

@router.get("/google/callback")
async def google_callback(request: Request):
    """
    Google OAuth callback - handle user authentication
    """
    try:
        token = await oauth.google.authorize_access_token(request)
        user_info = token.get('userinfo')
        
        if not user_info:
            raise HTTPException(status_code=400, detail="Failed to get user info from Google")
        
        # Create or get user
        email = user_info.get('email')
        first_name = user_info.get('given_name', '')
        last_name = user_info.get('family_name', '')
        
        user_data = create_or_get_oauth_user(
            email=email,
            first_name=first_name,
            last_name=last_name,
            oauth_provider='google'
        )
        
        # Generate access token
        access_token = generate_token()
        save_session(access_token, user_data)
        
        # Redirect to frontend with token
        frontend_url = os.getenv('FRONTEND_URL', 'http://localhost:3000')
        return RedirectResponse(url=f"{frontend_url}/auth/callback?token={access_token}")
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Google authentication failed: {str(e)}")

@router.get("/me")
async def get_current_user(authorization: Optional[str] = Header(None)):
    """
    Lấy thông tin user hiện tại từ token.
    Header: Authorization: Bearer <token>
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid authorization header")
    
    token = authorization.replace("Bearer ", "")
    user_data = get_user_from_token(token)
    
    if not user_data:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    
    return {"success": True, "user": user_data}