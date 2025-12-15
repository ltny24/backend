import json
import os
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel
from typing import Optional, List, Dict
from app.core.database import get_active_risks

router = APIRouter()

# Temporary in-memory storage (trong production nên dùng database)
user_locations_db: Dict[str, List[dict]] = {}
user_preferences_db: Dict[str, dict] = {}

# --- MODELS ---

class UserLocationUpdate(BaseModel):
    user_id: str
    lat: float
    lng: float
    accuracy: Optional[float] = None
    timestamp: str

class QuietHours(BaseModel):
    enabled: bool
    start: str  # Format: "22:00"
    end: str    # Format: "07:00"

class AlertPreferences(BaseModel):
    enabled_categories: List[str] = ["weather", "disaster"]
    min_severity: str = "medium"
    notification_radius_km: int = 50
    quiet_hours: Optional[QuietHours] = None
    sound_enabled: bool = True      
    vibration_enabled: bool = True

class UserPreferencesUpdate(BaseModel):
    user_id: str
    preferences: AlertPreferences

# --- USER LOCATION ENDPOINTS ---

@router.post("/location")
async def update_user_location(location: UserLocationUpdate):
    """
    Cập nhật vị trí người dùng để gửi alerts nearby chính xác.
    Gọi mỗi 5-10 phút khi app active.
    """
    user_id = location.user_id
    
    # Initialize user location history if not exists
    if user_id not in user_locations_db:
        user_locations_db[user_id] = []
    
    # Add new location
    location_entry = {
        "lat": location.lat,
        "lng": location.lng,
        "accuracy": location.accuracy,
        "timestamp": location.timestamp,
        "recorded_at": datetime.now().isoformat()
    }
    
    user_locations_db[user_id].append(location_entry)
    
    # Keep only last 100 locations per user (memory management)
    if len(user_locations_db[user_id]) > 100:
        user_locations_db[user_id] = user_locations_db[user_id][-100:]
    
    return {
        "success": True,
        "message": "Location updated successfully",
        "location": location_entry
    }

@router.get("/location/{user_id}")
async def get_user_location(user_id: str):
    """
    Lấy vị trí hiện tại (mới nhất) của người dùng.
    """
    if user_id not in user_locations_db or not user_locations_db[user_id]:
        raise HTTPException(status_code=404, detail="No location data found for this user")
    
    latest_location = user_locations_db[user_id][-1]
    
    return {
        "success": True,
        "user_id": user_id,
        "location": latest_location
    }

@router.get("/location/{user_id}/history")
async def get_user_location_history(
    user_id: str,
    limit: int = 50
):
    """
    Lấy lịch sử vị trí của người dùng.
    """
    if user_id not in user_locations_db:
        return {
            "success": True,
            "user_id": user_id,
            "locations": [],
            "total": 0
        }
    
    locations = user_locations_db[user_id][-limit:]
    
    return {
        "success": True,
        "user_id": user_id,
        "locations": locations,
        "total": len(user_locations_db[user_id])
    }

@router.delete("/location/{user_id}")
async def delete_user_location_history(user_id: str):
    """
    Xóa toàn bộ lịch sử vị trí của người dùng (privacy).
    """
    if user_id in user_locations_db:
        del user_locations_db[user_id]
    
    return {
        "success": True,
        "message": "Location history deleted successfully"
    }

# --- ALERT PREFERENCES ENDPOINTS ---

@router.post("/alert-preferences")
async def update_alert_preferences(preferences_update: UserPreferencesUpdate):
    """
    Lưu tùy chọn thông báo của người dùng.
    """
    user_id = preferences_update.user_id
    preferences = preferences_update.preferences
    
    # Store preferences
    user_preferences_db[user_id] = {
        "enabled_categories": preferences.enabled_categories,
        "min_severity": preferences.min_severity,
        "notification_radius_km": preferences.notification_radius_km,
        "quiet_hours": preferences.quiet_hours.dict() if preferences.quiet_hours else None,
        "updated_at": datetime.now().isoformat()
    }
    
    return {
        "success": True,
        "message": "Preferences updated successfully",
        "preferences": user_preferences_db[user_id]
    }

@router.get("/alert-preferences/{user_id}")
async def get_alert_preferences(user_id: str):
    """
    Lấy tùy chọn thông báo hiện tại của user.
    """
    if user_id not in user_preferences_db:
        # Return default preferences
        default_preferences = {
            "enabled_categories": ["weather", "disaster"],
            "min_severity": "medium",
            "notification_radius_km": 50,
            "quiet_hours": None,
            "updated_at": None
        }
        return {
            "success": True,
            "preferences": default_preferences,
            "is_default": True
        }
    
    return {
        "success": True,
        "preferences": user_preferences_db[user_id],
        "is_default": False
    }

@router.delete("/alert-preferences/{user_id}")
async def reset_alert_preferences(user_id: str):
    """
    Reset về preferences mặc định.
    """
    if user_id in user_preferences_db:
        del user_preferences_db[user_id]
    
    return {
        "success": True,
        "message": "Preferences reset to default"
    }

# --- ALERT ENGAGEMENT ENDPOINTS ---

class AlertEngagement(BaseModel):
    user_id: str
    viewed_at: Optional[str] = None
    dismissed_at: Optional[str] = None

alert_engagement_db: Dict[str, List[dict]] = {}

@router.post("/alerts/{alert_id}/view")
async def mark_alert_viewed(alert_id: str, engagement: AlertEngagement):
    """
    Đánh dấu user đã xem alert.
    """
    if alert_id not in alert_engagement_db:
        alert_engagement_db[alert_id] = []
    
    alert_engagement_db[alert_id].append({
        "user_id": engagement.user_id,
        "action": "view",
        "timestamp": engagement.viewed_at or datetime.now().isoformat()
    })
    
    return {
        "success": True,
        "message": "Alert marked as viewed"
    }

@router.post("/alerts/{alert_id}/dismiss")
async def dismiss_alert(alert_id: str, engagement: AlertEngagement):
    """
    User dismiss pop-up notification.
    """
    if alert_id not in alert_engagement_db:
        alert_engagement_db[alert_id] = []
    
    alert_engagement_db[alert_id].append({
        "user_id": engagement.user_id,
        "action": "dismiss",
        "timestamp": engagement.dismissed_at or datetime.now().isoformat()
    })
    
    return {
        "success": True,
        "message": "Alert dismissed"
    }

@router.post("/alerts/{alert_id}/share")
async def share_alert(alert_id: str, user_id: str):
    """
    Đánh dấu user đã chia sẻ alert.
    """
    if alert_id not in alert_engagement_db:
        alert_engagement_db[alert_id] = []
    
    alert_engagement_db[alert_id].append({
        "user_id": user_id,
        "action": "share",
        "timestamp": datetime.now().isoformat()
    })
    
    return {
        "success": True,
        "message": "Alert share recorded"
    }

@router.get("/alerts/{alert_id}/engagement")
async def get_alert_engagement(alert_id: str):
    """
    Lấy thống kê engagement của một alert.
    """
    if alert_id not in alert_engagement_db:
        return {
            "success": True,
            "alert_id": alert_id,
            "total_views": 0,
            "total_dismissals": 0,
            "total_shares": 0,
            "engagements": []
        }
    
    engagements = alert_engagement_db[alert_id]
    
    views = sum(1 for e in engagements if e["action"] == "view")
    dismissals = sum(1 for e in engagements if e["action"] == "dismiss")
    shares = sum(1 for e in engagements if e["action"] == "share")
    
    return {
        "success": True,
        "alert_id": alert_id,
        "total_views": views,
        "total_dismissals": dismissals,
        "total_shares": shares,
        "engagements": engagements
    }

# --- NOTIFICATION ENDPOINTS ---

class PushNotificationRequest(BaseModel):
    user_ids: List[str]
    alert_id: str
    title: str
    body: str
    data: Optional[Dict] = None

@router.post("/notifications/push")
async def send_push_notification(notification: PushNotificationRequest):
    """
    Gửi push notification qua Firebase/OneSignal (mock implementation).
    Trong production, integrate với Firebase Cloud Messaging hoặc OneSignal.
    """
    # Mock implementation
    # TODO: Integrate with actual push notification service
    
    successful_sends = []
    failed_sends = []
    
    for user_id in notification.user_ids:
        # Simulate sending
        try:
            # Here you would call Firebase/OneSignal API
            # firebase_admin.messaging.send(message)
            successful_sends.append(user_id)
        except Exception as e:
            failed_sends.append({"user_id": user_id, "error": str(e)})
    
    return {
        "success": True,
        "sent_count": len(successful_sends),
        "failed_count": len(failed_sends),
        "successful_sends": successful_sends,
        "failed_sends": failed_sends,
        "message": f"Push notification sent to {len(successful_sends)} users"
    }

@router.get("/notifications/{user_id}/history")
async def get_notification_history(
    user_id: str,
    limit: int = 50
):
    """
    Lấy lịch sử notification của user.
    """
    # Mock implementation
    # TODO: Query from database
    
    return {
        "success": True,
        "user_id": user_id,
        "notifications": [],
        "total": 0,
        "message": "Feature coming soon"
    }
# --- [THÊM MỚI] ENDPOINT KIỂM TRA RỦI RO ĐỘNG TỪ DB ---

class RiskCheckRequest(BaseModel):
    lat: float
    lon: float
    radius_km: int = 50

@router.post("/check-risk")
async def check_user_risk_status(data: RiskCheckRequest):
    """
    API động: Kiểm tra rủi ro xung quanh vị trí user dựa trên dữ liệu thật từ DB.
    Frontend sẽ gọi API này thay vì dùng mock data.
    """
    # 1. Gọi hàm DB lấy rủi ro (đã import từ app.core.database)
    risks = get_active_risks(lat=data.lat, lon=data.lon, radius_km=data.radius_km)
    
    alerts = []
    status = "Safe"
    
    for risk in risks:
        raw = risk.get('raw_data', {})
        hazard_type = raw.get('overall_hazard_prediction', 'Unknown')
        
        # Bỏ qua nếu là an toàn
        if hazard_type == 'No':
            continue

        status = "Warning" # Có ít nhất 1 mối nguy
        
        # Lấy mức độ nghiêm trọng
        label_key = f"{hazard_type.lower()}_label"
        severity = str(raw.get(label_key, 'Low')).capitalize()
        
        alerts.append({
            "id": str(risk['id']),
            "type": hazard_type,
            "title": risk['title'],
            "description": risk.get('description', ''),
            "severity": severity,
            "time": str(risk['event_time']),
            "coordinates": {"lat": risk['lat'], "lon": risk['lon']}
        })
    
    # Sắp xếp mức độ nguy hiểm lên đầu (High -> Low)
    alerts.sort(key=lambda x: 1 if x['severity'] == 'High' else 2)

    return {
        "status": status,
        "check_location": {"lat": data.lat, "lon": data.lon},
        "alerts_count": len(alerts),
        "alerts": alerts
    }
@router.get("/preferences")
async def get_user_preferences(user_id: str):
    # Trong thực tế: Query DB lấy preferences của user_id
    # Demo: Lấy từ dict tạm
    return user_preferences_db.get(user_id, AlertPreferences()) # Trả về default nếu chưa có
@router.post("/preferences")
async def update_user_preferences(data: UserPreferencesUpdate):
    # Trong thực tế: Lưu vào DB
    user_preferences_db[data.user_id] = data.preferences
    return {"success": True, "message": "Preferences updated"}