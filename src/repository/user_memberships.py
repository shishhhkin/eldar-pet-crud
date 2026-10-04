from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from sqlalchemy import exists, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.user_memberships import UserMembershipModel
from src.models.users import UserModel
from src.repository.base import Repo
from src.schemas.library import LibraryMembership


class UserMembershipRepo(Repo[UserMembershipModel]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, UserMembershipModel)

    async def store(self, membership: LibraryMembership, synced_at: datetime) -> None:
        stmt = pg_insert(UserMembershipModel).values(
            id=membership.id,
            user_id=membership.user_id,
            number=membership.number,
            issued_at=membership.issued_at,
            version=membership.version,
            synced_at=synced_at,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[UserMembershipModel.user_id],
            set_={
                'number': stmt.excluded.number,
                'issued_at': stmt.excluded.issued_at,
                'version': stmt.excluded.version,
                'synced_at': func.greatest(UserMembershipModel.synced_at, stmt.excluded.synced_at),
                'updated_at': func.now(),
            },
            where=UserMembershipModel.version <= stmt.excluded.version,
        )
        await self.session.execute(stmt)

    async def pending_user_ids(self, limit: int) -> Sequence[UUID]:
        has_membership = exists().where(UserMembershipModel.user_id == UserModel.id)
        stmt = (
            select(UserModel.id)
            .where(UserModel.is_deleted.is_(False), ~has_membership)
            .order_by(UserModel.id)
            .limit(limit)
        )
        return (await self.session.execute(stmt)).scalars().all()
