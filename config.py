"""
설정 파일 - 스코어링 가중치, 조회 기간, 유니버스 설정
필요에 따라 이 파일의 값만 바꾸면 전체 로직이 조정됩니다.
"""
import os

# ===== 유니버스 설정 =====
MARKETS = ["KOSPI", "KOSDAQ"]
UNIVERSE_PER_MARKET = 300  # 각 시장의 시가총액 상위 종목 수
MIN_MARKET_CAP = 0

# ===== 데이터 조회 기간 =====
PRICE_LOOKBACK_DAYS = 90
INVESTOR_LOOKBACK_DAYS = 20
BUYBACK_LOOKBACK_DAYS = 30

# ===== 스코어링 가중치 =====
WEIGHT_SUPPLY_DEMAND = 1 / 3
WEIGHT_TECHNICAL = 1 / 3
WEIGHT_EVENT = 1 / 3

# ===== 결과 노출 개수 =====
TOP_N = 10  # 첫 화면은 상위 10개, 전체보기로 분석 완료 종목 전체 표시

# ===== DART Open API =====
DART_API_KEY = os.environ.get("DART_API_KEY", "")

# ===== 경로 =====
DATA_DIR = "data"
DOCS_DIR = "docs"
