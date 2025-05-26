import importlib.util
import os
import re
import socket
import sys
import time
from pathlib import Path

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from pymongo import MongoClient
from testcontainers.core.container import DockerContainer

# Global store for all normalized route calls in each worker
ROUTE_CALLS = set()


def get_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


def normalize_path(path: str) -> str:
    path = path.split("?", 1)[0]
    uuid_pattern = re.compile(r"/[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")
    return uuid_pattern.sub("/{id}", path)


@pytest.fixture()
def mongo_container():
    host_port = get_free_port()
    c = (
        DockerContainer("mongo:latest")
        .with_exposed_ports(27017)
        .with_bind_ports(27017, host_port)
        .with_command("mongod --bind_ip_all --noauth")
    )
    c.start()
    host = c.get_container_host_ip()

    deadline = time.time() + 30
    while time.time() < deadline:
        try:
            client = MongoClient(host=host, port=host_port, serverSelectionTimeoutMS=1000)
            client.admin.command("ping")
            break
        except Exception:
            time.sleep(1)
    else:
        c.stop()
        pytest.skip("MongoDB container did not start in time")

    print(f"[mongo-container] Running on {host}:{host_port}")
    yield host, host_port
    c.stop()


@pytest.fixture()
def client(mongo_container):
    host, port = mongo_container
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setenv("MONGO_HOST", host)
    monkeypatch.setenv("MONGO_PORT", str(port))

    # Load mock datahub
    mock_path = os.path.abspath("tests/mocks/mock_datahub.py")
    spec = importlib.util.spec_from_file_location("datahub", mock_path)
    mock_datahub = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mock_datahub)
    sys.modules["datahub"] = mock_datahub

    import main

    with TestClient(main.app) as client:
        # Patch HTTP methods to track normalized route usage
        for method in ("get", "post", "put", "delete", "patch"):
            original = getattr(client, method)

            def make_tracker(orig):
                def tracker(url, *args, **kwargs):
                    ROUTE_CALLS.add(normalize_path(url))
                    return orig(url, *args, **kwargs)

                return tracker

            setattr(client, method, make_tracker(original))

        yield client

    monkeypatch.undo()


def get_all_routes():
    import main

    return [route.path for route in main.app.routes if isinstance(route, APIRoute)]


def pytest_sessionfinish(session, exitstatus):
    root = Path(session.config.rootpath)
    workerinput = getattr(session.config, "workerinput", None)
    if workerinput:
        # Running in a worker: write calls to file
        wid = workerinput.get("workerid", "unknown")
        file = root / f".route_calls_{wid}.txt"
        file.write_text("\n".join(sorted(ROUTE_CALLS)))


def pytest_unconfigure(config):
    if getattr(config, "workerinput", None):
        return

    # Fetch all called routes and delete file dumps afterwards
    root_dir = Path(config.rootpath)
    all_calls = set()
    for temp_file in root_dir.glob(".route_calls_*.txt"):
        all_calls.update(temp_file.read_text().splitlines())
        temp_file.unlink()

    defined = set(get_all_routes())
    missing = sorted(defined - all_calls)
    if not missing:
        print("\033[32mAll defined routes were called in the tests!\033[0m\n")
        return

    print("\n")
    print("\033[31mROUTE COVERAGE FAILURE\033[0m")
    print(f"\033[31mRoutes missing tests: {missing}\033[0m")
    print("> Implement Tests for these routes.\n")
    sys.exit(1)
