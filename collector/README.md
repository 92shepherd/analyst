# collector

KIS Open API 기반 **일봉 시세 수집** 서비스 (처리 파이프라인 단계 ①).
코스피·코스닥(국내)과 나스닥·뉴욕(해외) 전종목의 일봉(OHLCV)을 수집해 `db`에 적재한다.

## 아키텍처 (Clean Architecture)

의존성은 항상 안쪽(도메인)을 향한다.

```
infrastructure (KIS HTTP/DB/스케줄러/FastAPI)
└─ adapters (KIS 어댑터·Mapper, Postgres 리포지토리, API/스케줄 핸들러)
   └─ application (CollectDailyPricesUseCase + 포트)
      └─ domain (Stock, DailyPrice = SQLAlchemy ORM 모델, Market enum)
```

| 레이어 | 위치 | 책임 |
| --- | --- | --- |
| domain | `src/collector/domain` | 엔티티(= SQLAlchemy ORM 모델, **단일 모델**) + Base·enum |
| application | `src/collector/application` | 유즈케이스 + 아웃바운드 포트 |
| adapters | `src/collector/adapters` | 포트 구현(KIS/Postgres), 진입점(API/스케줄) |
| infrastructure | `src/collector/infrastructure` | KIS 클라이언트, DB 엔진, 설정, DI |

**단일 모델**: 도메인 엔티티(`Stock`·`DailyPrice`)가 곧 SQLAlchemy ORM 모델이다(별도 영속화 모델 없음). 도메인/유즈케이스에는 httpx·KIS 응답이 새지 않으며(SQLAlchemy 매핑만 도메인에서 허용), KIS 응답→모델 변환은 어댑터의 Mapper가 담당한다. 포트 분리는 유지된다.

## 데이터 흐름

1. `StockRepositoryPort`로 DB의 **종목 마스터**(수집 유니버스)를 읽는다. *(마스터 적재는 이 서비스 범위 밖 — 읽기 전용 가정)*
2. 종목별 최근 적재일 다음 날부터 **증분**으로 일봉 조회 (`MarketDataPort` → KIS REST).
   - 국내: `inquire-daily-itemchartprice` (TR `FHKST03010100`)
   - 해외: `overseas-price/.../dailyprice` (TR `HHDFS76240000`)
3. `(ticker, market, trade_date)` 기준 **멱등 upsert**로 `collector.daily_prices`에 적재.

이 출력 테이블은 `analyst`가 읽는 **계약**이다. 스키마 변경 시 문서화한다.

## 실행

### Docker Compose (권장)

프로젝트 루트에서 db + collector를 함께 띄운다. collector 컨테이너는 기동 시
`alembic upgrade head`로 스키마를 적용한 뒤 앱을 시작한다.

```bash
cp .env.example .env   # 루트 .env: DB 계정 + KIS 앱키/시크릿
docker compose up --build
```

### 로컬 개발

```bash
pip install -e ".[dev]"

cp .env.example .env    # collector 로컬용 (COLLECTOR_DATABASE_URL 등)
alembic upgrade head    # DB 마이그레이션 (SQLAlchemy 모델 기반)

collector               # 스케줄러 + 수동 트리거 API
```

마이그레이션은 **Alembic**으로 관리한다. 모델 변경 후:

```bash
alembic revision --autogenerate -m "변경 설명"
alembic upgrade head
```

수동 트리거:

```bash
curl -X POST localhost:8000/collect/daily \
  -H 'content-type: application/json' \
  -d '{"markets":["KOSPI"],"lookback_days":5}'
```

## 설정 (env, 접두사 `COLLECTOR_`)

| 키 | 기본값 | 설명 |
| --- | --- | --- |
| `KIS_ENV` | `paper` | `paper`(모의)/`real`(실전) |
| `KIS_APP_KEY` / `KIS_APP_SECRET` | — | KIS 인증 |
| `KIS_RATE_LIMIT_PER_SEC` | `8` | 호출 스로틀 |
| `DATABASE_URL` | postgres+asyncpg | 비동기 DSN |
| `DOMESTIC_CRON` | `0 16 * * mon-fri` | 국내 수집 |
| `OVERSEAS_CRON` | `0 7 * * tue-sat` | 해외 수집(미 마감 후 KST) |

## 테스트

```bash
pytest          # 유즈케이스/Mapper 단위 테스트 (포트는 mock)
```

## 스케줄 (국장/미장 분리)

`AsyncIOScheduler`에 두 개의 독립 cron 잡을 등록한다(`main.py`).

| 잡 | 대상 | 기본 cron | env |
| --- | --- | --- | --- |
| `collect_domestic_daily` | 코스피·코스닥 | `0 16 * * mon-fri` | `COLLECTOR_DOMESTIC_CRON` |
| `collect_overseas_daily` | 나스닥·뉴욕 | `0 7 * * tue-sat` | `COLLECTOR_OVERSEAS_CRON` |

각 잡은 해당 시장만 필터링해 수집하므로 국장/미장을 서로 다른 시각에 자동 수집한다.

## 설계 메모

- KIS 호출은 `infrastructure/kis` 클라이언트와 `adapters/outbound/kis` 어댑터만 경유한다.
- 토큰 발급/만료/갱신은 클라이언트에 캡슐화(호출부 비노출), 레이트리밋은 토큰버킷 스로틀.
- 모의투자가 기본 환경. 시크릿은 env로만 주입.
- 한 종목 실패가 배치 전체를 막지 않도록 종목 단위로 예외를 격리한다.
- **단일 모델**: `Stock`·`DailyPrice`는 SQLAlchemy 선언형 모델이며, 가격 불변식은 DB CHECK 제약(`high>=low`, 음수 금지)과 `@validates`로 강제한다.

### 향후 (이 MVP 범위 밖)
- 종목 마스터 적재 잡(KIS 마스터 파일 → `collector.stocks`).
- 100건 초과 장기 히스토리 페이지네이션, 휴장일 캘린더 정교화.
- 단계 ② 지표 계산 유즈케이스.
