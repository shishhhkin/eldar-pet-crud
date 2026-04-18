# Базовый класс для всех ORM-моделей сервиса.
#
# Вынесен в отдельный модуль, чтобы:
# - избежать циклических импортов между моделями;
# - дать alembic/env.py одну стабильную точку импорта (`Base.metadata`);
# - не плодить разные MetaData в разных модулях.
import sqlalchemy as sa
from sqlalchemy.orm import DeclarativeBase

# Соглашение об именовании ограничений/индексов. Нужно, чтобы alembic autogenerate
# стабильно именовал PK/FK/UQ/IX/CK — иначе миграции на эти объекты плавают.
NAMING_CONVENTION = {
    'ix': 'ix_%(column_0_label)s',
    'uq': 'uq_%(table_name)s_%(column_0_name)s',
    'ck': 'ck_%(table_name)s_%(constraint_name)s',
    'fk': 'fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s',
    'pk': 'pk_%(table_name)s',
}


class Base(DeclarativeBase):
    """Базовый класс для всех моделей сервиса."""

    metadata = sa.MetaData(naming_convention=NAMING_CONVENTION)

    @classmethod
    def on_conflict_constraint(cls) -> tuple | None:
        return None
