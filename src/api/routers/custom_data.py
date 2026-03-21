"""Custom Data Environment API endpoints (Pillar 2 Supplement – Part 6)."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_session
from src.engines.expression_parser import evaluate, validate, ParseError, EvalError
from src.models.custom_data import CustomFieldDefinition, CustomFieldValue
from src.schemas.custom_data import (
    CreateCustomFieldRequest,
    CustomFieldDefinitionResponse,
    CustomFieldValueResponse,
    ValidateExpressionRequest,
    ValidateExpressionResponse,
)

router = APIRouter(tags=["Custom Data"])


@router.post(
    "/analytics/custom-fields",
    response_model=CustomFieldDefinitionResponse,
    status_code=201,
)
async def create_custom_field(
    body: CreateCustomFieldRequest,
    session: AsyncSession = Depends(get_session),
):
    """Create a new custom computed field."""
    # Validate expression
    validation = validate(body.expression)

    field = CustomFieldDefinition(
        field_id=uuid.uuid4(),
        name=body.name,
        description=body.description,
        expression=body.expression,
        field_type=body.field_type.upper(),
        scope=body.scope.upper(),
        is_valid=validation["is_valid"],
        validation_error=validation.get("error"),
        depends_on=validation.get("dependencies"),
    )
    session.add(field)
    await session.commit()
    await session.refresh(field)
    return field


@router.get(
    "/analytics/custom-fields",
    response_model=list[CustomFieldDefinitionResponse],
)
async def list_custom_fields(
    session: AsyncSession = Depends(get_session),
    scope: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
):
    """List all custom field definitions."""
    query = select(CustomFieldDefinition).limit(limit)
    if scope:
        query = query.where(CustomFieldDefinition.scope == scope.upper())
    query = query.order_by(CustomFieldDefinition.name)

    result = await session.execute(query)
    return result.scalars().all()


@router.get(
    "/analytics/custom-fields/validate",
    response_model=ValidateExpressionResponse,
)
async def validate_expression_endpoint(
    expression: str = Query(..., min_length=1),
):
    """Validate a custom field expression."""
    result = validate(expression)
    return ValidateExpressionResponse(**result)


@router.get(
    "/analytics/custom-fields/{field_id}",
    response_model=CustomFieldDefinitionResponse,
)
async def get_custom_field(
    field_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get a custom field definition by ID."""
    result = await session.execute(
        select(CustomFieldDefinition).where(CustomFieldDefinition.field_id == field_id)
    )
    field = result.scalar_one_or_none()
    if not field:
        raise HTTPException(status_code=404, detail="Custom field not found")
    return field


@router.post(
    "/analytics/custom-fields/{field_id}/compute",
    response_model=CustomFieldValueResponse,
)
async def compute_field_value(
    field_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    context: dict[str, float] | None = None,
):
    """Compute a custom field value with given context."""
    result = await session.execute(
        select(CustomFieldDefinition).where(CustomFieldDefinition.field_id == field_id)
    )
    field = result.scalar_one_or_none()
    if not field:
        raise HTTPException(status_code=404, detail="Custom field not found")

    if not field.is_valid:
        raise HTTPException(status_code=400, detail=f"Invalid expression: {field.validation_error}")

    try:
        value = evaluate(field.expression, context or {})
    except (ParseError, EvalError) as e:
        raise HTTPException(status_code=400, detail=f"Evaluation error: {e}")

    # Store computed value
    fv = CustomFieldValue(
        id=uuid.uuid4(),
        field_id=field_id,
        value_numeric=value if field.field_type == "NUMERIC" else None,
        value_boolean=bool(value) if field.field_type == "BOOLEAN" else None,
        value_string=str(value) if field.field_type == "STRING" else None,
    )
    session.add(fv)
    await session.commit()
    await session.refresh(fv)
    return fv


@router.delete(
    "/analytics/custom-fields/{field_id}",
    status_code=204,
)
async def delete_custom_field(
    field_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Delete a custom field definition."""
    result = await session.execute(
        select(CustomFieldDefinition).where(CustomFieldDefinition.field_id == field_id)
    )
    field = result.scalar_one_or_none()
    if not field:
        raise HTTPException(status_code=404, detail="Custom field not found")
    await session.delete(field)
    await session.commit()
