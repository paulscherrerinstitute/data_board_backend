import re

from conftest import get_all_routes


def normalize_path(path: str) -> str:
    # Replace UUID segments (8-4-4-4-12 hex) in URL path with {id}
    uuid_pattern = re.compile(r"/[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")
    return uuid_pattern.sub("/{id}", path)


# This test is defined to run last in conftest.py
def test_all_routes_are_tested(route_calls):
    all_routes = get_all_routes()
    normalized_calls = {normalize_path(url) for url in route_calls}

    missed = all_routes - normalized_calls
    assert not missed, f"Routes missing tests: {missed}\n> Implement Tests for these routes."
