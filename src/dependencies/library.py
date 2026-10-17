from typing import Annotated, cast

from fastapi import Depends, Request

from src.clients.library import LibraryClient


def get_library(request: Request) -> LibraryClient:
    return cast('LibraryClient', request.app.state.library)


LibraryClientDep = Annotated[LibraryClient, Depends(get_library)]
