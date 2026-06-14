"""FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.config import get_settings
from app.database import init_db
from app.scheduler import configure_scheduler, start_scheduler, shutdown_scheduler
from app.utils.logging import logger

# Import models so metadata is populated
import app.models  # noqa: F401


@asynccontextmanager
async def lifespan(application: FastAPI):
    """Startup and shutdown lifecycle events."""
    settings = get_settings()
    logger.info("Starting CurioSync Daily Publisher")

    # Initialize database tables
    await init_db()
    logger.info("Database initialized")

    # Configure and start scheduler
    configure_scheduler(
        hour=settings.schedule_hour,
        minute=settings.schedule_minute,
    )
    start_scheduler()

    yield

    # Shutdown
    shutdown_scheduler()
    logger.info("Application shut down")


def create_app() -> FastAPI:
    """Application factory."""
    settings = get_settings()

    application = FastAPI(
        title="CurioSync",
        description="Automatically publish daily curated tech news summaries to LinkedIn",
        version="1.0.0",
        lifespan=lifespan,
    )

    # Session middleware for OAuth state and user sessions
    application.add_middleware(
        SessionMiddleware,
        secret_key=settings.secret_key,
        max_age=86400 * 30,  # 30 days
    )

    # Static files
    application.mount("/static", StaticFiles(directory="app/static"), name="static")

    # Register routes
    from app.routes.auth import router as auth_router
    from app.routes.news import router as news_router
    from app.routes.draft import router as draft_router
    from app.routes.linkedin import router as linkedin_router
    from app.routes.scheduler import router as scheduler_router
    from app.routes.history import router as history_router
    from app.routes.pages import router as pages_router

    application.include_router(auth_router)
    application.include_router(news_router)
    application.include_router(draft_router)
    application.include_router(linkedin_router)
    application.include_router(scheduler_router)
    application.include_router(history_router)
    application.include_router(pages_router)

    return application


app = create_app()
