"""상위 스크리닝 종목의 선정일 종가 대비 1·5거래일 성과를 누적합니다."""
from __future__ import annotations

import os
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd

import config


HISTORY_PATH = os.path.join(config.DATA_DIR, "screening_history.csv")
COLUMNS = [
    "screen_date",
    "ticker",
    "name",
    "rank",
    "total_score",
    "entry_date",
    "entry_close",
    "d1_date",
    "d1_close",
    "d1_return",
    "d5_date",
    "d5_close",
    "d5_return",
]


def _load_history() -> pd.DataFrame:
    if not os.path.exists(HISTORY_PATH):
        return pd.DataFrame(columns=COLUMNS)
    history = pd.read_csv(HISTORY_PATH, dtype={"ticker": str, "screen_date": str})
    for column in COLUMNS:
        if column not in history.columns:
            history[column] = pd.NA
    history["ticker"] = history["ticker"].astype(str).str.zfill(6)
    return history[COLUMNS]


def _load_names() -> dict:
    path = os.path.join(config.DATA_DIR, "universe.csv")
    if not os.path.exists(path):
        return {}
    universe = pd.read_csv(path, dtype={"ticker": str})
    if not {"ticker", "name"}.issubset(universe.columns):
        return {}
    universe["ticker"] = universe["ticker"].astype(str).str.zfill(6)
    return dict(zip(universe["ticker"], universe["name"]))


def _load_prices(ticker: str) -> pd.DataFrame:
    path = os.path.join(config.DATA_DIR, "prices", f"{ticker}.csv")
    if not os.path.exists(path):
        return pd.DataFrame(columns=["날짜", "종가"])
    prices = pd.read_csv(path, dtype={"날짜": str})
    if not {"날짜", "종가"}.issubset(prices.columns):
        return pd.DataFrame(columns=["날짜", "종가"])
    prices["날짜"] = prices["날짜"].astype(str).str[:10]
    prices["종가"] = pd.to_numeric(prices["종가"], errors="coerce")
    return (
        prices.dropna(subset=["날짜", "종가"])
        .drop_duplicates("날짜")
        .sort_values("날짜")
        .reset_index(drop=True)
    )


def _return_pct(exit_close, entry_close):
    if pd.isna(exit_close) or pd.isna(entry_close) or float(entry_close) <= 0:
        return pd.NA
    return round((float(exit_close) / float(entry_close) - 1) * 100, 4)


def _update_existing(history: pd.DataFrame) -> pd.DataFrame:
    if history.empty:
        return history
    price_cache = {}
    for index, row in history.iterrows():
        ticker = str(row["ticker"]).zfill(6)
        prices = price_cache.setdefault(ticker, _load_prices(ticker))
        if prices.empty:
            continue
        sessions = prices[prices["날짜"] >= str(row["screen_date"])].reset_index(drop=True)
        if sessions.empty:
            continue

        entry_date = str(sessions.iloc[0]["날짜"])
        entry_close = float(sessions.iloc[0]["종가"])
        history.at[index, "entry_date"] = entry_date
        history.at[index, "entry_close"] = entry_close

        if len(sessions) >= 2:
            d1_close = float(sessions.iloc[1]["종가"])
            history.at[index, "d1_date"] = str(sessions.iloc[1]["날짜"])
            history.at[index, "d1_close"] = d1_close
            history.at[index, "d1_return"] = _return_pct(d1_close, entry_close)

        if len(sessions) >= 6:
            d5_close = float(sessions.iloc[5]["종가"])
            history.at[index, "d5_date"] = str(sessions.iloc[5]["날짜"])
            history.at[index, "d5_close"] = d5_close
            history.at[index, "d5_return"] = _return_pct(d5_close, entry_close)
    return history


def update_tracking():
    today = datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y-%m-%d")
    history = _update_existing(_load_history())

    scores = pd.read_csv(os.path.join(config.DATA_DIR, "scores.csv"), dtype={"ticker": str})
    scores["ticker"] = scores["ticker"].astype(str).str.zfill(6)
    scores["total_score"] = pd.to_numeric(scores["total_score"], errors="coerce")
    scores = scores.dropna(subset=["total_score"]).sort_values(
        "total_score", ascending=False, kind="stable"
    )
    names = _load_names()

    existing_keys = set(zip(history["screen_date"].astype(str), history["ticker"].astype(str)))
    new_rows = []
    for rank, (_, row) in enumerate(scores.head(int(config.TOP_N)).iterrows(), 1):
        ticker = str(row["ticker"]).zfill(6)
        if (today, ticker) in existing_keys:
            continue
        new_rows.append(
            {
                "screen_date": today,
                "ticker": ticker,
                "name": names.get(ticker, ticker),
                "rank": rank,
                "total_score": round(float(row["total_score"]), 4),
            }
        )

    if new_rows:
        history = pd.concat([history, pd.DataFrame(new_rows)], ignore_index=True)
    history = history[COLUMNS].sort_values(["screen_date", "rank"], kind="stable")
    os.makedirs(config.DATA_DIR, exist_ok=True)
    history.to_csv(HISTORY_PATH, index=False, encoding="utf-8-sig")
    completed_d1 = pd.to_numeric(history["d1_return"], errors="coerce").notna().sum()
    completed_d5 = pd.to_numeric(history["d5_return"], errors="coerce").notna().sum()
    print(
        f"[성과추적] 누적 {len(history)}건 · 1거래일 완료 {completed_d1}건 · "
        f"5거래일 완료 {completed_d5}건"
    )
    return history


if __name__ == "__main__":
    update_tracking()
