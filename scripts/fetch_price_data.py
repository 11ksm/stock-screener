"""
가격/거래량 데이터 수집 (KRX, pykrx 라이브러리 사용)
코스피 + 코스닥 전체 종목의 OHLCV를 수집합니다 (기술적지표 계산용).
"""
import os
import sys
import time
from datetime import datetime, timedelta

import config
from pykrx import stock


def get_universe():
    tickers = []
    for market in config.MARKETS:
        tickers += stock.get_market_ticker_list(market=market)
    return sorted(set(tickers))


def fetch_all_prices():
    end = datetime.today()
    start = end - timedelta(days=config.PRICE_LOOKBACK_DAYS)
    start_str, end_str = start.strftime("%Y%m%d"), end.strftime("%Y%m%d")

    tickers = get_universe()
    print(f"[가격데이터] 대상 종목 수: {len(tickers)}")

    out_dir = os.path.join(config.DATA_DIR, "prices")
    os.makedirs(out_dir, exist_ok=True)

    failed = []
    for i, ticker in enumerate(tickers):
        try:
            df = stock.get_market_ohlcv(start_str, end_str, ticker)
            if df is None or df.empty:
                continue
            df.to_csv(os.path.join(out_dir, f"{ticker}.csv"), encoding="utf-8-sig")
        except Exception:
            failed.append(ticker)
        if i % 200 == 0:
            print(f"  진행: {i}/{len(tickers)}")
        time.sleep(0.05)  # KRX 서버 부하 방지용 딜레이

    print(f"[가격데이터] 완료. 실패 {len(failed)}건 / 전체 {len(tickers)}건")
    return tickers


if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    fetch_all_prices()
