from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.clients.library import LibraryClient
from src.dependencies.authors import AuthorServiceTxDep
from src.dependencies.genres import GenreServiceTxDep
from src.dependencies.users import UserServiceTxDep
from src.infra.cache import Cache
from src.services.invalidation_outbox import InvalidationOutbox
from src.services.membership_issuer import MembershipIssuer


async def test_write_services_record_invalidations_in_data_session(
    session_factory: async_sessionmaker[AsyncSession],
    cache: Cache,
    outbox: InvalidationOutbox,
    library: LibraryClient,
    membership_issuer: MembershipIssuer,
) -> None:
    app = FastAPI()
    app.state.session_factory = session_factory
    app.state.cache = cache
    app.state.outbox = outbox
    app.state.library = library
    app.state.membership_issuer = membership_issuer

    @app.get('/sessions')
    async def sessions(
        authors: AuthorServiceTxDep, genres: GenreServiceTxDep, users: UserServiceTxDep
    ) -> dict[str, bool]:
        return {
            'authors': authors.invalidations.session is authors.repo.session,
            'genres': genres.invalidations.session is genres.repo.session,
            'users': users.invalidations.session is users.repo.session,
        }

    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test') as client:
        response = await client.get('/sessions')

    assert response.json() == {'authors': True, 'genres': True, 'users': True}
