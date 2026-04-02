"""
Government Citizen Services API server.

Run:
    uvicorn api.server:app --reload --port 8001
"""

from fastapi import FastAPI
from api.auth import router as auth_router
from api.handoff import router as handoff_router
from api.models import init_db

app = FastAPI(
    title="Government Citizen Services API",
    version="0.1.0",
    description="Mock government backend — authentication, application status, appointments.",
)

app.include_router(auth_router)
app.include_router(handoff_router)


@app.on_event("startup")
def on_startup():
    init_db()


@app.get("/health")
def health():
    return {"status": "ok"}
