# backend/main.py
import asyncio
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager

from config import settings
from db import init_db
from cache import init_cache, close_cache
from routers import search, content, history
from auth.router import router as auth_router
from proxy.hls import router as proxy_router
from proxy.hls import close_session as close_proxy_session
from workers.db_writer import init_writer, stop_writer
from models.availability import ContentAvailability 
from availability.scheduler import _startup 

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await init_cache()
    init_writer(settings.DATABASE_URL)
    asyncio.create_task(_startup())
    yield
    await close_cache()
    await close_proxy_session()
    stop_writer()

app = FastAPI(
    title="nud",
    version="0.1.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# routers
app.include_router(auth_router,      prefix="/auth",    tags=["auth"])
app.include_router(search.router,    prefix="/search",  tags=["search"])
app.include_router(content.router,   prefix="/content", tags=["content"])
app.include_router(history.router,   prefix="/history", tags=["history"])
app.include_router(proxy_router,     prefix="/proxy",   tags=["proxy"])


@app.get("/health")
async def health():
    return {"status": "ok"}


# Serve frontend — must be last so it doesn't shadow API routes
frontend_dist = os.path.join(os.path.dirname(__file__), "../frontend/dist")
if os.path.exists(frontend_dist):
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")