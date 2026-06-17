from uuid import uuid4

from httpx import AsyncClient


async def test_request_id_generated_when_missing(client: AsyncClient) -> None:
    response = await client.get(f'/authors/{uuid4()}')

    rid = response.headers.get('X-Request-ID')
    assert rid
    assert response.json()['request_id'] == rid


async def test_request_id_echoed_from_header(client: AsyncClient) -> None:
    response = await client.get(f'/authors/{uuid4()}', headers={'X-Request-ID': 'trace-abc'})

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
