from sqlalchemy import event
from sqlalchemy.orm import ORMExecuteState, Session, with_loader_criteria

from src.models.base import Base


@event.listens_for(Session, 'do_orm_execute')
def _filter_soft_deleted(execute_state: ORMExecuteState) -> None:
    if (
        execute_state.is_select
        and not execute_state.is_column_load
        and not execute_state.is_relationship_load
        and not execute_state.execution_options.get('include_deleted', False)
    ):
        execute_state.statement = execute_state.statement.options(
            with_loader_criteria(
                Base,
                lambda cls: cls.is_deleted.is_(False),
                include_aliases=True,
            )
        )
