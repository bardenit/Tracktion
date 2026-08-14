import logging
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from slowapi.errors import RateLimitExceeded
from slowapi import _rate_limit_exceeded_handler

from app.config import settings, validate_production_secret
from app.database import engine
from app.migrations import require_database_current
from app.limiter import limiter
from app.routes import auth, vehicles, fuel, maintenance, expenses, documents, parts, trips, ocr, inspection, tires
from app.routes import settings as settings_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    validate_production_secret(settings)
    if settings.JWT_SECRET_KEY == "change-me-in-production":
        if not settings.DEBUG:
            raise RuntimeError(
                "JWT_SECRET_KEY is set to the default value. "
                "Set a strong random secret via the JWT_SECRET_KEY environment variable."
            )
        logging.warning("JWT_SECRET_KEY is using the default value — change it before deploying.")
    if "*" in settings.CORS_ORIGINS and not settings.DEBUG:
        logging.warning(
            "CORS_ORIGINS is set to wildcard '*'. "
            "Set a specific origin via the CORS_ORIGINS environment variable."
        )
    try:
        require_database_current(engine)
        app.state.database_ready = True
        yield
    finally:
        app.state.database_ready = False


app = FastAPI(
    title="Tracktion API",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    openapi_url="/openapi.json" if settings.DEBUG else None,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


class StrippedSlashMiddleware:
    """Serve collection routes when an upstream proxy drops the trailing slash.

    Cloudflare rewrites `/api/vehicles/` to `/api/vehicles` before the request
    reaches this application. Starlette would answer with a 307 to the slashed
    path, which the edge strips again on the way back, so the redirect can never
    be satisfied and the browser gives up. Rewrite the path in place instead,
    but only when the slashed variant is a route this application actually
    serves, so unknown paths still reach the normal 404.
    """

    def __init__(self, app, routes):
        self.app = app
        self.routes = routes
        self._slashed_paths = None

    def slashed_paths(self):
        if self._slashed_paths is None:
            self._slashed_paths = {
                route.path
                for route in self.routes
                if getattr(route, "path", "").endswith("/") and route.path != "/"
            }
        return self._slashed_paths

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            path = scope.get("path", "")
            if path and not path.endswith("/") and f"{path}/" in self.slashed_paths():
                scope = dict(scope)
                scope["path"] = f"{path}/"
        await self.app(scope, receive, send)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self' 'wasm-unsafe-eval'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self' data:"
    return response


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(vehicles.router, prefix="/api/vehicles", tags=["vehicles"])
app.include_router(fuel.router, prefix="/api/fuel", tags=["fuel"])
app.include_router(maintenance.router, prefix="/api/maintenance", tags=["maintenance"])
app.include_router(expenses.router, prefix="/api/expenses", tags=["expenses"])
app.include_router(documents.router, prefix="/api/documents", tags=["documents"])
app.include_router(parts.router, prefix="/api/parts", tags=["parts"])
app.include_router(trips.router, prefix="/api/trips", tags=["trips"])
app.include_router(settings_router.router, prefix="/api/settings", tags=["settings"])
app.include_router(ocr.router, prefix="/api/ocr", tags=["ocr"])
app.include_router(inspection.router, prefix="/api/inspection", tags=["inspection"])
app.include_router(tires.router, prefix="/api/tires", tags=["tires"])

app.add_middleware(StrippedSlashMiddleware, routes=app.routes)


@app.get("/health")
async def health(request: Request, response: Response):
    try:
        require_database_current(engine)
        database_ready = bool(getattr(request.app.state, "database_ready", False))
    except Exception:
        database_ready = False
    if not database_ready:
        response.status_code = 503
        return {"status": "unhealthy", "database": "unavailable"}
    return {"status": "healthy", "database": "ready"}
