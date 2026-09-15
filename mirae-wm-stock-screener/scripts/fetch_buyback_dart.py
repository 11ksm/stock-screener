"""
자사주 매입/처분/소각 공시 수집 (DART Open API, https://opendart.fss.or.kr)
무료 API 키가 필요합니다 (회원가입 후 즉시 발급).
GitHub Secrets에 DART_API_KEY 로 등록하면 자동으로 사용됩니다.
"""
import os
import time
from datetime import datetime, timedelta

import requests
import pandas as pd
import config

DART_LIST_URL = "https://opendart.fss.or.kr/api/list.json"

# 소각 > 취득 > 처분 순으로 주가에 우호적이라고 보고 가중치를 다르게 부여
KEYWORD_WEIGHTS = [
    ("소각", 100),
    ("취득", 80),
    ("처분", 30),
]


def keyword_weight(report_nm: str) -> int:
    for kw, w in KEYWORD_WEIGHTS:
        if kw in report_nm and "자기주식" in report_nm:
            return w
    return 0


def fetch_buyback_disclosures() -> pd.DataFrame:
    if not config.DART_API_KEY:
        print("[재료이벤트] DART_API_KEY가 설정되지 않아 이 단계는 건너뜁니다. (수급/기술 2항목만으로 임시 산정)")
        empty = pd.DataFrame(columns=["stock_code", "corp_name", "report_nm", "rcept_dt", "event_raw"])
        os.makedirs(config.DATA_DIR, exist_ok=True)
        empty.to_csv(os.path.join(config.DATA_DIR, "buyback_events.csv"), index=False, encoding="utf-8-sig")
        return empty

    end = datetime.today()
    start = end - timedelta(days=config.BUYBACK_LOOKBACK_DAYS)

    rows = []
    page = 1
    while True:
        params = {
            "crtfc_key": config.DART_API_KEY,
            "bgn_de": start.strftime("%Y%m%d"),
            "end_de": end.strftime("%Y%m%d"),
            "page_no": page,
            "page_count": 100,
        }
        try:
            resp = requests.get(DART_LIST_URL, params=params, timeout=10)
            data = resp.json()
        except Exception as e:
            print(f"[재료이벤트] DART 요청 실패: {e}")
            break

        if data.get("status") != "000":
            # 013: 해당 기간에 공시 없음 등 - 정상 종료 케이스도 포함
            break

        items = data.get("list", [])
        if not items:
            break

        for item in items:
            report_nm = item.get("report_nm", "")
            w = keyword_weight(report_nm)
            if w > 0 and item.get("stock_code"):
                rows.append({
                    "stock_code": item.get("stock_code"),
                    "corp_name": item.get("corp_name"),
                    "report_nm": report_nm,
                    "rcept_dt": item.get("rcept_dt"),
                    "event_raw": w,
                })

        total_page = data.get("total_page", 1)
        if page >= total_page:
            break
        page += 1
        time.sleep(0.2)

    df = pd.DataFrame(rows)
    os.makedirs(config.DATA_DIR, exist_ok=True)
    df.to_csv(os.path.join(config.DATA_DIR, "buyback_events.csv"), index=False, encoding="utf-8-sig")
    print(f"[재료이벤트] 완료. 자사주 관련 공시 {len(df)}건 발견")
    return df


if __name__ == "__main__":
    fetch_buyback_disclosures()
