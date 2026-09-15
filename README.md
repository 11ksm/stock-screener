# 수원WM 데일리 종목 스크리닝 홈페이지

매일 아침 자동으로 코스피+코스닥 전체 종목을 아래 3항목으로 스코어링(각 1/3 균등 가중)하여
정적 홈페이지를 갱신하는 프로젝트입니다.

- **기관/외국인 수급**: 최근 20거래일 순매수거래대금 합산
- **기술적지표**: 이동평균 정배열, RSI, MACD, 거래량 급증 종합
- **재료성 이벤트**: 자사주 취득/소각 공시 (DART Open API)

---

## 1. GitHub 저장소 만들기

1. github.com 로그인 → 우측 상단 **+** → **New repository**
2. Repository name: 예) `stock-screener` (Public으로 설정해야 GitHub Pages 무료 사용 가능)
3. 생성 후, 이 폴더 전체를 저장소에 업로드합니다.
   - 컴퓨터에 git이 있다면:
     ```
     cd mirae-wm-stock-screener
     git init
     git add .
     git commit -m "init"
     git branch -M main
     git remote add origin https://github.com/본인계정/stock-screener.git
     git push -u origin main
     ```
   - git이 낯설다면: 저장소 페이지의 **Add file → Upload files**로 이 폴더 안의 파일/폴더를 그대로 드래그 앤 드롭해서 올려도 됩니다.

## 2. Actions 쓰기 권한 켜기 (자동 커밋을 위해 필요)

저장소 **Settings → Actions → General → Workflow permissions**에서
**"Read and write permissions"**를 선택 후 저장하세요.
(이걸 안 하면 매일 자동 업데이트된 결과를 저장소에 커밋하지 못합니다.)

## 3. DART API 키 등록 (자사주 매입/소각 데이터용)

1. https://opendart.fss.or.kr 에서 무료 회원가입 → 마이페이지에서 인증키 발급 (즉시 발급, 무료)
2. 저장소 **Settings → Secrets and variables → Actions → New repository secret**
3. Name: `DART_API_KEY`, Value: 발급받은 키 붙여넣기 → 저장

> 키를 등록하지 않아도 나머지(수급+기술) 2항목만으로 임시 작동은 하지만,
> 원래 요청하신 "자사주 매입/소각" 항목을 쓰려면 필수입니다.

## 4. GitHub Pages 켜기 (홈페이지로 공개)

저장소 **Settings → Pages**에서
- Source: **Deploy from a branch**
- Branch: **main**, 폴더: **/docs**
로 설정 후 저장. 잠시 후 `https://본인계정.github.io/stock-screener/` 주소로 접속 가능합니다.

## 5. 자동 실행 확인

- `.github/workflows/daily-update.yml`이 매일 한국시간 08:30(평일)에 자동 실행되어
  데이터를 수집하고 `docs/index.html`을 갱신 후 자동 커밋합니다.
- 지금 바로 테스트하고 싶다면 저장소 **Actions 탭 → Daily Stock Screening → Run workflow** 버튼으로 수동 실행해보세요.
- 전체 종목(약 2,500개) 처리 특성상 첫 실행은 10~30분 정도 걸릴 수 있습니다.

---

## 폴더 구조

```
config.py                     # 가중치/기간 등 전체 설정
run_pipeline.py                # 전체 파이프라인 실행 진입점
scripts/
  fetch_price_data.py          # KRX 가격/거래량 수집
  fetch_investor_data.py       # 기관/외국인 수급 수집
  fetch_buyback_dart.py        # DART 자사주 매입/소각 공시 수집
  compute_score.py             # 3항목 스코어링 및 합산
  generate_html.py             # 결과를 docs/index.html로 렌더링
templates/index_template.html  # 홈페이지 디자인 템플릿
docs/index.html                 # 실제 배포되는 홈페이지 (자동 생성됨)
.github/workflows/daily-update.yml  # 매일 자동 실행 스케줄
```

## 커스터마이징

- **비중 조정**: `config.py`의 `WEIGHT_SUPPLY_DEMAND / WEIGHT_TECHNICAL / WEIGHT_EVENT` 값을 바꾸면 됩니다 (현재 1/3씩 균등).
- **노출 종목 수**: `config.py`의 `TOP_N` (기본 50)
- **소형주 제외로 속도 개선**: `config.py`의 `MIN_MARKET_CAP`을 원하는 시가총액(원)으로 설정 (기능 연동은 필요시 추가 구현)
- **디자인 변경**: `templates/index_template.html`의 CSS 부분 수정

## 참고 및 주의사항

- 데이터 출처: KRX(pykrx), DART Open API. 모두 공개 데이터입니다.
- `pykrx`는 비공식 라이브러리로 KRX 정책 변경 시 일부 함수의 동작이나 컬럼명이 바뀔 수 있습니다.
  로컬에서 `python run_pipeline.py`를 한 번 돌려보고 에러가 나면 해당 함수의 반환 컬럼명을 확인해 코드 상단 주석의 안내를 참고해 조정하세요.
- 이 홈페이지는 투자 판단을 보조하는 참고 자료이며, 실제 매매 전에는 최신 공시와 시세를 반드시 재확인하시길 권장합니다.
