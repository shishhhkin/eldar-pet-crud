from fastapi import FastAPI

from src.exceptions import AppError
from src.exceptions.handlers.app_error import app_error_handler
from src.exceptions.handlers.unhandled import unhandled_error_handler


def register_exception_handlers(app: FastAPI) -> None:
    app.exception_handler(AppError)(app_error_handler)
    app.exception_handler(Exception)(unhandled_error_handler)


__all__ = ['register_exception_handlers']
