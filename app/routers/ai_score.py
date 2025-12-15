from fastapi import APIRouter, HTTPException
# Import Schema và Predictor chúng ta đã sửa ở bước trước
from app.ml.predictor import SafetyPredictor
from app.ml.schemas import SafetyInput # Hoặc .schemas nếu bạn đặt tên đó

router = APIRouter()

# Khởi tạo model 1 lần duy nhất để dùng chung
try:
    predictor = SafetyPredictor()
except Exception as e:
    print(f"❌ [AIRouter] Lỗi load AI Model: {e}")
    predictor = None

@router.post("/predict")
def predict_safety_score(data: SafetyInput):
    """
    API nhận thông tin thời tiết -> Trả về điểm an toàn (0-100) và mức độ rủi ro.
    """
    if not predictor:
        raise HTTPException(status_code=500, detail="AI Model chưa sẵn sàng")
    
    try:
        # Gọi hàm predict từ class SafetyPredictor
        result = predictor.predict(data)
        return {
            "success": True,
            "data": result,
            "input_summary": f"{data.location} (Temp: {data.temperature})"
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Lỗi dự đoán: {str(e)}")