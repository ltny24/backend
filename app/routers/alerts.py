import json
import os
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from typing import List, Optional, Dict
import math
from collections import defaultdict

# Import tiện ích tính khoảng cách
from app.core.gis_utils import haversine_distance

router = APIRouter()

# --- CẤU HÌNH ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
JSON_FILE_PATH = os.path.join(BASE_DIR, "data", "processed", "processed_risk_zones.json")

# [FIX] Hàm load dữ liệu động (Gọi mỗi khi API được request để lấy dữ liệu mới nhất)
def load_risk_data():
    if not os.path.exists(JSON_FILE_PATH):
        print(f"⚠️ [AlertsRouter] Không tìm thấy file: {JSON_FILE_PATH}")
        return []
        
    try:
        with open(JSON_FILE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            # Xử lý GeoJSON
            if isinstance(data, dict) and "features" in data:
                return data["features"]
            elif isinstance(data, list):
                return data
            return []
    except Exception as e:
        print(f"❌ [AlertsRouter] Lỗi đọc JSON: {e}")
        return []

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, user_id: str):
        await websocket.accept()
        self.active_connections[user_id] = websocket

    def disconnect(self, user_id: str):
        if user_id in self.active_connections:
            del self.active_connections[user_id]

    async def send_personal_message(self, message: dict, user_id: str):
        if user_id in self.active_connections:
            await self.active_connections[user_id].send_json(message)

    async def broadcast(self, message: dict):
        for connection in self.active_connections.values():
            await connection.send_json(message)

manager = ConnectionManager()

# --- MODELS ---
class AlertLocation(BaseModel):
    province: str
    district: Optional[str] = None
    coordinates: List[float]  # [lat, lon]

class Alert(BaseModel):
    id: str
    title: str
    description: str
    severity: str  # high, medium, low
    category: str  # weather, disaster, health, security
    location: AlertLocation
    priority: int
    affected_population: Optional[int] = None
    issued_at: str
    expires_at: Optional[str] = None
    source: str

class NearbyAlert(Alert):
    distance_km: float
    should_notify: bool

class UserLocation(BaseModel):
    lat: float
    lng: float
    province: Optional[str] = None

# --- HELPER FUNCTIONS ---

def map_risk_level_to_severity(risk_level: str) -> str:
    """Chuyển đổi risk_level sang severity"""
    mapping = {
        "Critical": "high",
        "High Risk": "high",
        "Medium Risk": "medium",
        "Low Risk": "low",
        "Info": "low"
    }
    return mapping.get(risk_level, "low")

def map_disaster_type_to_category(disaster_type: str) -> str:
    """Chuyển đổi disaster_type sang category"""
    mapping = {
        "wind": "weather",
        "flood": "disaster",
        "earthquake": "disaster",
        "storm": "weather",
        "typhoon": "weather",
        "landslide": "disaster",
        "tsunami": "disaster"
    }
    return mapping.get(disaster_type.lower(), "weather")

def calculate_priority(
    severity: str,
    affected_population: int,
    issued_at: datetime,
    intensity: float
) -> int:
    """
    Tính priority score (0-100)
    """
    # Severity Score (40%)
    severity_map = {'high': 100, 'medium': 60, 'low': 30}
    severity_score = severity_map.get(severity, 30)
    
    # Population Impact (30%)
    population_score = min(100, (affected_population / 10000) * 10) if affected_population else 50
    
    # Intensity Score (20%)
    intensity_score = max(0, min(100, (abs(intensity) * 100)))
    
    # Recency Score (10%)
    now = datetime.now()
    if issued_at.tzinfo is not None:
        now = now.astimezone()
        
    try:
        hours_since_issued = (now - issued_at).total_seconds() / 3600
    except Exception:
        hours_since_issued = 0

    recency_score = max(0, 100 - (hours_since_issued * 5))
    
    priority = (
        severity_score * 0.4 +
        population_score * 0.3 +
        intensity_score * 0.2 +
        recency_score * 0.1
    )
    
    return round(priority)

def convert_risk_zone_to_alert(zone: dict, index: int) -> Alert:
    """Chuyển đổi risk zone data sang Alert format"""
    props = zone.get("properties", {})
    geom = zone.get("geometry", {})
    
    # 1. Lấy Hazard Type & Risk Level
    raw_hazard = props.get("hazard_type") or props.get("risk_type") or "Unknown"
    risk_level = props.get("risk_level", "Info")

    # Nếu risk_level là No -> Hazard là No
    if risk_level == "No":
        hazard_type = "No"
        severity = "low"
    else:
        hazard_type = raw_hazard
        severity = map_risk_level_to_severity(risk_level)

    category = map_disaster_type_to_category(hazard_type)
    
    # 2. Lấy Tọa độ (Center)
    center = props.get("center", [0, 0])
    lat, lon = center[0], center[1]
    
    # 3. Các chỉ số khác
    affected_pop = 10000 
    
    # Xử lý thời gian
    time_str = props.get("time")
    try:
        if time_str:
            # [FIX] Thay thế khoảng trắng bằng 'T' để đúng chuẩn ISO 8601
            # Ví dụ: "2025-12-08 09:00" -> "2025-12-08T09:00"
            clean_time_str = time_str.replace(" ", "T")
            
            # Xử lý trường hợp chuỗi có 'Z' (UTC)
            if "Z" in clean_time_str:
                clean_time_str = clean_time_str.replace("Z", "+00:00")
                
            issued_at = datetime.fromisoformat(clean_time_str)
        else:
            # Nếu không có time, lấy thời gian sửa file JSON (để chính xác hơn là now)
            file_mod_time = os.path.getmtime(JSON_FILE_PATH)
            issued_at = datetime.fromtimestamp(file_mod_time).astimezone()
    except Exception as e:
        print(f"⚠️ Lỗi parse time '{time_str}': {e}. Dùng thời gian hiện tại.")
        issued_at = datetime.now().astimezone()
    
    priority = calculate_priority(
        severity=severity,
        affected_population=affected_pop,
        issued_at=issued_at,
        intensity=props.get("intensity", 0)
    )
    
    # 4. Tạo Title & Description
    location_name = props.get("name", "Unknown")
    if "]" in location_name:
        location_name = location_name.split("]")[1].strip()

    if hazard_type == "No":
        title = f"✅ An toàn: {location_name}"
    else:
        title = f"⚠️ {hazard_type} tại {location_name}"
    
    description = props.get("description", "")

    return Alert(
        id=str(props.get("id", f"alert_{index}")),
        title=title,
        description=description,
        severity=severity,
        category=category,
        location=AlertLocation(
            province=location_name,
            coordinates=[lat, lon]
        ),
        priority=priority,
        affected_population=affected_pop,
        issued_at=issued_at.isoformat(),
        source="System"
    )

# --- ENDPOINTS ---

@router.get("/national")
def get_national_alerts(
    limit: int = Query(20, ge=1, le=100),
    severity: Optional[str] = Query(None, regex="^(high|medium|low)$"),
    category: Optional[str] = Query(None, regex="^(weather|disaster|health|security)$")
):
    """Lấy danh sách cảnh báo toàn quốc"""
    # [FIX] Load lại dữ liệu mỗi khi gọi API
    current_risk_data = load_risk_data()
    
    alerts = []
    
    for idx, zone in enumerate(current_risk_data):
        alert = convert_risk_zone_to_alert(zone, idx)
        
        if severity and alert.severity != severity:
            continue
        if category and alert.category != category:
            continue
        
        alerts.append(alert)
    
    # Sort by priority (cao -> thấp)
    alerts.sort(key=lambda x: x.priority, reverse=True)
    
    # Limit results
    limited_alerts = alerts[:limit]
    
    return {
        "success": True,
        "data": [alert.model_dump() for alert in limited_alerts],
        "total": len(alerts),
        "page": 1,
        "description": "Top sự kiện có độ rủi ro cao nhất trên toàn quốc"
    }

@router.get("/nearby")
def get_nearby_alerts(lat: float, lng: float, radius: float = 50.0): 
    """Lấy cảnh báo gần user"""
    # [FIX] Load lại dữ liệu mỗi khi gọi API
    current_risk_data = load_risk_data()
    
    all_nearby = []
    
    for idx, zone in enumerate(current_risk_data):
        alert = convert_risk_zone_to_alert(zone, idx)
        if not alert: continue
        
        dist = haversine_distance(lat, lng, alert.location.coordinates[0], alert.location.coordinates[1])
        
        if dist <= radius:
            should_notify = (alert.severity == "high" and dist < 10) or (alert.severity == "medium" and dist < 5)
            
            nearby_alert = NearbyAlert(
                **alert.dict(), 
                distance_km=round(dist, 1), 
                should_notify=should_notify
            )
            all_nearby.append(nearby_alert)
    
    # Logic lọc thông minh
    hazards = [a for a in all_nearby if a.severity != 'safe' and a.category != 'weather']
    
    if hazards:
        hazards.sort(key=lambda x: x.distance_km)
        return {"success": True, "data": [a.dict() for a in hazards]}
    
    if all_nearby:
        all_nearby.sort(key=lambda x: x.distance_km)
        return {"success": True, "data": [all_nearby[0].dict()]} 
        
    return {"success": True, "data": []}

@router.get("/all")
def get_all_alerts(
    lat: Optional[float] = Query(None),
    lng: Optional[float] = Query(None),
    limit: int = Query(50, ge=1, le = 200),
    category: Optional[str] = Query(None, regex="^(weather|disaster|health|security)$")
):
    """Kết hợp NATIONAL + NEAR ME"""
    national_response = get_national_alerts(limit=20, category=category)
    national_alerts = national_response["data"]
    
    nearby = []
    if lat is not None and lng is not None:
        nearby_response = get_nearby_alerts(lat=lat, lng=lng, radius=50.0)
        nearby = nearby_response["data"]
    
    # Merge
    alert_map = {}
    for alert in nearby:
        alert_id = alert["id"]
        alert_map[alert_id] = alert
    
    for alert in national_alerts:
        alert_id = alert["id"]
        if alert_id not in alert_map:
            alert_map[alert_id] = alert
    
    combined_alerts = list(alert_map.values())
    
    def sort_key(alert):
        distance = alert.get("distance_km", 9999)
        priority = alert.get("priority", 0)
        return (distance, -priority)
    
    combined_alerts.sort(key=sort_key)
    
    return {
        "success": True,
        "data": {
            "national": national_alerts[:20],
            "nearby": nearby[:20],
            "combined": combined_alerts[:limit]
        },
        "total": len(combined_alerts)
    }

@router.get("/latest")
def get_latest_alerts(limit: int = Query(10, ge=1, le=50)):
    """Lấy các cảnh báo mới nhất"""
    # [FIX] Load dữ liệu mới
    current_risk_data = load_risk_data()
    
    alerts = []
    for idx, zone in enumerate(current_risk_data):
        alert = convert_risk_zone_to_alert(zone, idx)
        if alert.severity in ["high", "medium"]:
            alerts.append(alert)
    
    alerts.sort(key=lambda x: (x.priority, x.issued_at), reverse=True)
    
    return {
        "success": True,
        "data": [alert.model_dump() for alert in alerts[:limit]],
        "total": len(alerts)
    }

@router.get("/statistics")
def get_alert_statistics():
    """Thống kê tổng quan"""
    # [FIX] Load dữ liệu mới
    current_risk_data = load_risk_data()
    total_alerts = len(current_risk_data)
    
    severity_counts = {"high": 0, "medium": 0, "low": 0}
    category_counts = defaultdict(int)
    
    for idx, zone in enumerate(current_risk_data):
        alert = convert_risk_zone_to_alert(zone, idx)
        severity_counts[alert.severity] = severity_counts.get(alert.severity, 0) + 1
        category_counts[alert.category] += 1
    
    return {
        "success": True,
        "statistics": {
            "total_alerts": total_alerts,
            "by_severity": severity_counts,
            "by_category": dict(category_counts),
            "high_priority_count": severity_counts["high"],
            "active_alerts": total_alerts
        }
    }

@router.get("/{alert_id}", response_model=Alert)
async def get_alert_detail(alert_id: str):
    """API lấy chi tiết alert"""
    # [FIX] Load dữ liệu mới
    current_risk_data = load_risk_data()
    
    for idx, zone in enumerate(current_risk_data):
        props = zone.get("properties", {})
        current_id = str(props.get("id", f"alert_{idx}"))
        
        if current_id == alert_id:
            return convert_risk_zone_to_alert(zone, idx)
            
    raise HTTPException(status_code=404, detail="Alert not found")

# --- WEBSOCKET ---

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, user_id: str = Query(...)):
    await manager.connect(websocket, user_id)
    try:
        await manager.send_personal_message({
            "type": "connected",
            "message": "Connected to Alert Hub",
            "timestamp": datetime.now().isoformat()
        }, user_id)
        
        while True:
            data = await websocket.receive_json()
            if data.get("type") == "ping":
                await manager.send_personal_message({
                    "type": "pong",
                    "timestamp": datetime.now().isoformat()
                }, user_id)
            
            elif data.get("type") == "update_location":
                lat = data.get("lat")
                lng = data.get("lng")
                nearby_response = get_nearby_alerts(lat=lat, lng=lng, radius=20.0)
                # ... handle notification logic ...
            
    except WebSocketDisconnect:
        manager.disconnect(user_id)
    except Exception as e:
        manager.disconnect(user_id)

@router.post("/broadcast")
async def broadcast_alert(alert_id: str):
    # [FIX] Load dữ liệu mới
    current_risk_data = load_risk_data()
    
    target_alert = None
    target_index = -1
    
    for idx, zone in enumerate(current_risk_data):
        props = zone.get("properties", {})
        current_id = str(props.get("id", f"alert_{idx}"))
        
        if current_id == alert_id:
            target_alert = zone
            target_index = idx
            break
    
    if target_alert:
        alert = convert_risk_zone_to_alert(target_alert, target_index)
        await manager.broadcast({
            "type": "broadcast_alert",
            "data": alert.model_dump(),
            "timestamp": datetime.now().isoformat()
        })
        return {"success": True, "message": "Alert broadcasted"}
    
    raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")