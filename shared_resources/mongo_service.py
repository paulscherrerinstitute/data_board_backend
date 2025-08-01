import logging

from shared_resources.variables import SharedState

logger = logging.getLogger("uvicorn")


def check_mongo_connected(shared: SharedState):
    logger.info("Checking MongoDB connection.")
    try:
        shared.mongo_client.admin.command("ping")
        logger.info("MongoDB connected.")
    except Exception:
        raise RuntimeError(
            "Cannot reach MongoDB server. Have you set the MONGO_HOST and MONGO_PORT environment variables correctly?"
        ) from None


def configure_mongo_indices(shared: SharedState):
    indexes = shared.mongo_db["dashboards"].index_information()
    if not any("last_access" in idx.get("key", [])[0] for idx in indexes.values()):
        shared.mongo_db["dashboards"].create_index([("last_access", 1)])
        logger.info("Created index on last_access in MongoDB.")
    else:
        logger.info("Index on last_access already exists in MongoDB.")
