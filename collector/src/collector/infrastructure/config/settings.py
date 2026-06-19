"""환경 설정 (pydantic-settings). 모의투자(paper)/실전(real) 분기.

시크릿/키는 코드에 하드코딩하지 않고 env로 주입한다. 기본 환경은 모의투자.
"""
from __future__ import annotations

from enum import Enum

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class KisEnv(str, Enum):
    PAPER = "paper"  # 모의투자
    REAL = "real"  # 실전투자


# 환경별 base URL.
_BASE_URLS: dict[KisEnv, str] = {
    KisEnv.PAPER: "https://openapivts.koreainvestment.com:29443",
    KisEnv.REAL: "https://openapi.koreainvestment.com:9443",
}

# 시세 조회 TR_ID는 모의/실전 공통(조회계 TR). 환경별로 다르면 여기서 분기.
DOMESTIC_DAILY_PATH = "/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice"
DOMESTIC_DAILY_TR_ID = "FHKST03010100"
OVERSEAS_DAILY_PATH = "/uapi/overseas-price/v1/quotations/dailyprice"
OVERSEAS_DAILY_TR_ID = "HHDFS76240000"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="COLLECTOR_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # KIS 환경/인증 (기본: 모의투자)
    kis_env: KisEnv = KisEnv.PAPER
    kis_app_key: str = Field(default="", description="KIS 앱키")
    kis_app_secret: str = Field(default="", description="KIS 앱시크릿")

    # KIS 호출 레이트리밋 (초당 요청 수). 모의투자 기본 보수적 값.
    kis_rate_limit_per_sec: float = 8.0
    kis_timeout_sec: float = 10.0

    # DB (async dsn). 예: postgresql+asyncpg://user:pass@db:5432/trading
    database_url: str = "postgresql+asyncpg://postgres:postgres@db:5432/trading"

    # 스케줄 (cron). 기본: 국내 16:00, 해외(미 동부 마감 후 KST) 07:00.
    domestic_cron: str = "0 16 * * mon-fri"
    overseas_cron: str = "0 7 * * tue-sat"
    timezone: str = "Asia/Seoul"

    # API 서버
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    @property
    def kis_base_url(self) -> str:
        return _BASE_URLS[self.kis_env]

    # KisTrConfig 프로토콜 충족용 속성.
    @property
    def domestic_daily_path(self) -> str:
        return DOMESTIC_DAILY_PATH

    @property
    def domestic_daily_tr_id(self) -> str:
        return DOMESTIC_DAILY_TR_ID

    @property
    def overseas_daily_path(self) -> str:
        return OVERSEAS_DAILY_PATH

    @property
    def overseas_daily_tr_id(self) -> str:
        return OVERSEAS_DAILY_TR_ID


def load_settings() -> Settings:
    return Settings()
