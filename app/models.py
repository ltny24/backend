# app/models.py
from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey, DateTime, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base

# 1. BẢNG USER (Giữ nguyên, thêm relationship để nối với các bảng kia)
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    phone_number = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Móc nối sang các bảng con (Để dễ truy vấn ngược)
    emergency_contacts = relationship("EmergencyContact", back_populates="owner", cascade="all, delete-orphan")
    medical_info = relationship("MedicalInfo", back_populates="owner", uselist=False, cascade="all, delete-orphan")
    saved_locations = relationship("SavedLocation", back_populates="owner", cascade="all, delete-orphan")

# 2. BẢNG LIÊN HỆ KHẨN CẤP
class EmergencyContact(Base):
    __tablename__ = "emergency_contacts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id")) # Cái này để biết liên hệ này của ai
    name = Column(String, nullable=False)
    phone = Column(String, nullable=False)
    relationship = Column(String, nullable=True) # Mối quan hệ (Bố, mẹ...)

    owner = relationship("User", back_populates="emergency_contacts")

# 3. BẢNG THÔNG TIN Y TẾ
class MedicalInfo(Base):
    __tablename__ = "medical_infos"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True) # Mỗi người chỉ có 1 hồ sơ y tế
    blood_type = Column(String, nullable=True) # Nhóm máu
    allergies = Column(Text, nullable=True)    # Dị ứng
    conditions = Column(Text, nullable=True)   # Bệnh nền
    notes = Column(Text, nullable=True)

    owner = relationship("User", back_populates="medical_info")

# 4. BẢNG VỊ TRÍ ĐÃ LƯU (Saved Locations)
class SavedLocation(Base):
    __tablename__ = "saved_locations"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    name = Column(String, nullable=False) # Tên gợi nhớ (Nhà, Công ty...)
    address = Column(String, nullable=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    owner = relationship("User", back_populates="saved_locations")