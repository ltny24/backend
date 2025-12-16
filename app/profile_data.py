# app/routers/profile_data.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional

from app.database import get_db
from app.models import User, EmergencyContact, MedicalInfo, SavedLocation

# Dùng lại hàm lấy user hiện tại từ file login (hoặc viết lại nếu cần)
# Giả sử bạn để logic lấy user từ session trong app/auth/auth_utils.py hoặc tương tự
# Ở đây mình viết tạm hàm phụ thuộc để lấy user_id từ session
from fastapi import Request

def get_current_user_id(request: Request):
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Chưa đăng nhập")
    return user_id

router = APIRouter()

# --- 1. SCHEMAS (Khuôn mẫu dữ liệu gửi lên) ---
class ContactCreate(BaseModel):
    name: str
    phone: str
    relation_type: Optional[str] = None

class MedicalCreate(BaseModel):
    blood_type: Optional[str] = None
    allergies: Optional[str] = None
    conditions: Optional[str] = None
    notes: Optional[str] = None

class LocationCreate(BaseModel):
    name: str
    address: Optional[str] = None
    latitude: float
    longitude: float

# --- 2. API LIÊN HỆ KHẨN CẤP ---
@router.post("/contacts")
async def add_contact(data: ContactCreate, db: Session = Depends(get_db), user_id: int = Depends(get_current_user_id)):
    new_contact = EmergencyContact(
        user_id=user_id,
        name=data.name,
        phone=data.phone,
        relation_type=data.relation_type
    )
    db.add(new_contact)
    db.commit()
    db.refresh(new_contact)
    return {"success": True, "message": "Đã lưu liên hệ", "id": new_contact.id}

@router.get("/contacts")
async def get_contacts(db: Session = Depends(get_db), user_id: int = Depends(get_current_user_id)):
    return db.query(EmergencyContact).filter(EmergencyContact.user_id == user_id).all()

# --- 3. API THÔNG TIN Y TẾ ---
@router.post("/medical")
async def update_medical(data: MedicalCreate, db: Session = Depends(get_db), user_id: int = Depends(get_current_user_id)):
    # Kiểm tra xem đã có hồ sơ chưa
    medical_info = db.query(MedicalInfo).filter(MedicalInfo.user_id == user_id).first()
    
    if medical_info:
        # Update cái cũ
        medical_info.blood_type = data.blood_type
        medical_info.allergies = data.allergies
        medical_info.conditions = data.conditions
        medical_info.notes = data.notes
    else:
        # Tạo mới
        medical_info = MedicalInfo(
            user_id=user_id,
            blood_type=data.blood_type,
            allergies=data.allergies,
            conditions=data.conditions,
            notes=data.notes
        )
        db.add(medical_info)
    
    db.commit()
    return {"success": True, "message": "Đã cập nhật hồ sơ y tế"}

@router.get("/medical")
async def get_medical(db: Session = Depends(get_db), user_id: int = Depends(get_current_user_id)):
    return db.query(MedicalInfo).filter(MedicalInfo.user_id == user_id).first()

# --- 4. API VỊ TRÍ ĐÃ LƯU ---
@router.post("/locations")
async def add_location(data: LocationCreate, db: Session = Depends(get_db), user_id: int = Depends(get_current_user_id)):
    new_loc = SavedLocation(
        user_id=user_id,
        name=data.name,
        address=data.address,
        latitude=data.latitude,
        longitude=data.longitude
    )
    db.add(new_loc)
    db.commit()
    return {"success": True, "message": "Đã lưu địa điểm"}

@router.get("/locations")
async def get_locations(db: Session = Depends(get_db), user_id: int = Depends(get_current_user_id)):
    return db.query(SavedLocation).filter(SavedLocation.user_id == user_id).all()