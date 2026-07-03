from __future__ import annotations

import re
import unicodedata

from pydantic_core import PydanticCustomError

_WHITESPACE_RE = re.compile(r'\s+')
_INVISIBLE_CHARS = dict.fromkeys(
    map(ord, '​‌‍⁠﻿'),
    None,
)


def clean_text(value: str) -> str:
    """Убирает невидимые символы, приводит к NFC, схлопывает пробелы и обрезает края"""
    value = value.translate(_INVISIBLE_CHARS)
    value = unicodedata.normalize('NFC', value)
    return _WHITESPACE_RE.sub(' ', value).strip()


def normalize_text(value: object) -> object:
    """Чистит строку через clean_text для хранения; не-строки возвращает без изменений"""
    if not isinstance(value, str):
        return value
    return clean_text(value)


def normalize_key(value: object) -> object:
    """Канонический регистронезависимый вид (casefold + ё -> е) для сравнения и уникальности"""
    if not isinstance(value, str):
        return value
    return clean_text(value).casefold().replace('ё', 'е')


def forbid_null(value: object) -> object:
    """Отклоняет явный null в PATCH-полях, отличая его от «поле не передано»"""
    if value is None:
        raise PydanticCustomError('not_nullable', 'Value must not be null')
    return value
