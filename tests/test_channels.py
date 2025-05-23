from mocks.mock_datahub import MOCK_CHANNELS

# from shared_resources.variables import shared_variables as shared


def test_channels_search_all(client):
    response = client.get("/channels/search", params={"search_text": ".*", "allow_cached_response": False})
    assert response.status_code == 200
    expected = MOCK_CHANNELS

    assert response.json() == expected


def test_channels_search_matching_all(client):
    response = client.get(
        "/channels/search",
        params={"search_text": "channel", "allow_cached_response": False},
    )
    assert response.status_code == 200
    expected = MOCK_CHANNELS

    assert response.json() == expected


def test_channels_search_matching_single(client):
    response = client.get(
        "/channels/search",
        params={"search_text": "channel-2", "allow_cached_response": False},
    )
    assert response.status_code == 200
    expected = {"channels": [MOCK_CHANNELS["channels"][1]]}
    assert response.json() == expected


def test_channels_recent(client):
    # Make the channel be registered as an available channel
    """
    response = client.get("/channels/search", params={"search_text": "test-channel-1"})
    assert response.status_code == 200
    """
    # Make the channel be added to recent channels
    response = client.get(
        "/channels/curve",
        params={"channel_name": "test-channel-1", "begin_time": 1, "end_time": 2},
    )
    assert response.status_code == 200

    response = client.get("/channels/recent")
    assert response.status_code == 200
    assert "channels" in response.json()
    assert len(response.json()["channels"]) > 0
    """
    expected = {
        "channels": [
            {
                "backend": "test-backend",
                "name": "test-channel-1",
                "seriesId": "1234",
                "source": "",
                "type": "string",
                "shape": [],
                "unit": "",
                "description": "",
            }
        ]
    }
    assert response.json() == expected
    """


def test_curve_data_raw(client):
    response = client.get(
        "/channels/curve",
        params={"channel_name": "test-channel-1", "begin_time": 1, "end_time": 2},
    )
    assert response.status_code == 200
    expected = {
        "curve": {
            "test-channel-1": {
                "1747406011306952345": 200.88821411132812,
                "1747406011316952346": 200.27146911621094,
                "1747406011326952347": 201.0301513671875,
                "1747406011336952348": 200.6446990966797,
                "1747406011346952349": 200.5498809814453,
                "1747406011356952350": 200.7425994873047,
            },
            "test-channel-1_meta": {
                "1747406011306952345": {
                    "pulseId": 24244952345,
                },
                "1747406011316952346": {
                    "pulseId": 24244952346,
                },
                "1747406011326952347": {
                    "pulseId": 24244952347,
                },
                "1747406011336952348": {
                    "pulseId": 24244952348,
                },
                "1747406011346952349": {
                    "pulseId": 24244952349,
                },
                "1747406011356952350": {
                    "pulseId": 24244952350,
                },
                "raw": True,
            },
        },
    }
    assert response.json() == expected


def test_curve_data_binned(client):
    response = client.get(
        "/channels/curve",
        params={
            "channel_name": "test-channel-1",
            "begin_time": 1,
            "end_time": 2,
            "num_bins": 3,
        },
    )
    assert response.status_code == 200
    expected = {
        "curve": {
            "test-channel-1": {
                "1747406011275000064": 200.44788,
                "1747406011324999936": 200.65315,
                "1747406011375000064": 200.6333,
            },
            "test-channel-1_min": {
                "1747406011275000064": 200.06227,
                "1747406011324999936": 200.27147,
                "1747406011375000064": 200.43915,
            },
            "test-channel-1_max": {
                "1747406011275000064": 200.69548,
                "1747406011324999936": 201.03015,
                "1747406011375000064": 200.7426,
            },
            "test-channel-1_meta": {
                "1747406011275000064": {
                    "count": 5,
                },
                "1747406011324999936": {
                    "count": 5,
                },
                "1747406011375000064": {
                    "count": 5,
                },
                "raw": False,
            },
        },
    }
    assert response.json() == expected


"""
def test_raw_link_success_default_base(client):
    params = {"channel_name": "test-channel", "begin_time": 10, "end_time": 20}
    resp = client.get("/channels/raw-link", params=params)
    assert resp.status_code == 200

    expected = (
        "https://data-api.psi.ch/api/4/events?backend=sf-databuffer&channelName=test-channel&begDate=10&endDate=20"
    )
    assert resp.json() == expected


def test_raw_link_success_custom_base(monkeypatch, client):
    monkeypatch.setattr(shared, "DATA_API_BASE_URL", "https://custom-url/api")
    params = {"channel_name": "foo", "begin_time": 123, "end_time": 456}
    resp = client.get("/channels/raw-link", params=params)
    assert resp.status_code == 200

    expected = "https://custom-url/api/events?backend=sf-databuffer&channelName=foo&begDate=123&endDate=456"
    assert resp.json() == expected
"""
