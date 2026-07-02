from fastapi.responses import JSONResponse

from src.middleware import REQUEST_ID_HEADER


def error_response(status_code: int, code: str, detail: str, rid: str | None) -> JSONResponse:
    headers = {REQUEST_ID_HEADER: rid} if rid else None
    return JSONResponse(
        status_code=status_code,
        content={'code': code, 'detail': detail, 'request_id': rid},
        headers=headers,
    )
