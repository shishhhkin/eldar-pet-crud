import asyncio
from uuid import uuid4

from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.genre_moods import genre_moods
from src.models.moods import MoodModel
from src.schemas.moods import MAX_MOODS_PER_GENRE


def _payload(name: str = 'фантастика', *, moods: list[dict] | None = None) -> dict:
    return {'name': name, 'moods': moods if moods is not None else [{'name': 'грусть'}]}


async def test_create_genre(client: AsyncClient) -> None:
    response = await client.post('/genres', json=_payload())

    assert response.status_code == 201
    body = response.json()
    assert body['name'] == 'фантастика'
    assert [mood['name'] for mood in body['moods']] == ['грусть']
    assert 'id' in body


async def test_create_genre_with_nested_moods(client: AsyncClient) -> None:
    response = await client.post(
        '/genres', json=_payload('роман', moods=[{'name': 'грусть'}, {'name': 'надежда'}])
    )

    assert response.status_code == 201
    body = response.json()
    names = [mood['name'] for mood in body['moods']]
    assert names == ['грусть', 'надежда']
    for mood in body['moods']:
        assert 'id' in mood


async def test_read_genre(client: AsyncClient) -> None:
    created = (
        await client.post('/genres', json=_payload('роман', moods=[{'name': 'грусть'}]))
    ).json()

    response = await client.get(f'/genres/{created["id"]}')

    assert response.status_code == 200
    assert response.json() == created


async def test_read_genre_not_found(client: AsyncClient) -> None:
    response = await client.get(f'/genres/{uuid4()}')

    assert response.status_code == 404
    body = response.json()
    assert body['code'] == 'not_found'
    assert body['detail'].startswith('Genre ')
    assert 'not found' in body['detail']
    assert body['request_id']


async def test_update_genre_scalar_and_moods(client: AsyncClient) -> None:
    created = (
        await client.post('/genres', json=_payload('old', moods=[{'name': 'грусть'}]))
    ).json()

    response = await client.patch(
        f'/genres/{created["id"]}', json=_payload('new', moods=[{'name': 'радость'}])
    )

    assert response.status_code == 200
    body = response.json()
    assert body['id'] == created['id']
    assert body['name'] == 'new'
    assert [mood['name'] for mood in body['moods']] == ['радость']


async def test_update_genre_name_only_preserves_moods(client: AsyncClient) -> None:
    created = (
        await client.post('/genres', json=_payload('old', moods=[{'name': 'грусть'}]))
    ).json()

    response = await client.patch(f'/genres/{created["id"]}', json={'name': 'new'})

    assert response.status_code == 200
    body = response.json()
    assert body['name'] == 'new'
    assert body['moods'] == created['moods']


async def test_update_genre_moods_only_preserves_name(client: AsyncClient) -> None:
    created = (
        await client.post('/genres', json=_payload('роман', moods=[{'name': 'грусть'}]))
    ).json()

    response = await client.patch(f'/genres/{created["id"]}', json={'moods': [{'name': 'радость'}]})

    assert response.status_code == 200
    body = response.json()
    assert body['name'] == 'роман'
    assert [mood['name'] for mood in body['moods']] == ['радость']


async def test_update_genre_rejects_null_name(client: AsyncClient) -> None:
    created = (await client.post('/genres', json=_payload('x'))).json()

    response = await client.patch(f'/genres/{created["id"]}', json={'name': None})

    assert response.status_code == 422


async def test_update_genre_rejects_empty_moods(client: AsyncClient) -> None:
    created = (await client.post('/genres', json=_payload('x', moods=[{'name': 'грусть'}]))).json()

    response = await client.patch(f'/genres/{created["id"]}', json={'moods': []})

    assert response.status_code == 422


async def test_update_genre_rejects_empty_body(client: AsyncClient) -> None:
    created = (await client.post('/genres', json=_payload('x', moods=[{'name': 'грусть'}]))).json()

    response = await client.patch(f'/genres/{created["id"]}', json={})

    assert response.status_code == 422
    error = response.json()['detail'][0]
    assert error['type'] == 'at_least_one_field'
    assert error['msg'] == 'At least one of "name" or "moods" must be provided'


async def test_update_genre_not_found(client: AsyncClient) -> None:
    response = await client.patch(f'/genres/{uuid4()}', json=_payload('x'))

    assert response.status_code == 404


async def test_delete_genre(client: AsyncClient) -> None:
    created = (await client.post('/genres', json=_payload('x'))).json()

    response = await client.delete(f'/genres/{created["id"]}')
    assert response.status_code == 204

    follow_up = await client.get(f'/genres/{created["id"]}')
    assert follow_up.status_code == 404


async def test_delete_genre_not_found(client: AsyncClient) -> None:
    response = await client.delete(f'/genres/{uuid4()}')

    assert response.status_code == 404


async def test_moods_are_shared_between_genres(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    g1 = (await client.post('/genres', json=_payload('роман', moods=[{'name': 'грусть'}]))).json()
    g2 = (
        await client.post(
            '/genres', json=_payload('драма', moods=[{'name': 'грусть'}, {'name': 'надежда'}])
        )
    ).json()

    sad_in_g1 = next(mood for mood in g1['moods'] if mood['name'] == 'грусть')
    sad_in_g2 = next(mood for mood in g2['moods'] if mood['name'] == 'грусть')
    assert sad_in_g1['id'] == sad_in_g2['id']

    mood_count = await db_session.scalar(select(func.count()).select_from(MoodModel))
    assert mood_count == 2
    link_count = await db_session.scalar(select(func.count()).select_from(genre_moods))
    assert link_count == 3


async def test_delete_genre_retains_moods(client: AsyncClient, db_session: AsyncSession) -> None:
    created = (
        await client.post('/genres', json=_payload('роман', moods=[{'name': 'грусть'}]))
    ).json()

    await client.delete(f'/genres/{created["id"]}')

    assert (await client.get(f'/genres/{created["id"]}')).status_code == 404
    mood_count = await db_session.scalar(select(func.count()).select_from(MoodModel))
    assert mood_count == 1


async def test_create_genre_duplicate_name(client: AsyncClient) -> None:
    first = await client.post('/genres', json=_payload('uniq'))
    assert first.status_code == 201

    response = await client.post('/genres', json=_payload('uniq'))

    assert response.status_code == 409
    body = response.json()
    assert body['code'] == 'already_exists'
    assert body['detail'] == 'Genre already exists'
    assert body['request_id']


async def test_update_genre_to_duplicate_name(client: AsyncClient) -> None:
    await client.post('/genres', json=_payload('первый'))
    created = (await client.post('/genres', json=_payload('второй'))).json()

    response = await client.patch(f'/genres/{created["id"]}', json={'name': 'первый'})

    assert response.status_code == 409
    body = response.json()
    assert body['code'] == 'already_exists'
    assert body['detail'] == 'Genre already exists'
    assert body['request_id']


async def test_update_genre_to_duplicate_name_with_moods(client: AsyncClient) -> None:
    await client.post('/genres', json=_payload('первый'))
    created = (await client.post('/genres', json=_payload('второй'))).json()

    response = await client.patch(
        f'/genres/{created["id"]}',
        json={'name': 'первый', 'moods': [{'name': 'радость'}]},
    )

    assert response.status_code == 409
    assert response.json()['code'] == 'already_exists'


async def test_concurrent_genre_updates_to_same_new_name_only_one_wins(
    client: AsyncClient,
) -> None:
    second = (await client.post('/genres', json=_payload('второй'))).json()
    third = (await client.post('/genres', json=_payload('третий'))).json()

    responses = await asyncio.gather(
        client.patch(f'/genres/{second["id"]}', json={'name': 'общее'}),
        client.patch(f'/genres/{third["id"]}', json={'name': 'общее'}),
    )

    statuses = sorted(response.status_code for response in responses)
    assert statuses == [200, 409]
    conflict = next(response for response in responses if response.status_code == 409)
    assert conflict.json()['code'] == 'already_exists'


async def test_concurrent_genre_create_and_update_to_same_name_only_one_wins(
    client: AsyncClient,
) -> None:
    existing = (await client.post('/genres', json=_payload('второй'))).json()

    responses = await asyncio.gather(
        client.post('/genres', json=_payload('общее')),
        client.patch(f'/genres/{existing["id"]}', json={'name': 'общее'}),
    )

    statuses = [response.status_code for response in responses]
    assert 409 in statuses
    assert any(status in (200, 201) for status in statuses)
    conflict = responses[statuses.index(409)]
    assert conflict.json()['code'] == 'already_exists'


async def test_update_genre_to_deleted_name(client: AsyncClient) -> None:
    first = (await client.post('/genres', json=_payload('первый'))).json()
    created = (await client.post('/genres', json=_payload('второй'))).json()
    await client.delete(f'/genres/{first["id"]}')

    response = await client.patch(f'/genres/{created["id"]}', json={'name': 'первый'})

    assert response.status_code == 200
    assert response.json()['name'] == 'первый'


async def test_recreate_genre_with_deleted_name(client: AsyncClient) -> None:
    created = (await client.post('/genres', json=_payload('uniq'))).json()
    await client.delete(f'/genres/{created["id"]}')

    response = await client.post('/genres', json=_payload('uniq'))

    assert response.status_code == 201
    assert response.json()['id'] != created['id']


async def test_create_genre_empty_name(client: AsyncClient) -> None:
    response = await client.post('/genres', json=_payload(''))

    assert response.status_code == 422


async def test_create_genre_strips_whitespace(client: AsyncClient) -> None:
    response = await client.post('/genres', json=_payload('  фантастика  '))

    assert response.status_code == 201
    assert response.json()['name'] == 'фантастика'


async def test_create_genre_blank_after_strip(client: AsyncClient) -> None:
    response = await client.post('/genres', json=_payload('   '))

    assert response.status_code == 422


async def test_create_genre_strips_mood_name(client: AsyncClient) -> None:
    response = await client.post('/genres', json=_payload('роман', moods=[{'name': '  грусть  '}]))

    assert response.status_code == 201
    assert response.json()['moods'][0]['name'] == 'грусть'


async def test_create_genre_empty_mood_name(client: AsyncClient) -> None:
    response = await client.post('/genres', json=_payload('роман', moods=[{'name': ''}]))

    assert response.status_code == 422


async def test_create_genre_empty_moods(client: AsyncClient) -> None:
    response = await client.post('/genres', json=_payload('роман', moods=[]))

    assert response.status_code == 422


async def test_create_genre_duplicate_moods_deduped(client: AsyncClient) -> None:
    response = await client.post(
        '/genres', json=_payload('роман', moods=[{'name': 'грусть'}, {'name': 'грусть'}])
    )

    assert response.status_code == 201
    assert [mood['name'] for mood in response.json()['moods']] == ['грусть']


async def test_create_genre_too_many_moods(client: AsyncClient) -> None:
    moods = [{'name': f'mood_{i}'} for i in range(MAX_MOODS_PER_GENRE + 1)]

    response = await client.post('/genres', json=_payload('роман', moods=moods))

    assert response.status_code == 422


async def test_create_genre_max_moods_allowed(client: AsyncClient) -> None:
    moods = [{'name': f'mood_{i}'} for i in range(MAX_MOODS_PER_GENRE)]

    response = await client.post('/genres', json=_payload('роман', moods=moods))

    assert response.status_code == 201
    assert len(response.json()['moods']) == MAX_MOODS_PER_GENRE


async def test_update_genre_too_many_moods(client: AsyncClient) -> None:
    created = (await client.post('/genres', json=_payload('x', moods=[{'name': 'грусть'}]))).json()
    moods = [{'name': f'mood_{i}'} for i in range(MAX_MOODS_PER_GENRE + 1)]

    response = await client.patch(f'/genres/{created["id"]}', json={'moods': moods})

    assert response.status_code == 422
