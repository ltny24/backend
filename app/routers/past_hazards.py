from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import List, Optional
import pandas as pd
import os
import joblib
from datetime import datetime
import numpy as np

router = APIRouter()

# Đường dẫn tới file dữ liệu
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
NORMALIZED_DATA_PATH = os.path.join(BASE_DIR, "data", "normalized_data.csv")
SCALER_PATH = os.path.join(BASE_DIR, "data", "models", "hazard_scaler.pkl")

# Load scaler
try:
    scaler = joblib.load(SCALER_PATH)
except Exception as e:
    print(f"Warning: Could not load scaler: {e}")
    scaler = None

class HazardStat(BaseModel):
    """Thống kê 1 loại hazard"""
    hazard_type: str  # "Rain", "Wind", "Storm", "Flood", "Earthquake"
    count: int
    percentage: float
    high_events: int
    mid_high_events: int
    mid_events: int
    low_events: int
    no_events: int
    top_months: List[int] = []
    top_provinces: List[str] = []

class PastHazardsResponse(BaseModel):
    """Response tổng hợp thống kê các hazard quá khứ"""
    success: bool
    total_records: int
    year_range: str
    hazards_stats: List[HazardStat]
    top_locations: dict  # { location: count }

def inverse_transform_features(df: pd.DataFrame, features_list: list) -> pd.DataFrame:
    """
    Inverse transform normalized features back to original scale using scaler.
    features_list: list of column names to inverse transform
    """
    if scaler is None:
        return df
    
    try:
        # Lấy những cột cần transform
        cols_to_transform = [c for c in features_list if c in df.columns]
        if not cols_to_transform:
            return df
        
        # Inverse transform
        df_copy = df.copy()
        df_copy[cols_to_transform] = scaler.inverse_transform(df[cols_to_transform])
        return df_copy
    except Exception as e:
        print(f"Warning: Could not inverse transform: {e}")
        return df

def is_large_hazard(row) -> bool:
    """
    Xác định nếu hazard là 'lớn' (high hoặc mid-high risk).
    """
    hazard_cols = ['rain_label', 'wind_label', 'storm_label', 'flood_label', 'earthquake_label']
    for col in hazard_cols:
        val = str(row.get(col, 'no')).lower()
        if val in ['high', 'mid-high']:
            return True
    return False

@router.get("", response_model=PastHazardsResponse, tags=["Past Hazards"])
@router.get("/", response_model=PastHazardsResponse, tags=["Past Hazards"])
async def get_past_hazards(
    year: Optional[int] = Query(None, description="Specific year (default: all 2024-2025)"),
    include_all: bool = Query(True, description="Include all hazards or only large ones"),
    province: Optional[str] = Query(None, description="Province name to filter records (exact match from data list)"),
    center_lat: Optional[float] = Query(None, description="Center latitude to filter by distance"),
    center_lon: Optional[float] = Query(None, description="Center longitude to filter by distance"),
    radius_km: Optional[float] = Query(50.0, description="Radius in km to filter around center")
) -> PastHazardsResponse:
    """
    Lấy thống kê các thiên tai đã xảy ra trong 2024-2025 (hoặc năm chỉ định).
    
    **Query Parameters:**
    - `year` (optional): Năm cụ thể (mặc định: tất cả 2024-2025)
    - `include_all` (bool): Nếu True, tính tất cả hazard; nếu False, chỉ hazard lớn (high/mid-high)
    
    **Response:**
    - Thống kê từng loại hazard: Rain, Wind, Storm, Flood, Earthquake
    - Tổng số bản ghi
    - Top locations
    """
    try:
        # Kiểm tra file tồn tại
        if not os.path.exists(NORMALIZED_DATA_PATH):
            raise FileNotFoundError(f"Dữ liệu không tìm thấy: {NORMALIZED_DATA_PATH}")
        
        # Đọc dữ liệu bằng chunk để tránh memory overload (file 57.77 MB)
        print(f"📊 Reading normalized_data.csv from {NORMALIZED_DATA_PATH}")
        
        # Initialize collections
        all_data = []
        hazard_counts = {
            'rain': {'high': 0, 'mid-high': 0, 'mid': 0, 'low': 0, 'no': 0},
            'wind': {'high': 0, 'mid-high': 0, 'mid': 0, 'low': 0, 'no': 0},
            'storm': {'high': 0, 'mid-high': 0, 'mid': 0, 'low': 0, 'no': 0},
            'flood': {'high': 0, 'mid-high': 0, 'mid': 0, 'low': 0, 'no': 0},
            'earthquake': {'high': 0, 'mid-high': 0, 'mid': 0, 'low': 0, 'no': 0},
        }
        location_counts = {}
        # Per-hazard month and province counters
        month_counts = {
            'rain': {}, 'wind': {}, 'storm': {}, 'flood': {}, 'earthquake': {}
        }
        province_counts = {
            'rain': {}, 'wind': {}, 'storm': {}, 'flood': {}, 'earthquake': {}
        }
        # For earthquake we also aggregate eq_dist sums/counts per province to compute average distance
        province_eq_dist = { 'earthquake': {} }
        year_min, year_max = None, None
        total_filtered = 0
        
        # Read in chunks
        chunk_size = 10000
        for chunk in pd.read_csv(NORMALIZED_DATA_PATH, chunksize=chunk_size):
            # Normalize year column to string for robust comparison (handles stray header rows)
            chunk_year_str = chunk['year'].astype(str)
            if year:
                chunk = chunk[(chunk_year_str == str(year))]
            else:
                chunk = chunk[chunk_year_str.isin(["2024", "2025"])]
            
            if chunk.empty:
                continue

            # If province provided, filter rows whose location ends with that province
            if province:
                if 'location' in chunk.columns:
                    prov_series = chunk['location'].astype(str).str.split(' - ').str[-1].str.strip().str.lower()
                    chunk = chunk[prov_series == str(province).strip().lower()]
                else:
                    continue

            # If center coordinates provided, filter rows by haversine distance <= radius_km
            if center_lat is not None and center_lon is not None:
                if 'lat' in chunk.columns and 'lon' in chunk.columns:
                    # coerce numeric
                    lat2 = pd.to_numeric(chunk['lat'], errors='coerce')
                    lon2 = pd.to_numeric(chunk['lon'], errors='coerce')
                    # drop rows without coords
                    mask_valid = lat2.notna() & lon2.notna()
                    if not mask_valid.any():
                        continue
                    lat2 = lat2[mask_valid]
                    lon2 = lon2[mask_valid]
                    # haversine vectorized
                    R = 6371.0
                    lat1 = float(center_lat) * (3.141592653589793 / 180.0)
                    lon1 = float(center_lon) * (3.141592653589793 / 180.0)
                    lat2r = lat2 * (3.141592653589793 / 180.0)
                    lon2r = lon2 * (3.141592653589793 / 180.0)
                    dlat = lat2r - lat1
                    dlon = lon2r - lon1
                    a = (np.sin(dlat / 2) ** 2) + np.cos(lat1) * np.cos(lat2r) * (np.sin(dlon / 2) ** 2)
                    c = 2 * np.arcsin(np.sqrt(a))
                    d = R * c
                    # rebuild chunk with mask (align index)
                    within_mask = d <= float(radius_km)
                    # map back to original chunk index
                    keep_index = lat2.index[within_mask]
                    chunk = chunk.loc[keep_index]
                else:
                    # no lat/lon to filter, skip this chunk
                    continue
            
            # Filter large hazards if not include_all
            if not include_all:
                chunk = chunk[chunk.apply(is_large_hazard, axis=1)]
            
            if chunk.empty:
                continue
            
            # Count hazards
            for hz_type in ['rain', 'wind', 'storm', 'flood', 'earthquake']:
                col_name = f"{hz_type}_label"
                if col_name in chunk.columns:
                    # normalize to lowercase strings to avoid capitalization mismatches
                    counts = chunk[col_name].fillna('no').astype(str).str.lower().value_counts().to_dict()
                    for level in ['high', 'mid-high', 'mid', 'low', 'no']:
                        hazard_counts[hz_type][level] += counts.get(level, 0)
                    # For statistics we only consider mid and above (exclude 'low')
                    # Special case: for wind, exclude 'mid' (only 'high' and 'mid-high')
                    if hz_type == 'wind':
                        mid_plus_mask = chunk[col_name].fillna('no').astype(str).str.lower().isin(['high', 'mid-high'])
                    else:
                        mid_plus_mask = chunk[col_name].fillna('no').astype(str).str.lower().isin(['high', 'mid-high', 'mid'])
                    non_low_rows = chunk[mid_plus_mask]
                    if not non_low_rows.empty:
                        # Month counts (mid+ only)
                        if 'month' in non_low_rows.columns:
                            months = non_low_rows['month'].astype(int).value_counts().to_dict()
                            for m, c in months.items():
                                month_counts[hz_type][int(m)] = month_counts[hz_type].get(int(m), 0) + int(c)
                        # Province counts from location (assume format 'Area - Province') (mid+ only)
                        if 'location' in non_low_rows.columns:
                            provs = non_low_rows['location'].apply(lambda x: str(x).split(' - ')[-1].strip()).value_counts().to_dict()
                            for p, c in provs.items():
                                province_counts[hz_type][p] = province_counts[hz_type].get(p, 0) + int(c)
                        # Special: for earthquake gather eq_dist per province to compute average distance
                        if hz_type == 'earthquake' and 'eq_dist' in non_low_rows.columns:
                            # coerce numeric eq_dist
                            non_low_rows['eq_dist_num'] = pd.to_numeric(non_low_rows['eq_dist'], errors='coerce')
                            for prov, grp in non_low_rows.groupby(non_low_rows['location'].apply(lambda x: str(x).split(' - ')[-1].strip())):
                                vals = grp['eq_dist_num'].dropna()
                                if vals.empty:
                                    continue
                                s = vals.sum()
                                c = len(vals)
                                if prov not in province_eq_dist['earthquake']:
                                    province_eq_dist['earthquake'][prov] = [0.0, 0]
                                province_eq_dist['earthquake'][prov][0] += float(s)
                                province_eq_dist['earthquake'][prov][1] += int(c)
            
            # Count locations
            if 'location' in chunk.columns:
                loc_counts = chunk['location'].value_counts().to_dict()
                for loc, cnt in loc_counts.items():
                    location_counts[loc] = location_counts.get(loc, 0) + cnt
            
            # Track year range
            if 'year' in chunk.columns:
                    # Coerce to numeric years, ignore non-numeric rows
                    numeric_years = pd.to_numeric(chunk['year'], errors='coerce').dropna().astype(int).unique()
                    if len(numeric_years) > 0:
                        if year_min is None:
                            year_min = numeric_years.min()
                            year_max = numeric_years.max()
                        else:
                            year_min = min(year_min, numeric_years.min())
                            year_max = max(year_max, numeric_years.max())
            
            total_filtered += len(chunk)
        
        if total_filtered == 0:
            return PastHazardsResponse(
                success=False,
                total_records=0,
                year_range=f"{year}" if year else "2024-2025",
                hazards_stats=[],
                top_locations={}
            )
        
        year_range = f"{year_min}-{year_max}" if year_min is not None else (f"{year}" if year else "2024-2025")
        
        # Build hazard stats
        hazards_stats = []
        hazard_types = ['rain', 'wind', 'storm', 'flood', 'earthquake']
        
        for hz_type in hazard_types:
            counts = hazard_counts[hz_type]
            total = sum(counts.values())
            # For reported stats we exclude 'low' — only mid and above
            # Special case: for wind, exclude 'mid' from reported stats
            if hz_type == 'wind':
                non_no = sum(v for k, v in counts.items() if k in ['high', 'mid-high'])
            else:
                non_no = sum(v for k, v in counts.items() if k in ['high', 'mid-high', 'mid'])
            # percentage = share of this hazard's mid+ events relative to all filtered records
            percentage = (non_no / total_filtered * 100) if total_filtered > 0 else 0

            # Top months and provinces
            top_months = []
            if month_counts.get(hz_type):
                sorted_months = sorted(month_counts[hz_type].items(), key=lambda x: x[1], reverse=True)
                top_months = [int(m) for m, _ in sorted_months[:2]]

            top_provs = []
            if hz_type == 'earthquake':
                # For earthquake present province with average eq_dist: "Province cách X km"
                provs = province_eq_dist.get('earthquake', {})
                if provs:
                    # compute average and sort by count (descending)
                    prov_list = []
                    # match counts for ordering
                    prov_counts = province_counts.get('earthquake', {})
                    for p, (s, c) in provs.items():
                        avg = s / c if c > 0 else None
                        prov_list.append((p, prov_counts.get(p, 0), avg))
                    prov_list_sorted = sorted(prov_list, key=lambda x: x[1], reverse=True)
                    top_provs = [f"{p} cách {round(avg,1)}km" for p, _, avg in prov_list_sorted[:4] if avg is not None]
                else:
                    # fallback to simple province counts
                    if province_counts.get('earthquake'):
                        sorted_provs = sorted(province_counts['earthquake'].items(), key=lambda x: x[1], reverse=True)
                        top_provs = [p for p, _ in sorted_provs[:4]]
            else:
                if province_counts.get(hz_type):
                    sorted_provs = sorted(province_counts[hz_type].items(), key=lambda x: x[1], reverse=True)
                    top_provs = [p for p, _ in sorted_provs[:4]]
            # For wind, hide mid_events in the returned breakdown (set to 0)
            mid_events_value = counts.get('mid', 0)
            if hz_type == 'wind':
                mid_events_value = 0

            stat = HazardStat(
                hazard_type=hz_type.capitalize(),
                count=non_no,
                percentage=round(percentage, 2),
                high_events=counts.get('high', 0),
                mid_high_events=counts.get('mid-high', 0),
                mid_events=mid_events_value,
                low_events=counts.get('low', 0),
                no_events=counts.get('no', 0),
                top_months=top_months,
                top_provinces=top_provs
            )
            hazards_stats.append(stat)
        
        # Top locations
        top_locs = dict(sorted(location_counts.items(), key=lambda x: x[1], reverse=True)[:10])
        
        print(f"✅ Processed {total_filtered} records with hazards")
        
        return PastHazardsResponse(
            success=True,
            total_records=total_filtered,
            year_range=year_range,
            hazards_stats=hazards_stats,
            top_locations=top_locs
        )
    
    except FileNotFoundError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        print(f"❌ Error in past_hazards endpoint: {e}")
        raise HTTPException(status_code=500, detail=f"Lỗi khi lấy dữ liệu: {str(e)}")

@router.get("/by-month", tags=["Past Hazards"])
async def get_hazards_by_month(year: Optional[int] = Query(None)):
    """
    Lấy thống kê hazard theo tháng trong năm chỉ định (hoặc toàn bộ 2024-2025).
    
    **Response:**
    - Dữ liệu hazard cho từng tháng
    """
    try:
        if not os.path.exists(NORMALIZED_DATA_PATH):
            raise FileNotFoundError(f"Dữ liệu không tìm thấy: {NORMALIZED_DATA_PATH}")
        
        df = pd.read_csv(NORMALIZED_DATA_PATH)
        # coerce numeric year matching for robustness
        df['year'] = pd.to_numeric(df['year'], errors='coerce')
        if year:
            df = df[df['year'] == int(year)]
        else:
            df = df[df['year'].isin([2024, 2025])]
        
        # Lọc chỉ hazard lớn
        df = df[df.apply(is_large_hazard, axis=1)]
        
        if df.empty:
            return {
                "success": False,
                "message": "Không có dữ liệu",
                "data": {}
            }
        
        # Group by month
        monthly_data = {}
        for month in range(1, 13):
            month_df = df[df['month'] == month]
            if not month_df.empty:
                monthly_data[str(month)] = {
                    "count": len(month_df),
                    "locations": len(month_df['location'].unique()),
                    "primary_hazard": month_df['overall_hazard_prediction'].value_counts().index[0] if not month_df.empty else "Unknown"
                }
        
        return {
            "success": True,
            "year": year if year else "2024-2025",
            "data": monthly_data
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi: {str(e)}")
