"""FastAPI app: dashboard API + coach chat + static frontend.

Local single-user app — binds to 127.0.0.1 only; never expose publicly.
"""

from __future__ import annotations

from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import api, chat

WEB_DIST = Path(__file__).resolve().parents[3] / "web" / "dist"


class SpaStaticFiles(StaticFiles):
    """Serve the built SPA; unknown paths fall back to index.html for client routing."""

    async def get_response(self, path: str, scope):  # type: ignore[no-untyped-def]
        try:
            response = await super().get_response(path, scope)
        except StarletteHTTPException as e:
            if e.status_code == 404:
                return FileResponse(WEB_DIST / "index.html")
            raise
        if response.status_code == 404:
            return FileResponse(WEB_DIST / "index.html")
        return response


def create_app() -> FastAPI:
    app = FastAPI(title="garmin-coach", docs_url="/api/docs", openapi_url="/api/openapi.json")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],  # vite dev
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(api.router)
    app.include_router(chat.router)
    if WEB_DIST.exists():
        app.mount("/", SpaStaticFiles(directory=WEB_DIST, html=True), name="frontend")
    return app


def main() -> None:
    uvicorn.run(create_app(), host="127.0.0.1", port=8787)


if __name__ == "__main__":
    main()
