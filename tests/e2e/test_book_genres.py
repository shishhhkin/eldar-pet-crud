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

    response = await client.post(
        '/books', json={'title': 't', 'author_id': author['id']}
    )

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


async def test_delete_book_cleans_association(
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

    count_before = await db_session.scalar(select(func.count()).select_from(book_genres))
    assert count_before == 1

    await client.delete(f'/books/{created["id"]}')

    count_after = await db_session.scalar(select(func.count()).select_from(book_genres))
    assert count_after == 0


async def test_delete_genre_cleans_association(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    author = await _create_author(client)
    g1 = await _create_genre(client, 'роман')
    await client.post(
        '/books',
        json={'title': 't', 'author_id': author['id'], 'genre_ids': [g1['id']]},
    )

    await client.delete(f'/genres/{g1["id"]}')

    count = await db_session.scalar(select(func.count()).select_from(book_genres))
    assert count == 0


async def test_delete_author_cascades_books_and_associations(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    author = await _create_author(client)
    g1 = await _create_genre(client, 'роман')
    await client.post(
        '/books',
        json={'title': 't', 'author_id': author['id'], 'genre_ids': [g1['id']]},
    )

    await client.delete(f'/authors/{author["id"]}')

    count = await db_session.scalar(select(func.count()).select_from(book_genres))
    assert count == 0
