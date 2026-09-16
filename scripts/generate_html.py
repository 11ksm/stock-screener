"""스코어와 시장지수를 정적 HTML 홈페이지(docs/index.html)로 렌더링합니다."""
import json
import os
from datetime import datetime
from html import escape
from zoneinfo import ZoneInfo

import pandas as pd

import config


TEMPLATE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "templates",
    "index_template.html",
)


def get_universe_map(tickers):
    fallback = {ticker: {"name": ticker, "market": "-"} for ticker in tickers}
    path = os.path.join(config.DATA_DIR, "universe.csv")
    if not os.path.exists(path):
        return fallback
    universe = pd.read_csv(path, dtype={"ticker": str})
    if not {"ticker", "name"}.issubset(universe.columns):
        return fallback
    universe["ticker"] = universe["ticker"].astype(str).str.zfill(6)
    if "market" not in universe.columns:
        universe["market"] = "-"
    return {
        row["ticker"]: {"name": row["name"], "market": row["market"]}
        for _, row in universe.iterrows()
    }


def _performance_badge(label: str, item) -> str:
    if not item:
        return f'<span class="perf-badge pending">{escape(label)} 집계 전</span>'
    value = float(item["return"])
    direction = "positive" if value > 0 else "negative" if value < 0 else "flat"
    title = (
        f"{item['screen_date']} 선정 · 매수가 {float(item['entry_close']):,.0f}원 · "
        f"평가일 {item['exit_date']} · 종가 {float(item['exit_close']):,.0f}원"
    )
    return (
        f'<span class="perf-badge {direction}" title="{escape(title)}">'
        f"{escape(label)} {value:+.2f}% ({escape(str(item['screen_date'])[5:].replace('-', '/'))})</span>"
    )


def render_rows(df: pd.DataFrame, profiles: dict, performance: dict) -> str:
    rows_html = []
    for i, row in df.reset_index(drop=True).iterrows():
        ticker = str(row["ticker"]).zfill(6)
        market = escape(str(row.get("market", "-")))
        profile = profiles.get(ticker, {}) if isinstance(profiles, dict) else {}
        business = str(profile.get("summary") or profile.get("industry") or "기업개요 미수집")
        perf = performance.get(ticker, {})
        if ticker not in performance and i >= int(config.TOP_N):
            performance_html = '<span class="perf-badge pending">추적 이력 없음</span>'
        else:
            performance_html = (
                _performance_badge("1일", perf.get("d1"))
                + _performance_badge("1주", perf.get("d5"))
            )
        rows_html.append(
            f"""<tr>
  <td class="rank">{i + 1}</td>
  <td class="stock-cell">
    <div class="stock-title"><span class="stock-name">{escape(str(row.get('name', '')))}</span>{performance_html}</div>
    <div class="business-summary">{escape(business)}</div>
  </td>
  <td><span class="market-badge">{market}</span></td>
  <td class="ticker">{escape(ticker)}</td>
  <td class="score-total" data-sort-value="{float(row['total_score']):.4f}">
    <details class="score-details">
      <summary>{row['total_score']:.1f}</summary>
      <div class="score-breakdown">
        <span>수급 <b>{row['supply_score']:.1f}</b></span>
        <span>기술 <b>{row['tech_score']:.1f}</b></span>
        <span>재료 <b>{row['event_score']:.1f}</b></span>
      </div>
    </details>
  </td>
</tr>"""
        )
    return "\n".join(rows_html)


def _format_value(value):
    if value is None:
        return "-"
    return f"{float(value):,.2f}"


def _format_signed(value, suffix=""):
    if value is None:
        return "-"
    number = float(value)
    return f"{number:+,.2f}{suffix}"


def _format_as_of(value):
    if not value:
        return "기준시각 없음"
    try:
        traded_at = datetime.fromisoformat(value)
        return traded_at.strftime("%m/%d %H:%M")
    except (TypeError, ValueError):
        return escape(str(value))


def load_market_items():
    path = os.path.join(config.DATA_DIR, "market_indices.json")
    if not os.path.exists(path):
        return []
    try:
        with open(path, encoding="utf-8") as file:
            payload = json.load(file)
        return payload.get("items", []) if isinstance(payload, dict) else []
    except (OSError, json.JSONDecodeError):
        return []


def load_company_profiles():
    path = os.path.join(config.DATA_DIR, "company_profiles.json")
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as file:
            payload = json.load(file)
        return payload if isinstance(payload, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def load_performance_map():
    path = os.path.join(config.DATA_DIR, "screening_history.csv")
    if not os.path.exists(path):
        return {}
    try:
        history = pd.read_csv(path, dtype={"ticker": str, "screen_date": str})
    except (OSError, pd.errors.EmptyDataError, pd.errors.ParserError):
        return {}
    required = {"ticker", "screen_date", "entry_close", "d1_return", "d5_return"}
    if not required.issubset(history.columns):
        return {}
    history["ticker"] = history["ticker"].astype(str).str.zfill(6)
    history = history.sort_values("screen_date", ascending=False, kind="stable")
    result = {}
    horizon_columns = {
        "d1": ("d1_return", "d1_date", "d1_close"),
        "d5": ("d5_return", "d5_date", "d5_close"),
    }
    for ticker, group in history.groupby("ticker", sort=False):
        result[ticker] = {}
        for horizon, (return_col, date_col, close_col) in horizon_columns.items():
            if not {return_col, date_col, close_col}.issubset(group.columns):
                continue
            values = group.copy()
            values[return_col] = pd.to_numeric(values[return_col], errors="coerce")
            values["entry_close"] = pd.to_numeric(values["entry_close"], errors="coerce")
            values[close_col] = pd.to_numeric(values[close_col], errors="coerce")
            values = values.dropna(subset=[return_col, "entry_close", close_col])
            if values.empty:
                continue
            latest = values.iloc[0]
            result[ticker][horizon] = {
                "return": float(latest[return_col]),
                "screen_date": str(latest["screen_date"]),
                "entry_close": float(latest["entry_close"]),
                "exit_date": str(latest[date_col]),
                "exit_close": float(latest[close_col]),
            }
    return result


def render_market_cards(items):
    cards = []
    for item in items:
        status = item.get("status")
        change = item.get("change")
        direction = "flat"
        if isinstance(change, (int, float)):
            direction = "up" if change > 0 else "down" if change < 0 else "flat"
        if status != "ok" or item.get("value") is None:
            cards.append(
                f"""<article class="market-card unavailable">
  <div class="market-card-top"><span>{escape(str(item.get('short_name', '-')))}</span><span class="status-dot"></span></div>
  <strong>데이터 없음</strong>
  <p>{escape(str(item.get('name', '')))}</p>
</article>"""
            )
            continue
        delay = escape(str(item.get("delay", "")))
        delay_text = f" · {delay}" if delay else ""
        cards.append(
            f"""<article class="market-card {direction}">
  <div class="market-card-top"><span>{escape(str(item.get('short_name', '-')))}</span><span class="status-dot"></span></div>
  <strong>{_format_value(item.get('value'))}</strong>
  <p>{_format_signed(item.get('change'))} <b>{_format_signed(item.get('change_rate'), '%')}</b></p>
  <small>{_format_as_of(item.get('as_of'))}{delay_text}</small>
</article>"""
        )
    if not cards:
        return '<div class="market-empty">시장지수 데이터를 불러오지 못했습니다. 종목 순위는 정상적으로 표시됩니다.</div>'
    return "\n".join(cards)


def render_us_market_review(items):
    labels = {
        ".DJI": "다우",
        ".INX": "S&P500",
        ".IXIC": "나스닥",
        ".SOX": "SOX",
    }
    rates = {
        str(item.get("code")): item.get("change_rate")
        for item in items
        if item.get("status") == "ok"
        and str(item.get("code")) in labels
        and isinstance(item.get("change_rate"), (int, float))
    }
    if len(rates) < 3:
        return """<div class="us-review-copy">
  <strong>미국시장 리뷰 준비 중</strong>
  <p>주요 미국지수 데이터가 충분하지 않아 자동 요약을 생성하지 않았습니다.</p>
</div>"""

    values = list(rates.values())
    if all(value > 0 for value in values):
        headline = "미국 증시 전반 상승"
    elif all(value < 0 for value in values):
        headline = "미국 증시 전반 하락"
    else:
        headline = "미국 증시 혼조"

    spx = rates.get(".INX")
    nasdaq = rates.get(".IXIC")
    sox = rates.get(".SOX")
    if nasdaq is not None and sox is not None and nasdaq > 0 and sox > 0:
        if spx is not None and sox > spx:
            style = "반도체를 중심으로 성장주가 상대 우위를 보여 국내 대형 기술주 투자심리에 우호적일 수 있습니다."
        else:
            style = "기술주와 반도체가 동반 강세를 보여 국내 성장주 투자심리에 우호적일 수 있습니다."
    elif nasdaq is not None and sox is not None and nasdaq < 0 and sox < 0:
        style = "기술주와 반도체가 동반 약세를 보여 국내 성장주와 반도체주의 변동성 확대에 유의할 필요가 있습니다."
    else:
        style = "기술주와 반도체의 방향이 엇갈려 국내 시장에서도 업종별 차별화 가능성이 높습니다."

    night_rate = next(
        (
            item.get("change_rate")
            for item in items
            if str(item.get("code")) == "K2I1!"
            and item.get("status") == "ok"
            and isinstance(item.get("change_rate"), (int, float))
        ),
        None,
    )
    if night_rate is not None and night_rate > 0:
        domestic = "KOSPI200 야간선물은 상승 마감해 국내 개장 초반 심리에 긍정적이나, 환율과 외국인 선물 수급을 함께 확인해야 합니다."
    elif night_rate is not None and night_rate < 0:
        domestic = "KOSPI200 야간선물은 하락 마감해 국내 개장 초반 경계감이 예상되며, 환율과 외국인 선물 수급 확인이 필요합니다."
    else:
        domestic = "국내 개장 방향은 원·달러 환율과 외국인 선물 수급을 추가로 확인해야 합니다."

    return f"""<div class="us-review-copy">
  <strong>{escape(headline)}</strong>
  <p>{escape(style)}</p>
  <p>{escape(domestic)}</p>
</div>"""


def generate():
    scores_path = os.path.join(config.DATA_DIR, "scores.csv")
    df = pd.read_csv(scores_path)
    df["ticker"] = df["ticker"].astype(str).str.zfill(6)
    universe_map = get_universe_map(df["ticker"].tolist())
    df["name"] = df["ticker"].map(lambda ticker: universe_map.get(ticker, {}).get("name", ticker))
    df["market"] = df["ticker"].map(lambda ticker: universe_map.get(ticker, {}).get("market", "-"))
    df = df.sort_values("total_score", ascending=False, kind="stable").reset_index(drop=True)

    with open(TEMPLATE_PATH, encoding="utf-8") as file:
        template = file.read()

    updated_at = datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y-%m-%d %H:%M KST")
    market_items = load_market_items()
    html = template.replace("{{MARKET_CARDS}}", render_market_cards(market_items))
    html = html.replace("{{US_MARKET_REVIEW}}", render_us_market_review(market_items))
    html = html.replace(
        "{{ROWS}}",
        render_rows(df, load_company_profiles(), load_performance_map()),
    )
    html = html.replace("{{UPDATED_AT}}", updated_at)
    html = html.replace("{{TOTAL_COUNT}}", str(len(df)))
    html = html.replace("{{TOP_N}}", str(config.TOP_N))
    html = html.replace("{{UNIVERSE_PER_MARKET}}", str(config.UNIVERSE_PER_MARKET))

    os.makedirs(config.DOCS_DIR, exist_ok=True)
    with open(os.path.join(config.DOCS_DIR, "index.html"), "w", encoding="utf-8") as file:
        file.write(html)
    print("[홈페이지] docs/index.html 생성 완료")


if __name__ == "__main__":
    generate()
