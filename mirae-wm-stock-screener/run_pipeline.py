"""
전체 파이프라인 실행 스크립트.
GitHub Actions가 매일 아침 이 파일 하나만 실행하면 됩니다:  python run_pipeline.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "scripts"))

import fetch_price_data
import fetch_investor_data
import fetch_buyback_dart
import compute_score
import generate_html


def main():
    print("=== 1. 가격/거래량 데이터 수집 ===")
    fetch_price_data.fetch_all_prices()

    print("=== 2. 기관/외국인 수급 데이터 수집 ===")
    fetch_investor_data.fetch_investor_flows()

    print("=== 3. 자사주 매입/소각 공시 수집 ===")
    fetch_buyback_dart.fetch_buyback_disclosures()

    print("=== 4. 스코어링 계산 ===")
    compute_score.compute_scores()

    print("=== 5. 홈페이지 생성 ===")
    generate_html.generate()

    print("=== 완료 ===")


if __name__ == "__main__":
    main()
