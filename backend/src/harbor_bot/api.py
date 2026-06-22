import asyncio
from contextlib import suppress
from datetime import UTC
from datetime import date as Date
from datetime import datetime as DateTime
from decimal import Decimal
from pathlib import Path
from typing import Annotated, Any

from fastapi import (
    BackgroundTasks,
    Depends,
    FastAPI,
    HTTPException,
    Query,
    WebSocket,
    WebSocketDisconnect,
)
from sqlalchemy import text
from starlette.requests import HTTPConnection

from harbor_bot.backtester.service import BacktestService
from harbor_bot.config.defaults import load_default_config
from harbor_bot.config.models import ConfigUpdateRequest
from harbor_bot.config.service import ConfigService
from harbor_bot.feed.live import ingest_pricing_stream
from harbor_bot.feed.source_service import CandleSourceService
from harbor_bot.instruments import default_instrument_rules
from harbor_bot.lab.service import LabService
from harbor_bot.oanda.client import OandaApiError, OandaClient
from harbor_bot.oanda.stream import parse_pricing_stream_lines, reconnecting_frames
from harbor_bot.observability.service import ObservabilityService
from harbor_bot.observability.websocket import WebSocketHub
from harbor_bot.optimizer.service import OptimizerService
from harbor_bot.paper_engine.config import load_paper_engine_config
from harbor_bot.paper_engine.models import PaperEngineConfig
from harbor_bot.paper_engine.service import PaperForwardService
from harbor_bot.persistence import (
    backtest_repository,
    config_repository,
    execution_repository,
    variant_repository,
)
from harbor_bot.persistence.database import create_engine
from harbor_bot.settings import Settings, redact_secret_text
from harbor_bot.strategy.models import InstrumentRules, strategy_config_from_defaults

FromQuery = Annotated[DateTime, Query(alias="from")]
ToQuery = Annotated[DateTime, Query(alias="to")]
OptionalFromQuery = Annotated[DateTime | None, Query(alias="from")]
OptionalToQuery = Annotated[DateTime | None, Query(alias="to")]
OptionalEventTypeQuery = Annotated[str | None, Query(alias="type")]


def get_backtest_service(connection: HTTPConnection) -> BacktestService:
    return connection.app.state.backtest_service


def get_observability_service(connection: HTTPConnection) -> ObservabilityService:
    return connection.app.state.observability_service


def get_optimizer_service(connection: HTTPConnection) -> OptimizerService:
    return connection.app.state.optimizer_service


def get_lab_service(connection: HTTPConnection) -> LabService:
    return connection.app.state.lab_service


def get_paper_forward_service(connection: HTTPConnection) -> PaperForwardService:
    return connection.app.state.paper_forward_service


def get_product_query_service(connection: HTTPConnection) -> Any:
    return connection.app.state.product_query_service


def get_candle_source_service(connection: HTTPConnection) -> CandleSourceService:
    return connection.app.state.candle_source_service


def get_config_service(connection: HTTPConnection) -> ConfigService:
    return connection.app.state.config_service


def get_control_service(connection: HTTPConnection) -> Any:
    service = connection.app.state.control_service
    if service is None:
        raise HTTPException(status_code=503, detail="practice controls are not configured")
    return service


def get_websocket_hub(connection: HTTPConnection) -> WebSocketHub:
    return connection.app.state.websocket_hub


def get_readiness_checker(connection: HTTPConnection) -> Any:
    return connection.app.state.readiness_checker


BACKTEST_SERVICE_DEPENDENCY = Depends(get_backtest_service)
OBSERVABILITY_SERVICE_DEPENDENCY = Depends(get_observability_service)
OPTIMIZER_SERVICE_DEPENDENCY = Depends(get_optimizer_service)
LAB_SERVICE_DEPENDENCY = Depends(get_lab_service)
PAPER_FORWARD_SERVICE_DEPENDENCY = Depends(get_paper_forward_service)
PRODUCT_QUERY_SERVICE_DEPENDENCY = Depends(get_product_query_service)
CANDLE_SOURCE_SERVICE_DEPENDENCY = Depends(get_candle_source_service)
CONFIG_SERVICE_DEPENDENCY = Depends(get_config_service)
CONTROL_SERVICE_DEPENDENCY = Depends(get_control_service)
WEBSOCKET_HUB_DEPENDENCY = Depends(get_websocket_hub)
READINESS_CHECKER_DEPENDENCY = Depends(get_readiness_checker)


def _packaged_fixture_base_path() -> Path:
    return Path(__file__).resolve().parent / "backtester" / "fixtures"


def create_app(
    backtest_service: BacktestService | None = None,
    observability_service: ObservabilityService | None = None,
    optimizer_service: OptimizerService | None = None,
    lab_service: LabService | None = None,
    paper_forward_service: PaperForwardService | None = None,
    product_query_service: Any | None = None,
    candle_source_service: CandleSourceService | None = None,
    config_service: ConfigService | None = None,
    control_service: Any | None = None,
    websocket_hub: WebSocketHub | None = None,
    readiness_checker: Any | None = None,
    settings: Settings | None = None,
) -> FastAPI:
    app = FastAPI(title="Harbor", version="0.1.0")
    app.state.backtest_service = backtest_service or BacktestService(
        fixture_base_path=_packaged_fixture_base_path()
    )
    app.state.settings = settings or Settings()
    app.state.settings.validate_startup()
    app.state.websocket_hub = websocket_hub or WebSocketHub()
    app.state.control_service = control_service
    app.state.live_pricing_stream_state = {"state": "disabled", "running": False}
    app.state.live_pricing_stream_task = None
    persistence_engine = None
    if (
        observability_service is None
        or optimizer_service is None
        or lab_service is None
        or paper_forward_service is None
        or product_query_service is None
        or candle_source_service is None
        or config_service is None
        or readiness_checker is None
    ):
        persistence_engine = create_engine(app.state.settings)
        app.state.persistence_engine = persistence_engine
    if observability_service is None:
        observability_service = ObservabilityService(
            engine=persistence_engine,
            settings=app.state.settings,
            execution_status_provider=control_service,
        )
    app.state.observability_service = observability_service
    if optimizer_service is None:
        optimizer_service = OptimizerService(
            persistence_engine=persistence_engine,
            fixture_base_path=_packaged_fixture_base_path(),
        )
    app.state.optimizer_service = optimizer_service
    paper_config = load_paper_engine_config()
    if lab_service is None:
        lab_service = LabService(engine=persistence_engine, paper_config=paper_config)
    app.state.lab_service = lab_service
    if product_query_service is None:
        product_query_service = ProductQueryService(
            engine=persistence_engine,
            paper_config=paper_config,
        )
    app.state.product_query_service = product_query_service
    if candle_source_service is None:
        candle_source_service = CandleSourceService(
            engine=persistence_engine,
            settings=app.state.settings,
            live_stream_status_provider=lambda: _live_pricing_stream_status(app),
        )
    app.state.candle_source_service = candle_source_service
    if config_service is None:
        config_service = ConfigService(
            engine=persistence_engine,
            defaults=load_default_config(),
        )
    app.state.config_service = config_service
    if paper_forward_service is None:
        strategy_config = strategy_config_from_defaults(load_default_config())
        paper_forward_service = PaperForwardService(
            engine=persistence_engine,
            base_strategy_config=strategy_config,
            instrument_rules=_default_instrument_rules(strategy_config.instrument),
            paper_config=paper_config,
            websocket_hub=app.state.websocket_hub,
        )
    app.state.paper_forward_service = paper_forward_service
    if readiness_checker is None:
        readiness_checker = ReadinessChecker(
            engine=persistence_engine,
            settings=app.state.settings,
        )
    app.state.readiness_checker = readiness_checker

    @app.on_event("startup")
    async def start_runtime_workers() -> None:
        if not _should_start_live_pricing_stream(app):
            return
        now = DateTime.now(tz=UTC)
        app.state.live_pricing_stream_state = {
            "state": "starting",
            "running": False,
            "last_started_at": now,
        }
        task = asyncio.create_task(_run_live_pricing_stream(app))
        app.state.live_pricing_stream_task = task
        app.state.live_pricing_stream_state = {
            "state": "running",
            "running": True,
            "last_started_at": now,
        }
        task.add_done_callback(lambda done: _record_live_pricing_stream_done(app, done))

    @app.on_event("shutdown")
    async def stop_runtime_workers() -> None:
        task = app.state.live_pricing_stream_task
        if task is None:
            return
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task
        app.state.live_pricing_stream_state = {
            **dict(app.state.live_pricing_stream_state),
            "state": "stopped",
            "running": False,
            "last_stopped_at": DateTime.now(tz=UTC),
        }

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/ready")
    async def ready(
        checker: Any = READINESS_CHECKER_DEPENDENCY,
    ) -> dict[str, Any]:
        result = await checker.check()
        if result.get("status") != "ready":
            raise HTTPException(status_code=503, detail=_jsonable(result))
        return _jsonable(result)

    @app.get("/api/status")
    async def read_status(
        service: ObservabilityService = OBSERVABILITY_SERVICE_DEPENDENCY,
    ) -> dict[str, Any]:
        return _jsonable(await service.get_status())

    @app.get("/api/levels")
    async def read_levels(
        date: Date,
        instrument: str,
        service: ObservabilityService = OBSERVABILITY_SERVICE_DEPENDENCY,
    ) -> dict[str, Any] | None:
        levels = await service.get_levels(date=date, instrument=instrument)
        if levels is None:
            return None
        return _jsonable(levels)

    @app.get("/api/candles")
    async def read_candles(
        instrument: str,
        start: FromQuery,
        end: ToQuery,
        service: ObservabilityService = OBSERVABILITY_SERVICE_DEPENDENCY,
    ) -> list[dict[str, Any]]:
        return _jsonable(await service.get_candles(instrument=instrument, start=start, end=end))

    @app.get("/api/candles/source")
    async def read_candle_source(
        instrument: str | None = None,
        service: CandleSourceService = CANDLE_SOURCE_SERVICE_DEPENDENCY,
    ) -> dict[str, Any]:
        return _jsonable(await service.get_status(instrument=instrument))

    @app.post("/api/candles/import")
    async def import_candles(
        payload: dict[str, Any],
        service: CandleSourceService = CANDLE_SOURCE_SERVICE_DEPENDENCY,
    ) -> dict[str, Any]:
        try:
            return _jsonable(await service.import_historical(payload))
        except OandaApiError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/markers")
    async def read_markers(
        date: Date,
        instrument: str,
        service: ObservabilityService = OBSERVABILITY_SERVICE_DEPENDENCY,
    ) -> dict[str, Any]:
        return _jsonable(await service.get_markers(date=date, instrument=instrument))

    @app.get("/api/events")
    async def read_events(
        level: str | None = None,
        module: str | None = None,
        event_type: OptionalEventTypeQuery = None,
        start: OptionalFromQuery = None,
        end: OptionalToQuery = None,
        limit: int = 100,
        service: ObservabilityService = OBSERVABILITY_SERVICE_DEPENDENCY,
    ) -> list[dict[str, Any]]:
        request: dict[str, Any] = {"level": level, "limit": limit}
        if any(value is not None for value in (module, event_type, start, end)):
            request.update(
                {
                    "module": module,
                    "event_type": event_type,
                    "start": start,
                    "end": end,
                }
            )
        return _jsonable(await service.get_events(**request))

    @app.get("/api/trades")
    async def read_trade_journal(
        start: OptionalFromQuery = None,
        end: OptionalToQuery = None,
        limit: int = 200,
        service: Any = PRODUCT_QUERY_SERVICE_DEPENDENCY,
    ) -> dict[str, Any]:
        return _jsonable(await service.list_trades(start=start, end=end, limit=limit))

    @app.websocket("/ws")
    async def websocket_endpoint(
        websocket: WebSocket,
        service: ObservabilityService = OBSERVABILITY_SERVICE_DEPENDENCY,
        hub: WebSocketHub = WEBSOCKET_HUB_DEPENDENCY,
    ) -> None:
        await hub.connect(websocket)
        try:
            status = await service.get_status()
            await hub.send(websocket, hub.envelope("status", status))
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            pass
        finally:
            hub.disconnect(websocket)

    @app.post("/api/backtests")
    async def start_backtest(
        payload: dict[str, Any],
        service: BacktestService = BACKTEST_SERVICE_DEPENDENCY,
    ) -> dict[str, Any]:
        try:
            return await service.start_backtest(payload)
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/backtests")
    async def list_backtests(
        limit: int = 100,
        service: Any = PRODUCT_QUERY_SERVICE_DEPENDENCY,
    ) -> dict[str, Any]:
        return _jsonable(await service.list_backtest_runs(limit=limit))

    @app.post("/api/optimize")
    async def start_optimization(
        payload: dict[str, Any],
        background_tasks: BackgroundTasks,
        service: OptimizerService = OPTIMIZER_SERVICE_DEPENDENCY,
    ) -> dict[str, Any]:
        try:
            return await service.start_optimization(payload, background_tasks=background_tasks)
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/optimize/preflight")
    async def preflight_optimization(
        payload: dict[str, Any],
        service: OptimizerService = OPTIMIZER_SERVICE_DEPENDENCY,
    ) -> dict[str, Any]:
        try:
            return _jsonable(await service.preflight_optimization(payload))
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/optimize")
    async def list_optimization_studies(
        limit: int = 100,
        service: Any = PRODUCT_QUERY_SERVICE_DEPENDENCY,
    ) -> dict[str, Any]:
        return _jsonable(await service.list_optimizer_studies(limit=limit))

    @app.get("/api/optimize/{study_id}")
    async def read_optimization_study(
        study_id: int,
        service: LabService = LAB_SERVICE_DEPENDENCY,
    ) -> dict[str, Any]:
        snapshot = await service.get_lab_snapshot(study_id=study_id)
        if snapshot is None:
            raise HTTPException(status_code=404, detail="optimization study not found")
        return _jsonable(snapshot)

    @app.get("/api/variants")
    async def read_variants(
        service: LabService = LAB_SERVICE_DEPENDENCY,
    ) -> dict[str, Any]:
        return _jsonable(await service.get_variant_overview())

    @app.get("/api/variants/{variant_id}")
    async def read_variant_detail(
        variant_id: int,
        service: Any = PRODUCT_QUERY_SERVICE_DEPENDENCY,
    ) -> dict[str, Any]:
        detail = await service.get_variant_detail(variant_id=variant_id)
        if detail is None:
            raise HTTPException(status_code=404, detail="variant not found")
        return _jsonable(detail)

    @app.get("/api/config")
    async def read_config_values(
        service: ConfigService = CONFIG_SERVICE_DEPENDENCY,
    ) -> dict[str, Any]:
        return _jsonable(await service.get_snapshot())

    @app.put("/api/config")
    async def update_config_values(
        payload: dict[str, Any],
        service: ConfigService = CONFIG_SERVICE_DEPENDENCY,
    ) -> dict[str, Any]:
        try:
            request = ConfigUpdateRequest(
                updates=payload["updates"],
                confirmation=str(payload["confirmation"]),
            )
            return _jsonable(await service.update_config(request))
        except KeyError as exc:
            raise HTTPException(
                status_code=400,
                detail="updates and confirmation are required",
            ) from exc
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/variants")
    async def create_paper_variant(
        payload: dict[str, Any],
        service: LabService = LAB_SERVICE_DEPENDENCY,
    ) -> dict[str, Any]:
        try:
            trial_id = int(payload["trial_id"])
            label = payload.get("label")
            if label is not None:
                label = str(label)
            return _jsonable(await service.create_paper_variant(trial_id=trial_id, label=label))
        except KeyError as exc:
            raise HTTPException(status_code=400, detail="trial_id is required") from exc
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/variants/{variant_id}/retire")
    async def retire_paper_variant(
        variant_id: int,
        service: LabService = LAB_SERVICE_DEPENDENCY,
    ) -> dict[str, Any]:
        result = await service.retire_paper_variant(variant_id=variant_id)
        if result.status == "not_found":
            raise HTTPException(status_code=404, detail="paper variant not found")
        return _jsonable(result)

    @app.post("/api/variants/{variant_id}/promote")
    async def promote_variant_for_practice(
        variant_id: int,
        service: LabService = LAB_SERVICE_DEPENDENCY,
    ) -> dict[str, Any]:
        try:
            result = await service.promote_variant_for_practice(
                variant_id=variant_id,
                trading_enabled=False,
                open_broker_trade_count=0,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if result.status == "not_found":
            raise HTTPException(status_code=404, detail="paper variant not found")
        return _jsonable(result)

    @app.post("/api/control/trading")
    async def set_trading_enabled(
        payload: dict[str, Any],
        service: Any = CONTROL_SERVICE_DEPENDENCY,
    ) -> dict[str, Any]:
        try:
            enabled = bool(payload["enabled"])
            confirmation_token = str(payload["confirmation_token"])
            return _jsonable(
                await service.set_trading_enabled(
                    enabled=enabled,
                    confirmation_token=confirmation_token,
                )
            )
        except KeyError as exc:
            raise HTTPException(
                status_code=400,
                detail="enabled and confirmation_token are required",
            ) from exc
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/control/flatten")
    async def flatten_now(
        payload: dict[str, Any],
        service: Any = CONTROL_SERVICE_DEPENDENCY,
    ) -> dict[str, Any]:
        try:
            confirmation_token = str(payload["confirmation_token"])
            reason = str(payload.get("reason", "manual"))
            return _jsonable(
                await service.flatten_now(
                    reason=reason,
                    confirmation_token=confirmation_token,
                )
            )
        except KeyError as exc:
            raise HTTPException(status_code=400, detail="confirmation_token is required") from exc
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/backtests/{run_id}")
    async def read_backtest(
        run_id: int,
        service: BacktestService = BACKTEST_SERVICE_DEPENDENCY,
    ) -> dict[str, Any]:
        result = await service.get_backtest(run_id)
        if result is None:
            raise HTTPException(status_code=404, detail="backtest not found")
        return result

    return app


def _default_instrument_rules(instrument: str) -> InstrumentRules:
    return default_instrument_rules(instrument)


def _should_start_live_pricing_stream(app: FastAPI) -> bool:
    settings = app.state.settings
    return bool(
        settings.oanda_pricing_stream_enabled
        and settings.oanda_api_token
        and settings.oanda_account_id
        and getattr(app.state, "persistence_engine", None) is not None
        and getattr(app.state, "paper_forward_service", None) is not None
    )


async def _run_live_pricing_stream(app: FastAPI) -> None:
    settings = app.state.settings
    instruments = settings.research_instruments

    async def on_closed_candle(candle: Any) -> None:
        await app.state.paper_forward_service.run_closed_candles((candle,))

    async with OandaClient.from_settings(settings) as client:
        frames = reconnecting_frames(
            lambda: parse_pricing_stream_lines(client.stream_pricing_lines(instruments)),
            initial_delay_seconds=settings.oanda_reconnect_initial_seconds,
            max_delay_seconds=settings.oanda_reconnect_max_seconds,
            sleep=asyncio.sleep,
        )
        await ingest_pricing_stream(
            engine=app.state.persistence_engine,
            frames=frames,
            instruments=instruments,
            heartbeat_timeout_seconds=settings.oanda_stream_heartbeat_timeout_seconds,
            on_closed_candle=on_closed_candle,
        )


def _live_pricing_stream_status(app: FastAPI) -> dict[str, Any]:
    state = dict(getattr(app.state, "live_pricing_stream_state", {}))
    task = getattr(app.state, "live_pricing_stream_task", None)
    if task is not None and not task.done():
        state["running"] = True
        state["state"] = "running"
    else:
        state["running"] = False
    return state


def _record_live_pricing_stream_done(app: FastAPI, task: asyncio.Task[Any]) -> None:
    state = dict(getattr(app.state, "live_pricing_stream_state", {}))
    state["running"] = False
    state["last_stopped_at"] = DateTime.now(tz=UTC)
    if task.cancelled():
        state["state"] = "stopped"
    else:
        error = task.exception()
        if error is None:
            state["state"] = "stopped"
        else:
            state["state"] = "failed"
            state["last_error"] = redact_secret_text(error)
    app.state.live_pricing_stream_state = state


class ReadinessChecker:
    def __init__(self, *, engine: Any, settings: Settings) -> None:
        self._engine = engine
        self._settings = settings

    async def check(self) -> dict[str, Any]:
        checks: dict[str, Any] = {}
        status = "ready"

        try:
            checks["config"] = self._settings.validate_startup()
        except Exception as exc:  # pragma: no cover - defensive runtime path
            status = "not_ready"
            checks["config"] = {"error": redact_secret_text(exc)}

        try:
            async with self._engine.connect() as connection:
                await connection.execute(text("select 1"))
            checks["database"] = "ok"
        except Exception as exc:  # pragma: no cover - defensive runtime path
            status = "not_ready"
            checks["database"] = {"error": redact_secret_text(exc)}

        return {"status": status, "checks": checks}


class ProductQueryService:
    def __init__(self, *, engine: Any, paper_config: PaperEngineConfig) -> None:
        self._engine = engine
        self._paper_config = paper_config

    async def list_trades(
        self,
        *,
        start: DateTime | None,
        end: DateTime | None,
        limit: int,
    ) -> dict[str, Any]:
        async with self._engine.connect() as connection:
            trades = await execution_repository.list_trade_journal(
                connection,
                start=start,
                end=end,
                limit=limit,
            )
        return {"trades": trades}

    async def list_backtest_runs(self, *, limit: int) -> dict[str, Any]:
        async with self._engine.connect() as connection:
            runs = await backtest_repository.list_backtest_runs(connection, limit=limit)
        return {"runs": runs}

    async def list_optimizer_studies(self, *, limit: int) -> dict[str, Any]:
        async with self._engine.connect() as connection:
            studies = await variant_repository.list_study_summaries(connection, limit=limit)
        return {"studies": studies}

    async def get_variant_detail(self, *, variant_id: int) -> dict[str, Any] | None:
        async with self._engine.connect() as connection:
            return await variant_repository.get_variant_detail(
                connection,
                variant_id=variant_id,
                initial_nav=self._paper_config.initial_nav,
                limit=self._paper_config.max_lab_rows,
            )

    async def get_config_values(self) -> dict[str, Any]:
        async with self._engine.connect() as connection:
            values = await config_repository.list_config_values(connection)
        return {"values": values}


def _jsonable(value: Any) -> Any:
    if hasattr(value, "to_jsonable"):
        return value.to_jsonable()
    if isinstance(value, DateTime):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, tuple | list):
        return [_jsonable(item) for item in value]
    return value


app = create_app()
