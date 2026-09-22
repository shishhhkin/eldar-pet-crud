from typing import Annotated, cast

from fastapi import Depends, Request

from src.infra.cache import Cache


def get_cache(request: Request) -> Cache:
    return cast('Cache', request.app.state.cache)


CacheDep = Annotated[Cache, Depends(get_cache)]
