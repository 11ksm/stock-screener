"""
스코어링 로직
- 기관/외국인 수급 점수 (20일 누적 순매수거래대금 → 0~100 정규화)
- 기술적지표 점수 (이동평균 정배열, RSI, MACD, 거래량 급증 → 0~100 정규화)
- 재료성 이벤트 점수 (자사주 취득/소각 공시 → 0~100)
세 점수를 config.py의 가중치(기본 균등 1/3)로 합산합니다.
"""
import os
import pandas as pd
import numpy as np
import config


def _rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def _macd(series: pd.Series, fast=12, slow=26, signal=9):
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    return macd_line, signal_line


def score_technical() -> pd.DataFrame:
    price_dir = os.path.join(config.DATA_DIR, "prices")
    scores = {}
    if not os.path.isdir(price_dir):
        return pd.DataFrame(columns=["ticker", "tech_raw"])

    for fname in os.listdir(price_dir):
        if not fname.endswith(".csv"):
            continue
        ticker = fname.replace(".csv", "")
        try:
            df = pd.read_csv(os.path.join(price_dir, fname))
            close_col = "종가" if "종가" in df.columns else df.columns[-1]
            vol_col = "거래량" if "거래량" in df.columns else None
            close = df[close_col]
            if len(close) < 30:
                continue

            ma5 = close.rolling(5).mean()
            ma20 = close.rolling(20).mean()
            ma60 = close.rolling(60).mean() if len(close) >= 60 else pd.Series([np.nan] * len(close))
            r = _rsi(close).iloc[-1]
            macd_line, signal_line = _macd(close)

            point = 0
            # 이동평균 정배열
            if not np.isnan(ma60.iloc[-1]) and ma5.iloc[-1] > ma20.iloc[-1] > ma60.iloc[-1]:
                point += 40
            elif ma5.iloc[-1] > ma20.iloc[-1]:
                point += 20
            # RSI 모멘텀 구간
            if not np.isnan(r):
                if 50 <= r <= 70:
                    point += 30
                elif 40 <= r < 50:
                    point += 15
            # MACD 골든크로스 / 상승 추세
            if len(macd_line) >= 2:
                if macd_line.iloc[-1] > signal_line.iloc[-1] and macd_line.iloc[-2] <= signal_line.iloc[-2]:
                    point += 20
                elif macd_line.iloc[-1] > signal_line.iloc[-1]:
                    point += 10
            # 거래량 급증
            if vol_col and len(df[vol_col]) >= 20:
                vol = df[vol_col]
                vol_ma20 = vol.rolling(20).mean().iloc[-1]
                if vol_ma20 and vol.iloc[-1] > vol_ma20 * 1.5:
                    point += 10

            scores[ticker] = point
        except Exception:
            continue

    return pd.DataFrame(list(scores.items()), columns=["ticker", "tech_raw"])


def score_supply_demand() -> pd.DataFrame:
    path = os.path.join(config.DATA_DIR, "investor_flows.csv")
    if not os.path.exists(path):
        return pd.DataFrame(columns=["ticker", "supply_raw"])
    df = pd.read_csv(path)
    if df.empty or "ticker" not in df.columns:
        return pd.DataFrame(columns=["ticker", "supply_raw"])
    agg = df.groupby("ticker")["순매수거래대금"].sum().reset_index()
    agg.columns = ["ticker", "supply_raw"]
    return agg


def score_event() -> pd.DataFrame:
    path = os.path.join(config.DATA_DIR, "buyback_events.csv")
    if not os.path.exists(path):
        return pd.DataFrame(columns=["ticker", "event_raw"])
    df = pd.read_csv(path)
    if df.empty:
        return pd.DataFrame(columns=["ticker", "event_raw"])
    df["stock_code"] = df["stock_code"].astype(str).str.zfill(6)
    agg = df.groupby("stock_code")["event_raw"].max().reset_index()
    agg.columns = ["ticker", "event_raw"]
    return agg


def _normalize_0_100(series: pd.Series) -> pd.Series:
    if series.empty or series.max() == series.min():
        return series * 0
    return (series - series.min()) / (series.max() - series.min()) * 100


def compute_scores() -> pd.DataFrame:
    tech = score_technical()
    supply = score_supply_demand()
    event = score_event()

    merged = pd.merge(tech, supply, on="ticker", how="outer")
    merged = pd.merge(merged, event, on="ticker", how="outer").fillna(0)

    merged["tech_score"] = _normalize_0_100(merged["tech_raw"])
    merged["supply_score"] = _normalize_0_100(merged["supply_raw"])
    merged["event_score"] = merged["event_raw"].clip(upper=100)

    merged["total_score"] = (
        merged["supply_score"] * config.WEIGHT_SUPPLY_DEMAND
        + merged["tech_score"] * config.WEIGHT_TECHNICAL
        + merged["event_score"] * config.WEIGHT_EVENT
    )

    merged = merged.sort_values("total_score", ascending=False).reset_index(drop=True)
    os.makedirs(config.DATA_DIR, exist_ok=True)
    merged.to_csv(os.path.join(config.DATA_DIR, "scores.csv"), index=False, encoding="utf-8-sig")
    print(f"[스코어링] 완료. 총 {len(merged)}종목 산정")
    return merged


if __name__ == "__main__":
    compute_scores()
