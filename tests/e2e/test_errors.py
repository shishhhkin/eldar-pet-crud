from uuid import uuid4

from httpx import AsyncClient


async def test_request_id_generated_when_missing(client: AsyncClient) -> None:
    response = await client.get(f'/authors/{uuid4()}')

    rid = response.headers.get('X-Request-ID')
    assert rid
    assert response.json()['request_id'] == rid


async def test_request_id_echoed_from_header(client: AsyncClient) -> None:
    response = await client.get(
        f'/authors/{uuid4()}', headers={'X-Request-ID': 'trace-abc'}
    )

    assert response.headers['X-Request-ID'] == 'trace-abc'
    assert response.json()['request_id'] == 'trace-abc'


async def test_not_found_error_shape(client: AsyncClient) -> None:
    missing_id = uuid4()
    response = await client.get(f'/authors/{missing_id}')

    assert response.status_code == 404
    body = response.json()
    assert body['code'] == 'not_found'
    assert str(missing_id) in body['detail']
    assert body['request_id']


async def test_validation_error_shape_for_unknown_genre(client: AsyncClient) -> None:
    author = (await client.post('/authors', json={'name': 'A', 'bio': None})).json()
    missing_genre_id = uuid4()

    response = await client.post(
        '/books',
        json={
            'title': 'T',
            'author_id': author['id'],
            'genre_ids': [str(missing_genre_id)],
        },
    )

    assert response.status_code == 422
    body = response.json()
    assert body['code'] == 'validation_error'
    assert str(missing_genre_id) in body['detail']
    assert body['request_id']
