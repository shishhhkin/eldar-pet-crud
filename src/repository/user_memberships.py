from sqlalchemy import case, func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.user_memberships import UserMembershipModel
from src.repository.base import Repo
from src.schemas.library import LibraryMembership


class UserMembershipRepo(Repo[UserMembershipModel]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, UserMembershipModel)

    async def store(self, membership: LibraryMembership) -> UserMembershipModel:
        stmt = pg_insert(UserMembershipModel).values(
            id=membership.id,
            user_id=membership.user_id,
            number=membership.number,
            issued_at=membership.issued_at,
            version=membership.version,
        )
        newer = UserMembershipModel.version <= stmt.excluded.version
        upsert = stmt.on_conflict_do_update(
            index_elements=[UserMembershipModel.user_id],
            set_={
                'number': case((newer, stmt.excluded.number), else_=UserMembershipModel.number),
                'issued_at': case(
                    (newer, stmt.excluded.issued_at), else_=UserMembershipModel.issued_at
                ),
                'version': case((newer, stmt.excluded.version), else_=UserMembershipModel.version),
                'synced_at': func.greatest(UserMembershipModel.synced_at, func.now()),
                'updated_at': func.now(),
            },
        ).returning(UserMembershipModel)
        result = await self.session.scalars(upsert, execution_options={'populate_existing': True})
        return result.one()
