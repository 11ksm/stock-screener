"""GitHub Actions에서 실행하는 전체 파이프라인."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "scripts"))

import fetch_market_indices
import fetch_price_data
import fetch_investor_data
import fetch_buyback_dart
import compute_score
import fetch_company_profiles
import update_tracking
import generate_html


def main():
    print("=== 0. 국내·미국 주요 지수 수집 ===")
    fetch_market_indices.fetch_market_indices()

    print("=== 1. 가격/거래량 데이터 수집 ===")
    fetch_price_data.fetch_all_prices()

    print("=== 2. 기관/외국인 수급 데이터 수집 ===")
    fetch_investor_data.fetch_investor_flows()

    print("=== 3. 자사주 매입/소각 공시 수집 ===")
    fetch_buyback_dart.fetch_buyback_disclosures()

    print("=== 4. 스코어링 계산 ===")
    compute_score.compute_scores()

    print("=== 5. 선정종목 성과 추적 ===")
    update_tracking.update_tracking()

    print("=== 6. 기업 주요사업 정보 수집 ===")
    fetch_company_profiles.fetch_company_profiles()

    print("=== 7. 홈페이지 생성 ===")
    generate_html.generate()

    print("=== 완료 ===")


if __name__ == "__main__":
    main()
