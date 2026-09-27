"""Static command-center shell. Operational data is owner-authenticated API state."""

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse, JSONResponse


router = APIRouter()
ASSETS = Path(__file__).resolve().parents[1] / "dashboard"


@router.get("/dashboard", include_in_schema=False)
async def dashboard():
    return FileResponse(ASSETS / "index.html", headers={"Cache-Control": "no-store"})


@router.get("/dashboard/manifest.webmanifest", include_in_schema=False)
async def dashboard_manifest():
    return JSONResponse({"name": "Jarvis AI Core", "short_name": "Jarvis",
                         "start_url": "/dashboard", "display": "standalone",
                         "background_color": "#030c17", "theme_color": "#051626",
                         "icons": [{"src": "/dashboard/icon.svg", "sizes": "any",
                                    "type": "image/svg+xml", "purpose": "any maskable"}]})


@router.get("/dashboard/icon.svg", include_in_schema=False)
async def dashboard_icon():
    return FileResponse(ASSETS / "icon.svg", media_type="image/svg+xml")
