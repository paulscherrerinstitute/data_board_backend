import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import bson
import requests
from jsonschema import ValidationError, validate
from pymongo import ReturnDocument

from shared_resources.exceptions import (
    DashboardProtectedError,
    DashboardSizeError,
    DashboardValidationError,
)
from shared_resources.variables import SharedState

logger = logging.getLogger("uvicorn")

# Dashboard storage
DASHBOARD_MAX_TOTAL_STORAGE_BYTES = int(
    os.getenv("DASHBOARD_MAX_TOTAL_STORAGE_BYTES", 10 * 1024**3)
)  # default 10GB total
DASHBOARD_EVICTION_THRESHOLD = float(os.getenv("DASHBOARD_EVICTION_THRESHOLD", 0.95))  # start evicting at 95% of total
DASHBOARD_TARGET_UTILIZATION = float(os.getenv("DASHBOARD_TARGET_UTILIZATION", 0.60))  # reduce down to 60% of total

# Dashboard validation
DEFAULT_SCHEMA_BASE_URL = "https://raw.githubusercontent.com/paulscherrerinstitute/data_board_frontend/main/schema/"
SCHEMA_PATH = os.getenv("SCHEMA_PATH") or DEFAULT_SCHEMA_BASE_URL
VALIDATE_DASHBOARD_SCHEMA = os.getenv("VALIDATE_DASHBOARD_SCHEMA", "true").lower() in (
    "1",
    "true",
    "yes",
    "on",
)
VALIDATE_DASHBOARD_SIZE = os.getenv("VALIDATE_DASHBOARD_SIZE", "true").lower() in (
    "1",
    "true",
    "yes",
    "on",
)
DASHBOARD_MAX_SINGLE_BYTES = int(os.getenv("DASHBOARD_MAX_SINGLE_BYTES", 10 * 1024**2))  # default 10MB per dashboard


def fetch_schema(schema_name: str) -> Dict:
    base = SCHEMA_PATH.rstrip("/")
    try:
        if base.startswith("http"):
            response = requests.get(f"{base}/{schema_name}", timeout=10)
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
    if not VALIDATE_DASHBOARD_SCHEMA:
        return
    try:
        validate(instance=dashboard, schema=dashboard_schema)
    except ValidationError as e:
        logger.error(f"Schema validation failed: {e.message}")
        raise DashboardValidationError("Dashboard validation failed.") from e


def check_dashboard_size(dashboard: Dict[str, Any]) -> int:
    size = len(bson.encode(dashboard))
    if VALIDATE_DASHBOARD_SIZE and size > DASHBOARD_MAX_SINGLE_BYTES:
        raise DashboardSizeError(f"Size {size} exceeds max {DASHBOARD_MAX_SINGLE_BYTES}")
    return size


def validate_dashboard(dashboard: Dict[str, Any]) -> int:
    check_dashboard_schema(dashboard)
    return check_dashboard_size(dashboard)


def check_dashboard_protection(shared: SharedState, dashboard_id):
    existing = shared.mongo_db["dashboards"].find_one({"_id": dashboard_id})
    if not existing:
        return None
    if existing.get("protected"):
        raise DashboardProtectedError(f"Dashboard {dashboard_id} is protected and cannot be changed.")


def enforce_storage_limits(shared: SharedState) -> None:
    coll = shared.mongo_db["dashboards"]

    # Calculate total storage used by summing _size of all dashboards
    total = next(coll.aggregate([{"$group": {"_id": None, "total": {"$sum": "$_size"}}}]), {}).get("total", 0)

    # Exit early if we're below the eviction threshold
    if total < DASHBOARD_MAX_TOTAL_STORAGE_BYTES * DASHBOARD_EVICTION_THRESHOLD:
        return

    # Set the target storage to reach after eviction
    target = int(DASHBOARD_MAX_TOTAL_STORAGE_BYTES * DASHBOARD_TARGET_UTILIZATION)

    # Iterate over non-whitelisted dashboards sorted by oldest access time
    for doc in coll.find(
        {"whitelisted": {"$ne": True}},
        sort=[("last_access", 1)],
        projection={"_size": 1},
    ):
        if total <= target:
            break

        size = doc.get("_size", 0)
        coll.delete_one({"_id": doc["_id"]})
        total -= size
        logger.info(f"Evicted {doc['_id']}, freed {size}, total now {total}")


def get_record(shared: SharedState, dashboard_id: str) -> Optional[Dict[str, Any]]:
    doc = shared.mongo_db["dashboards"].find_one({"_id": dashboard_id})
    return doc if doc else None


def whitelist_dashboard(shared: SharedState, dashboard_id: str, whitelisted: bool = True) -> bool:
    result = shared.mongo_db["dashboards"].update_one({"_id": dashboard_id}, {"$set": {"whitelisted": whitelisted}})
    return result.matched_count == 1


def protect_dashboard(shared: SharedState, dashboard_id: str, protected: bool = True) -> bool:
    result = shared.mongo_db["dashboards"].update_one({"_id": dashboard_id}, {"$set": {"protected": protected}})
    return result.matched_count == 1


def create_dashboard(shared: SharedState, dashboard: Dict[str, Any]) -> Dict[str, Any]:
    size = validate_dashboard(dashboard)
    dashboard_id = str(uuid.uuid4())

    shared.mongo_db["dashboards"].insert_one(
        {
            "_id": dashboard_id,
            "dashboard": dashboard,
            "_size": size,
            "last_access": datetime.now(timezone.utc),
        }
    )
    enforce_storage_limits(shared)
    return {"id": dashboard_id, **dashboard}


def get_dashboard(shared: SharedState, dashboard_id: str) -> Optional[Dict[str, Any]]:
    doc = shared.mongo_db["dashboards"].find_one_and_update(
        {"_id": dashboard_id},
        {"$set": {"last_access": datetime.now(timezone.utc)}},
        return_document=ReturnDocument.AFTER,
    )
    return {"id": dashboard_id, **doc.get("dashboard", {})} if doc else None


def update_dashboard(shared: SharedState, dashboard_id: str, dashboard: Dict[str, Any]) -> Dict[str, Any]:
    check_dashboard_protection(shared, dashboard_id)
    size = validate_dashboard(dashboard)
    updated = shared.mongo_db["dashboards"].find_one_and_update(
        {"_id": dashboard_id},
        {
            "$set": {
                "dashboard": dashboard,
                "_size": size,
                "last_access": datetime.now(timezone.utc),
            }
        },
        return_document=ReturnDocument.AFTER,
    )
    if updated:
        enforce_storage_limits(shared)
        return {"id": dashboard_id, **dashboard}
    return None


def delete_dashboard(shared: SharedState, dashboard_id: str) -> Optional[Dict[str, Any]]:
    check_dashboard_protection(shared, dashboard_id)
    doc = shared.mongo_db["dashboards"].find_one_and_delete({"_id": dashboard_id})
    return {"id": dashboard_id, **doc.get("dashboard", {})} if doc else None
