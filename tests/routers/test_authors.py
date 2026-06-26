from uuid import UUID, uuid4

from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.books import BookModel
from src.repository import Repo
from src.schemas.authors import _MAX_BOOKS_PER_AUTHOR


def _payload(
    name: str = 'Лев Толстой',
    bio: str | None = 'русский писатель',
    *,
    books: list[dict] | None = None,
) -> dict:
    return {'name': name, 'bio': bio, 'books': books if books is not None else []}


async def test_create_author(client: AsyncClient) -> None:
    response = await client.post('/authors', json=_payload())

    assert response.status_code == 201
    body = response.json()
    assert body['name'] == 'Лев Толстой'
    assert body['bio'] == 'русский писатель'
    assert body['books'] == []
    assert 'id' in body


async def test_create_author_without_bio(client: AsyncClient) -> None:
    response = await client.post('/authors', json={'name': 'Аноним'})

    assert response.status_code == 201
    assert response.json()['bio'] is None


async def test_create_author_with_nested_books(client: AsyncClient) -> None:
    response = await client.post(
        '/authors',
        json=_payload(books=[{'title': 'Война и мир'}, {'title': 'Анна Каренина'}]),
    )

    assert response.status_code == 201
    body = response.json()
    titles = [book['title'] for book in body['books']]
    assert titles == ['Война и мир', 'Анна Каренина']
    for book in body['books']:
        assert 'id' in book
        assert 'author_id' not in book


async def test_read_author(client: AsyncClient) -> None:
    created = (
        await client.post('/authors', json=_payload(books=[{'title': 'Война и мир'}]))
    ).json()

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


async def test_update_author_scalar_fields(client: AsyncClient) -> None:
    created = (await client.post('/authors', json=_payload())).json()

    response = await client.patch(
        f'/authors/{created["id"]}',
        json=_payload(name='Л. Н. Толстой', bio=None),
    )

    assert response.status_code == 200
    body = response.json()
    assert body['id'] == created['id']
    assert body['name'] == 'Л. Н. Толстой'
    assert body['bio'] is None


async def test_update_author_name_only_preserves_fields(client: AsyncClient) -> None:
    created = (
        await client.post(
            '/authors',
            json=_payload(bio='русский писатель', books=[{'title': 'Война и мир'}]),
        )
    ).json()

    response = await client.patch(f'/authors/{created["id"]}', json={'name': 'Л. Н. Толстой'})

    assert response.status_code == 200
    body = response.json()
    assert body['name'] == 'Л. Н. Толстой'
    assert body['bio'] == 'русский писатель'
    assert body['books'] == created['books']


async def test_update_author_rejects_null_name(client: AsyncClient) -> None:
    created = (await client.post('/authors', json=_payload())).json()

    response = await client.patch(f'/authors/{created["id"]}', json={'name': None})

    assert response.status_code == 422


async def test_update_author_replaces_books(client: AsyncClient) -> None:
    created = (await client.post('/authors', json=_payload(books=[{'title': 'Старое'}]))).json()

    response = await client.patch(
        f'/authors/{created["id"]}',
        json=_payload(books=[{'title': 'Новое'}]),
    )

    assert response.status_code == 200
    body = response.json()
    assert [book['title'] for book in body['books']] == ['Новое']
    assert body['books'][0]['id'] != created['books'][0]['id']


async def test_update_author_clears_books(client: AsyncClient) -> None:
    created = (
        await client.post('/authors', json=_payload(books=[{'title': 'Война и мир'}]))
    ).json()

    response = await client.patch(f'/authors/{created["id"]}', json=_payload(books=[]))

    assert response.status_code == 200
    assert response.json()['books'] == []


async def test_update_author_hard_deletes_replaced_books(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    created = (await client.post('/authors', json=_payload(books=[{'title': 'Старое'}]))).json()

    await client.patch(f'/authors/{created["id"]}', json=_payload(books=[{'title': 'Новое'}]))

    rows = (await db_session.execute(select(BookModel))).scalars().all()
    assert [book.title for book in rows] == ['Новое']


async def test_update_author_not_found(client: AsyncClient) -> None:
    response = await client.patch(f'/authors/{uuid4()}', json=_payload())

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


async def test_delete_author_soft_cascades_books(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    created = (
        await client.post(
            '/authors',
            json=_payload(books=[{'title': 'Первая'}, {'title': 'Вторая'}]),
        )
    ).json()

    book_repo = Repo(db_session, BookModel)

    count_before = await db_session.scalar(select(func.count()).select_from(BookModel))
    assert count_before == 2

    await client.delete(f'/authors/{created["id"]}')

    visible = (await db_session.execute(book_repo.select())).scalars().all()
    assert visible == []

    rows = (await db_session.execute(select(BookModel))).scalars().all()
    assert len(rows) == 2
    assert all(book.is_deleted for book in rows)


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


async def test_create_author_strips_book_title(client: AsyncClient) -> None:
    response = await client.post('/authors', json=_payload(books=[{'title': '  Война и мир  '}]))

    assert response.status_code == 201
    assert response.json()['books'][0]['title'] == 'Война и мир'


async def test_create_author_empty_book_title(client: AsyncClient) -> None:
    response = await client.post('/authors', json=_payload(books=[{'title': ''}]))

    assert response.status_code == 422


async def test_create_author_too_many_books(client: AsyncClient) -> None:
    books = [{'title': f'book_{i}'} for i in range(_MAX_BOOKS_PER_AUTHOR + 1)]

    response = await client.post('/authors', json=_payload(books=books))

    assert response.status_code == 422


async def test_create_author_max_books_allowed(client: AsyncClient) -> None:
    books = [{'title': f'book_{i}'} for i in range(_MAX_BOOKS_PER_AUTHOR)]

    response = await client.post('/authors', json=_payload(books=books))

    assert response.status_code == 201
    assert len(response.json()['books']) == _MAX_BOOKS_PER_AUTHOR


async def test_update_author_too_many_books(client: AsyncClient) -> None:
    created = (await client.post('/authors', json=_payload())).json()
    books = [{'title': f'book_{i}'} for i in range(_MAX_BOOKS_PER_AUTHOR + 1)]

    response = await client.patch(f'/authors/{created["id"]}', json={'books': books})

    assert response.status_code == 422


async def test_delete_author_soft_retains_book_row(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    created = (
        await client.post('/authors', json=_payload(books=[{'title': 'Война и мир'}]))
    ).json()
    book_id = created['books'][0]['id']

    await client.delete(f'/authors/{created["id"]}')

    book = await db_session.get(BookModel, UUID(book_id))
    assert book is not None
    assert book.is_deleted is True
