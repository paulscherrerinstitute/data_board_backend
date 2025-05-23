from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, ORJSONResponse

from shared_resources import dashboard_service
from shared_resources.decorators import timeout
from shared_resources.exceptions import (
    DashboardProtectedError,
    DashboardSizeError,
    DashboardValidationError,
)

router = APIRouter(tags=["dashboards"])
maintenance_router = APIRouter(tags=["dashboards", "maintenance"])


@maintenance_router.get("/{id}", description="Returns the full mongodb entry as JSON")
def get_full_record_route(request: Request, id: str):
    result = dashboard_service.get_record(request.app.state.shared, id)
    if result is None:
        raise HTTPException(status_code=404, detail="Dashboard not found")
    return ORJSONResponse(content=result, status_code=200)


@maintenance_router.post("/{id}/whitelist", description="Disables auto-deletion when storage is low")
def whitelist_dashboard_route(request: Request, id: str):
    if not dashboard_service.whitelist_dashboard(request.app.state.shared, id, True):
        raise HTTPException(status_code=404, detail="Dashboard not found")
    return {"message": f"Dashboard {id} whitelisted"}


@maintenance_router.delete("/{id}/whitelist", description="Enables auto-deletion when storage is low")
def unwhitelist_dashboard_route(request: Request, id: str):
    if not dashboard_service.whitelist_dashboard(request.app.state.shared, id, False):
        raise HTTPException(status_code=404, detail="Dashboard not found")
    return {"message": f"Dashboard {id} unwhitelisted"}


@maintenance_router.post("/{id}/protect", description="Makes dashboard read-only and whitelists it")
def protect_dashboard_route(request: Request, id: str):
    if not dashboard_service.protect_dashboard(request.app.state.shared, id, True):
        raise HTTPException(status_code=404, detail="Dashboard not found")
    dashboard_service.whitelist_dashboard(request.app.state.shared, id, True)
    return {"message": f"Dashboard {id} protected and whitelisted"}


@maintenance_router.delete("/{id}/protect", description="Makes dashboard writable again, doesn't change whitelisting")
def unprotect_dashboard_route(request: Request, id: str):
    if not dashboard_service.protect_dashboard(request.app.state.shared, id, False):
        raise HTTPException(status_code=404, detail="Dashboard not found")
    return {"message": f"Dashboard {id} unprotected, may still be whitelisted"}


@router.post("/")
@timeout(5)
def create_dashboard_route(request: Request, dashboard: Dict[str, Any]):
    try:
        result = dashboard_service.create_dashboard(request.app.state.shared, dashboard)
        return JSONResponse(content=result, status_code=201)
    except DashboardSizeError as e:
        raise HTTPException(status_code=413, detail=e.message) from e
    except DashboardValidationError as e:
        raise HTTPException(status_code=422, detail=e.message) from e


@router.get("/{id}")
@timeout(5)
def get_dashboard_route(request: Request, id: str):
    result = dashboard_service.get_dashboard(request.app.state.shared, id)
    if result is None:
        raise HTTPException(status_code=404, detail="Dashboard not found")
    return JSONResponse(content=result, status_code=200)


@router.patch("/{id}")
@timeout(5)
def update_dashboard_route(request: Request, id: str, dashboard: Dict[str, Any]):
    try:
        result = dashboard_service.update_dashboard(request.app.state.shared, id, dashboard)
        if result is None:
            raise HTTPException(status_code=404, detail="Dashboard not found") from None
        return JSONResponse(content=result, status_code=200)
    except DashboardSizeError as e:
        raise HTTPException(status_code=413, detail=e.message) from e
    except DashboardProtectedError as e:
        raise HTTPException(status_code=403, detail=e.message) from e


@router.delete("/{id}")
@timeout(5)
def delete_dashboard_route(request: Request, id: str):
    try:
        result = dashboard_service.delete_dashboard(request.app.state.shared, id)
        if result is None:
            raise HTTPException(status_code=404, detail="Dashboard not found")
        return JSONResponse(content=result, status_code=200)
    except DashboardProtectedError as e:
        raise HTTPException(status_code=403, detail=e.message) from e
