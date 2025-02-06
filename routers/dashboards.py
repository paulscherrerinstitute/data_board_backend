from typing import Any, Dict
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from shared_resources import dashboard_service

router = APIRouter(tags=["dashboards"])

@router.post("/")
async def create_dashboard(dashboard: Dict[str, Any]):
    result = dashboard_service.create_dashboard(dashboard)
    return JSONResponse(content=result, status_code=201)

@router.get("/{id}")
async def get_dashboard(id: str):
    result = dashboard_service.get_dashboard(id)
    if result is None:
        raise HTTPException(status_code=404, detail="Dashboard not found")
    return JSONResponse(content=result)

@router.patch("/{id}")
async def update_dashboard(id: str, dashboard: Dict[str, Any]):
    result = dashboard_service.update_dashboard(id, dashboard)
    if result is None:
        raise HTTPException(status_code=404, detail="Dashboard not found")
    return JSONResponse(content=result)

@router.delete("/{id}")
async def delete_dashboard(id: str):
    result = dashboard_service.delete_dashboard(id)
    if result is None:
        raise HTTPException(status_code=404, detail="Dashboard not found")
    return JSONResponse(content=result)