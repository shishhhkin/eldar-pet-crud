from uuid import uuid4

from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.book_genres import book_genres


async def _create_author(client: AsyncClient) -> dict:
    response = await client.post('/authors', json={'name': 'Толстой', 'bio': None})
    return response.json()


async def _create_genre(client: AsyncClient, name: str) -> dict:
    response = await client.post('/genres', json={'name': name})
    return response.json()


async def test_create_book_with_genres(client: AsyncClient) -> None:
    author = await _create_author(client)
    g1 = await _create_genre(client, 'роман')
    g2 = await _create_genre(client, 'классика')

    response = await client.post(
        '/books',
        json={
            'title': 'Война и мир',
            'author_id': author['id'],
            'genre_ids': [g1['id'], g2['id']],
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert 'genre_ids' not in body
    returned = {g['id']: g['name'] for g in body['genres']}
    assert returned == {g1['id']: g1['name'], g2['id']: g2['name']}


async def test_create_book_without_genres_defaults_empty(client: AsyncClient) -> None:
    author = await _create_author(client)

    response = await client.post('/books', json={'title': 't', 'author_id': author['id']})

    assert response.status_code == 201
    assert response.json()['genres'] == []


async def test_update_book_replaces_genres(client: AsyncClient) -> None:
    author = await _create_author(client)
    g1 = await _create_genre(client, 'роман')
    g2 = await _create_genre(client, 'классика')
    g3 = await _create_genre(client, 'драма')

    created = (
        await client.post(
            '/books',
            json={
                'title': 't',
                'author_id': author['id'],
                'genre_ids': [g1['id'], g2['id']],
            },
        )
    ).json()

    response = await client.put(
        f'/books/{created["id"]}',
        json={'title': 't', 'author_id': author['id'], 'genre_ids': [g3['id']]},
    )

    assert response.status_code == 200
    ids = [g['id'] for g in response.json()['genres']]
    assert ids == [g3['id']]


async def test_update_book_clears_genres(client: AsyncClient) -> None:
    author = await _create_author(client)
    g1 = await _create_genre(client, 'роман')
    created = (
        await client.post(
            '/books',
            json={'title': 't', 'author_id': author['id'], 'genre_ids': [g1['id']]},
        )
    ).json()

    response = await client.put(
        f'/books/{created["id"]}',
        json={'title': 't', 'author_id': author['id'], 'genre_ids': []},
    )

    assert response.status_code == 200
    assert response.json()['genres'] == []


async def test_create_book_with_unknown_genre(client: AsyncClient) -> None:
    author = await _create_author(client)

    response = await client.post(
        '/books',
        json={
            'title': 't',
            'author_id': author['id'],
            'genre_ids': [str(uuid4())],
        },
    )

    assert response.status_code == 422


async def test_delete_book_retains_association(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    author = await _create_author(client)
    g1 = await _create_genre(client, 'роман')
    created = (
        await client.post(
            '/books',
            json={'title': 't', 'author_id': author['id'], 'genre_ids': [g1['id']]},
        )
    ).json()

    await client.delete(f'/books/{created["id"]}')

    assert (await client.get(f'/books/{created["id"]}')).status_code == 404
    assert (await client.get(f'/genres/{g1["id"]}')).json()['books'] == []
    count = await db_session.scalar(select(func.count()).select_from(book_genres))
    assert count == 1


async def test_delete_genre_retains_association(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    author = await _create_author(client)
    g1 = await _create_genre(client, 'роман')
    book = (
        await client.post(
            '/books',
            json={'title': 't', 'author_id': author['id'], 'genre_ids': [g1['id']]},
        )
    ).json()

    await client.delete(f'/genres/{g1["id"]}')

    assert (await client.get(f'/genres/{g1["id"]}')).status_code == 404
    assert (await client.get(f'/books/{book["id"]}')).json()['genres'] == []
    count = await db_session.scalar(select(func.count()).select_from(book_genres))
    assert count == 1


async def test_delete_author_soft_cascades_books(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    author = await _create_author(client)
    g1 = await _create_genre(client, 'роман')
    book = (
        await client.post(
            '/books',
            json={'title': 't', 'author_id': author['id'], 'genre_ids': [g1['id']]},
        )
    ).json()

    await client.delete(f'/authors/{author["id"]}')

    assert (await client.get(f'/authors/{author["id"]}')).status_code == 404
    assert (await client.get(f'/books/{book["id"]}')).status_code == 404
    count = await db_session.scalar(select(func.count()).select_from(book_genres))
    assert count == 1
