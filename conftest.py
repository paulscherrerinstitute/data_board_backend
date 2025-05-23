import importlib.util
import os
import socket
import sys
import time

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from pymongo import MongoClient
from testcontainers.core.container import DockerContainer


def pytest_collection_modifyitems(items):
    last_test = None
    for item in items:
        if item.nodeid.endswith("::test_all_routes_are_tested"):
            last_test = item
            break

    if last_test:
        items.remove(last_test)
        items.append(last_test)


def get_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="session")
def mongo_container():
    host_port = get_free_port()
    c = (
        DockerContainer("mongo:6.0")
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


@pytest.fixture(scope="session")
def route_calls():
    return set()


@pytest.fixture()
def client(mongo_container, monkeypatch, route_calls):
    host, port = mongo_container
    monkeypatch.setenv("MONGO_HOST", host)
    monkeypatch.setenv("MONGO_PORT", str(port))

    mock_path = os.path.abspath("tests/mocks/mock_datahub.py")
    spec = importlib.util.spec_from_file_location("datahub", mock_path)
    mock_datahub = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mock_datahub)

    sys.modules["datahub"] = mock_datahub

    import main

    client = TestClient(main.app)

    # Patch HTTP methods to track route usage
    original_get = client.get
    original_post = client.post
    original_put = client.put
    original_delete = client.delete
    original_patch = client.patch

    def tracking_get(url, *args, **kwargs):
        route_calls.add(url)
        return original_get(url, *args, **kwargs)

    def tracking_post(url, *args, **kwargs):
        route_calls.add(url)
        return original_post(url, *args, **kwargs)

    def tracking_put(url, *args, **kwargs):
        route_calls.add(url)
        return original_put(url, *args, **kwargs)

    def tracking_delete(url, *args, **kwargs):
        route_calls.add(url)
        return original_delete(url, *args, **kwargs)

    def tracking_patch(url, *args, **kwargs):
        route_calls.add(url)
        return original_patch(url, *args, **kwargs)

    client.get = tracking_get
    client.post = tracking_post
    client.put = tracking_put
    client.delete = tracking_delete
    client.patch = tracking_patch

    yield client


def get_all_routes():
    import main

    return {route.path for route in main.app.routes if isinstance(route, APIRoute)}
