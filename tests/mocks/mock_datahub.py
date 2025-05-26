import re

import numpy as np

MOCK_CHANNELS = {
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
        },
        {
            "backend": "test-backend",
            "name": "test-channel-2",
            "seriesId": "5678",
            "source": "",
            "type": "string",
            "shape": [],
            "unit": "",
            "description": "",
        },
    ]
}


class Enum:
    def __init__(self, id, desc):
        self.id = id
        self.desc = desc
        self.dtype = "enum"
        self.shape = []

    def __str__(self):
        return f"{self.id}:{self.desc}"


class Table:
    def __init__(self):
        self.data = {}

    def clear(self):
        self.data = {}


class Daqbuf:
    def __init__(self, backend=None, parallel=False):
        self.listener = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def search(self, regex=None, case_sensitive=False):
        flags = 0 if case_sensitive else re.IGNORECASE
        pattern = re.compile(regex, flags)
        return {"channels": [channel for channel in MOCK_CHANNELS["channels"] if pattern.search(channel["name"])]}

    def add_listener(self, listener):
        self.listener = listener

    def remove_listeners(self):
        self.listener = None

    def request(self, query, background=False):
        bins = "bins" in query
        channel = query["channels"][0]

        if bins:
            self.listener.data = {
                channel: [
                    {
                        "timestamp": 1747406011275000064,
                        "pulse_id": None,
                        channel: np.float64(200.44788),
                    },
                    {
                        "timestamp": 1747406011324999936,
                        "pulse_id": None,
                        channel: np.float64(200.65315),
                    },
                    {
                        "timestamp": 1747406011375000064,
                        "pulse_id": None,
                        channel: np.float64(200.6333),
                    },
                ],
                f"{channel} max": [
                    {
                        "timestamp": 1747406011275000064,
                        "pulse_id": None,
                        f"{channel} max": np.float64(200.69548),
                    },
                    {
                        "timestamp": 1747406011324999936,
                        "pulse_id": None,
                        f"{channel} max": np.float64(201.03015),
                    },
                    {
                        "timestamp": 1747406011375000064,
                        "pulse_id": None,
                        f"{channel} max": np.float64(200.7426),
                    },
                ],
                f"{channel} min": [
                    {
                        "timestamp": 1747406011275000064,
                        "pulse_id": None,
                        f"{channel} min": np.float64(200.06227),
                    },
                    {
                        "timestamp": 1747406011324999936,
                        "pulse_id": None,
                        f"{channel} min": np.float64(200.27147),
                    },
                    {
                        "timestamp": 1747406011375000064,
                        "pulse_id": None,
                        f"{channel} min": np.float64(200.43915),
                    },
                ],
                f"{channel} count": [
                    {
                        "timestamp": 1747406011275000064,
                        "pulse_id": None,
                        f"{channel} count": np.int64(5),
                    },
                    {
                        "timestamp": 1747406011324999936,
                        "pulse_id": None,
                        f"{channel} count": np.int64(5),
                    },
                    {
                        "timestamp": 1747406011375000064,
                        "pulse_id": None,
                        f"{channel} count": np.int64(5),
                    },
                ],
            }
        else:
            self.listener.data = {
                channel: [
                    {
                        "timestamp": 1747406011306952345,
                        "pulse_id": 24244952345,
                        channel: np.float64(200.88821411132812),
                    },
                    {
                        "timestamp": 1747406011316952346,
                        "pulse_id": 24244952346,
                        channel: np.float64(200.27146911621094),
                    },
                    {
                        "timestamp": 1747406011326952347,
                        "pulse_id": 24244952347,
                        channel: np.float64(201.0301513671875),
                    },
                    {
                        "timestamp": 1747406011336952348,
                        "pulse_id": 24244952348,
                        channel: np.float64(200.6446990966797),
                    },
                    {
                        "timestamp": 1747406011346952349,
                        "pulse_id": 24244952349,
                        channel: np.float64(200.5498809814453),
                    },
                    {
                        "timestamp": 1747406011356952350,
                        "pulse_id": 24244952350,
                        channel: np.float64(200.7425994873047),
                    },
                ]
            }

    def join(self):
        pass
