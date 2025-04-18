from typing import Any, Dict
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from shared_resources.decorators import timeout
from shared_resources import dashboard_service

router = APIRouter(tags=["dashboards"])

@router.post("/")
@timeout(5)
def create_dashboard(dashboard: Dict[str, Any]):
    result = dashboard_service.create_dashboard(dashboard)
    return JSONResponse(content=result, status_code=201)

@router.get("/{id}")
@timeout(5)
def get_dashboard(id: str):
    result = dashboard_service.get_dashboard(id)
    if result is None:
        raise HTTPException(status_code=404, detail="Dashboard not found")
    return JSONResponse(content=result, status_code=200)

@router.patch("/{id}")
@timeout(5)
def update_dashboard(id: str, dashboard: Dict[str, Any]):
    result = dashboard_service.update_dashboard(id, dashboard)
    if result is None:
        raise HTTPException(status_code=404, detail="Dashboard not found")
    return JSONResponse(content=result, status_code=200)

@router.delete("/{id}")
@timeout(5)
def delete_dashboard(id: str):
    result = dashboard_service.delete_dashboard(id)
    if result is None:
        raise HTTPException(status_code=404, detail="Dashboard not found")
    return JSONResponse(content=result, status_code=200)