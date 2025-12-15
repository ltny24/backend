import psycopg2
from psycopg2.extras import RealDictCursor
from app.core.config import DB_CONFIG
from psycopg2.extras import Json, execute_values

def get_db_connection():
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except Exception as e:
        print(f"❌ Database Connection Error: {e}")
        return None

def fetch_latest_weather_data(lat: float, lon: float, radius_km: int = 50):
    conn = get_db_connection()
    if not conn: return None
    
    result = None
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            sql = """
                SELECT raw_data 
                FROM events 
                WHERE event_type = 'weather_analytics'
                AND event_time >= NOW() - INTERVAL '24 HOURS'
                AND ST_DWithin(
                    geom::geography, 
                    ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography, 
                    %s
                )
                ORDER BY event_time DESC 
                LIMIT 1
            """
            cur.execute(sql, (lon, lat, radius_km * 1000))
            row = cur.fetchone()
            if row: result = row['raw_data'] 
    except Exception as e:
        print(f"❌ Error fetching weather data: {e}")
    finally:
        conn.close()
    
    return result

def get_active_risks(lat=None, lon=None, radius_km=50, limit=200):
    conn = get_db_connection()
    if not conn: return []
    
    results = []
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # [FIX] Đã XÓA dòng: AND raw_data->>'overall_hazard_prediction' != 'No'
            # Để hiển thị cả những vùng an toàn (Info/Green)
            base_query = """
                SELECT id, title, description, event_time, 
                       ST_X(geom::geometry) as lon, ST_Y(geom::geometry) as lat,
                       raw_data
                FROM events 
                WHERE event_time >= NOW() - INTERVAL '24 HOURS'
            """
            
            if lat is not None and lon is not None:
                query = base_query + """
                    AND ST_DWithin(
                        geom::geography, 
                        ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography, 
                        %s
                    )
                    ORDER BY event_time DESC
                """
                cur.execute(query, (lon, lat, radius_km * 1000))
            else:
                query = base_query + " ORDER BY event_time DESC LIMIT %s"
                cur.execute(query, (limit * 2,)) 
            
            raw_results = cur.fetchall()

            # Lọc trùng (chỉ lấy mới nhất cho mỗi địa điểm)
            seen_locations = set()
            unique_results = []
            
            for row in raw_results:
                loc_name = row['title']
                hazard_type = row['raw_data'].get('overall_hazard_prediction', 'Unknown')
                
                # Key duy nhất gồm Tên + Loại rủi ro
                unique_key = f"{loc_name}-{hazard_type}"
                
                if unique_key not in seen_locations:
                    unique_results.append(row)
                    seen_locations.add(unique_key)
            
            results = unique_results[:limit]

    except Exception as e:
        print(f"❌ Lỗi Query DB (get_active_risks): {e}")
    finally:
        if conn: conn.close()
    
    return results
def write_events_to_database(events_list):
    """
    Ghi dữ liệu thu thập được vào bảng events (Dùng cho Data Collector)
    """
    if not events_list:
        print("ℹ️ [DB] Không có sự kiện mới để ghi.")
        return
    
    conn = get_db_connection()
    if not conn: return

    try:
        with conn.cursor() as cur:
            sql = """
            INSERT INTO events (source, event_type, title, description, event_time, geom, raw_data)
            VALUES %s
            ON CONFLICT DO NOTHING; -- Tránh lỗi nếu trùng lặp
            """
            data_to_insert = []
            for event in events_list:
                geom_sql = None
                if event["lon"] is not None and event["lat"] is not None:
                    # Tạo cú pháp hình học cho PostGIS
                    geom_sql = f"ST_SetSRID(ST_MakePoint({event['lon']}, {event['lat']}), 4326)"
                
                data_to_insert.append((
                    event["source"], 
                    event["event_type"], 
                    event["title"],
                    event["description"], 
                    event.get("event_time"),
                    geom_sql, # Lưu ý: Khi dùng execute_values, chuỗi này cần xử lý khéo léo hoặc dùng string format trước
                    Json(event["raw_data"])
                ))
            
            # Lưu ý: execute_values với PostGIS cần xử lý geom cẩn thận. 
            # Để đơn giản và an toàn nhất trong context này, ta loop insert hoặc dùng logic cũ.
            # Dưới đây là logic an toàn từ code cũ của bạn, chuyển sang dùng conn backend:
            
            for item in data_to_insert:
                # Bung item ra để insert từng dòng (chậm hơn chút nhưng an toàn logic cũ)
                cur.execute("""
                    INSERT INTO events (source, event_type, title, description, event_time, geom, raw_data)
                    VALUES (%s, %s, %s, %s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326), %s)
                """, (
                    item[0], item[1], item[2], item[3], item[4], 
                    events_list[data_to_insert.index(item)]['lon'], # Lấy lại lon
                    events_list[data_to_insert.index(item)]['lat'], # Lấy lại lat
                    item[6]
                ))
            
            conn.commit()
            print(f"✅ [DB] Đã ghi {len(data_to_insert)} sự kiện vào Database.")
            
    except Exception as error:
        print(f"❌ [DB] Lỗi khi ghi batch: {error}")
    finally:
        conn.close()