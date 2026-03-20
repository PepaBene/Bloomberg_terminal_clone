"""Sort parameter parsing for API endpoints (Spec 17.2).

Supports sort expressions via query parameter:
    ?sort=name           # ascending by name
    ?sort=-fiscal_year   # descending by fiscal_year
    ?sort=-fiscal_year,name  # multi-field sort

Prefix ``-`` indicates descending order.
"""

import logging

from sqlalchemy import asc, desc

logger = logging.getLogger(__name__)


def parse_sort_param(sort_param: str | None) -> list[tuple[str, str]]:
    """Parse a sort string into a list of (field_name, direction) tuples.

    Parameters
    ----------
    sort_param : str or None
        Comma-separated sort fields, e.g. ``"-fiscal_year,name"``.

    Returns
    -------
    list[tuple[str, str]]
        Each element is ``(field_name, "asc"|"desc")``.
    """
    if not sort_param:
        return []

    result = []
    for field in sort_param.split(","):
        field = field.strip()
        if not field:
            continue
        if field.startswith("-"):
            result.append((field[1:], "desc"))
        else:
            result.append((field, "asc"))
    return result


def apply_sorting(query, model_class, sort_param: str | None, *, allowed_fields: set[str] | None = None):
    """Apply sort expressions to a SQLAlchemy query.

    Parameters
    ----------
    query : Select
        The SQLAlchemy select statement to sort.
    model_class : type
        The model class to resolve column names against.
    sort_param : str or None
        Raw sort parameter from the request.
    allowed_fields : set[str], optional
        Whitelist of sortable field names.  If provided, unknown fields are
        silently ignored.

    Returns
    -------
    Select
        The sorted query.
    """
    sort_fields = parse_sort_param(sort_param)

    for field_name, direction in sort_fields:
        if allowed_fields and field_name not in allowed_fields:
            logger.debug("Ignoring non-sortable field: %s", field_name)
            continue

        column = getattr(model_class, field_name, None)
        if column is None:
            logger.debug("Ignoring unknown sort field: %s", field_name)
            continue

        if direction == "desc":
            query = query.order_by(desc(column))
        else:
            query = query.order_by(asc(column))

    return query
