import os
import urllib.parse  # <--- QUAN TRỌNG: Thư viện xử lý ký tự đặc biệt
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# ======================================================
# CẤU HÌNH KẾT NỐI DATABASE
# ======================================================

# 1. Lấy biến môi trường
DB_HOST = os.getenv("DB_HOST")
DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASS")
DB_NAME = os.getenv("DB_NAME")
DB_PORT = os.getenv("DB_PORT", "5432") # Mặc định 5432

SQLALCHEMY_DATABASE_URL = ""
connect_args = {} # Cấu hình phụ cho SQLite

# 2. Ưu tiên ghép từ 5 biến lẻ (Cách an toàn nhất)
if DB_HOST and DB_USER and DB_PASS and DB_NAME:
    # Mã hóa User và Pass để chấp hết mọi ký tự đặc biệt
    encoded_user = urllib.parse.quote_plus(DB_USER)
    encoded_pass = urllib.parse.quote_plus(DB_PASS)
    
    SQLALCHEMY_DATABASE_URL = (
        f"postgresql://{encoded_user}:{encoded_pass}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    )
    print("✅ Đang kết nối Database bằng biến lẻ (DB_HOST, DB_USER...)")

# 3. Hoặc dùng biến gộp DATABASE_URL
elif os.getenv("DATABASE_URL"):
    SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL")
    # Fix lỗi Render (postgres -> postgresql)
    if SQLALCHEMY_DATABASE_URL.startswith("postgres://"):
        SQLALCHEMY_DATABASE_URL = SQLALCHEMY_DATABASE_URL.replace("postgres://", "postgresql://", 1)
    print("✅ Đang kết nối Database bằng biến gộp DATABASE_URL")

# 4. Fallback: Dùng SQLite (Chỉ cho Local)
else:
    print("⚠️ WARNING: Không tìm thấy biến môi trường DB. Dùng SQLite tạm thời.")
    SQLALCHEMY_DATABASE_URL = "sqlite:///./sql_app.db"
    # SQLite cần dòng này để không lỗi với FastAPI
    connect_args = {"check_same_thread": False}

# ======================================================
# KHỞI TẠO ENGINE
# ======================================================

# Tạo Engine với cấu hình phù hợp
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args=connect_args # Chỉ có tác dụng nếu là SQLite
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()