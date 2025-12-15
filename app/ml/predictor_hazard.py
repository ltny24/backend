import os
import joblib
import numpy as np
import pandas as pd
import xgboost as xgb

# Lấy đường dẫn gốc
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

MODEL_PATH = os.path.join(BASE_DIR, "data", "models", "hazard_model.pkl")
# Chúng ta sẽ ưu tiên lấy feature từ model, file này chỉ là dự phòng
FEATURES_PATH = os.path.join(BASE_DIR, "data", "models", "features_list.pkl")
LABEL_PATH = os.path.join(BASE_DIR, "data", "models", "hazard_label_encoder.pkl")

# Mapping chuẩn để chuyển đổi chuỗi sang số (Khớp với logic data_collector)
RISK_MAPPING = {
    "no": 0, "safe": 0,
    "low": 1, "info": 1,
    "mid": 2, "medium": 2,
    "mid-high": 3,
    "high": 4, "danger": 4
}

class HazardPredictor:
    def __init__(self):
        self.model = None
        self.features = []
        self.label_encoder = None
        self.model_type = "sklearn" # Mặc định
        
        self.DEFAULT_MAP = {
            0: "No", 1: "Rain", 2: "Storm", 3: "Wind", 4: "Flood", 5: "Earthquake"
        }
        
        self._load_model()

    def _load_model(self):
        if not os.path.exists(MODEL_PATH):
            print(f"⚠️ Model not found at: {MODEL_PATH}")
            return

        try:
            # 1. Load Model
            loaded_object = joblib.load(MODEL_PATH)

            # Tự động nhận diện loại Model
            if isinstance(loaded_object, xgb.Booster):
                self.model = loaded_object
                self.model_type = "xgboost"
            elif hasattr(loaded_object, "get_booster"): 
                self.model = loaded_object.get_booster()
                self.model_type = "xgboost"
            else:
                self.model = loaded_object
                self.model_type = "sklearn"

            # 2. TỰ ĐỘNG LẤY FEATURE NAMES TỪ MODEL (Quan trọng để fix lỗi)
            if hasattr(self.model, "feature_names_in_"):
                self.features = list(self.model.feature_names_in_)
                print(f"✅ Detected features from model: {self.features}")
            elif hasattr(self.model, "feature_names"):
                self.features = list(self.model.feature_names)
                print(f"✅ Detected features from booster: {self.features}")
            elif os.path.exists(FEATURES_PATH):
                # Chỉ dùng file list nếu model không tự khai báo được
                self.features = joblib.load(FEATURES_PATH)
                print(f"⚠️ Loaded features from list file: {self.features}")
            else:
                print("❌ Cannot determine input features!")

            # 3. Load Label Encoder cho Output
            if os.path.exists(LABEL_PATH):
                self.label_encoder = joblib.load(LABEL_PATH)

            print(f"✅ Hazard Model loaded ({self.model_type}).")
            
        except Exception as e:
            print(f"❌ Error loading model: {e}")
            self.model = None

    def _prepare_value(self, feature_name, value):
        """
        Xử lý giá trị đầu vào:
        - Nếu là số: Giữ nguyên.
        - Nếu là chuỗi (High, Low...): Chuyển thành số (4, 1...).
        """
        # Nếu giá trị là chuỗi, thử map sang số
        if isinstance(value, str):
            val_lower = value.lower().strip()
            return float(RISK_MAPPING.get(val_lower, 0)) # Mặc định 0 nếu không khớp
        
        # Nếu là số thì ép kiểu float
        try:
            return float(value)
        except:
            return 0.0

    def _prepare(self, data: dict):
        """Chuẩn bị dữ liệu input khớp hoàn toàn với yêu cầu của Model"""
        try:
            row = []
            if not self.features:
                print("⚠️ No features defined for model input.")
                return None

            for feature in self.features:
                # Lấy giá trị từ DB (data)
                raw_val = data.get(feature, 0)
                
                # Xử lý giá trị (Encode nếu cần)
                clean_val = self._prepare_value(feature, raw_val)
                row.append(clean_val)
                
            return np.array(row).reshape(1, -1)
        except Exception as e:
            print(f"⚠️ Error preparing data: {e}")
            return None

    def predict_overall_hazard(self, input_data: dict):
        if not self.model:
            return "Unknown"

        try:
            # 1. Chuẩn bị dữ liệu
            X = self._prepare(input_data)
            if X is None: return "Unknown"
            
            # 2. Chạy dự báo
            if self.model_type == "xgboost":
                dmatrix = xgb.DMatrix(X)
                dmatrix.feature_names = self.features
                pred_raw = self.model.predict(dmatrix)
            else:
                # Scikit-Learn cần DataFrame có tên cột
                X_df = pd.DataFrame(X, columns=self.features)
                pred_raw = self.model.predict(X_df)
            
            # 3. Xử lý kết quả
            if isinstance(pred_raw, list): pred_raw = np.array(pred_raw)

            if len(pred_raw.shape) > 1:
                label_id = int(np.argmax(pred_raw[0]))
            else:
                val = pred_raw[0] if isinstance(pred_raw, (np.ndarray, list)) else pred_raw
                label_id = int(round(val))

            # 4. Map sang tên gọi
            if self.label_encoder:
                try:
                    return self.label_encoder.inverse_transform([label_id])[0]
                except:
                    return self.DEFAULT_MAP.get(label_id, "Unknown")
            else:
                return self.DEFAULT_MAP.get(label_id, "Unknown")

        except Exception as e:
            print(f"⚠️ Prediction logic error: {e}")
            return "Unknown"