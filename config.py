"""
설정 파일 - 스코어링 가중치, 조회 기간, 유니버스 설정
필요에 따라 이 파일의 값만 바꾸면 전체 로직이 조정됩니다.
"""
import os

# ===== 유니버스 설정 =====
MARKETS = ["KOSPI", "KOSDAQ"]  # 코스피 + 코스닥 전체
MIN_MARKET_CAP = 0  # 시가총액 필터(원). 0이면 필터 없음.
# 종목 수가 많아 Actions 실행 시간이 너무 길어지면(2500여 종목 x 매일 실행)
# 예: 50_000_000_000 (500억) 처럼 값을 주면 소형주를 제외해 속도를 크게 줄일 수 있습니다.

# ===== 데이터 조회 기간 =====
PRICE_LOOKBACK_DAYS = 90      # 기술적지표 계산용 가격 데이터 조회일수
INVESTOR_LOOKBACK_DAYS = 20   # 기관/외국인 수급 조회 거래일수
BUYBACK_LOOKBACK_DAYS = 30    # 자사주 매입/소각 공시 조회일수(최근 N일 이내 공시만 유효 처리)

# ===== 스코어링 가중치 (요청하신 대로 3항목 균등 비중) =====
WEIGHT_SUPPLY_DEMAND = 1 / 3   # 기관/외국인 수급
WEIGHT_TECHNICAL = 1 / 3       # 기술적지표
WEIGHT_EVENT = 1 / 3           # 자사주 매입/소각 등 재료성 이벤트

# ===== 결과 노출 개수 =====
TOP_N = 50  # 홈페이지에 표시할 상위 종목 수

# ===== DART Open API =====
# https://opendart.fss.or.kr 에서 무료 회원가입 후 발급받은 인증키를
# GitHub 저장소 Settings > Secrets and variables > Actions 에 DART_API_KEY 로 등록하세요.
DART_API_KEY = os.environ.get("DART_API_KEY", "")

# ===== 경로 =====
DATA_DIR = "data"
DOCS_DIR = "docs"
