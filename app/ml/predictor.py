import os
import joblib
import pandas as pd
import xgboost as xgb
import json

# --- SỬA LỖI IMPORT TẠI ĐÂY ---
# Thay vì "from src.schemas.safety_schema...", ta dùng đường dẫn mới:
try:
    # Nếu bạn đặt file là app/ml/schemas.py
    from app.ml.schemas import SafetyInput 
except ImportError:
    # Fallback: Nếu bạn vẫn để tên cũ là safety_schema.py trong app/ml/
    try:
        from app.ml.schemas import SafetyInput
    except ImportError:
        # Fallback 2: Nếu chạy trực tiếp tại thư mục con (lúc test)
        from .schemas import SafetyInput

# --- CẤU HÌNH ĐƯỜNG DẪN MODEL (Tuyệt đối hóa để tránh lỗi File Not Found) ---
# Lấy đường dẫn gốc của dự án (TravelSafetyBackend)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Trỏ vào thư mục data/models mà bạn đã copy sang
MODEL_PATH = os.path.join(BASE_DIR, "data", "models", "xgboost_safety.json")
FEATURES_PATH = os.path.join(BASE_DIR, "data", "models", "features_list.pkl")

class SafetyPredictor:
    def __init__(self):
        self.model = None
        self.features = []
        self._load_model()

    def _load_model(self):
        """Load model XGBoost và danh sách features"""
        if not os.path.exists(MODEL_PATH):
            raise FileNotFoundError(f"❌ Không tìm thấy model tại: {MODEL_PATH}")
        
        if not os.path.exists(FEATURES_PATH):
            raise FileNotFoundError(f"❌ Không tìm thấy feature list tại: {FEATURES_PATH}")

        # Load Model
        self.model = xgb.Booster()
        self.model.load_model(MODEL_PATH)
        
        # Load Features List
        self.features = joblib.load(FEATURES_PATH)
        print(f"✅ AI Model loaded successfully from {MODEL_PATH}")

    def predict_safety_score(self, input_data: dict) -> dict:
        """
        Dự đoán điểm an toàn từ dữ liệu đầu vào.
        Input: Dictionary chứa các trường như temperature, wind_speed...
        Output: Dictionary {'safety_score': 85, 'risk_level': 'Low', ...}
        """
        if not self.model:
            raise Exception("Model chưa được load!")

        # 1. Chuyển đổi input dict thành DataFrame
        # Đảm bảo thứ tự cột khớp với lúc train (dùng self.features)
        input_df = pd.DataFrame([input_data])
        
        # Tạo các cột còn thiếu (nếu có) và điền 0 hoặc giá trị mặc định
        for col in self.features:
            if col not in input_df.columns:
                input_df[col] = 0.0
                
        # Chỉ lấy đúng các cột feature cần thiết theo thứ tự
        input_df = input_df[self.features]

        # 2. Tạo DMatrix cho XGBoost
        dtest = xgb.DMatrix(input_df)

        # 3. Dự đoán (Model trả về giá trị 0-100 hoặc 0-1 tùy lúc train)
        # Giả sử model trả về 0-100
        score = self.model.predict(dtest)[0]
        
        # Logic hậu xử lý (nếu model trả về 0-1 thì nhân 100)
        # score = float(score) * 100 if score <= 1 else float(score)
        
        final_score = float(score)

        # 4. Phân loại rủi ro (Logic riêng của AI hoặc dùng chung GIS)
        risk_level = "Info"
        if final_score < 25: risk_level = "High"
        elif final_score < 50: risk_level = "Medium"
        elif final_score < 80: risk_level = "Low"

        return {
            "safety_score": round(final_score, 2),
            "risk_level": risk_level
        }

    # Hàm wrapper để hỗ trợ Pydantic Input (nếu gọi từ API)
    def predict(self, input_obj):
        if hasattr(input_obj, 'dict'):
            data = input_obj.dict()
        else:
            data = input_obj
        return self.predict_safety_score(data)