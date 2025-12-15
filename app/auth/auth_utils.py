import hashlib
import secrets
from sqlalchemy.orm import Session
from app.models import User  # Import model User để làm việc với Database

# ---- 1. PASSWORD HASHING (Giữ nguyên logic bảo mật cũ) ----
def hash_password(password: str) -> str:
    """Mã hóa mật khẩu bằng SHA-256 và Salt"""
    salt = secrets.token_hex(16)
    pwd_hash = hashlib.sha256((password + salt).encode()).hexdigest()
    return f"{salt}${pwd_hash}"

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Kiểm tra mật khẩu nhập vào có khớp với mật khẩu đã mã hóa không"""
    try:
        salt, pwd_hash = hashed_password.split('$')
        return hashlib.sha256((plain_password + salt).encode()).hexdigest() == pwd_hash
    except:
        return False

# ---- 2. DATABASE OPERATIONS (Thay thế hoàn toàn CSV/JSON) ----

def get_user_by_email(db: Session, email: str):
    """
    Tìm user trong Database PostgreSQL bằng email.
    """
    return db.query(User).filter(User.email == email).first()

def create_new_user(db: Session, email: str, password: str, first_name: str, last_name: str, phone: str):
    """
    Tạo user mới và lưu vĩnh viễn vào Database PostgreSQL.
    """
    # 1. Mã hóa mật khẩu
    hashed_pwd = hash_password(password)
    
    # 2. Tạo đối tượng User
    new_user = User(
        email=email,
        password_hash=hashed_pwd,
        first_name=first_name,
        last_name=last_name,
        phone_number=phone
    )
    
    # 3. Lưu xuống Database
    db.add(new_user)
    db.commit()          # Lệnh cam kết: "Lưu ngay lập tức!"
    db.refresh(new_user) # Lấy lại ID vừa tạo
    
    return new_user

def create_oauth_user(db: Session, email: str, first_name: str, last_name: str):
    """
    Tạo user Google. 
    Vì Database yêu cầu bắt buộc có pass, ta sẽ tự sinh một pass ngẫu nhiên cực khó.
    Người dùng không cần biết pass này (vì họ login bằng Google).
    """
    # 1. Tự sinh mật khẩu ngẫu nhiên (dài 32 ký tự)
    random_password = secrets.token_urlsafe(32)
    hashed_pwd = hash_password(random_password)
    
    # 2. Tạo user với mật khẩu ngẫu nhiên đó
    new_user = User(
        email=email,
        password_hash=hashed_pwd, # <--- Giờ nó có dữ liệu rồi, không phải None nữa
        first_name=first_name,
        last_name=last_name,
        phone_number=None
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user
# ---- LƯU Ý ----
# Các hàm save_session, load_sessions (JSON) đã bị XÓA BỎ.
# Lý do: Chúng ta đã chuyển sang dùng Cookie Session (SessionMiddleware) xịn hơn trong main.py.