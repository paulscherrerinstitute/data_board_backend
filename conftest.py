import importlib.util
import os
import socket
import sys
import time

import pytest
from fastapi.testclient import TestClient
from pymongo import MongoClient
from testcontainers.core.container import DockerContainer


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


@pytest.fixture()
def client(mongo_container, monkeypatch):
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
    yield client
