"""
네이버 증권의 종목별 투자자 동향을 수집합니다.

네이버 화면은 외국인/기관 순매수 '수량'을 제공합니다. 기존 점수 계산과의
호환을 위해 해당 날짜 종가를 곱한 추정 순매수대금(원)을 생성합니다.
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


WORKERS = _env_int("NAVER_MAX_WORKERS", 8, 1, 12)


def _get_json(url: str, *, params=None, referer: str, attempts: int = 4):
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
    raise RuntimeError(f"네이버 투자자 동향을 읽지 못했습니다: {last_error}")


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


def _trend_rows(payload):
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("dealTrendInfos", "trendInfos", "result", "data"):
            value = payload.get(key)
            if isinstance(value, list):
                return value
    return []


def _load_close_map(ticker: str):
    path = os.path.join(config.DATA_DIR, "prices", f"{ticker}.csv")
    if not os.path.exists(path):
        return {}
    df = pd.read_csv(path)
    if "날짜" not in df.columns or "종가" not in df.columns:
        return {}
    result = {}
    for _, row in df.iterrows():
        date = str(row["날짜"])[:10]
        result[date] = _number(row["종가"])
        result[date.replace("-", "")] = _number(row["종가"])
    return result


def _fetch_one(ticker: str):
    close_map = _load_close_map(ticker)
    if not close_map:
        raise RuntimeError("가격 파일 없음")
    payload = _get_json(
        f"{BASE_URL}/front-api/stock/domestic/trend",
        params={"code": ticker},
        referer=f"{BASE_URL}/domestic/stock/{ticker}/total",
    )
    rows = _trend_rows(payload)
    if not rows:
        raise RuntimeError("투자자 동향이 비어 있음")

    output = []
    latest_close = list(close_map.values())[-1]
    for item in rows[: int(config.INVESTOR_LOOKBACK_DAYS)]:
        if not isinstance(item, dict):
            continue
        date = str(_first(item, ["localTradedAt", "localDate", "bizdate", "date"]) or "")[:10]
        if not date:
            continue
        if len(date) == 8 and date.isdigit():
            normalized_date = f"{date[:4]}-{date[4:6]}-{date[6:8]}"
        else:
            normalized_date = date
        close = _number(_first(item, ["closePrice", "close", "종가"]))
        if close <= 0:
            close = close_map.get(
                normalized_date,
                close_map.get(normalized_date.replace("-", ""), latest_close),
            )
        foreign_qty = _number(
            _first(item, ["foreignerPureBuyQuant", "foreignerNetPurchaseQuantity", "외국인"])
        )
        organ_qty = _number(
            _first(item, ["organPureBuyQuant", "institutionPureBuyQuant", "institutionNetPurchaseQuantity", "기관"])
        )
        output.extend(
            [
                {
                    "ticker": ticker,
                    "순매수거래대금": foreign_qty * close,
                    "date": normalized_date,
                    "investor": "외국인(수량×종가 추정)",
                },
                {
                    "ticker": ticker,
                    "순매수거래대금": organ_qty * close,
                    "date": normalized_date,
                    "investor": "기관(수량×종가 추정)",
                },
            ]
        )
    if not output:
        raise RuntimeError("사용 가능한 투자자 행이 없음")
    return output


def fetch_investor_flows():
    universe_path = os.path.join(config.DATA_DIR, "universe.csv")
    if not os.path.exists(universe_path):
        raise RuntimeError("data/universe.csv가 없습니다. 가격 수집을 먼저 실행하세요.")
    universe = pd.read_csv(universe_path, dtype={"ticker": str})
    tickers = universe["ticker"].astype(str).str.zfill(6).tolist()

    all_rows = []
    failed = []
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        jobs = {pool.submit(_fetch_one, ticker): ticker for ticker in tickers}
        for index, future in enumerate(as_completed(jobs), 1):
            ticker = jobs[future]
            try:
                all_rows.extend(future.result())
            except Exception as exc:
                failed.append((ticker, str(exc)))
            if index % 50 == 0 or index == len(tickers):
                print(f"[수급데이터] {index}/{len(tickers)} 처리")

    successful_tickers = len(tickers) - len(failed)
    success_rate = successful_tickers / max(len(tickers), 1)
    if not all_rows or success_rate < 0.70:
        sample = "; ".join(f"{ticker}: {message}" for ticker, message in failed[:5])
        raise RuntimeError(
            f"[수급데이터] 성공률이 낮습니다: {successful_tickers}/{len(tickers)}. 예시: {sample}"
        )

    df = pd.DataFrame(all_rows)
    os.makedirs(config.DATA_DIR, exist_ok=True)
    df.to_csv(
        os.path.join(config.DATA_DIR, "investor_flows.csv"),
        index=False,
        encoding="utf-8-sig",
    )
    print(f"[수급데이터] 완료: {successful_tickers}종목, {len(df)}행")
    return df


if __name__ == "__main__":
    fetch_investor_flows()
