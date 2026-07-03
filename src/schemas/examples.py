from __future__ import annotations

from typing import Any

_ID_EXAMPLE = '3fa85f64-5717-4562-b3fc-2c963f66afa6'

BOOK_PAYLOAD_EXAMPLE: dict[str, Any] = {'title': 'Война и мир'}
BOOK_READ_EXAMPLE: dict[str, Any] = {'id': _ID_EXAMPLE, 'title': 'Война и мир'}

MOOD_PAYLOAD_EXAMPLE: dict[str, Any] = {'name': 'Меланхоличное'}
MOOD_READ_EXAMPLE: dict[str, Any] = {'id': _ID_EXAMPLE, 'name': 'Меланхоличное'}

AUTHOR_CREATE_EXAMPLES: dict[str, Any] = {
    'with_books': {
        'summary': 'С книгами',
        'value': {
            'name': 'Лев Толстой',
            'bio': 'Русский писатель, классик мировой литературы.',
            'books': [{'title': 'Война и мир'}, {'title': 'Анна Каренина'}],
        },
    },
    'without_books': {
        'summary': 'Без книг',
        'value': {
            'name': 'Лев Толстой',
            'bio': 'Русский писатель, классик мировой литературы.',
        },
    },
}
AUTHOR_UPDATE_EXAMPLES: dict[str, Any] = {
    'name_and_bio': {
        'summary': 'Имя и био',
        'value': {
            'name': 'Лев Николаевич Толстой',
            'bio': 'Русский писатель, классик мировой литературы.',
        },
    },
    'bio_only': {
        'summary': 'Только био',
        'value': {'bio': 'Граф, писатель и мыслитель.'},
    },
    'books_only': {
        'summary': 'Только книги (замена)',
        'value': {'books': [{'title': 'Воскресение'}]},
    },
}
AUTHOR_READ_EXAMPLE: dict[str, Any] = {
    'id': _ID_EXAMPLE,
    'name': 'Лев Толстой',
    'bio': 'Русский писатель, классик мировой литературы.',
    'books': [BOOK_READ_EXAMPLE],
}

GENRE_CREATE_EXAMPLES: dict[str, Any] = {
    'multiple_moods': {
        'summary': 'С несколькими настроениями',
        'value': {
            'name': 'Фэнтези',
            'moods': [{'name': 'Меланхоличное'}, {'name': 'Атмосферное'}],
        },
    },
    'single_mood': {
        'summary': 'С одним настроением',
        'value': {'name': 'Детектив', 'moods': [{'name': 'Напряжённое'}]},
    },
}
GENRE_UPDATE_EXAMPLES: dict[str, Any] = {
    'both': {
        'summary': 'Имя и настроения',
        'value': {'name': 'Фэнтези', 'moods': [{'name': 'Меланхоличное'}]},
    },
    'name_only': {
        'summary': 'Только имя',
        'value': {'name': 'Фэнтези'},
    },
    'moods_only': {
        'summary': 'Только настроения',
        'value': {'moods': [{'name': 'Атмосферное'}]},
    },
}
GENRE_READ_EXAMPLE: dict[str, Any] = {
    'id': _ID_EXAMPLE,
    'name': 'Фэнтези',
    'moods': [MOOD_READ_EXAMPLE],
}

PROFILE_PAYLOAD_EXAMPLE: dict[str, Any] = {
    'avatar_url': 'https://example.com/avatars/john.png',
    'bio': 'Книжный энтузиаст и коллекционер фантастики',
    'socials': {'telegram': '@john_doe', 'github': 'johndoe'},
}
PROFILE_READ_EXAMPLE: dict[str, Any] = {'id': _ID_EXAMPLE, **PROFILE_PAYLOAD_EXAMPLE}
USER_CREATE_EXAMPLES: dict[str, Any] = {
    'full': {
        'summary': 'Полный профиль',
        'value': {
            'username': 'john_doe',
            'email': 'john@example.com',
            'profile': PROFILE_PAYLOAD_EXAMPLE,
        },
    },
    'minimal': {
        'summary': 'Минимальный профиль',
        'value': {
            'username': 'jane_doe',
            'email': 'jane@example.com',
            'profile': {'bio': 'Любитель научпопа'},
        },
    },
}
USER_UPDATE_EXAMPLES: dict[str, Any] = {
    'email_only': {
        'summary': 'Только email',
        'value': {'email': 'john.doe@example.com'},
    },
    'username_only': {
        'summary': 'Только username',
        'value': {'username': 'john_doe_2'},
    },
    'profile_only': {
        'summary': 'Только профиль',
        'value': {'profile': PROFILE_PAYLOAD_EXAMPLE},
    },
}
USER_READ_EXAMPLE: dict[str, Any] = {
    'id': _ID_EXAMPLE,
    'username': 'john_doe',
    'email': 'john@example.com',
    'created_at': '2026-01-15T10:30:00Z',
    'profile': PROFILE_READ_EXAMPLE,
}
