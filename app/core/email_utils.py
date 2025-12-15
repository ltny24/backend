# app/core/email_utils.py
"""
Tiện ích gửi thông báo qua Email
Thay thế SMS bằng Email để gửi cảnh báo SOS
"""

import os
import smtplib
import logging
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


def send_email(
    to_email: str,
    subject: str,
    body: str,
    is_html: bool = True
) -> Tuple[bool, str]:
    """
    Gửi email thông báo
    
    Args:
        to_email: Địa chỉ email nhận
        subject: Tiêu đề email
        body: Nội dung email
        is_html: Gửi dưới dạng HTML hay plain text
        
    Returns:
        (success, message)
    """
    try:
        smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
        smtp_port = int(os.getenv("SMTP_PORT", "587"))
        email_from = os.getenv("EMAIL_FROM", "")
        email_password = os.getenv("EMAIL_PASSWORD", "")
        
        if not email_from or not email_password:
            return False, "Email chua duoc cau hinh"
        
        msg = MIMEMultipart()
        msg['From'] = email_from
        msg['To'] = to_email
        msg['Subject'] = subject
        
        content_type = 'html' if is_html else 'plain'
        msg.attach(MIMEText(body, content_type, 'utf-8'))
        
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(email_from, email_password)
            server.send_message(msg)
        
        logger.info(f"Email sent successfully to {to_email}")
        return True, "Email sent successfully"
    
    except Exception as e:
        error_msg = f"Email error: {str(e)}"
        logger.error(f"[EMAIL] {error_msg}")
        return False, error_msg


def send_bulk_emails(
    email_list: List[str],
    subject: str,
    body: str,
    is_html: bool = True
) -> Dict:
    """
    Gui email toi nhieu dia chi
    
    Returns:
        {
            "total": int,
            "success": int,
            "failed": int,
            "details": List[Dict]
        }
    """
    results = {
        "total": len(email_list),
        "success": 0,
        "failed": 0,
        "details": []
    }
    
    for email in email_list:
        success, message = send_email(email, subject, body, is_html)
        results["details"].append({
            "email": email,
            "success": success,
            "message": message
        })
        
        if success:
            results["success"] += 1
        else:
            results["failed"] += 1
    
    return results


def send_sos_alert_email(
    recipient_email: str,
    user_name: str,
    latitude: float,
    longitude: float,
    rescue_station: Dict,
    medical_notes: Optional[str] = None,
    recipient_type: str = "family"
) -> Tuple[bool, str]:
    """
    Gui thong bao SOS qua email
    
    Args:
        recipient_email: Email nguoi nhan
        user_name: Ten nguoi can cuu
        latitude: Vi do
        longitude: Kinh do
        rescue_station: Thong tin tram cuu ho
        medical_notes: Ghi chu y te
        recipient_type: Loai nguoi nhan ("family" hoac "rescue_station")
    """
    
    google_map_link = f"https://www.google.com/maps/search/?api=1&query={latitude},{longitude}"
    current_time = datetime.now().strftime("%H:%M %d/%m/%Y")
    
    # Normalize rescue_station keys (handle both 'Name' and 'name', etc.)
    station_name = rescue_station.get('Name') or rescue_station.get('name', 'Không xác định')
    station_phone = rescue_station.get('Phone') or rescue_station.get('phone', '112')
    station_distance = rescue_station.get('distance_km', 0)
    
    if isinstance(station_distance, dict):
        station_distance = 0
    
    if recipient_type == "family":
        # Email cho nguoi than
        subject = f"[CANH BAO SOS] {user_name} can cuu ho!"
        
        html_body = f"""
        <html>
            <head>
                <meta charset="utf-8">
                <style>
                    body {{ font-family: Arial, sans-serif; }}
                    .alert {{ background-color: #ff6b6b; color: white; padding: 20px; border-radius: 5px; }}
                    .info {{ margin: 15px 0; padding: 10px; background-color: #f0f0f0; border-left: 4px solid #ff6b6b; }}
                    .map-link {{ color: #0066cc; text-decoration: none; }}
                    .timestamp {{ color: #666; font-size: 12px; }}
                </style>
            </head>
            <body>
                <div class="alert">
                    <h2>CANH BAO: {user_name} CAN CUU HO</h2>
                </div>
                
                <div class="info">
                    <strong>Thoi gian:</strong> {current_time}<br>
                    <strong>Vi tri:</strong> <a href="{google_map_link}" class="map-link">Xem tren Google Maps</a><br>
                    <strong>Toa do:</strong> {latitude:.4f}, {longitude:.4f}<br>
                    <strong>Y te:</strong> {medical_notes or 'Khong co thong tin'}
                </div>
                
                <div class="info">
                    <strong>Tram cuu ho gan nhat:</strong><br>
                    Ten: {station_name}<br>
                    Khoang cach: {station_distance:.2f} km<br>
                    Dien thoai: {station_phone}
                </div>
                
                <p style="color: red; font-weight: bold;">
                    HAY LIEN HE NGAY: {station_phone} hoac 112
                </p>
                
                <p class="timestamp">Thong bao tu he thong Travel Safety</p>
            </body>
        </html>
        """
    
    else:  # recipient_type == "rescue_station"
        # Email cho tram cuu ho
        subject = f"[THONG BAO CUU HO] {user_name} - Cap do: KHAN CAP"
        
        html_body = f"""
        <html>
            <head>
                <meta charset="utf-8">
                <style>
                    body {{ font-family: Arial, sans-serif; }}
                    .alert {{ background-color: #ff6b6b; color: white; padding: 20px; border-radius: 5px; }}
                    .info {{ margin: 15px 0; padding: 10px; background-color: #f0f0f0; border-left: 4px solid #ff6b6b; }}
                    .map-link {{ color: #0066cc; text-decoration: none; }}
                </style>
            </head>
            <body>
                <div class="alert">
                    <h2>THONG BAO CUU HO KHAN CAP</h2>
                </div>
                
                <div class="info">
                    <strong>Nguoi can cuu:</strong> {user_name}<br>
                    <strong>Thoi gian:</strong> {current_time}<br>
                    <strong>Vi tri:</strong> <a href="{google_map_link}" class="map-link">Xem tren Google Maps</a><br>
                    <strong>Toa do:</strong> {latitude:.4f}, {longitude:.4f}
                </div>
                
                <div class="info">
                    <strong>Khoang cach den vi tri:</strong> {rescue_station.get('distance_km', 0):.2f} km<br>
                    <strong>Tinh trang y te:</strong> {medical_notes or 'Khong co thong tin chi tiet'}
                </div>
                
                <p style="color: red; font-weight: bold;">
                    VUI LONG TIEN HANH CUU HO CAP TOC
                </p>
                
                <p>Thong bao tu he thong Travel Safety</p>
            </body>
        </html>
        """
    
    return send_email(recipient_email, subject, html_body, is_html=True)


def send_sos_to_family(
    family_emails: List[str],
    user_name: str,
    latitude: float,
    longitude: float,
    rescue_station: Dict,
    medical_notes: Optional[str] = None
) -> Dict:
    """
    Gui thong bao SOS toi nguoi than
    """
    results = {
        "total": len(family_emails),
        "success": 0,
        "failed": 0,
        "details": []
    }
    
    for email in family_emails:
        success, message = send_sos_alert_email(
            email,
            user_name,
            latitude,
            longitude,
            rescue_station,
            medical_notes,
            "family"
        )
        
        results["details"].append({
            "email": email,
            "success": success,
            "message": message
        })
        
        if success:
            results["success"] += 1
        else:
            results["failed"] += 1
    
    return results


def send_sos_to_rescue_station(
    rescue_station_email: str,
    user_name: str,
    latitude: float,
    longitude: float,
    rescue_station: Dict,
    medical_notes: Optional[str] = None
) -> Tuple[bool, str]:
    """
    Gui thong bao SOS toi tram cuu ho
    """
    return send_sos_alert_email(
        rescue_station_email,
        user_name,
        latitude,
        longitude,
        rescue_station,
        medical_notes,
        "rescue_station"
    )


# Backward compatibility functions
def send_sms_with_fallback(phone: str, message: str) -> Dict:
    """
    Wrapper function - gui email thay vi SMS
    """
    return {
        "success": False,
        "phone": phone,
        "message": "SMS da duoc thay the bang email",
        "provider": None,
        "error": "Su dung email thay vi SMS"
    }


def send_bulk_sms_alert(phone_list: List[str], message: str) -> Dict:
    """
    Wrapper function - gui email thay vi SMS
    """
    results = {"total": len(phone_list), "success": 0, "failed": 0, "details": []}
    for phone in phone_list:
        res = send_sms_with_fallback(phone, message)
        results["details"].append(res)
        if res["success"]: results["success"] += 1
        else: results["failed"] += 1
    return results