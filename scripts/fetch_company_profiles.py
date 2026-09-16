"""현재 상위 종목의 업종과 주요 사업 요약을 공개 기업정보에서 수집합니다."""
from __future__ import annotations

import html
import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
import requests

import config


PROFILE_PATH = os.path.join(config.DATA_DIR, "company_profiles.json")
PROFILE_URL = "https://navercomp.wisereport.co.kr/v2/company/c1010001.aspx"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
    ),
    "Referer": "https://finance.naver.com/",
}


def _clean_html(value: str) -> str:
    value = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", html.unescape(value)).strip()


def _clip(value: str, limit: int = 180) -> str:
    if len(value) <= limit:
        return value
    clipped = value[:limit].rsplit(" ", 1)[0].rstrip("., ")
    return f"{clipped}…"


def _fetch_profile(ticker: str) -> dict:
    response = requests.get(
        PROFILE_URL,
        params={"cmp_cd": ticker},
        headers=HEADERS,
        timeout=(10, 25),
    )
    response.raise_for_status()
    text = response.text
    industry_match = re.search(r"WICS\s*:\s*([^<]+)", text, flags=re.I)
    industry = _clean_html(industry_match.group(1)) if industry_match else ""
    bullets = [
        _clean_html(value)
        for value in re.findall(
            r'<li[^>]*class=["\'][^"\']*dot_cmp[^"\']*["\'][^>]*>(.*?)</li>',
            text,
            flags=re.I | re.S,
        )
    ]
    bullets = [value for value in bullets if value]
    summary = _clip(" ".join(bullets[:2])) if bullets else ""
    if not summary and not industry:
        raise ValueError("기업개요와 업종 정보가 없습니다.")
    return {
        "industry": industry,
        "summary": summary or f"{industry} 업종",
        "source": "네이버 기업정보(FnGuide)",
        "updated_at": datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="seconds"),
    }


def _fetch_profile_with_retry(ticker: str):
    last_error = None
    for attempt in range(2):
        try:
            return ticker, _fetch_profile(ticker), None
        except Exception as exc:
            last_error = exc
            if attempt == 0:
                time.sleep(1)
    return ticker, None, str(last_error)


def _load_profiles() -> dict:
    if not os.path.exists(PROFILE_PATH):
        return {}
    try:
        with open(PROFILE_PATH, encoding="utf-8") as file:
            payload = json.load(file)
        return payload if isinstance(payload, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _is_fresh(item: dict) -> bool:
    try:
        updated = datetime.fromisoformat(str(item.get("updated_at", "")))
        if updated.tzinfo is None:
            updated = updated.replace(tzinfo=ZoneInfo("Asia/Seoul"))
        return updated >= datetime.now(ZoneInfo("Asia/Seoul")) - timedelta(days=90)
    except (TypeError, ValueError):
        return False


def fetch_company_profiles():
    scores = pd.read_csv(os.path.join(config.DATA_DIR, "scores.csv"), dtype={"ticker": str})
    scores["ticker"] = scores["ticker"].astype(str).str.zfill(6)
    scores["total_score"] = pd.to_numeric(scores["total_score"], errors="coerce")
    targets = (
        scores.dropna(subset=["total_score"])
        .sort_values("total_score", ascending=False, kind="stable")
        ["ticker"]
        .tolist()
    )
    profiles = _load_profiles()
    pending = [ticker for ticker in targets if ticker not in profiles or not _is_fresh(profiles[ticker])]
    if pending:
        with ThreadPoolExecutor(max_workers=8) as pool:
            jobs = [pool.submit(_fetch_profile_with_retry, ticker) for ticker in pending]
            for index, future in enumerate(as_completed(jobs), 1):
                ticker, profile, error = future.result()
                if profile:
                    profiles[ticker] = profile
                elif error:
                    print(f"[기업개요] {ticker} 수집 실패: {error}")
                if index % 50 == 0 or index == len(jobs):
                    print(f"[기업개요] 신규/갱신 {index}/{len(jobs)} 처리")

    os.makedirs(config.DATA_DIR, exist_ok=True)
    with open(PROFILE_PATH, "w", encoding="utf-8") as file:
        json.dump(profiles, file, ensure_ascii=False, indent=2)
    success = sum(ticker in profiles for ticker in targets)
    print(f"[기업개요] 분석종목 {success}/{len(targets)}개 사용 가능")
    return profiles


if __name__ == "__main__":
    fetch_company_profiles()
