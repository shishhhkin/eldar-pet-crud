from typing import Annotated, cast

from fastapi import Depends, Request

from src.services.membership_service import MembershipService


def get_membership_service(request: Request) -> MembershipService:
    return cast('MembershipService', request.app.state.membership_service)


MembershipServiceDep = Annotated[MembershipService, Depends(get_membership_service)]
