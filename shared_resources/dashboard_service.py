from typing import Any, Dict

import json
import uuid

from shared_resources.variables import shared_variables as shared

def create_dashboard(dashboard: Dict[str, Any]) -> Dict[str, Any]:
    id = str(uuid.uuid4())
    dashboard_json = json.dumps(dashboard)
    shared.redis_client.set(f"dashboard:{id}", dashboard_json)
    return {"id": id, **dashboard}

def get_dashboard(id: str) -> Dict[str, Any]:
    dashboard_json = shared.redis_client.get(f"dashboard:{id}")
    if dashboard_json is None:
        return None
    dashboard = json.loads(dashboard_json)
    return {"id": id, **dashboard}

def update_dashboard(id: str, dashboard: Dict[str, Any]) -> Dict[str, Any]:
    dashboard_json = shared.redis_client.get(f"dashboard:{id}")
    if dashboard_json is None:
        return None
    dashboard_orig = dict(json.loads(dashboard_json))
    dashboard_orig.update(dashboard)
    dashboard_json = json.dumps(dashboard_orig)
    shared.redis_client.set(f"dashboard:{id}", dashboard_json)
    return {"id": id, **dashboard_orig}
    
def delete_dashboard(id: str) -> Dict[str, Any]:
    dashboard_json = shared.redis_client.get(f"dashboard:{id}")
    if dashboard_json is None:
        return None
    dashboard = json.loads(dashboard_json)
    shared.redis_client.delete(f"dashboard:{id}")
    return {"id": id, **dashboard}