from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from temporalio.client import Client as TemporalClient

from app.config import get_settings
from app.logging import configure_logging, get_logger
from app.routes import aops, cases, evals, health, inbox, knowledge, salesforce

log = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level)
    log.info("api.startup", env=settings.env)

    try:
        app.state.temporal = await TemporalClient.connect(
            settings.temporal_host, namespace=settings.temporal_namespace
        )
        log.info("api.temporal_connected", host=settings.temporal_host)
    except Exception as e:
        log.warning("api.temporal_unavailable", error=str(e))
        app.state.temporal = None

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
app.include_router(aops.router, tags=["aops"])
app.include_router(cases.router, tags=["cases"])
app.include_router(inbox.router, tags=["inbox"])
app.include_router(knowledge.router, tags=["knowledge"])
app.include_router(evals.router, tags=["evals"])
