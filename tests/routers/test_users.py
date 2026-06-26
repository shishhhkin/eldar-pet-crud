from uuid import uuid4

from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.user_profiles import UserProfileModel
from src.repository import Repo


def _payload(
    username: str = 'alice',
    email: str = 'alice@example.com',
    *,
    avatar_url: str | None = 'https://example.com/a.png',
    bio: str | None = 'hello',
    socials: dict | None = None,
) -> dict:
    return {
        'username': username,
        'email': email,
        'profile': {
            'avatar_url': avatar_url,
            'bio': bio,
            'socials': socials if socials is not None else {'tg': '@alice'},
        },
    }


async def test_create_user(client: AsyncClient) -> None:
    response = await client.post('/users', json=_payload())

    assert response.status_code == 201
    body = response.json()
    assert body['username'] == 'alice'
    assert body['email'] == 'alice@example.com'
    assert body['profile']['avatar_url'] == 'https://example.com/a.png'
    assert body['profile']['bio'] == 'hello'
    assert body['profile']['socials'] == {'tg': '@alice'}
    assert 'id' in body
    assert 'created_at' in body
    assert 'id' in body['profile']
    assert 'user_id' not in body['profile']


async def test_read_user(client: AsyncClient) -> None:
    created = (await client.post('/users', json=_payload())).json()

    response = await client.get(f'/users/{created["id"]}')

    assert response.status_code == 200
    assert response.json() == created


async def test_read_user_not_found(client: AsyncClient) -> None:
    response = await client.get(f'/users/{uuid4()}')

    assert response.status_code == 404
    body = response.json()
    assert body['code'] == 'not_found'
    assert 'not found' in body['detail']
    assert body['request_id']


async def test_update_user(client: AsyncClient) -> None:
    created = (await client.post('/users', json=_payload())).json()

    new_payload = _payload(
        username='alice2',
        email='alice2@example.com',
        avatar_url=None,
        bio='updated',
        socials={'gh': 'alice'},
    )
    response = await client.patch(f'/users/{created["id"]}', json=new_payload)

    assert response.status_code == 200
    body = response.json()
    assert body['username'] == 'alice2'
    assert body['email'] == 'alice2@example.com'
    assert body['profile']['avatar_url'] is None
    assert body['profile']['bio'] == 'updated'
    assert body['profile']['socials'] == {'gh': 'alice'}
    assert body['id'] == created['id']
    assert body['profile']['id'] == created['profile']['id']
    assert body['created_at'] == created['created_at']


async def test_update_user_username_only_preserves_fields(client: AsyncClient) -> None:
    created = (await client.post('/users', json=_payload())).json()

    response = await client.patch(f'/users/{created["id"]}', json={'username': 'alice2'})

    assert response.status_code == 200
    body = response.json()
    assert body['username'] == 'alice2'
    assert body['email'] == created['email']
    assert body['profile'] == created['profile']


async def test_update_user_rejects_null_username(client: AsyncClient) -> None:
    created = (await client.post('/users', json=_payload())).json()

    response = await client.patch(f'/users/{created["id"]}', json={'username': None})

    assert response.status_code == 422


async def test_update_user_rejects_null_email(client: AsyncClient) -> None:
    created = (await client.post('/users', json=_payload())).json()

    response = await client.patch(f'/users/{created["id"]}', json={'email': None})

    assert response.status_code == 422


async def test_update_user_not_found(client: AsyncClient) -> None:
    response = await client.patch(f'/users/{uuid4()}', json=_payload())

    assert response.status_code == 404


async def test_delete_user(client: AsyncClient) -> None:
    created = (await client.post('/users', json=_payload())).json()

    response = await client.delete(f'/users/{created["id"]}')
    assert response.status_code == 204

    follow_up = await client.get(f'/users/{created["id"]}')
    assert follow_up.status_code == 404


async def test_delete_user_not_found(client: AsyncClient) -> None:
    response = await client.delete(f'/users/{uuid4()}')

    assert response.status_code == 404


async def test_delete_cascades_profile(client: AsyncClient, db_session: AsyncSession) -> None:
    created = (await client.post('/users', json=_payload())).json()

    profile_repo = Repo(db_session, UserProfileModel)

    count_before = await db_session.scalar(select(func.count()).select_from(UserProfileModel))
    assert count_before == 1

    await client.delete(f'/users/{created["id"]}')

    visible = (await db_session.execute(profile_repo.select())).scalars().all()
    assert visible == []

    rows = (await db_session.execute(select(UserProfileModel))).scalars().all()
    assert len(rows) == 1
    assert rows[0].is_deleted is True


async def test_recreate_user_with_deleted_credentials(client: AsyncClient) -> None:
    created = (await client.post('/users', json=_payload())).json()
    await client.delete(f'/users/{created["id"]}')

    response = await client.post('/users', json=_payload())
    assert response.status_code == 201
    assert response.json()['id'] != created['id']


async def test_create_user_invalid_email(client: AsyncClient) -> None:
    response = await client.post('/users', json=_payload(email='not-an-email'))

    assert response.status_code == 422


async def test_create_user_missing_profile(client: AsyncClient) -> None:
    response = await client.post('/users', json={'username': 'bob', 'email': 'bob@example.com'})

    assert response.status_code == 422


async def test_create_user_duplicate_username(client: AsyncClient) -> None:
    first = await client.post('/users', json=_payload())
    assert first.status_code == 201

    response = await client.post(
        '/users', json=_payload(username='alice', email='other@example.com')
    )

    assert response.status_code == 409


async def test_create_user_username_with_dash_rejected(client: AsyncClient) -> None:
    response = await client.post('/users', json=_payload(username='john-doe'))

    assert response.status_code == 422


async def test_create_user_username_too_short(client: AsyncClient) -> None:
    response = await client.post('/users', json=_payload(username='ab'))

    assert response.status_code == 422


async def test_create_user_username_too_long(client: AsyncClient) -> None:
    response = await client.post('/users', json=_payload(username='a' * 65))

    assert response.status_code == 422


async def test_create_user_invalid_avatar_url(client: AsyncClient) -> None:
    response = await client.post('/users', json=_payload(avatar_url='not-a-url'))

    assert response.status_code == 422


async def test_create_user_bio_too_long(client: AsyncClient) -> None:
    response = await client.post('/users', json=_payload(bio='a' * 2001))

    assert response.status_code == 422


async def test_create_user_socials_key_too_long(client: AsyncClient) -> None:
    response = await client.post('/users', json=_payload(socials={'a' * 33: 'value'}))

    assert response.status_code == 422
