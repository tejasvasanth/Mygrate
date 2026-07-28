"""FastAPI app entrypoint."""
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402

from app.api import (  # noqa: E402
    connections, health, jobs, migrations, monitoring, operations, public,
)
from app.config import get_settings  # noqa: E402

settings = get_settings()

app = FastAPI(
    title="DB Migration Agent",
    description="Agentic database migration — schema analysis, data profiling, "
                "AI planning, chunked execution and validation.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url, "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(connections.router)
app.include_router(migrations.router)
app.include_router(jobs.router)
app.include_router(operations.router)
app.include_router(monitoring.router)
app.include_router(public.router)
