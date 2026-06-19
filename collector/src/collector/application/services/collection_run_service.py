"""수집 런 기록 서비스 (횡단 관심사).

핵심 use case(CollectDailyPricesUseCase)는 그대로 두고, "언제/무엇을 실행했고
결과가 어땠는지"를 런 단위로 DB에 기록하는 얇은 래퍼다. 스케줄 잡과 수동 트리거가
모두 이 서비스를 경유하므로 기록 경로가 하나로 통일된다.

흐름:
  1) RUNNING 런 1행 insert → run_id 확보
  2) use_case.execute() 실행
  3) finally에서 결과 카운트로 최종 상태 update (예외 시에도 반드시 종료 기록)
"""
from __future__ import annotations

import logging

from collector.application.ports import CollectionRunRepositoryPort
from collector.application.use_cases import (
    CollectDailyPricesCommand,
    CollectDailyPricesResult,
    CollectDailyPricesUseCase,
)
from collector.domain import JobType, Market, RunStatus

logger = logging.getLogger(__name__)

# 실패 사유 요약에 담을 최대 항목 수(전체 실패 목록이 길어도 요약만 저장).
_MAX_ERROR_ITEMS = 20


def _resolve_status(result: CollectDailyPricesResult) -> RunStatus:
    """집계 결과로 최종 상태 판정."""
    if result.failed == 0:
        return RunStatus.SUCCEEDED
    if result.succeeded == 0:
        return RunStatus.FAILED
    return RunStatus.PARTIAL


def _summarize_failures(result: CollectDailyPricesResult) -> str | None:
    if not result.failures:
        return None
    items = result.failures[:_MAX_ERROR_ITEMS]
    summary = "; ".join(f"{ticker}: {reason}" for ticker, reason in items)
    extra = len(result.failures) - len(items)
    if extra > 0:
        summary += f" (그 외 {extra}건)"
    return summary


class CollectionRunService:
    def __init__(
        self,
        use_case: CollectDailyPricesUseCase,
        run_repo: CollectionRunRepositoryPort,
    ) -> None:
        self._use_case = use_case
        self._run_repo = run_repo

    async def execute_recorded(
        self, job_type: JobType, command: CollectDailyPricesCommand
    ) -> CollectDailyPricesResult:
        """수집을 실행하고 런 1행으로 기록한다(결과만 반환).

        스케줄 핸들러용. 실행 중 예외가 나면 FAILED 로 기록 후 재전파한다.
        """
        _, result = await self.execute_recorded_with_id(job_type, command)
        return result

    async def execute_recorded_with_id(
        self, job_type: JobType, command: CollectDailyPricesCommand
    ) -> tuple[int, CollectDailyPricesResult]:
        """execute_recorded 와 동일하되 발급된 run_id 도 함께 반환한다.

        수동 트리거 API 가 응답에 run_id 를 싣기 위해 사용한다.

        Args:
            job_type: 트리거 종류(DOMESTIC/OVERSEAS/MANUAL).
            command: 수집 명령(시장 필터 등).
        Returns:
            (run_id, 실행 결과). 실행 중 예외가 나면 FAILED 로 기록 후 재전파한다.
        """
        markets: list[Market] | None = command.markets
        run_id = await self._run_repo.start(job_type, markets)

        result = CollectDailyPricesResult()
        status = RunStatus.FAILED
        error_summary: str | None = None
        try:
            result = await self._use_case.execute(command)
            status = _resolve_status(result)
            error_summary = _summarize_failures(result)
            return run_id, result
        except Exception as exc:  # noqa: BLE001 - 기록 후 재전파(거래 안전: 실패도 감사)
            status = RunStatus.FAILED
            error_summary = repr(exc)
            logger.exception("수집 런 실행 중 예외 (run_id=%s)", run_id)
            raise
        finally:
            await self._run_repo.finish(
                run_id,
                status,
                total_stocks=result.total_stocks,
                succeeded=result.succeeded,
                failed=result.failed,
                rows_written=result.rows_written,
                error_summary=error_summary,
            )
