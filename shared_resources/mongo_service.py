import logging

from shared_resources.variables import shared_variables as shared

logger = logging.getLogger("uvicorn")


def is_mongo_connected():
    try:
        shared.mongo_client.admin.command("ping")
    except Exception:
        raise RuntimeError(
            "Cannot reach MongoDB server. Have you set the MONGO_HOST and MONGO_PORT environment variables correctly?"
        ) from None


def configure_mongo_indices():
    indexes = shared.mongo_db["dashboards"].index_information()
    if not any("last_access" in idx.get("key", [])[0] for idx in indexes.values()):
        shared.mongo_db["dashboards"].create_index([("last_access", 1)])
        logger.info("Created index on last_access in MongoDB")
    else:
        logger.info("Index on last_access already exists in MongoDB")
