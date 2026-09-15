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
    """최근 20일 중 KOSPI와 KOSDAQ 목록이 모두 확인되는 날짜를 사용합니다.

    pykrx는 date를 생략하면 KRX 영업일 조회를 먼저 수행합니다. 이 조회가
    빈 결과를 반환할 경우 IndexError가 발생하므로 날짜를 명시적으로 전달합니다.
    일부 시장만 수집된 상태로 점수화하지 않도록 두 시장이 모두 확인되어야 합니다.
    """
    today = datetime.today()
    recent_errors = []

    for days_ago in range(20):
        date_str = (today - timedelta(days=days_ago)).strftime("%Y%m%d")
        market_tickers = {}

        for market in config.MARKETS:
            try:
                values = stock.get_market_ticker_list(
                    date=date_str,
                    market=market,
                )
                market_tickers[market] = list(values or [])
            except Exception as exc:
                market_tickers[market] = []
                recent_errors.append(
                    f"{date_str} {market}: {type(exc).__name__}: {exc}"
                )

        if market_tickers and all(market_tickers.get(m) for m in config.MARKETS):
            tickers = []
            for market in config.MARKETS:
                tickers.extend(market_tickers[market])
            tickers = sorted(set(tickers))
            print(f"[가격데이터] 종목 목록 기준일: {date_str}")
            return tickers

    details = " | ".join(recent_errors[-4:]) if recent_errors else "빈 목록 반환"
    raise RuntimeError(
        "[가격데이터] 최근 20일 내 KOSPI·KOSDAQ 종목 목록을 모두 확인하지 "
        f"못했습니다. 부분 데이터로 점수화하지 않습니다. 상세: {details}"
    )


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
                failed.append(ticker)
                continue
            df.to_csv(os.path.join(out_dir, f"{ticker}.csv"), encoding="utf-8-sig")
        except Exception:
            failed.append(ticker)
        if i % 200 == 0:
            print(f"  진행: {i}/{len(tickers)}")
        time.sleep(0.05)  # KRX 서버 부하 방지용 딜레이

    success_count = len(tickers) - len(failed)
    print(
        f"[가격데이터] 완료. 성공 {success_count}건 / 실패 {len(failed)}건 / "
        f"전체 {len(tickers)}건"
    )
    if success_count == 0:
        raise RuntimeError(
            "[가격데이터] 전 종목 가격 수집이 실패했습니다. 빈 데이터로 점수화하지 않습니다."
        )
    return tickers


if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    fetch_all_prices()
