"""
스코어링 결과를 정적 HTML 홈페이지(docs/index.html)로 렌더링합니다.
종목명은 가격 수집 단계에서 저장한 data/universe.csv를 사용합니다.
"""
import os
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd

import config


TEMPLATE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "templates",
    "index_template.html",
)


def get_name_map(tickers):
    universe_path = os.path.join(config.DATA_DIR, "universe.csv")
    if not os.path.exists(universe_path):
        return {ticker: ticker for ticker in tickers}
    universe = pd.read_csv(universe_path, dtype={"ticker": str})
    if "ticker" not in universe.columns or "name" not in universe.columns:
        return {ticker: ticker for ticker in tickers}
    universe["ticker"] = universe["ticker"].astype(str).str.zfill(6)
    return dict(zip(universe["ticker"], universe["name"]))


def render_rows(df: pd.DataFrame) -> str:
    rows_html = []
    top = df.head(config.TOP_N).reset_index(drop=True)
    for i, row in top.iterrows():
        rows_html.append(
            f"""<tr>
  <td>{i + 1}</td>
  <td>{row.get('name', '')}</td>
  <td>{row['ticker']}</td>
  <td class="score-total">{row['total_score']:.1f}</td>
  <td>{row['supply_score']:.1f}</td>
  <td>{row['tech_score']:.1f}</td>
  <td>{row['event_score']:.1f}</td>
</tr>"""
        )
    return "\n".join(rows_html)


def generate():
    scores_path = os.path.join(config.DATA_DIR, "scores.csv")
    df = pd.read_csv(scores_path)
    df["ticker"] = df["ticker"].astype(str).str.zfill(6)
    name_map = get_name_map(df["ticker"].tolist())
    df["name"] = df["ticker"].map(name_map).fillna(df["ticker"])

    with open(TEMPLATE_PATH, encoding="utf-8") as f:
        template = f.read()

    updated_at = datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y-%m-%d %H:%M KST")
    html = template.replace("{{ROWS}}", render_rows(df))
    html = html.replace("{{UPDATED_AT}}", updated_at)
    html = html.replace("{{TOTAL_COUNT}}", str(len(df)))

    os.makedirs(config.DOCS_DIR, exist_ok=True)
    with open(os.path.join(config.DOCS_DIR, "index.html"), "w", encoding="utf-8") as f:
        f.write(html)
    print("[홈페이지] docs/index.html 생성 완료")


if __name__ == "__main__":
    generate()
