from uuid import uuid4

from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.books import BookModel


async def _create_author(client: AsyncClient, name: str = 'Лев Толстой') -> dict:
    response = await client.post('/authors', json={'name': name, 'bio': None})
    assert response.status_code == 201
    return response.json()


async def test_create_book(client: AsyncClient) -> None:
    author = await _create_author(client)

    response = await client.post('/books', json={'title': 'Война и мир', 'author_id': author['id']})

    assert response.status_code == 201
    body = response.json()
    assert body['title'] == 'Война и мир'
    assert body['author'] == {'id': author['id'], 'name': author['name']}
    assert 'id' in body
    assert 'author_id' not in body


async def test_read_book(client: AsyncClient) -> None:
    author = await _create_author(client)
    created = (
        await client.post('/books', json={'title': 'Война и мир', 'author_id': author['id']})
    ).json()

    response = await client.get(f'/books/{created["id"]}')

    assert response.status_code == 200
    assert response.json() == created


async def test_read_book_not_found(client: AsyncClient) -> None:
    response = await client.get(f'/books/{uuid4()}')

    assert response.status_code == 404
    body = response.json()
    assert body['code'] == 'not_found'
    assert 'not found' in body['detail']
    assert body['request_id']


async def test_update_book_reassigns_author(client: AsyncClient) -> None:
    author1 = await _create_author(client, name='Толстой')
    author2 = await _create_author(client, name='Достоевский')
    created = (
        await client.post('/books', json={'title': 'Старое название', 'author_id': author1['id']})
    ).json()

    response = await client.put(
        f'/books/{created["id"]}',
        json={'title': 'Новое название', 'author_id': author2['id']},
    )

    assert response.status_code == 200
    body = response.json()
    assert body['id'] == created['id']
    assert body['title'] == 'Новое название'
    assert body['author'] == {'id': author2['id'], 'name': author2['name']}


async def test_update_book_not_found(client: AsyncClient) -> None:
    author = await _create_author(client)
    response = await client.put(
        f'/books/{uuid4()}',
        json={'title': 't', 'author_id': author['id']},
    )

    assert response.status_code == 404


async def test_delete_book(client: AsyncClient) -> None:
    author = await _create_author(client)
    created = (
        await client.post('/books', json={'title': 'Война и мир', 'author_id': author['id']})
    ).json()

    response = await client.delete(f'/books/{created["id"]}')
    assert response.status_code == 204

    follow_up = await client.get(f'/books/{created["id"]}')
    assert follow_up.status_code == 404


async def test_delete_book_not_found(client: AsyncClient) -> None:
    response = await client.delete(f'/books/{uuid4()}')

    assert response.status_code == 404


async def test_delete_author_cascades_books(client: AsyncClient, db_session: AsyncSession) -> None:
    author = await _create_author(client)
    await client.post('/books', json={'title': 'Первая', 'author_id': author['id']})
    await client.post('/books', json={'title': 'Вторая', 'author_id': author['id']})

    count_before = await db_session.scalar(select(func.count()).select_from(BookModel))
    assert count_before == 2

    await client.delete(f'/authors/{author["id"]}')

    count_after = await db_session.scalar(select(func.count()).select_from(BookModel))
    assert count_after == 0


async def test_create_book_with_unknown_author(client: AsyncClient) -> None:
    response = await client.post('/books', json={'title': 'Сиротка', 'author_id': str(uuid4())})

    assert response.status_code == 409


async def test_create_book_empty_title(client: AsyncClient) -> None:
    author = await _create_author(client)
    response = await client.post('/books', json={'title': '', 'author_id': author['id']})

    assert response.status_code == 422


async def test_create_book_invalid_author_id(client: AsyncClient) -> None:
    response = await client.post('/books', json={'title': 'x', 'author_id': 'not-a-uuid'})

    assert response.status_code == 422


async def test_create_book_strips_title(client: AsyncClient) -> None:
    author = await _create_author(client)
    response = await client.post(
        '/books', json={'title': '  Война и мир  ', 'author_id': author['id']}
    )

    assert response.status_code == 201
    assert response.json()['title'] == 'Война и мир'


async def test_create_book_blank_title(client: AsyncClient) -> None:
    author = await _create_author(client)
    response = await client.post('/books', json={'title': '   ', 'author_id': author['id']})

    assert response.status_code == 422
