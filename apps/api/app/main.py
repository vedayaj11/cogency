from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.logging import configure_logging, get_logger
from app.routes import health, salesforce

log = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level)
    log.info("api.startup", env=settings.env)
    yield
    log.info("api.shutdown")


app = FastAPI(
    title="Cogency API",
    version="0.0.1",
    description="Agentic case management on Salesforce.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, tags=["health"])
app.include_router(salesforce.router, prefix="/v1/integrations/salesforce", tags=["salesforce"])
