from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from app.core.rescue_finder import rescue_finder # Import logic từ bước 1
import httpx

router = APIRouter(
    tags=["Rescue"],
    responses={404: {"description": "Not found"}},
)

# Định nghĩa dữ liệu đầu vào
class UserLocation(BaseModel):
    lat: float
    lon: float
    filter_type: str = None  # Tùy chọn: 'hospital', 'police', v.v.

@router.post("/nearest")
async def get_nearest_rescue(location: UserLocation):
    """
    API tìm nơi viện trợ gần nhất dựa trên tọa độ người dùng.
    """
    try:
        result = rescue_finder.find_nearest_station(
            location.lat, 
            location.lon, 
            location.filter_type
        )
        
        if result:
            return {
                "status": "success",
                "data": result,
                "message": "Đã tìm thấy trạm gần nhất"
            }
        else:
            return {
                "status": "not_found", 
                "message": "Không tìm thấy dữ liệu hoặc không có trạm phù hợp"
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/list")
async def get_all_rescue_stations(filter_type: str = None):
    """
    API lấy danh sách tất cả các nơi cứu hộ (bệnh viện, công an, UBND, v.v.).
    
    Query parameters:
        - filter_type: Lọc theo loại (optional): 'hospital', 'police', 'townhall', 'fire_station', v.v.
    
    Response: List of rescue stations với tất cả thông tin (Name, Type, Phone, Lat, Lon, Address)
    """
    try:
        stations = rescue_finder.get_all_stations(filter_type)
        
        return {
            "status": "success",
            "data": stations,
            "count": len(stations),
            "message": f"Đã lấy {len(stations)} trạm cứu hộ" + (f" loại {filter_type}" if filter_type else "")
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/route/{profile}/{coordinates}")
async def get_route_proxy(profile: str, coordinates: str, request: Request):
    """
    Proxy endpoint để lấy đường đi từ OSRM service.
    Format: /route/driving/lng1,lat1;lng2,lat2?overview=full&geometries=geojson&...
    """
    try:
        # Build URL with query params from frontend
        query_string = str(request.url.query)
        if query_string:
            osrm_url = f"https://router.project-osrm.org/route/v1/{profile}/{coordinates}?{query_string}"
        else:
            osrm_url = f"https://router.project-osrm.org/route/v1/{profile}/{coordinates}"
        
        print(f"[ROUTING PROXY] ✓ Request received")
        print(f"[ROUTING PROXY] Profile: {profile}")
        print(f"[ROUTING PROXY] Coordinates: {coordinates}")
        print(f"[ROUTING PROXY] Query: {query_string}")
        print(f"[ROUTING PROXY] Full URL: {osrm_url}")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(osrm_url)
            print(f"[ROUTING PROXY] ✓ Response status: {response.status_code}")
            
            response.raise_for_status()
            data = response.json()
            
            print(f"[ROUTING PROXY] ✓ Routes found: {len(data.get('routes', []))}")
            if data.get('routes'):
                print(f"[ROUTING PROXY] ✓ First route distance: {data['routes'][0].get('distance')} meters")
            return data
            
    except httpx.TimeoutException:
        print("[ROUTING PROXY] ✗ Timeout error")
        raise HTTPException(status_code=504, detail="Routing service timeout")
    except httpx.HTTPError as e:
        print(f"[ROUTING PROXY] ✗ HTTP Error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"OSRM service error: {str(e)}")
    except Exception as e:
        print(f"[ROUTING PROXY] ✗ Exception: {type(e).__name__}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
        raise HTTPException(status_code=500, detail=str(e))