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


def render_rows(df: pd.DataFrame) -> str:
    rows_html = []
    for i, row in df.reset_index(drop=True).iterrows():
        market = escape(str(row.get("market", "-")))
        rows_html.append(
            f"""<tr>
  <td class="rank">{i + 1}</td>
  <td class="stock-name">{escape(str(row.get('name', '')))}</td>
  <td><span class="market-badge">{market}</span></td>
  <td class="ticker">{escape(str(row['ticker']))}</td>
  <td class="score-total">{row['total_score']:.1f}</td>
  <td>{row['supply_score']:.1f}</td>
  <td>{row['tech_score']:.1f}</td>
  <td>{row['event_score']:.1f}</td>
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


def generate():
    scores_path = os.path.join(config.DATA_DIR, "scores.csv")
    df = pd.read_csv(scores_path)
    df["ticker"] = df["ticker"].astype(str).str.zfill(6)
    universe_map = get_universe_map(df["ticker"].tolist())
    df["name"] = df["ticker"].map(lambda ticker: universe_map.get(ticker, {}).get("name", ticker))
    df["market"] = df["ticker"].map(lambda ticker: universe_map.get(ticker, {}).get("market", "-"))

    with open(TEMPLATE_PATH, encoding="utf-8") as file:
        template = file.read()

    updated_at = datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y-%m-%d %H:%M KST")
    html = template.replace("{{MARKET_CARDS}}", render_market_cards(load_market_items()))
    html = html.replace("{{ROWS}}", render_rows(df))
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
