from typing import Tuple, List

from flask_sqlalchemy.query import Query
from sqlalchemy import Subquery, func

from tools import rpc_tools, db


def add_pins_with_priority(
        original_query,
        project_id: int,
        entity: db.Base,
) -> Tuple[Query, List[str]]:
    """
    Add project-wide pin status to query results and ensure pinned items appear first.
    Pinned items are ordered by updated_at DESC (most recently pinned first), then unpinned items follow.

    :param original_query: Original SQLAlchemy query
    :param project_id: Project ID
    :param entity: Entity model with pins_entity_name attribute
    :return: Tuple of (modified query, list of column names added)
    """
    Pin = rpc_tools.RpcMixin().rpc.timeout(2).social_get_pin_model()

    pins_subquery: Subquery = (
        db.session.query(
            Pin.entity_id,
            func.coalesce(func.bool_or(True), False).label('is_pinned'),
            func.max(Pin.updated_at).label('pin_updated_at')
        )
        .filter(
            Pin.entity == entity.pins_entity_name,
            Pin.project_id == project_id,
        )
        .group_by(Pin.entity_id)
        .subquery()
    )

    mutated_query = (
        original_query
        .outerjoin(pins_subquery, pins_subquery.c.entity_id == entity.id)
        .add_columns(
            func.coalesce(pins_subquery.c.is_pinned, False),
            pins_subquery.c.pin_updated_at
        )
    )

    return mutated_query, ['is_pinned', 'pin_updated_at']

