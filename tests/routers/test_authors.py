from uuid import uuid4

from httpx import AsyncClient


def _payload(name: str = 'Лев Толстой', bio: str | None = 'русский писатель') -> dict:
    return {'name': name, 'bio': bio}


async def test_create_author(client: AsyncClient) -> None:
    response = await client.post('/authors', json=_payload())

    assert response.status_code == 201
    body = response.json()
    assert body['name'] == 'Лев Толстой'
    assert body['bio'] == 'русский писатель'
    assert 'id' in body


async def test_create_author_without_bio(client: AsyncClient) -> None:
    response = await client.post('/authors', json={'name': 'Аноним'})

    assert response.status_code == 201
    assert response.json()['bio'] is None


async def test_read_author(client: AsyncClient) -> None:
    created = (await client.post('/authors', json=_payload())).json()

    response = await client.get(f'/authors/{created["id"]}')

    assert response.status_code == 200
    assert response.json() == created


async def test_read_author_not_found(client: AsyncClient) -> None:
    response = await client.get(f'/authors/{uuid4()}')

    assert response.status_code == 404
    body = response.json()
    assert body['code'] == 'not_found'
    assert 'not found' in body['detail']
    assert body['request_id']


async def test_update_author(client: AsyncClient) -> None:
    created = (await client.post('/authors', json=_payload())).json()

    response = await client.put(
        f'/authors/{created["id"]}',
        json=_payload(name='Л. Н. Толстой', bio=None),
    )

    assert response.status_code == 200
    body = response.json()
    assert body['id'] == created['id']
    assert body['name'] == 'Л. Н. Толстой'
    assert body['bio'] is None


async def test_update_author_not_found(client: AsyncClient) -> None:
    response = await client.put(f'/authors/{uuid4()}', json=_payload())

    assert response.status_code == 404


async def test_delete_author(client: AsyncClient) -> None:
    created = (await client.post('/authors', json=_payload())).json()

    response = await client.delete(f'/authors/{created["id"]}')
    assert response.status_code == 204

    follow_up = await client.get(f'/authors/{created["id"]}')
    assert follow_up.status_code == 404


async def test_delete_author_not_found(client: AsyncClient) -> None:
    response = await client.delete(f'/authors/{uuid4()}')

    assert response.status_code == 404


async def test_create_author_empty_name(client: AsyncClient) -> None:
    response = await client.post('/authors', json={'name': '', 'bio': None})

    assert response.status_code == 422


async def test_create_author_strips_whitespace(client: AsyncClient) -> None:
    response = await client.post('/authors', json={'name': '  Лев Толстой  ', 'bio': None})

    assert response.status_code == 201
    assert response.json()['name'] == 'Лев Толстой'


async def test_create_author_blank_after_strip(client: AsyncClient) -> None:
    response = await client.post('/authors', json={'name': '   ', 'bio': None})

    assert response.status_code == 422


async def test_create_author_bio_too_long(client: AsyncClient) -> None:
    response = await client.post('/authors', json={'name': 'X', 'bio': 'a' * 2001})

    assert response.status_code == 422


async def test_read_author_includes_books(client: AsyncClient) -> None:
    author = (await client.post('/authors', json=_payload())).json()
    book = (
        await client.post('/books', json={'title': 'Война и мир', 'author_id': author['id']})
    ).json()

    response = await client.get(f'/authors/{author["id"]}')

    assert response.status_code == 200
    body = response.json()
    assert body['books'] == [{'id': book['id'], 'title': book['title']}]


async def test_create_author_returns_empty_books(client: AsyncClient) -> None:
    response = await client.post('/authors', json=_payload())

    assert response.status_code == 201
    assert response.json()['books'] == []
