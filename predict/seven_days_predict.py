import requests
import pandas as pd
from datetime import datetime
import numpy as np
import joblib
import os
import sys

# ==============================
# LOAD MODEL + FEATURES + ENCODER
# ==============================

# Sửa đường dẫn - từ thư mục predict lên data folder
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_PATH = os.path.join(BASE_DIR, "data", "models", "hazard_model.pkl")
FEATURE_PATH = os.path.join(BASE_DIR, "data", "models", "hazard_features.pkl")
ENCODER_PATH = os.path.join(BASE_DIR, "data", "models", "hazard_label_encoder.pkl")
SCALER_PATH = os.path.join(BASE_DIR, "data", "models", "hazard_scaler.pkl")

print(f"Loading models from: {BASE_DIR}")
print(f"Model path: {MODEL_PATH}")

model = joblib.load(MODEL_PATH)
feature_list = joblib.load(FEATURE_PATH)
label_encoder = joblib.load(ENCODER_PATH)
scaler = joblib.load(SCALER_PATH)

# ==============================
# HÀM HỖ TRỢ GIỐNG historical_data.py
# ==============================

def level(v):
    return v or 0.0

# 🌧 Rain
def label_rain(p6, p24):
    p6 = level(p6)
    p24 = level(p24)

    if p24 > 80 or p6 > 40:
        return "high"
    if p24 > 50 or p6 > 25:
        return "mid-high"
    if p24 > 20 or p6 > 10:
        return "mid"
    if p24 > 3 or p6 > 1:
        return "low"
    return "no"

# 💨 Wind
def label_wind(gust6):
    gust6 = level(gust6)

    if gust6 > 30:
        return "high"
    if gust6 > 22:
        return "mid-high"
    if gust6 > 15:
        return "mid"
    if gust6 > 8:
        return "low"
    return "no"

# 🌩 Storm (OPTION B)
def label_storm(gust6, p6, p24, wind, pres):
    gust6 = level(gust6)
    p6 = level(p6)
    p24 = level(p24)

    score = 0

    # 1) Gió giật
    if gust6 > 28: score += 4
    elif gust6 > 20: score += 3
    elif gust6 > 13: score += 2
    elif gust6 > 7:  score += 1

    # thêm rule
    if gust6 > wind + 12 and p6 > 20:
        score += 2
    elif gust6 > wind + 8 and p6 > 10:
        score += 1

    # 2) Mưa
    if p24 > 80 or p6 > 40:
        score += 4
    elif p24 > 50 or p6 > 25:
        score += 3
    elif p24 > 20 or p6 > 10:
        score += 2
    elif p24 > 3 or p6 > 1:
        score += 1

    # 3) Áp suất
    if pres < 990: score += 4
    elif pres < 995: score += 3
    elif pres < 1000: score += 2
    elif pres < 1005: score += 1

    if score >= 14:
        return "high"
    if score >= 10:
        return "mid-high"
    if score >= 7:
        return "mid"
    if score >= 3:
        return "low"
    return "no"

# 🌊 Flood
def label_flood(river):
    river = level(river)

    if river > 8000: return "high"
    if river > 5000: return "mid-high"
    if river > 2000: return "mid"
    if river > 500:  return "low"
    return "no"

# 🌏 Earthquake
def label_earthquake(mag, dist):
    if mag is None or dist is None:
        return "no"

    if mag >= 6.0 and dist <= 150:
        return "high"
    if mag >= 5.5 and dist <= 300:
        return "mid-high"
    if mag >= 5.0 and dist <= 500:
        return "mid"
    if mag >= 4.5 and dist <= 800:
        return "low"
    return "no"

# Overall
RISK_ORDER = {"no": 0, "low": 1, "mid": 2, "mid-high": 3, "high": 4}
HAZARD_PRIORITY = ["wind", "rain", "storm", "flood", "earthquake"]

def overall_hazard_prediction_rule(flood, storm, rain, wind, eq):
    risks = {
        "flood": flood,
        "storm": storm,
        "rain": rain,
        "wind": wind,
        "earthquake": eq,
    }

    best = "no"
    best_score = 0
    
    for hz in HAZARD_PRIORITY:
        lv = risks[hz]
        score = RISK_ORDER[lv]
        
        # Wind cần score >= 3 (mid-high hoặc cao hơn), còn lại cần score >= 2 (mid hoặc cao hơn)
        if hz == "wind":
            min_threshold = 3  # mid-high hoặc cao hơn
        else:
            min_threshold = 2
        
        if score >= min_threshold and score > best_score:
            best = hz
            best_score = score

    if best_score == 0:  # Không có hazard nào thỏa mãn điều kiện
        return "No"
    return best.capitalize()

# ==============================
# GET 7-DAY FORECAST
# ==============================

def get_7day(lat, lon):
    url = (
        f"https://api.open-meteo.com/v1/forecast?"
        f"latitude={lat}&longitude={lon}"
        f"&hourly=precipitation,windgusts_10m,windspeed_10m,pressure_msl"
        f"&hourly=precipitation,windgusts_10m,windspeed_10m,pressure_msl,relativehumidity_2m"
        f"&daily=temperature_2m_max,temperature_2m_min,precipitation_sum"
        f"&timezone=auto"
    )

    data = requests.get(url).json()

    # ----- DAILY -----
    daily = data["daily"]
    df_daily = pd.DataFrame({
        "date": daily["time"],
        "temp_max": daily["temperature_2m_max"],
        "temp_min": daily["temperature_2m_min"],
        "precip24": daily["precipitation_sum"],
    })

    # ----- HOURLY -----
    hourly = data["hourly"]
    df_hourly = pd.DataFrame({
        "time": hourly["time"],
        "precip": hourly["precipitation"],
        "wind": hourly["windspeed_10m"],
        "gust": hourly["windgusts_10m"],
        "pressure": hourly["pressure_msl"],
        "humidity": hourly.get("relativehumidity_2m", [None]*len(hourly.get("time", [])))
    })

    # Convert time → date
    df_hourly["date"] = df_hourly["time"].str.slice(0, 10)

    precip6_list = []
    gust6_list = []
    wind_max_list = []
    pressure_list = []
    humidity_list = []

    # ----- TÍNH CHỈ SỐ THEO NGÀY -----
    for d in df_daily["date"]:
        day_hourly = df_hourly[df_hourly["date"] == d]

        # PRECIP 6H: 6 giờ đầu trong ngày
        precip6 = day_hourly["precip"].head(6).sum()

        # GUST6: max gió giật trong 6h đầu
        gust6 = day_hourly["gust"].head(6).max()

        # WIND_MAX: max gió cả ngày
        wind_max = day_hourly["wind"].max()

        # PRESSURE: trung bình ngày
        pres = day_hourly["pressure"].mean()

        # HUMIDITY: trung bình ngày (tính từ hourly relativehumidity_2m nếu có)
        hum = None
        if "humidity" in day_hourly.columns:
            try:
                hum = day_hourly["humidity"].mean()
            except Exception:
                hum = None

        precip6_list.append(precip6)
        gust6_list.append(gust6)
        wind_max_list.append(wind_max)
        pressure_list.append(pres)
        humidity_list.append(hum)

    df_daily["precip6"] = precip6_list
    df_daily["gust6"] = gust6_list
    df_daily["wind_max"] = wind_max_list
    df_daily["pressure"] = pressure_list
    # Round humidity to 1 decimal place (keep NaN for missing values)
    try:
        df_daily["humidity"] = pd.Series(humidity_list).astype(float).round(1)
    except Exception:
        # Fallback: assign as-is and let later code handle missing values
        df_daily["humidity"] = humidity_list

    return df_daily



# ==============================
# INTEGRATION WITH DATA COLLECTOR
# ==============================

def get_river_discharge_for_location(lat, lon):
    """
    Lấy dữ liệu river discharge real-time từ data_collector
    
    Cố gắng import function get_flood_forecast từ data_collector.
    Nếu thành công, lấy river data real-time.
    Nếu thất bại, dùng fallback value.
    """
    try:
        # Thay vì gọi API chậm, cố gắng đọc nhanh từ file live_data.csv trong backend/data
        live_path = os.path.join(BASE_DIR, "data", "live_data.csv")
        if os.path.exists(live_path):
            import csv as _csv
            best = None
            best_dist = None
            # Hàm haversine nhẹ dùng numpy
            def _haversine(lat1, lon1, lat2, lon2):
                R = 6371.0
                phi1, phi2 = np.radians(lat1), np.radians(lat2)
                dphi = np.radians(lat2 - lat1)
                dlambda = np.radians(lon2 - lon1)
                a = np.sin(dphi / 2) ** 2 + np.cos(phi1) * np.cos(phi2) * np.sin(dlambda / 2) ** 2
                return 2 * R * np.arcsin(np.sqrt(a))

            with open(live_path, mode='r', encoding='utf-8-sig') as f:
                reader = _csv.DictReader(f)
                for row in reader:
                    try:
                        rlat = float(row.get('lat') or 0)
                        rlon = float(row.get('lon') or 0)
                        dist = _haversine(lat, lon, rlat, rlon)
                        if best is None or dist < best_dist:
                            best = row
                            best_dist = dist
                    except Exception:
                        continue

            if best is not None and best.get('river_discharge'):
                try:
                    val = float(best.get('river_discharge'))
                    print(f"[live_data] Using river discharge from live_data.csv: {val} (dist {best_dist:.2f} km)")
                    return val
                except Exception:
                    pass

        # Nếu không có live file hoặc không tìm được giá trị, fallback sang data_collector
        sys.path.insert(0, os.path.join(BASE_DIR, "app", "worker"))
        from data_collector import get_flood_forecast
        river_value = get_flood_forecast(lat, lon)
        if river_value is not None:
            print(f"[data_collector] Got river discharge: {river_value}")
            return river_value
        else:
            print(f"[data_collector] No river data available, using fallback")
            return None
    except Exception as e:
        print(f"Warning: Could not load river data from data_collector or live file: {e}")
        return None

# ==============================
# MAIN 7-DAY PIPELINE
# ==============================

def forecast_7_days(lat, lon):
    df_fc = get_7day(lat, lon)

    # Lấy river discharge từ data_collector
    river_discharge = get_river_discharge_for_location(lat, lon)
    if river_discharge is None:
        river_discharge = 15  # fallback

    results = []

    for _, row in df_fc.iterrows():
        
        temp_avg = (row["temp_max"] + row["temp_min"]) / 2
        precip24 = row["precip24"]
        precip6  = row["precip6"]
        wind     = row["wind_max"]
        gust6    = row["gust6"] + 3
        pressure = row["pressure"]

        river    = river_discharge
        eq_mag   = 0
        eq_dist  = 999

        # ===== RULE LABELS =====
        rain_lb  = label_rain(precip6, precip24)
        wind_lb  = label_wind(gust6)
        storm_lb = label_storm(gust6, precip6, precip24, wind, pressure)
        flood_lb = label_flood(river)
        eq_lb    = label_earthquake(None, None)
        overall_rule = overall_hazard_prediction_rule(
            flood_lb, storm_lb, rain_lb, wind_lb, eq_lb
        )

        # ===== FEATURES FOR MODEL =====
        # Use daily humidity computed earlier (fallback to 70 if missing)
        day_humidity = row.get("humidity")
        try:
            day_humidity = float(day_humidity) if day_humidity is not None and not pd.isna(day_humidity) else 70.0
        except Exception:
            day_humidity = 70.0

        feature_values = {
            "temperature": temp_avg,
            "humidity": day_humidity,
            "pressure": pressure,
            "wind_speed": wind,
            "precip6": precip6,
            "precip24": precip24,
            "gust6": gust6,
            "river_discharge": river,
            "eq_mag": eq_mag,
            "eq_dist": eq_dist,
        }

        scaler_features = [
            'temperature', 'humidity', 'pressure', 'wind_speed',
            'precip6', 'precip24', 'gust6', 'river_discharge', 'eq_mag', 'eq_dist'
        ]

        df_input_raw = pd.DataFrame([[feature_values[f] for f in scaler_features]],
                                    columns=scaler_features)

        df_input_scaled = pd.DataFrame(
            scaler.transform(df_input_raw),
            columns=scaler_features
        )

        label_to_numeric = {"no": 0, "low": 1, "mid": 2, "mid-high": 3, "high": 4}
        df_input_scaled["rain_label"] = label_to_numeric[rain_lb]
        df_input_scaled["wind_label"] = label_to_numeric[wind_lb]
        df_input_scaled["storm_label"] = label_to_numeric[storm_lb]
        df_input_scaled["flood_label"] = label_to_numeric[flood_lb]
        df_input_scaled["earthquake_label"] = label_to_numeric[eq_lb]

        df_input = df_input_scaled[feature_list]

        pred = model.predict(df_input)[0]
        hazard_ml = label_encoder.inverse_transform([pred])[0]

        results.append({
            "date": row["date"],
            "lat": lat,
            "lon": lon,
            "temp_avg": temp_avg,
            "temp_min": row.get("temp_min"),
            "temp_max": row.get("temp_max"),
            "humidity": feature_values["humidity"],
            "precip24": precip24,
            "precip6": precip6,
            "wind_max": wind,
            "gust6": gust6,
            "pressure": pressure,
            "river_discharge": river,

            # Rule labels
            "rain_label_rule": rain_lb,
            "wind_label_rule": wind_lb,
            "storm_label_rule": storm_lb,
            "flood_label_rule": flood_lb,
            "earthquake_label_rule": eq_lb,
            "overall_hazard_rule": overall_rule,

            # ML prediction
            "overall_hazard_ml": hazard_ml,
        })

    return pd.DataFrame(results)


# ==============================
# RUN DEMO
# ==============================

if __name__ == "__main__":
    lat = 15.096740
    lon = 108.853070

    df = forecast_7_days(lat, lon)
    print(df)
    
    # Lưu file CSV ở thư mục backend (cùng cấp với app/)
    output_path = os.path.join(BASE_DIR, "final_7day_forecast.csv")
    df.to_csv(output_path, index=False)
    print(f"\nSaved to {output_path}")

# ==============================
# EXPORT FUNCTION ĐỂ BACKEND DÙNG
# ==============================

def generate_forecast_for_location(lat: float, lon: float) -> pd.DataFrame:
    """
    Generate dự đoán 7 ngày cho tọa độ cụ thể
    
    Args:
        lat: Vĩ độ
        lon: Kinh độ
    
    Returns:
        DataFrame với 7 ngày dự đoán
    """
    return forecast_7_days(lat, lon)
