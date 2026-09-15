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
    # 같은 KOSPI200 선물 코드의 가장 최근 체결값입니다. 오전 06:30 KST 실행 시
    # 전날 야간 세션 종료 후의 최신값을 우선 보여 주며, 실제 체결시각도 함께 표시합니다.
    "FUT": ("KOSPI200 야간선물", "코스피 200 선물"),
}
WORLD = {
    ".DJI": ("DOW", "다우존스"),
    ".INX": ("S&P 500", "S&P 500"),
    ".IXIC": ("NASDAQ", "나스닥 종합"),
    ".SOX": ("SOX", "필라델피아 반도체"),
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


def _unavailable(code: str, short_name: str, full_name: str, group: str, message: str):
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
        "source": "Npay 증권 공개 시세",
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
        "items": domestic + world,
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
