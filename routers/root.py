from fastapi import APIRouter

from shared_resources.decorators import timeout

router = APIRouter()


@router.get("/")
@timeout(5)
def root():
    return {"message": "Hello, World!"}


@router.get("/health", description="Simply tests connectivity")
@timeout(5)
def healthcheck():
    return {"message": "Alive and Well!"}
