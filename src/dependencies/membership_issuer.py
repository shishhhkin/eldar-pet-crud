from typing import Annotated, cast

from fastapi import Depends, Request

from src.services.membership_issuer import MembershipIssuer


def get_membership_issuer(request: Request) -> MembershipIssuer:
    return cast('MembershipIssuer', request.app.state.membership_issuer)


MembershipIssuerDep = Annotated[MembershipIssuer, Depends(get_membership_issuer)]
