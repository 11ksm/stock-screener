"""
기관/외국인 수급 데이터 수집
pykrx의 '투자자별 순매수' 집계 함수를 날짜별로 호출하여
최근 N거래일간 전체 종목의 기관/외국인 순매수 데이터를 모읍니다.

주의: pykrx 버전에 따라 반환 컬럼명이 다를 수 있습니다.
로컬에서 `python -c "from pykrx import stock; print(stock.get_market_net_purchases_of_equities_by_ticker('20240102','20240102','KOSPI','기관합계'))"`
로 컬럼명을 먼저 확인한 뒤 필요시 COLUMN 매핑을 조정하세요.
"""
import os
from datetime import datetime, timedelta

import pandas as pd
import config
from pykrx import stock


def get_date_candidates(end_date, n):
    days = []
    d = end_date
    while len(days) < n:
        days.append(d.strftime("%Y%m%d"))
        d -= timedelta(days=1)
    return days


def fetch_investor_flows():
    end = datetime.today()
    # 주말/공휴일에는 데이터가 없으므로 넉넉히 후보일을 뽑아 실제 수집된 날짜 수 기준으로 종료
    date_candidates = get_date_candidates(end, config.INVESTOR_LOOKBACK_DAYS + 15)

    frames = []
    used_days = 0
    for date in date_candidates:
        if used_days >= config.INVESTOR_LOOKBACK_DAYS:
            break
        day_frames = []
        for market in config.MARKETS:
            for investor in ["기관합계", "외국인"]:
                try:
                    d = stock.get_market_net_purchases_of_equities_by_ticker(
                        date, date, market, investor
                    )
                except Exception:
                    continue
                if d is None or d.empty:
                    continue
                d = d.reset_index()
                # 컬럼명 표준화 (버전에 따라 '티커' 또는 '종목코드'일 수 있음)
                ticker_col = next((c for c in d.columns if c in ("티커", "종목코드")), d.columns[0])
                amount_col = next((c for c in d.columns if "순매수거래대금" in c), None)
                if amount_col is None:
                    continue
                d = d.rename(columns={ticker_col: "ticker", amount_col: "순매수거래대금"})
                d["date"] = date
                d["investor"] = investor
                day_frames.append(d[["ticker", "순매수거래대금", "date", "investor"]])
        if day_frames:
            frames.append(pd.concat(day_frames, ignore_index=True))
            used_days += 1

    if not frames:
        print("[수급데이터] 수집 실패 - 데이터가 비어있습니다.")
        return pd.DataFrame()

    result = pd.concat(frames, ignore_index=True)
    os.makedirs(config.DATA_DIR, exist_ok=True)
    result.to_csv(os.path.join(config.DATA_DIR, "investor_flows.csv"), index=False, encoding="utf-8-sig")
    print(f"[수급데이터] 완료. {used_days}거래일 수집, 총 {len(result)}행")
    return result


if __name__ == "__main__":
    fetch_investor_flows()
