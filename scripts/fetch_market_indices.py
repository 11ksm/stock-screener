"""홈페이지 상단에 표시할 국내·미국 주요 지수 스냅샷을 수집합니다.

지수 수집은 종목 스크리닝과 분리되어 있습니다. 일부 지수 요청이 실패해도
data/market_indices.json에 해당 항목만 unavailable로 기록하고 파이프라인은 계속됩니다.
"""
from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import requests

import config


BASE_URL = "https://stock.naver.com"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.7",
    "Referer": "https://stock.naver.com/market/stock/kr",
}

DOMESTIC = {
    "KOSPI": ("KOSPI", "코스피"),
    "KOSDAQ": ("KOSDAQ", "코스닥"),
    "KPI200": ("KOSPI 200", "코스피 200"),
}
WORLD = {
    ".DJI": ("DOW", "다우존스"),
    ".INX": ("S&P 500", "S&P 500"),
    ".IXIC": ("NASDAQ", "나스닥 종합"),
    ".SOX": ("SOX", "필라델피아 반도체"),
}

FEAR_GREED_URL = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"
FEAR_GREED_HEADERS = {
    **HEADERS,
    "Accept-Language": "en-US,en;q=0.9",
    "Origin": "https://edition.cnn.com",
    "Referer": "https://edition.cnn.com/",
}
FEAR_GREED_RATINGS = {
    "extreme fear": ("Extreme Fear", "극도의 공포"),
    "fear": ("Fear", "공포"),
    "neutral": ("Neutral", "중립"),
    "greed": ("Greed", "탐욕"),
    "extreme greed": ("Extreme Greed", "극도의 탐욕"),
}


def _get_json(path: str, attempts: int = 3):
    last_error = None
    for attempt in range(attempts):
        try:
            response = requests.get(f"{BASE_URL}{path}", headers=HEADERS, timeout=(10, 25))
            response.raise_for_status()
            return response.json()
        except Exception as exc:
            last_error = exc
            if attempt + 1 < attempts:
                time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(str(last_error))


def _number(value):
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", "").replace("−", "-")
    text = re.sub(r"[^0-9.+-]", "", text)
    if text in ("", "+", "-", "."):
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _item(code: str, short_name: str, full_name: str, row: dict, group: str):
    return {
        "code": code,
        "short_name": short_name,
        "name": full_name,
        "group": group,
        "status": "ok",
        "value": _number(row.get("closePriceRaw", row.get("closePrice"))),
        "change": _number(
            row.get("compareToPreviousClosePriceRaw", row.get("compareToPreviousClosePrice"))
        ),
        "change_rate": _number(row.get("fluctuationsRatioRaw", row.get("fluctuationsRatio"))),
        "as_of": str(row.get("localTradedAt", "")),
        "market_status": str(row.get("marketStatus", "")),
        "delay": str(row.get("delayTimeName", "")),
        "source": "Npay 증권 공개 시세",
    }


def _unavailable(
    code: str,
    short_name: str,
    full_name: str,
    group: str,
    message: str,
    source: str = "Npay 증권 공개 시세",
):
    return {
        "code": code,
        "short_name": short_name,
        "name": full_name,
        "group": group,
        "status": "unavailable",
        "value": None,
        "change": None,
        "change_rate": None,
        "as_of": "",
        "market_status": "",
        "delay": "",
        "source": source,
        "message": message[:180],
    }


def _fetch_group(path: str, definitions: dict, group: str, code_key: str):
    try:
        payload = _get_json(path)
        rows = payload.get("datas", []) if isinstance(payload, dict) else []
        by_code = {str(row.get(code_key, "")): row for row in rows if isinstance(row, dict)}
        result = []
        for code, (short_name, full_name) in definitions.items():
            row = by_code.get(code)
            if row:
                result.append(_item(code, short_name, full_name, row, group))
            else:
                result.append(_unavailable(code, short_name, full_name, group, "응답에 항목이 없습니다."))
        return result
    except Exception as exc:
        return [
            _unavailable(code, short_name, full_name, group, str(exc))
            for code, (short_name, full_name) in definitions.items()
        ]


def _fetch_fear_greed():
    """CNN Fear & Greed Index의 최신 점수와 전일 대비 변화를 가져옵니다."""
    source = "CNN Business"
    last_error = None
    for attempt in range(3):
        try:
            response = requests.get(
                FEAR_GREED_URL,
                headers=FEAR_GREED_HEADERS,
                timeout=(10, 25),
            )
            response.raise_for_status()
            payload = response.json()
            row = payload.get("fear_and_greed", {}) if isinstance(payload, dict) else {}
            score = _number(row.get("score"))
            previous = _number(row.get("previous_close"))
            if score is None or not 0 <= score <= 100:
                raise ValueError("Fear & Greed 점수가 없거나 0~100 범위를 벗어났습니다.")

            rating_key = str(row.get("rating", "")).strip().lower().replace("_", " ")
            rating_en, rating_ko = FEAR_GREED_RATINGS.get(
                rating_key,
                (str(row.get("rating") or "Unclassified").title(), "구간 미분류"),
            )
            return {
                "code": "CNN_FEAR_GREED",
                "short_name": "Fear & Greed",
                "name": "CNN Fear & Greed Index",
                "group": "sentiment",
                "display_mode": "sentiment",
                "status": "ok",
                "value": round(score, 1),
                "change": round(score - previous, 1) if previous is not None else None,
                "change_rate": None,
                "rating": rating_en,
                "rating_ko": rating_ko,
                "as_of": str(row.get("timestamp", "")),
                "market_status": "CLOSE",
                "delay": "미국시장 심리",
                "source": source,
            }
        except Exception as exc:
            last_error = exc
            if attempt + 1 < 3:
                time.sleep(1.5 * (attempt + 1))
    return _unavailable(
        "CNN_FEAR_GREED",
        "Fear & Greed",
        "CNN Fear & Greed Index",
        "sentiment",
        str(last_error),
        source,
    )


def fetch_market_indices():
    domestic_codes = ",".join(DOMESTIC)
    world_codes = ",".join(WORLD)
    domestic = _fetch_group(
        f"/api/polling/domestic/index?itemCodes={domestic_codes}",
        DOMESTIC,
        "domestic",
        "itemCode",
    )
    world = _fetch_group(
        f"/api/polling/worldstock/index?reutersCodes={world_codes}",
        WORLD,
        "world",
        "reutersCode",
    )
    payload = {
        "generated_at": datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="seconds"),
        "items": domestic + [_fetch_fear_greed()] + world,
    }
    os.makedirs(config.DATA_DIR, exist_ok=True)
    output_path = os.path.join(config.DATA_DIR, "market_indices.json")
    with open(output_path, "w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)
    ok_count = sum(item["status"] == "ok" for item in payload["items"])
    print(f"[시장지수] {ok_count}/{len(payload['items'])}개 수집 완료")
    return payload


if __name__ == "__main__":
    fetch_market_indices()
