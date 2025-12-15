import os

# Đường dẫn gốc của dự án
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Đường dẫn dữ liệu
DATA_DIR = os.path.join(BASE_DIR, "data")
HISTORY_PATH = os.path.join(DATA_DIR, "history", "history.csv")
INFRA_PATH = os.path.join(DATA_DIR, "infrastructure")
MODEL_PATH = os.path.join(DATA_DIR, "models", "xgboost_safety.json")

DB_CONFIG = {
    "dbname": "itss_database",
    "user": "postgres",
    "password": "123", # Đảm bảo password đúng với máy bạn
    "host": "localhost",
    "port": "5432"
}

# API Key thật (để gọi OWM khi cần dữ liệu Live tức thì)
OWM_API_KEYS_LIST = [
    "8814cbadb40070726540197edbc5ed82",
    "a07905a6a722d423ac074ec59c6dc56c",
    "41574e5785febeb20b7ec9706ac2960a",
    "fa04a6d7dd10c2c5e5f313961ed9b748",
    "40c1b74868dc5a2187dcea556c138187",
    "4886be21c34791c6d9fe85a481edfe31",
    "4c810aff81a26a9f4fadd2dea2281f29",
    "588f2d0f4434cb5d018d09489e0f441a",
    "ae8ebf9e892fce5ee5eb7276c4bba186",
    "7d0c971c45fc5617ac58eb75b3b34233",
]
# Cấu hình model
MODEL_PARAMS = {
    "n_estimators": 100,
    "learning_rate": 0.1,
    "max_depth": 5,
    "objective": "reg:squarederror"
}

GDACS_URL = "https://www.gdacs.org/Xml/rssarchive.xml"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36"
}

VIETNAM_BBOX = {
    "min_lon": 102.0, "min_lat": 8.0,
    "max_lon": 110.0, "max_lat": 23.5
}

# Fallback nếu không đọc được CSV
TARGET_LOCATIONS = [
    {"name": "Ho Chi Minh City", "lat": 10.7769, "lon": 106.7009}
]