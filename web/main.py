import secrets
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.responses import FileResponse

from core.config import Settings
from core.db import create_engine, create_session_factory
from web.routers import admin as admin_router
from web.routers import auth as auth_router
from web.routers import channels as channels_router
from web.routers import digests as digests_router
from web.routers import users as users_router

_settings: Settings = None  # type: ignore[assignment]
_session_factory = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _settings, _session_factory
    _settings = Settings()
    if not _settings.WEB_JWT_SECRET:
        _settings.WEB_JWT_SECRET = secrets.token_hex(32)

    engine = create_engine(_settings)
    _session_factory = create_session_factory(engine)

    # Override the dependency
    from web import deps

    async def _get_session():
        async with _session_factory() as session:
            yield session

    app.dependency_overrides[deps.get_session] = _get_session

    yield
    await engine.dispose()


app = FastAPI(title="Tematch Dashboard", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(admin_router.router)
app.include_router(auth_router.router)
app.include_router(channels_router.router)
app.include_router(digests_router.router)
app.include_router(users_router.router)


@app.get("/api/health")
async def health():
    return {"status": "ok"}


# --- Static file serving (must be AFTER all API routes) ---

_frontend_dir = Path(__file__).parent / "frontend" / "dist"

if _frontend_dir.exists():
    app.mount("/assets", StaticFiles(directory=_frontend_dir / "assets"), name="assets")

    @app.get("/{path:path}")
    async def serve_spa(path: str):
        file = _frontend_dir / path
        if file.exists() and file.is_file():
            return FileResponse(file)
        return FileResponse(_frontend_dir / "index.html")
