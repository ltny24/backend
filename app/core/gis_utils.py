import json
import math
from sqlalchemy.orm import Session
from sqlalchemy import func

# ----- THUẬT TOÁN 1: TÔ MÀU (Logic cũ) -----
def get_risk_classification(safety_score: float) -> dict:
    """
    Phân loại Safety Score thành 4 cấp độ Rủi ro (Xanh, Vàng, Cam, Đỏ)
    """
    score = max(0, min(100, safety_score))

    if score >= 80:
        return {"level": "Info", "color_code": "#28A745"}
    elif score >= 50:
        return {"level": "Low", "color_code": "#FFC107"}
    elif score >= 25:
        return {"level": "Medium", "color_code": "#FF8C00"}
    else:
        return {"level": "High", "color_code": "#FF0000"}

# ----- THUẬT TOÁN 2: TÍNH BÁN KÍNH -----
def get_radius_in_meters(disaster_type: str, intensity: float) -> int:
    base_radius = 3000 
    
    if "storm" in disaster_type or "wind" in disaster_type:
        return int(base_radius + (intensity * 1500))
    elif "earthquake" in disaster_type:
        return int(base_radius + (intensity * 3000))
    elif "flood" in disaster_type:
        return int(base_radius + (intensity * 1)) 
    
    return base_radius

def calculate_influence_area(db: Session, center_lat: float, center_lon: float, disaster_type: str, intensity: float) -> dict:
    """
    Tính toán vùng ảnh hưởng GIS sử dụng PostGIS.
    """
    radius_meters = get_radius_in_meters(disaster_type, intensity)
    center_point_wkt = f'POINT({center_lon} {center_lat})'
    
    # Query PostGIS để tạo Polygon
    query = func.ST_AsGeoJSON(
        func.ST_Transform(
            func.ST_Buffer(
                func.ST_Transform(
                    func.ST_SetSRID(
                        func.ST_GeomFromText(center_point_wkt), 4326
                    ), 3857 # Mét
                ), 
                radius_meters
            ), 4326 # Độ (GPS)
        )
    )
    
    geojson_string = db.query(query).scalar()
    if geojson_string:
        return json.loads(geojson_string)
    return None

def haversine_distance(lat1, lon1, lat2, lon2):
    """Tính khoảng cách chim bay (km)"""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c