from __future__ import annotations

import re
import unicodedata
from typing import Annotated

from pydantic import BeforeValidator, StringConstraints

_WHITESPACE_RE = re.compile(r'\s+')
_WORD_START_RE = re.compile(r'\b\w')
_INVISIBLE_CHARS = dict.fromkeys(
    map(ord, '​‌‍⁠﻿'),
    None,
)


def _clean(value: str) -> str:
    value = value.translate(_INVISIBLE_CHARS)
    value = unicodedata.normalize('NFC', value)
    return _WHITESPACE_RE.sub(' ', value).strip()


def _dedup_key(value: object) -> object:
    if not isinstance(value, str):
        return value
    return _clean(value).casefold().replace('ё', 'е')


def _person_name(value: object) -> object:
    if not isinstance(value, str):
        return value
    cleaned = _clean(value).casefold()
    return _WORD_START_RE.sub(lambda match: match.group().upper(), cleaned)


def _plain_text(value: object) -> object:
    if not isinstance(value, str):
        return value
    return _clean(value)


DedupName = Annotated[
    str,
    BeforeValidator(_dedup_key),
    StringConstraints(min_length=1, max_length=128),
]
PersonName = Annotated[
    str,
    BeforeValidator(_person_name),
    StringConstraints(min_length=1, max_length=128),
]
ShortText = Annotated[
    str,
    BeforeValidator(_plain_text),
    StringConstraints(min_length=1, max_length=255),
]
LongText = Annotated[
    str,
    BeforeValidator(_plain_text),
    StringConstraints(min_length=1, max_length=2000),
]
