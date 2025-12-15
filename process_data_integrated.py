import os
import json
import math
import psycopg2
from psycopg2.extras import RealDictCursor
from app.core.config import DB_CONFIG
from app.ml.predictor_hazard import HazardPredictor
from app.core.gis_utils import get_risk_classification, get_radius_in_meters

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_FILE = os.path.join(BASE_DIR, "data", "processed", "processed_risk_zones.json")

def get_db_connection():
    try:
        return psycopg2.connect(**DB_CONFIG)
    except Exception as e:
        print(f"❌ DB Connection Failed: {e}")
        return None

# --- HÀM TẠO POLYGON TỪ TÂM (Thay vì để Frontend vẽ) ---
def create_geo_polygon(lat, lon, radius_meters, num_points=32):
    """
    Tạo danh sách toạ độ [lon, lat] cho hình đa giác (gần tròn).
    GeoJSON yêu cầu thứ tự [lon, lat].
    """
    coords = []
    for i in range(num_points + 1): # +1 để khép kín vòng tròn
        angle = math.radians(float(i) / num_points * 360)
        # 1 độ vĩ độ ~= 111320 mét
        d_lat = (radius_meters / 111320.0) * math.cos(angle)
        # 1 độ kinh độ ~= 111320 * cos(lat) mét
        d_lon = (radius_meters / (111320.0 * math.cos(math.radians(lat)))) * math.sin(angle)
        coords.append([lon + d_lon, lat + d_lat])
    return [coords] # GeoJSON Polygon là list của list các điểm

def calculate_dynamic_safety_score(risk_level_str, weather_data):
    base_score = 100
    deduction = 0
    
    # 1. Trừ điểm theo AI Risk Level
    rl = risk_level_str.lower()
    if 'high' in rl: deduction += 70      # Phạt nặng hơn
    elif 'mid-high' in rl: deduction += 50
    elif 'mid' in rl: deduction += 30
    elif 'low' in rl: deduction += 10
    
    # 2. Trừ điểm theo dữ liệu thực tế (để tránh bị 100 liên tục)
    if weather_data.get('rain_label', 'no') != 'no': deduction += 5
    if weather_data.get('wind_speed', 0) > 5: deduction += 5
    if weather_data.get('humidity', 0) > 90: deduction += 2

    return max(0, base_score - deduction)

def map_intensity_for_radius(risk_level_str):
    rl = risk_level_str.lower()
    if 'high' in rl: return 3.0
    if 'mid-high' in rl: return 2.0
    if 'mid' in rl: return 1.5
    return 1.0

def run_processing_pipeline():
    print("🔄 Bắt đầu xử lý dữ liệu (Tạo Polygon & Đánh giá rủi ro)...")
    
    try:
        predictor = HazardPredictor()
    except Exception as e:
        print(f"❌ Lỗi khởi tạo Model: {e}")
        return

    conn = get_db_connection()
    if not conn: return

    features_collection = []

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Lấy dữ liệu trong 24h qua (Bỏ DISTINCT ON để lấy nhiều event hơn)
            sql = """
                SELECT id, title, description, event_time, raw_data,
                    ST_X(geom::geometry) as lon, ST_Y(geom::geometry) as lat
                FROM events
                WHERE event_type = 'weather_analytics'
                AND event_time >= NOW() - INTERVAL '24 HOURS'
                ORDER BY event_time DESC
                LIMIT 100
            """
            cur.execute(sql)
            rows = cur.fetchall()
            print(f"📊 Đã lấy {len(rows)} điểm dữ liệu.")

            for row in rows:
                raw_data = row['raw_data']
                
                # A. Dự báo AI
                predicted_hazard = predictor.predict_overall_hazard(raw_data)
                
                # B. Xác định mức độ
                if predicted_hazard in ['No', 'Unknown']:
                    # Vẫn xử lý nhưng gán mức thấp để bản đồ có dữ liệu xanh/vàng
                    risk_level = "Info"
                else:
                    label_key = f"{predicted_hazard.lower()}_label"
                    risk_level = str(raw_data.get(label_key, 'low')).capitalize()

                # C. Tính điểm & Màu sắc
                safety_score = calculate_dynamic_safety_score(risk_level, raw_data)
                
                # Lấy màu từ utils (Đã có logic Xanh/Vàng/Cam/Đỏ)
                risk_class = get_risk_classification(safety_score)
                color = risk_class['color_code']

                # D. Tính bán kính & Tạo Polygon
                intensity = map_intensity_for_radius(risk_level)
                radius = get_radius_in_meters(predicted_hazard, intensity)
                
                # TẠO GEOMETRY POLYGON
                polygon_coords = create_geo_polygon(row['lat'], row['lon'], radius)

                # E. Tạo Feature
                feature = {
                    "type": "Feature",
                    "properties": {
                        "id": row['id'],
                        "name": row['title'],
                        "description": row['description'],
                        "hazard_type": predicted_hazard,
                        "risk_level": risk_level,
                        "safety_score": safety_score,
                        "radius": radius,
                        "color": color,
                        "time": str(row['event_time']),
                        # Lưu tâm để frontend dễ bay tới
                        "center": [row['lat'], row['lon']] 
                    },
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": polygon_coords
                    }
                }
                features_collection.append(feature)

        # Ghi file
        final_geojson = {
            "type": "FeatureCollection",
            "features": features_collection
        }

        os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            json.dump(final_geojson, f, ensure_ascii=False, indent=2)
            
        print(f"✅ Đã xuất {len(features_collection)} vùng Polygon ra file JSON.")

    except Exception as e:
        print(f"❌ Lỗi xử lý: {e}")
    finally:
        if conn: conn.close()

if __name__ == "__main__":
    run_processing_pipeline()