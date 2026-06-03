import logging
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from slowapi.errors import RateLimitExceeded
from slowapi import _rate_limit_exceeded_handler

from app.config import settings
from app.database import engine, Base, run_migrations
from app.limiter import limiter
from app.routes import auth, vehicles, fuel, maintenance, expenses, documents, parts, trips, ocr, inspection, tires
from app.routes import settings as settings_router

Base.metadata.create_all(bind=engine)
run_migrations()


@asynccontextmanager
async def lifespan(app: FastAPI):
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
    yield


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


@app.get("/health")
async def health():
    return {"status": "healthy"}
