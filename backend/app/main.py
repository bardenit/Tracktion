from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.config import settings
from app.database import engine, Base, run_migrations
from app.routes import auth, vehicles, fuel, maintenance, expenses, documents, parts, trips, ocr, inspection, tires
from app.routes import settings as settings_router

# Create tables and run migrations on startup
Base.metadata.create_all(bind=engine)
run_migrations()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("Vehicle Tracker API Starting...")
    yield
    # Shutdown
    print("Vehicle Tracker API Shutting Down...")


app = FastAPI(
    title="Vehicle Maintenance Tracker API",
    description="Self-hosted vehicle maintenance tracking",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
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


@app.get("/")
async def root():
    return {
        "message": "Vehicle Maintenance Tracker API",
        "version": "1.0.0",
        "docs": "/docs",
    }


@app.get("/health")
async def health():
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
