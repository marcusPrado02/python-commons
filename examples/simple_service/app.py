"""
examples/simple_service/app.py
================================
Minimal FastAPI microservice that wires up the core mp-commons building blocks:

- ``InProcessCommandBus`` — CQRS command dispatch
- ``FastAPICorrelationIdMiddleware`` — injects/propagates X-Correlation-ID
- ``FastAPIHealthRouter`` — /health/live and /health/ready endpoints
- ``HealthRegistry`` + ``LambdaHealthCheck`` — readiness probe
- Structured JSON logging via ``mp_commons.observability.logging``

Run with::

    uvicorn examples.simple_service.app:app --reload

"""
from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, AsyncGenerator

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import JSONResponse

from mp_commons.application.cqrs.commands import CommandBus, CommandHandler, InProcessCommandBus
from mp_commons.adapters.fastapi.middleware import FastAPICorrelationIdMiddleware
from mp_commons.adapters.fastapi.routers import FastAPIHealthRouter
from mp_commons.observability.logging import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Domain
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CreateOrderCommand:
    customer_id: str
    item_sku: str
    quantity: int


@dataclass(frozen=True)
class OrderCreatedResult:
    order_id: str
    customer_id: str
    item_sku: str
    quantity: int


# ---------------------------------------------------------------------------
# Command handler
# ---------------------------------------------------------------------------

_order_store: dict[str, OrderCreatedResult] = {}


class CreateOrderHandler(CommandHandler[CreateOrderCommand]):
    async def handle(self, cmd: CreateOrderCommand) -> OrderCreatedResult:
        import uuid

        order_id = str(uuid.uuid4())
        result = OrderCreatedResult(
            order_id=order_id,
            customer_id=cmd.customer_id,
            item_sku=cmd.item_sku,
            quantity=cmd.quantity,
        )
        _order_store[order_id] = result
        logger.info("order_created", order_id=order_id, customer_id=cmd.customer_id)
        return result


# ---------------------------------------------------------------------------
# Bootstrap helpers
# ---------------------------------------------------------------------------


def _build_command_bus() -> InProcessCommandBus:
    bus = InProcessCommandBus()
    bus.register(CreateOrderCommand, CreateOrderHandler())
    return bus


# ---------------------------------------------------------------------------
# Application state (shared across requests)
# ---------------------------------------------------------------------------


class _AppState:
    command_bus: InProcessCommandBus


_state = _AppState()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Initialize application resources on startup; clean up on shutdown."""
    _state.command_bus = _build_command_bus()
    logger.info("simple_service_started")
    yield
    logger.info("simple_service_stopped")


# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Simple Service",
    description="Minimal mp-commons wiring example",
    version="0.1.0",
    lifespan=lifespan,
)

# Middleware — correlation ID propagation
app.add_middleware(FastAPICorrelationIdMiddleware)

# Health router — /health/live and /health/ready
async def _self_check() -> bool:
    return True


app.include_router(FastAPIHealthRouter(readiness_checks=[_self_check]))


# ---------------------------------------------------------------------------
# Dependency injection helpers
# ---------------------------------------------------------------------------


def get_bus() -> CommandBus:
    return _state.command_bus


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.post("/orders", status_code=201, response_model=dict)
async def create_order(
    body: dict[str, Any],
    bus: CommandBus = Depends(get_bus),
) -> dict:
    try:
        cmd = CreateOrderCommand(
            customer_id=str(body["customer_id"]),
            item_sku=str(body["item_sku"]),
            quantity=int(body["quantity"]),
        )
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    result: OrderCreatedResult = await bus.dispatch(cmd)
    return {
        "order_id": result.order_id,
        "customer_id": result.customer_id,
        "item_sku": result.item_sku,
        "quantity": result.quantity,
    }


@app.get("/orders/{order_id}", response_model=dict)
async def get_order(order_id: str) -> dict:
    order = _order_store.get(order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return {
        "order_id": order.order_id,
        "customer_id": order.customer_id,
        "item_sku": order.item_sku,
        "quantity": order.quantity,
    }
