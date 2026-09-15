"""
네이버 증권 공개 화면용 JSON에서 종목 목록과 일봉을 수집합니다.

주의: 공식 공개 API가 아니므로 응답 형식 변경 또는 차단 가능성이 있습니다.
기본 수집 범위는 KOSPI/KOSDAQ 시가총액 상위 300종목씩입니다.
환경변수 NAVER_UNIVERSE_LIMIT_PER_MARKET로 시장별 종목 수를 조정할 수 있습니다.
"""
from __future__ import annotations

import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
import requests

import config


BASE_URL = "https://m.stock.naver.com"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.7",
}


def _env_int(name: str, default: int, low: int, high: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        value = default
    return max(low, min(value, high))


UNIVERSE_LIMIT = _env_int("NAVER_UNIVERSE_LIMIT_PER_MARKET", 300, 50, 1000)
WORKERS = _env_int("NAVER_MAX_WORKERS", 8, 1, 12)


def _get_json(url: str, *, params=None, referer: str = BASE_URL, attempts: int = 4):
    last_error = None
    headers = {**HEADERS, "Referer": referer}
    for attempt in range(attempts):
        try:
            response = requests.get(url, params=params, headers=headers, timeout=(10, 30))
            response.raise_for_status()
            return response.json()
        except Exception as exc:
            last_error = exc
            if attempt + 1 < attempts:
                time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"네이버 응답을 JSON으로 읽지 못했습니다: {last_error}")


def _first(row: dict, keys):
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return value
    return None


def _number(value):
    if value is None or value == "":
        return 0
    if isinstance(value, (int, float)):
        return value
    text = str(value).strip().replace(",", "").replace("−", "-")
    text = re.sub(r"[^0-9.+-]", "", text)
    if text in ("", "+", "-", "."):
        return 0
    try:
        return float(text)
    except ValueError:
        return 0


def get_universe() -> pd.DataFrame:
    rows = []
    for market in config.MARKETS:
        market_rows = []
        page = 1
        while len(market_rows) < UNIVERSE_LIMIT:
            page_size = min(100, UNIVERSE_LIMIT - len(market_rows))
            payload = _get_json(
                f"{BASE_URL}/api/stocks/marketValue/{market}",
                params={"page": page, "pageSize": page_size},
                referer=f"{BASE_URL}/domestic/marketValue/{market}",
            )
            stocks = payload.get("stocks", []) if isinstance(payload, dict) else payload
            if not isinstance(stocks, list):
                raise RuntimeError(f"{market} 종목 목록 형식이 예상과 다릅니다.")
            if not stocks:
                break

            for item in stocks:
                if not isinstance(item, dict):
                    continue
                ticker = str(
                    _first(item, ["itemCode", "code", "stockCode", "symbolCode"]) or ""
                )
                ticker = ticker.strip().lstrip("A")
                if not re.fullmatch(r"\d{6}", ticker):
                    continue
                name = str(_first(item, ["stockName", "name", "itemName"]) or ticker).strip()
                market_rows.append({"ticker": ticker, "name": name, "market": market})
            page += 1

        if len(market_rows) < 10:
            raise RuntimeError(f"{market} 종목 목록이 너무 적습니다({len(market_rows)}개).")
        rows.extend(market_rows)
        print(f"[가격데이터] {market} 종목 목록 {len(market_rows)}개 확인")

    universe = pd.DataFrame(rows).drop_duplicates("ticker").reset_index(drop=True)
    os.makedirs(config.DATA_DIR, exist_ok=True)
    universe.to_csv(
        os.path.join(config.DATA_DIR, "universe.csv"), index=False, encoding="utf-8-sig"
    )
    return universe


def _price_rows(payload):
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("priceInfos", "prices", "result", "data"):
            value = payload.get(key)
            if isinstance(value, list):
                return value
    return []


def _fetch_one(ticker: str):
    payload = _get_json(
        f"{BASE_URL}/api/stock/{ticker}/price",
        params={"pageSize": max(90, int(config.PRICE_LOOKBACK_DAYS)), "page": 1},
        referer=f"{BASE_URL}/domestic/stock/{ticker}/total",
    )
    records = []
    for item in _price_rows(payload):
        if not isinstance(item, dict):
            continue
        date = _first(item, ["localTradedAt", "localDate", "date"])
        close = _number(_first(item, ["closePrice", "close", "종가"]))
        if not date or close <= 0:
            continue
        records.append(
            {
                "날짜": str(date)[:10],
                "시가": _number(_first(item, ["openPrice", "open", "시가"])),
                "고가": _number(_first(item, ["highPrice", "high", "고가"])),
                "저가": _number(_first(item, ["lowPrice", "low", "저가"])),
                "종가": close,
                "거래량": _number(
                    _first(item, ["accumulatedTradingVolume", "tradingVolume", "volume", "거래량"])
                ),
            }
        )
    if len(records) < 30:
        raise RuntimeError(f"일봉이 {len(records)}개뿐입니다")
    df = pd.DataFrame(records).drop_duplicates("날짜").sort_values("날짜")
    df.to_csv(
        os.path.join(config.DATA_DIR, "prices", f"{ticker}.csv"),
        index=False,
        encoding="utf-8-sig",
    )
    return ticker


def fetch_all_prices():
    universe = get_universe()
    price_dir = os.path.join(config.DATA_DIR, "prices")
    os.makedirs(price_dir, exist_ok=True)

    succeeded = []
    failed = []
    tickers = universe["ticker"].astype(str).str.zfill(6).tolist()
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        jobs = {pool.submit(_fetch_one, ticker): ticker for ticker in tickers}
        for index, future in enumerate(as_completed(jobs), 1):
            ticker = jobs[future]
            try:
                succeeded.append(future.result())
            except Exception as exc:
                failed.append((ticker, str(exc)))
            if index % 50 == 0 or index == len(tickers):
                print(f"[가격데이터] {index}/{len(tickers)} 처리, 성공 {len(succeeded)}")

    success_rate = len(succeeded) / max(len(tickers), 1)
    if len(succeeded) < 50 or success_rate < 0.85:
        sample = "; ".join(f"{ticker}: {message}" for ticker, message in failed[:5])
        raise RuntimeError(
            f"[가격데이터] 성공률이 낮습니다: {len(succeeded)}/{len(tickers)}. 예시: {sample}"
        )
    print(f"[가격데이터] 완료: 성공 {len(succeeded)}, 실패 {len(failed)}")
    return succeeded


if __name__ == "__main__":
    fetch_all_prices()
