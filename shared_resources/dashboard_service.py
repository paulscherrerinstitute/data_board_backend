import json
from jsonschema import validate, ValidationError
from typing import Any, Dict
import bson
import requests
import os
import uuid
from shared_resources.exceptions import DashboardSizeError, DashboardValidationError
from shared_resources.variables import shared_variables as shared

import logging
logger = logging.getLogger("uvicorn")

MAX_DASHBOARD_SIZE = 1024 * 1024 # 1MB

DEFAULT_SCHEMA_BASE_URL = "https://raw.githubusercontent.com/paulscherrerinstitute/data_board_frontend/main/schema/"
SCHEMA_PATH = os.getenv("SCHEMA_PATH", DEFAULT_SCHEMA_BASE_URL)

def fetch_schema(schema_name: str) -> Dict:
    base = SCHEMA_PATH.rstrip("/")
    try:
        if base.startswith("http"):
            url = f"{base}/{schema_name}"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            return response.json()
        else:
            # Assume local file path
            path = os.path.join(base, schema_name)
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load schema {schema_name} from {base}: {e}")
        raise

dashboard_schema = fetch_schema("dashboarddto.schema.json")

def check_dashboard_schema(dashboard: Dict[str, Any]) -> None:
    try:
        validate(instance=dashboard, schema=dashboard_schema)
    except ValidationError as e:
        logger.error(f"Dashboard validation for dashboard ({dashboard}) failed: {e.message}")
        raise DashboardValidationError(f"Dashboard validation failed.")

def check_dashboard_size(dashboard: Dict[str, Any]) -> None:
    dashboard_bson = bson.encode(dashboard)
    dashboard_bson_length = len(dashboard_bson)
    if dashboard_bson_length > MAX_DASHBOARD_SIZE:
        logger.error(f"Dashboard size ({dashboard_bson_length}) exceeds the maximum allowed size of {MAX_DASHBOARD_SIZE} bytes.")
        raise DashboardSizeError(f"Dashboard size ({dashboard_bson_length}) exceeds the maximum allowed size of {MAX_DASHBOARD_SIZE} bytes.")

def validate_dashboard(dashboard: Dict[str, Any]) -> None:
    check_dashboard_schema(dashboard)
    check_dashboard_size(dashboard)

def create_dashboard(dashboard: Dict[str, Any]) -> Dict[str, Any]:
    validate_dashboard(dashboard)

    doc = {"_id": str(uuid.uuid4()), "dashboard": dashboard}
    dashboard_id = shared.mongo_db["dashboards"].insert_one(doc).inserted_id
    return {"id": str(dashboard_id), **dashboard}

def get_dashboard(dashboard_id: str) -> Dict[str, Any]:
    doc = shared.mongo_db["dashboards"].find_one({"_id": dashboard_id})
    if doc is None or "dashboard" not in doc:
        return None
    dashboard = doc["dashboard"]
    return {"id": dashboard_id, **dashboard}

def update_dashboard(dashboard_id: str, dashboard: Dict[str, Any]) -> Dict[str, Any]:
    validate_dashboard(dashboard)
    
    updated_doc = shared.mongo_db["dashboards"].find_one_and_update(
        {"_id": dashboard_id},
        {"$set": {"dashboard": dashboard}},
        return_document=True
    )
    if updated_doc is None or "dashboard" not in updated_doc:
        return None
    updated_dashboard = updated_doc["dashboard"] 
    return {"id": dashboard_id, **updated_dashboard}

def delete_dashboard(dashboard_id: str) -> Dict[str, Any]:
    doc = shared.mongo_db["dashboards"].find_one_and_delete({"_id": dashboard_id})
    if doc is None or "dashboard" not in doc:
        return None
    dashboard = doc["dashboard"]
    return {"id": dashboard_id, **dashboard}
