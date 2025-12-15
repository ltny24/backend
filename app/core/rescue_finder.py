import pandas as pd
import math
import os

class RescueFinder:
    def __init__(self, csv_path: str):
        self.csv_path = csv_path
        self.df = None
        self.load_data()

    def load_data(self):
        """Load dữ liệu CSV vào bộ nhớ RAM"""
        if os.path.exists(self.csv_path):
            try:
                self.df = pd.read_csv(self.csv_path)
                # Chuyển đổi cột Lat/Lon sang kiểu số
                self.df['Lat'] = pd.to_numeric(self.df['Lat'], errors='coerce')
                self.df['Lon'] = pd.to_numeric(self.df['Lon'], errors='coerce')
                self.df.dropna(subset=['Lat', 'Lon'], inplace=True)
                print(f"✅ Đã nạp {len(self.df)} địa điểm cứu hộ.")
            except Exception as e:
                print(f"❌ Lỗi khi đọc file CSV: {e}")
        else:
            print(f"⚠️ Không tìm thấy file tại: {self.csv_path}")

    def _haversine(self, lat1, lon1, lat2, lon2):
        """
        Thuật toán Haversine: Tính khoảng cách giữa 2 điểm trên mặt cầu (Trái đất)
        """
        R = 6371.0  # Bán kính Trái đất (km)
        
        d_lat = math.radians(lat2 - lat1)
        d_lon = math.radians(lon2 - lon1)
        
        a = (math.sin(d_lat / 2) ** 2 +
             math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
             math.sin(d_lon / 2) ** 2)
             
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return R * c

    def find_nearest_station(self, user_lat: float, user_lon: float, type_filter: str = None):
        """
        Tìm trạm gần nhất.
        Input: Lat, Lon của user.
        Output: Dict thông tin trạm gần nhất và khoảng cách.
        """
        if self.df is None or self.df.empty:
            return None

        min_dist = float('inf')
        nearest_station = None

        # Lọc theo loại (nếu cần)
        target_df = self.df
        if type_filter:
            # Giả sử trong CSV cột loại là 'Type'
            target_df = self.df[self.df['Type'] == type_filter]

        # Duyệt qua các điểm (Linear Search)
        # Với dữ liệu < 100k dòng, vòng lặp này vẫn cực nhanh (< 50ms)
        for _, row in target_df.iterrows():
            dist = self._haversine(user_lat, user_lon, row['Lat'], row['Lon'])
            
            if dist < min_dist:
                min_dist = dist
                nearest_station = row.to_dict()
                nearest_station['distance_km'] = round(dist, 2)

        return nearest_station

    def get_all_stations(self, type_filter: str = None):
        """
        Lấy tất cả các trạm cứu hộ (tùy chọn lọc theo loại).
        Input: type_filter (optional): 'hospital', 'police', 'townhall', v.v.
        Output: List of dicts chứa thông tin tất cả trạm.
        """
        if self.df is None or self.df.empty:
            return []
        
        target_df = self.df
        if type_filter:
            target_df = self.df[self.df['Type'] == type_filter]
        
        # Chuyển đổi thành list of dicts
        stations = []
        for _, row in target_df.iterrows():
            station = row.to_dict()
            # Xóa các giá trị NaN
            station = {k: v for k, v in station.items() if pd.notna(v)}
            stations.append(station)
        
        return stations


current_file_path = os.path.abspath(__file__)

core_dir = os.path.dirname(current_file_path)

backend_dir = os.path.dirname(os.path.dirname(core_dir))

csv_file_path = os.path.join(backend_dir, "Vietnam_Rescue.csv")

# Khởi tạo
rescue_finder = RescueFinder(csv_file_path)