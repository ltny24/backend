# app/models.py
from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey, DateTime, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base

# 1. BẢNG USER
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    phone_number = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Quan hệ
    emergency_contacts = relationship("EmergencyContact", back_populates="owner", cascade="all, delete-orphan")
    medical_info = relationship("MedicalInfo", back_populates="owner", uselist=False, cascade="all, delete-orphan")
    saved_locations = relationship("SavedLocation", back_populates="owner", cascade="all, delete-orphan")
    logs = relationship("UserLog", back_populates="owner", cascade="all, delete-orphan")

# 2. BẢNG LIÊN HỆ KHẨN CẤP (ĐÃ SỬA LỖI TÊN BIẾN)
class EmergencyContact(Base):
    __tablename__ = "emergency_contacts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    name = Column(String, nullable=False)
    phone = Column(String, nullable=False)
    
    # --- ĐÃ SỬA: Đổi tên từ 'relationship' thành 'relation_type' để tránh trùng lặp ---
    relation_type = Column(String, nullable=True) 

    owner = relationship("User", back_populates="emergency_contacts")

# 3. BẢNG THÔNG TIN Y TẾ
class MedicalInfo(Base):
    __tablename__ = "medical_infos"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True)
    blood_type = Column(String, nullable=True)
    allergies = Column(Text, nullable=True)
    conditions = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)

    owner = relationship("User", back_populates="medical_info")

# 4. BẢNG VỊ TRÍ ĐÃ LƯU
class SavedLocation(Base):
    __tablename__ = "saved_locations"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    name = Column(String, nullable=False)
    address = Column(String, nullable=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    owner = relationship("User", back_populates="saved_locations")

# 5. BẢNG NHẬT KÝ (LOGS)
class UserLog(Base):
    __tablename__ = "user_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    title = Column(String, nullable=False)
    description = Column(String, nullable=True)
    log_type = Column(String, default="INFO")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    owner = relationship("User", back_populates="logs")