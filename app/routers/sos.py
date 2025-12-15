# app/routers/sos.py

from fastapi import APIRouter, HTTPException, BackgroundTasks
from app.ml.schemas import SOSRequest
from app.core.rescue_finder import rescue_finder 
from app.core.email_utils import send_sos_to_family, send_sos_to_rescue_station
import pandas as pd
from datetime import datetime
import os
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

SOS_LOG_FILE = "data/sos_logs.csv"

def log_incident_to_csv(data: dict):
    """Ghi lai vu viec vao CSV"""
    os.makedirs(os.path.dirname(SOS_LOG_FILE), exist_ok=True)
    df = pd.DataFrame([data])
    if not os.path.isfile(SOS_LOG_FILE):
        df.to_csv(SOS_LOG_FILE, index=False)
    else:
        df.to_csv(SOS_LOG_FILE, mode='a', header=False, index=False)
    logger.info(f"Log SOS: {data['user_id']}")


def process_sos_background(
    incident_data: dict,
    contact_emails: list,
    rescue_station: dict,
    user_name: str,
    medical_notes: str
):
    """
    Ham chay ngam: Ghi log + Gui Email
    
    Quy trinh:
    1. Ghi log vao CSV
    2. Gui email toi nguoi than (ONLY)
    """
    
    logger.info(f"process_sos_background started - contact_emails: {contact_emails}")
    
    # 1. Ghi log
    log_incident_to_csv(incident_data)
    
    # 2. Gui email toi nguoi than
    if contact_emails:
        logger.info(f"Sending email to {len(contact_emails)} family members...")
        logger.info(f"Email list: {contact_emails}")
        logger.info(f"Rescue station data being sent: {rescue_station}")
        family_results = send_sos_to_family(
            contact_emails,
            user_name,
            incident_data['lat'],
            incident_data['long'],
            rescue_station,
            medical_notes
        )
        logger.info(f"Family email result: {family_results['success']}/{family_results['total']} sent")
        logger.info(f"Email details: {family_results.get('details', [])}")
        
        # Luu ket qua vao log
        incident_data['email_family_result'] = f"{family_results['success']}/{family_results['total']}"
    else:
        logger.warning("No family emails provided")
        incident_data['email_family_result'] = "No email provided"
    
    logger.info("SOS process completed")


@router.post("/trigger")
async def trigger_sos(request: SOSRequest, background_tasks: BackgroundTasks):
    """
    Kich hoat SOS Alert
    
    Quy trinh:
    1. Tim tram cuu ho gan nhat (de hien thi cho nguoi dung)
    2. Day vao background task:
       - Ghi log SOS
       - Gui email toi nguoi than ONLY
    3. Tra response ngay cho app
    """
    try:
        logger.info(f"SOS Request received: {request.dict()}")
        
        # 1. Tim doi cuu ho gan nhat (de hien thi trong response)
        rescue_station = rescue_finder.find_nearest_station(
            request.latitude, 
            request.longitude
        )
        
        logger.info(f"Rescue station found: {rescue_station}")
        
        if not rescue_station:
            rescue_station = {
                "Name": "National Rescue Center (Hotline)",
                "distance_km": -1,
                "Phone": "112",
                "Address": "Hotline",
                "Email": "sos@rescuecenter.vn"
            }
        else:
            # Normalize key names to match email template expectations
            # CSV columns might be: Name, Phone, Address, etc.
            if 'Name' not in rescue_station and 'name' in rescue_station:
                rescue_station['Name'] = rescue_station.pop('name')
            if 'Phone' not in rescue_station and 'phone' in rescue_station:
                rescue_station['Phone'] = rescue_station.pop('phone')
            if 'Address' not in rescue_station and 'address' in rescue_station:
                rescue_station['Address'] = rescue_station.pop('address')
        
        logger.info(f"Final rescue_station data: {rescue_station}")
        logger.info(f"SOS trigger from {request.user_id} - Nearest station: {rescue_station.get('Name', rescue_station.get('name', 'Unknown'))}")
        
        # 2. Chuan bi du lieu incident
        incident_data = {
            "timestamp": datetime.now().isoformat(),
            "user_id": request.user_id,
            "lat": request.latitude,
            "long": request.longitude,
            "medical_info": request.medical_notes or "No information",
            "contact_email": request.contact_email or "Not provided",
            "dispatched_to": rescue_station.get('name', 'Unknown'),
            "distance_km": rescue_station.get('distance_km', 0)
        }
        
        # 3. Prepare contact emails (only family)
        # Sửa đổi trong app/routers/sos.py
        contact_emails = []
        if request.contact_email:
            # Nếu gửi lên là list thì dùng extend, nếu là string thì append
            if isinstance(request.contact_email, list):
                contact_emails.extend(request.contact_email)
            else:
                contact_emails.append(request.contact_email)
        
        logger.info(f"Contact emails received: {contact_emails}")
        logger.info(f"Contact emails type: {type(request.contact_email)}")
        
        # 4. Day vao background task (ONLY family email, NO rescue station email)
        background_tasks.add_task(
            process_sos_background,
            incident_data,
            contact_emails,
            rescue_station,
            request.user_id,
            request.medical_notes or ""
        )
        
        # 5. Tra response ngay cho app
        return {
            "status": "SOS_DISPATCHED",
            "message": "SOS signal received and family notified",
            "nearest_rescue": rescue_station,
            "instruction": f"Nearest rescue: {rescue_station.get('name')} at {rescue_station.get('distance_km', 0):.2f}km. Call {rescue_station.get('phone', '112')} for help.",
            "email_status": "family_notification_sent"
        }

    except Exception as e:
        logger.error(f"SOS API error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def sos_health():
    """Test endpoint để kiểm tra SOS router có hoạt động không"""
    return {"status": "SOS router is working"}