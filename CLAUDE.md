# CLAUDE.md

이 문서는 본 프로젝트에서 코드를 작성·수정하는 모든 작업의 **최상위 지침**입니다.
Claude 및 모든 기여자는 작업 전 이 문서를 먼저 읽고, 아래 규칙을 **반드시** 준수합니다.

---

## 1. 프로젝트 개요

한국투자증권(KIS) Open API를 기반으로 한 **주식 자동매매 시스템**입니다.
주가·지표를 수집하여 종목별 투자의견을 산출하고, 의견에 따라 자동으로 매수·모니터링·매도를 수행합니다.

서비스는 **Docker Compose**로 여러 컨테이너를 나누어 운영하는 **마이크로서비스 구조**입니다.

### 1.1 처리 파이프라인 (핵심 도메인 흐름)

| 단계 | 이름 | 설명 | 담당 서비스 |
| --- | --- | --- | --- |
| 1 | 주가 수집 | KIS REST API로 종목별 시세(현재가·일봉·체결 등)를 수집 | `collector` |
| 2 | 지표 수집·계산 | 목표주가·투자의견 산출에 필요한 재무/기술 지표를 수집·계산 | `collector` |
| 3 | 투자의견 생성 | 종목별로 목표주가·투자의견(매수/관망/매도 등)을 생성 | `analyst` |
| 4 | 자동 매수 체결 | 생성된 투자의견에 따라 KIS 주문 API로 매수 주문 자동 체결 | `trading` |
| 5 | 보유 종목 모니터링 | 매수 체결된 종목을 KIS WebSocket으로 실시간 연결·지속 모니터링 | `trading` |
| 6 | 자동 매도 체결 | 모니터링 데이터로 매도 시그널을 계산하고 매도 주문 자동 체결 | `trading` |

> 1~3은 **분석 파이프라인**(배치/스케줄), 4~6은 **거래 파이프라인**(실시간)으로 구분해 설계합니다.

---

## 2. 서비스 구성 (Docker Compose)

| 서비스 | 기술 스택 | 책임 | 파이프라인 단계 |
| --- | --- | --- | --- |
| `db` | PostgreSQL 16 | 시세·지표·투자의견·주문·체결·감사로그 영속화 | 전체 |
| `auth-server` | Go, OAuth 2.1 | 인증/인가(토큰 발급·검증), 사용자/세션 관리 | 공통 |
| `web-front` | TypeScript, React | 대시보드 UI(투자의견·포지션·로그 조회, 킬스위치 등) | 공통 |
| `collector` | Python | 주가 수집 + 지표 수집·계산 | ①② |
| `analyst` | Python | 투자의견·목표주가 생성 | ③ |
| `trading` | Python | 자동 매수 / 실시간 모니터링 / 자동 매도 | ④⑤⑥ |

### 2.1 서비스 의존 관계

```
            ┌────────────┐        ┌──────────────┐
   사용자 ──│ web-front  │──토큰──│ auth-server  │
            │ (React/TS) │        │  (Go,OAuth2.1)│
            └─────┬──────┘        └──────┬───────┘
                  │  REST(인가됨)         │ 토큰 검증
                  ▼                       ▼
        ┌─────────────────────────────────────────┐
        │   collector → analyst → trading          │
        │   (Python 서비스, 단계 ①②  ③  ④⑤⑥)       │
        └─────────────────────────────────────────┘
                  │ 읽기/쓰기            ▲ KIS API(REST/WS)
                  ▼                     │
            ┌────────────┐        ┌──────────────┐
            │   db        │        │  KIS Open API │
            │ (Postgres16)│        │ (외부 시스템) │
            └────────────┘        └──────────────┘
```

### 2.2 서비스 간 통신 규칙

- **데이터 전달의 1차 경로는 `db`(PostgreSQL)** 이다. `collector`가 적재한 시세·지표를 `analyst`가 읽어 투자의견을 쓰고, `trading`이 투자의견을 읽어 주문을 실행한다.
- 단계 트리거(배치 완료 알림 등)가 필요하면 **메시지/이벤트 채널**(예: PostgreSQL `LISTEN/NOTIFY` 또는 별도 브로커)을 사용한다. 브로커 도입 여부는 운영 부하를 보고 결정하며, **합의 전까지 DB 폴링/스케줄을 기본**으로 한다.
- 서비스 간 동기 호출이 필요하면 **REST(JSON)** 를 사용하고, 외부에 노출되는 엔드포인트는 **`auth-server` 토큰 검증을 반드시 거친다.**
- 각 서비스는 **자신의 DB 스키마(또는 스키마 네임스페이스)를 소유**한다. 다른 서비스의 테이블을 직접 변경하지 않는다(읽기 공유는 허용하되 계약을 문서화).
- KIS Open API 호출은 **`collector`(시세 REST)와 `trading`(주문 REST·실시간 WS)에서만** 수행한다.

---

## 3. 필수 규칙 (반드시 준수)

### 규칙 1 — 소스코드 작업 시 Context7 사용

라이브러리·프레임워크·SDK·API를 다루는 모든 코드 작업에서는 **반드시 Context7로 최신 공식 문서를 조회**한 뒤 코드를 작성/수정합니다. 학습된 지식만으로 추측하지 않습니다.

적용 대상 예시(서비스별):
- `collector`/`analyst`/`trading`(Python): FastAPI, httpx/aiohttp, `websockets`, SQLAlchemy, pandas/numpy, pytest, KIS 연동 라이브러리
- `auth-server`(Go): 표준 라이브러리, OAuth2.1/OIDC 라이브러리, 라우터, DB 드라이버
- `web-front`(TypeScript/React): React, 라우팅·상태관리·데이터 패칭 라이브러리, 빌드 도구
- `db`/인프라: PostgreSQL 16, Docker Compose 설정

작업 절차:
1. 작업에 사용할 라이브러리/도구를 식별한다.
2. Context7로 해당 라이브러리의 최신 문서(API 시그니처·설정·마이그레이션)를 조회한다.
3. 조회 결과에 근거해 코드를 작성한다.

> 리팩터링, 비즈니스 로직 디버깅, 처음부터 작성하는 순수 스크립트, 일반 프로그래밍 개념에는 Context7가 불필요할 수 있으나, 외부 의존성의 사용법이 관여하면 항상 조회한다.

### 규칙 2 — Clean Architecture 준수

각 서비스 내부 구조와 의존성 방향은 아래 4장의 Clean Architecture 규칙을 따릅니다. 위반하는 코드는 작성하지 않습니다.

---

## 4. Clean Architecture (서비스별 내부 구조)

각 백엔드 서비스(`collector`/`analyst`/`trading`, 그리고 `auth-server`)는 **독립적으로 Clean Architecture**를 따릅니다. `web-front`는 컴포넌트/도메인 로직/데이터 접근(API 클라이언트)을 분리하는 동일한 원칙을 적용합니다.

### 4.1 레이어와 의존성 방향

의존성은 **항상 안쪽(도메인)을 향한다.** 바깥 레이어는 안쪽을 알지만, 안쪽은 바깥을 모른다.

```
┌──────────────────────────────────────────────────────────┐
│  Infrastructure / Frameworks                              │
│  (KIS REST/WS 클라이언트, Postgres, 스케줄러, 웹 프레임워크) │
│   ┌────────────────────────────────────────────────────┐ │
│   │  Interface Adapters                                 │ │
│   │  (Controller/Handler, Repository 구현, Mapper)      │ │
│   │   ┌──────────────────────────────────────────────┐ │ │
│   │   │  Application (Use Cases)                      │ │ │
│   │   │  (CollectPrices, GenerateOpinion, PlaceBuy…)  │ │ │
│   │   │   ┌────────────────────────────────────────┐ │ │ │
│   │   │   │  Domain (Entities · Value Objects)     │ │ │ │
│   │   │   │  (Stock, Price, Opinion, Order, …)     │ │ │ │
│   │   │   └────────────────────────────────────────┘ │ │ │
│   │   └──────────────────────────────────────────────┘ │ │
│   └────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────┘
        의존성 방향 →→→ 안쪽으로만
```

**핵심 의존성 규칙(The Dependency Rule):**
- Domain은 비즈니스 엔티티를 담는다. **단일 모델 방침**에 따라 도메인 엔티티는 SQLAlchemy 선언형 ORM 모델로 정의할 수 있다(4.1.1 참고). 그 외 프레임워크/외부 SDK(httpx·websockets·KIS 등)에는 의존하지 않는다.
- Application은 Domain에만 의존한다. 외부 시스템(DB·KIS·HTTP)은 **포트(인터페이스)** 로만 참조한다.
- Infrastructure/Adapter는 Application이 정의한 포트를 **구현(어댑터)** 한다.
- KIS API, WebSocket, 웹 프레임워크 등 구체 기술은 **가장 바깥**에 위치한다. 도메인/유즈케이스 코드에 KIS 응답·httpx·웹 프레임워크 타입이 새어 들어오면 안 된다. (예외: SQLAlchemy ORM 매핑은 도메인 모델 정의에 한해 허용 — 단일 모델)

#### 4.1.1 단일 모델 결정 (ORM = 도메인)

도메인 엔티티와 ORM 모델을 분리하지 않고 **하나의 SQLAlchemy 선언형 모델**로 운영한다. 즉 `Stock`·`DailyPrice`가 곧 테이블 매핑이다. 이에 따른 규칙 완화:
- 도메인 모델은 SQLAlchemy(`DeclarativeBase`, `Mapped`, `mapped_column`)에 의존할 수 있다.
- Use Case는 이 모델(=도메인)을 직접 다루고 반환할 수 있다.
- 단, **포트(인터페이스) 분리는 유지**한다. Use Case는 DB·KIS를 포트로만 호출하고, 세션/쿼리 등 영속성 절차는 어댑터(리포지토리)에 둔다.
- KIS 응답 dict·httpx·웹 프레임워크 타입은 여전히 도메인/유즈케이스로 유입 금지(어댑터 경계에서 모델로 변환).

### 4.2 Python 서비스 디렉터리 구조 (권장, `collector`/`analyst`/`trading` 공통)

```
<service>/                        # 예: collector
├── src/<service>/
│   ├── domain/                   # 레이어 1: 엔티티(= SQLAlchemy ORM 모델, 단일 모델) + Base·enum
│   ├── application/              # 레이어 2: 유즈케이스 + 포트(인터페이스)
│   │   ├── ports/                #   out: MarketDataPort, OrderPort, RealtimePort, Repository…
│   │   └── use_cases/
│   ├── adapters/                 # 레이어 3: 포트 구현·진입점
│   │   ├── inbound/              #   API 핸들러, 스케줄러 핸들러, WS 수신 핸들러
│   │   └── outbound/             #   포트 구현체 (Mapper 포함)
│   │       ├── kis/              #     KIS REST/WebSocket 어댑터
│   │       └── persistence/      #     Repository 구현 (Postgres)
│   ├── infrastructure/           # 레이어 4: 프레임워크·설정·부트스트랩
│   │   ├── kis/                  #   KIS HTTP/WS 클라이언트, 토큰 발급/갱신
│   │   ├── config/               #   env, 시크릿, 모의/실전 환경 분기
│   │   └── db/                   #   커넥션·세션·마이그레이션
│   └── main.py                   # 엔트리포인트(컴포지션 루트·DI 와이어링) — 4개 레이어 밖 최외곽
├── tests/                        # 유즈케이스 단위 테스트(포트는 mock)
├── pyproject.toml
└── Dockerfile
```

### 4.3 단계별 Use Case · Port · Adapter 매핑

| 단계 | 서비스 | Use Case | Port (out) | Adapter |
| --- | --- | --- | --- | --- |
| ① 주가 수집 | collector | `CollectPricesUseCase` | `MarketDataPort`, `PriceRepositoryPort` | KIS 시세 REST / Postgres |
| ② 지표 계산 | collector | `CalculateIndicatorsUseCase` | `MarketDataPort`, `IndicatorRepositoryPort` | KIS REST / Postgres |
| ③ 투자의견 | analyst | `GenerateOpinionUseCase` | `IndicatorRepositoryPort`, `OpinionRepositoryPort` | Postgres |
| ④ 자동 매수 | trading | `PlaceBuyOrderUseCase` | `OpinionRepositoryPort`, `OrderPort` | Postgres / KIS 주문 REST |
| ⑤ 모니터링 | trading | `MonitorPositionsUseCase` | `RealtimePort`, `PositionRepositoryPort` | KIS WebSocket / Postgres |
| ⑥ 자동 매도 | trading | `PlaceSellOrderUseCase` | `OrderPort`, `RealtimePort` | KIS 주문 / WS 어댑터 |

### 4.4 의존성 규칙 위반 금지 예시

- ❌ `domain/`·`application/` 안에서 `httpx`, `websockets`, KIS 응답 dict를 직접 import (단, SQLAlchemy 선언형 모델 정의는 도메인에서 허용 — 단일 모델)
- ❌ Use Case가 KIS API 응답 JSON(raw dict)을 그대로 반환 (도메인 모델로 변환 후 사용)
- ❌ 한 서비스의 도메인 모델을 다른 서비스가 직접 import (서비스 경계는 DB 스키마/REST 계약으로만 공유)
- ✅ Use Case는 포트 인터페이스만 호출하고, 어댑터가 KIS 응답 → 도메인 모델(= ORM)로 변환

---

## 5. 서비스별 지침

### 5.1 collector (Python, 단계 ①②)
- KIS 시세 REST로 현재가·일봉·체결 등을 폴링/배치 수집하고, 지표를 계산해 `db`에 적재한다.
- 수집 스케줄은 장 시간/휴장일을 고려한다. KIS 레이트리밋은 어댑터의 큐/스로틀로 관리한다.
- 출력(시세·지표 테이블)은 `analyst`가 읽는 **계약**이므로 스키마 변경 시 문서화한다.
- 주가 수집 시점의 밸류에이션(PER/PBR/EPS/BPS)은 주가와 **별도 테이블** `collector.valuation_snapshots`에 적재한다. 국내 일봉 응답 `output1`을 재사용해 추가 호출 없이 PER/EPS/PBR을 얻고 BPS는 주가÷PBR로 유도한다. 해외는 KIS 미제공(best-effort). 밸류에이션 적재 실패는 주가 수집 성공에 영향 없음(부가 지표).
- 수집 실행은 **런(job run) 단위**로 `collector.collection_runs`에 기록한다(스케줄·수동 트리거 공통, `CollectionRunService` 경유). 진행상황은 `GET /runs`·`GET /jobs`로 조회하고, 기동 시 비정상 종료로 남은 `RUNNING` 런은 `INTERRUPTED`로 정리한다(단일 인스턴스 전제).

### 5.2 analyst (Python, 단계 ③)
- `collector`가 적재한 지표를 읽어 종목별 목표주가·투자의견을 산출해 `db`에 저장한다.
- 의견 산출 로직(룰/모델)은 도메인·유즈케이스에 두고, 데이터 접근은 포트로만 한다.
- 산출 근거를 함께 저장해 감사 가능하도록 한다.

### 5.3 trading (Python, 단계 ④⑤⑥)
- 투자의견을 읽어 자동 매수, 보유 종목 실시간 모니터링(WebSocket), 매도 시그널 계산·자동 매도를 수행한다.
- 실제 자금이 움직이는 서비스이므로 **6장 자동매매 안전 규칙을 최우선**으로 적용한다.
- 주문/체결/시그널 근거를 모두 `db` 감사 로그에 남긴다.

### 5.4 auth-server (Go, OAuth 2.1)
- 인증/인가 전담. 표준 OAuth 2.1 플로우(PKCE 필수, Implicit·ROPC 미사용)를 따른다.
- 토큰 발급·검증·갱신을 담당하고, 다른 서비스의 보호된 엔드포인트는 이 토큰을 검증한다.
- 시크릿/키는 `config`(env·시크릿 매니저)로 주입하고 코드에 하드코딩하지 않는다.

### 5.5 web-front (TypeScript, React)
- 투자의견·포지션·주문·감사로그 조회 및 운영 제어(예: **킬 스위치**) UI를 제공한다.
- `auth-server`로 로그인하고, 백엔드 API 호출 시 토큰을 첨부한다.
- API 클라이언트/도메인 상태/프레젠테이션을 분리한다(비즈니스 로직을 컴포넌트에 섞지 않음).

### 5.6 db (PostgreSQL 16)
- 모든 영속 데이터의 단일 저장소. 서비스별 스키마(또는 네임스페이스)로 소유권을 구분한다.
- 스키마 변경은 **마이그레이션**으로 관리하고, 서비스 간 공유 테이블의 계약 변경은 사전 합의·문서화한다.

---

## 6. KIS API 연동 지침

- 모든 KIS 호출은 각 서비스의 `infrastructure/kis` 클라이언트와 `adapters/outbound/kis` 어댑터를 **반드시 경유**한다. 도메인/유즈케이스에서 직접 호출 금지.
- KIS 호출 주체는 **`collector`(시세)와 `trading`(주문·실시간)** 으로 한정한다.
- **접근 토큰**: 발급·만료·갱신 로직을 클라이언트 계층에 캡슐화하고, 호출부에 노출하지 않는다.
- **환경 분기**: 모의투자(paper)와 실전투자(real)는 base URL·앱키·TR_ID가 다르므로 `config`에서 환경값으로 분기한다. 기본값은 **모의투자**로 둔다.
- **시세(REST)**: 현재가·일봉 등 폴링/배치 수집은 단계 ①②(`collector`)에서 사용.
- **실시간(WebSocket)**: 체결가·호가 구독은 단계 ⑤(`trading`)에서 사용. 재연결(reconnect)·하트비트·구독 종목 수 제한을 어댑터에서 처리한다.
- **레이트리밋**: KIS 호출 한도를 어댑터에서 큐/스로틀로 관리한다.
- 연동 코드 작성·수정 시 **규칙 1(Context7)** 에 따라 최신 KIS 문서/라이브러리 사용법을 먼저 조회한다.

---

## 7. 자동매매 안전 규칙

자금이 실제로 움직이는 시스템(`trading`)이므로 다음을 강제한다.

- **모의투자 우선**: 신규/변경된 주문 로직은 모의투자 환경에서 검증 후에만 실전 전환.
- **주문 가드**: 종목당 최대 매수 금액, 1일 최대 주문 횟수, 총 노출 한도 등 리스크 한도를 Use Case 레벨에서 검증한다.
- **멱등성**: 주문 중복 체결을 막기 위해 클라이언트 주문 ID(멱등키)를 사용한다.
- **킬 스위치**: 전체 자동매매를 즉시 중단할 수 있는 플래그를 둔다(`web-front`에서 제어, `db`/설정에 반영).
- **감사 로그**: 모든 주문·체결·시그널 산출 근거를 `db`에 로깅한다. (`collector`도 같은 원칙으로 수집 실행을 `collection_runs` 런 단위로 기록한다 — §5.1 참고.)

---

## 8. 코딩 컨벤션

**공통**
- 의존성 주입은 인터페이스(포트) 기준으로 한다.
- 외부 응답은 어댑터 경계에서 검증·매핑한다(도메인으로 raw 데이터 유입 금지).
- 단위 테스트는 Use Case 단위로 작성하고, 포트는 목(mock)으로 대체한다.
- 커밋 전 lint·type-check·test 통과를 확인한다.
- 시크릿/키는 코드에 하드코딩하지 않고 `config`(env·시크릿)로 주입한다.

**Python (`collector`/`analyst`/`trading`)**
- 타입 힌트 필수, 정적 분석(mypy 등)·포매터(ruff/black 등) 적용. 도메인 모델은 가능하면 불변.
- 테스트는 pytest. 비동기 I/O는 어댑터에 격리한다.

**Go (`auth-server`)**
- 표준 포매팅(`gofmt`/`go vet`) 적용. 에러는 명시적으로 처리·래핑한다.

**TypeScript/React (`web-front`)**
- `strict` 모드 사용. API 클라이언트·상태관리·프레젠테이션 레이어 분리.

---

## 9. 작업 체크리스트 (코드 변경 시)

1. 작업에 외부 라이브러리/KIS API가 관여하는가? → **Context7로 최신 문서 조회**
2. 변경이 **올바른 서비스**에 위치하는가? → 파이프라인/책임 매핑 확인
3. 변경이 서비스 내 **올바른 레이어**에 위치하는가? → 의존성 방향(안쪽으로만) 확인
4. 도메인/유즈케이스에 프레임워크·KIS·ORM 타입이 새지 않았는가?
5. 서비스 경계를 침범하지 않았는가?(타 서비스 테이블/도메인 직접 의존 금지)
6. 주문/거래 로직이면 모의투자·리스크 가드·멱등성을 확인했는가?
7. 테스트·타입체크·린트를 통과했는가?
