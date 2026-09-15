"""
스코어링 결과를 정적 HTML 홈페이지(docs/index.html)로 렌더링합니다.
GitHub Pages가 docs/ 폴더를 서빙하도록 설정하면 이 파일이 곧 홈페이지가 됩니다.
"""
import os
from datetime import datetime

import pandas as pd
import config
from pykrx import stock

TEMPLATE_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "templates", "index_template.html")


def get_name_map(tickers):
    name_map = {}
    for t in tickers:
        try:
            name_map[t] = stock.get_market_ticker_name(t)
        except Exception:
            name_map[t] = t
    return name_map


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
    df["name"] = df["ticker"].map(name_map)

    with open(TEMPLATE_PATH, encoding="utf-8") as f:
        template = f.read()

    updated_at = datetime.now().strftime("%Y-%m-%d %H:%M KST")
    html = template.replace("{{ROWS}}", render_rows(df))
    html = html.replace("{{UPDATED_AT}}", updated_at)
    html = html.replace("{{TOTAL_COUNT}}", str(len(df)))

    os.makedirs(config.DOCS_DIR, exist_ok=True)
    with open(os.path.join(config.DOCS_DIR, "index.html"), "w", encoding="utf-8") as f:
        f.write(html)
    print("[홈페이지] docs/index.html 생성 완료")


if __name__ == "__main__":
    generate()
