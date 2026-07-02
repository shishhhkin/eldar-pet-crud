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
    value = value.translate(_INVISIBLE_CHARS)
    value = unicodedata.normalize('NFC', value)
    return _WHITESPACE_RE.sub(' ', value).strip()


def normalize_text(value: object) -> object:
    if not isinstance(value, str):
        return value
    return clean_text(value)


def dedup_key(value: object) -> object:
    if not isinstance(value, str):
        return value
    return clean_text(value).casefold().replace('ё', 'е')


def forbid_null(value: object) -> object:
    if value is None:
        raise PydanticCustomError('not_nullable', 'Value must not be null')
    return value
