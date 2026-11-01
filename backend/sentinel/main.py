from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .alerts_api import router as alerts_router
from .analytics import router as analytics_router
from .api import database_error_handler, router
from .config import get_settings
from .database import engine
from .monitor import Monitor


def create_app(*, start_monitoring=False):
    @asynccontextmanager
    async def lifespan(app):
        app.state.monitor = None
        if start_monitoring and get_settings().monitoring_enabled:
            app.state.monitor = Monitor(engine, concurrent=get_settings().check_concurrency)
            app.state.monitor.start()
        try:
            yield
        finally:
            if app.state.monitor:
                await app.state.monitor.close()

    app = FastAPI(
        title="API Sentinel",
        version="1.1.0",
        description="Local HTTP monitoring, historical statistics and alerts.",
        lifespan=lifespan,
    )
    app.state.monitor = None
    origins = get_settings().allowed_origins.split(",")
    app.add_middleware(
        TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "testserver"]
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Content-Type"],
    )

    @app.middleware("http")
    async def protect_browser_writes(request: Request, call_next):
        origin = request.headers.get("origin")
        if request.method not in {"GET", "HEAD", "OPTIONS"} and origin and origin not in origins:
            return JSONResponse(status_code=403, content={"detail": "Origin not allowed."})
        if (
            request.headers.get("content-length", "").isdigit()
            and int(request.headers["content-length"]) > 65536
        ):
            return JSONResponse(status_code=413, content={"detail": "Request too large."})
        return await call_next(request)

    app.add_exception_handler(SQLAlchemyError, database_error_handler)
    app.include_router(router)
    app.include_router(analytics_router)
    app.include_router(alerts_router)
    return app


app = create_app(start_monitoring=True)
