from uuid import uuid4

from httpx import AsyncClient


async def test_create_genre(client: AsyncClient) -> None:
    response = await client.post('/genres', json={'name': 'фантастика'})

    assert response.status_code == 201
    body = response.json()
    assert body['name'] == 'фантастика'
    assert 'id' in body


async def test_read_genre(client: AsyncClient) -> None:
    created = (await client.post('/genres', json={'name': 'роман'})).json()

    response = await client.get(f'/genres/{created["id"]}')

    assert response.status_code == 200
    assert response.json() == created


async def test_read_genre_not_found(client: AsyncClient) -> None:
    response = await client.get(f'/genres/{uuid4()}')

    assert response.status_code == 404
    assert response.json() == {'detail': 'Genre not found'}


async def test_update_genre(client: AsyncClient) -> None:
    created = (await client.post('/genres', json={'name': 'old'})).json()

    response = await client.put(f'/genres/{created["id"]}', json={'name': 'new'})

    assert response.status_code == 200
    body = response.json()
    assert body['id'] == created['id']
    assert body['name'] == 'new'


async def test_update_genre_not_found(client: AsyncClient) -> None:
    response = await client.put(f'/genres/{uuid4()}', json={'name': 'x'})

    assert response.status_code == 404


async def test_delete_genre(client: AsyncClient) -> None:
    created = (await client.post('/genres', json={'name': 'x'})).json()

    response = await client.delete(f'/genres/{created["id"]}')
    assert response.status_code == 204

    follow_up = await client.get(f'/genres/{created["id"]}')
    assert follow_up.status_code == 404


async def test_delete_genre_not_found(client: AsyncClient) -> None:
    response = await client.delete(f'/genres/{uuid4()}')

    assert response.status_code == 404


async def test_create_genre_duplicate_name(client: AsyncClient) -> None:
    first = await client.post('/genres', json={'name': 'uniq'})
    assert first.status_code == 201

    response = await client.post('/genres', json={'name': 'uniq'})

    assert response.status_code == 409


async def test_create_genre_empty_name(client: AsyncClient) -> None:
    response = await client.post('/genres', json={'name': ''})

    assert response.status_code == 422
