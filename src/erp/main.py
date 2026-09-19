"""Application Entrypoint."""

import uvicorn

from erp.config import settings


def main():
    """Runs the Uvicorn ASGI server."""
    uvicorn.run(
        "erp.api.app:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower(),
    )


if __name__ == "__main__":
    main()
