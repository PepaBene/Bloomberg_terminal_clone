"""Advanced query filtering for API endpoints (Spec 17.2).

Supports filter operators via query parameter suffixes:
    ?status__eq=ACTIVE
    ?country__in=US,GB,DE
    ?fiscal_year__gte=2020
    ?name__contains=Apple

Operators: eq, ne, gt, lt, gte, lte, in, contains, startswith
"""

import logging
from typing import Any

from fastapi import Query, Request
from sqlalchemy import Column, and_

logger = logging.getLogger(__name__)


def escape_like(value: str) -> str:
    """Escape SQL LIKE/ILIKE metacharacters."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


# Supported filter operators
OPERATORS = {"eq", "ne", "gt", "lt", "gte", "lte", "in", "contains", "startswith"}


def parse_filter_params(request: Request) -> dict[str, list[tuple[str, str, str]]]:
    """Parse filter parameters from the request query string.

    Returns a dict mapping field_name -> [(operator, value), ...].
    """
    filters: dict[str, list[tuple[str, str, str]]] = {}
    for key, value in request.query_params.items():
        # Skip pagination / known non-filter params
        if key in ("page", "page_size", "sort", "fields", "q"):
            continue

        if "__" in key:
            field_name, operator = key.rsplit("__", 1)
            if operator not in OPERATORS:
                continue
        else:
            field_name = key
            operator = "eq"

        filters.setdefault(field_name, []).append((field_name, operator, value))

    return filters


def apply_filters(query, model_class, filters: dict[str, list[tuple[str, str, str]]]):
    """Apply parsed filter expressions to a SQLAlchemy query.

    Parameters
    ----------
    query : Select
        The SQLAlchemy select statement to filter.
    model_class : type
        The model class to resolve column names against.
    filters : dict
        Output from ``parse_filter_params()``.

    Returns
    -------
    Select
        The filtered query.
    """
    conditions = []
    for field_name, expressions in filters.items():
        column = getattr(model_class, field_name, None)
        if column is None:
            logger.debug("Ignoring unknown filter field: %s", field_name)
            continue

        for _, operator, value in expressions:
            if operator == "eq":
                conditions.append(column == value)
            elif operator == "ne":
                conditions.append(column != value)
            elif operator == "gt":
                conditions.append(column > value)
            elif operator == "lt":
                conditions.append(column < value)
            elif operator == "gte":
                conditions.append(column >= value)
            elif operator == "lte":
                conditions.append(column <= value)
            elif operator == "in":
                values = [v.strip() for v in value.split(",")]
                conditions.append(column.in_(values))
            elif operator == "contains":
                conditions.append(column.ilike(f"%{escape_like(value)}%"))
            elif operator == "startswith":
                conditions.append(column.ilike(f"{escape_like(value)}%"))

    if conditions:
        query = query.where(and_(*conditions))

    return query
