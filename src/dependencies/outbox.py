from typing import Annotated, cast

from fastapi import Depends, Request

from src.services.invalidation_outbox import InvalidationOutbox


def get_outbox(request: Request) -> InvalidationOutbox:
    return cast('InvalidationOutbox', request.app.state.outbox)


OutboxDep = Annotated[InvalidationOutbox, Depends(get_outbox)]
