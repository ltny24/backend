# src/schemas/safety_schema.py
from pydantic import BaseModel, Field
from typing import Literal, Optional, List

class SafetyInput(BaseModel):
    # Thông tin vị trí
    location: str = Field(..., description="Tên địa điểm (Vd: Hà Nội)")
    lat: float = Field(..., description="Vĩ độ")
    lon: float = Field(..., description="Kinh độ")
    
    # Thông tin thời tiết cơ bản
    temperature: float = Field(..., description="Nhiệt độ (°C)")
    humidity: float = Field(..., description="Độ ẩm (%)")
    pressure: float = Field(..., description="Áp suất khí quyển (hPa)")
    wind_speed: float = Field(..., description="Tốc độ gió (m/s)")
    
    # Thông tin nâng cao (Mưa, Gió giật)
    precip6: float = Field(0.0, description="Lượng mưa trong 6 giờ qua (mm)")
    precip24: float = Field(0.0, description="Lượng mưa trong 24 giờ qua (mm)")
    gust6: float = Field(0.0, description="Tốc độ gió giật trong 6 giờ qua (m/s)")
    
    # Thông tin thiên tai (Thủy văn, Động đất)
    river_discharge: float = Field(-1.0, description="Lưu lượng nước sông (m3/s). -1 nếu không có dữ liệu")
    eq_mag: float = Field(-1.0, description="Độ lớn động đất (Richter). -1 nếu không có")
    eq_dist: float = Field(-1.0, description="Khoảng cách đến tâm chấn (km). -1 nếu không có")

class SafetyOutput(BaseModel):
    location: str
    safety_score: float
    risk_level: Literal['Info', 'Low', 'Medium', 'High']
    suggestion: str
class SOSRequest(BaseModel):
    latitude: float
    longitude: float
    user_id: Optional[str] = "anonymous"
    
    # App sends these fields (from App Local Storage)
    medical_notes: Optional[str] = None
    contact_email: List[str] = []
    
    timestamp: Optional[str] = None