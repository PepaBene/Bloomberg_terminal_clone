"""API tests for custom data environment endpoints (Pillar 2 Supplement – Part 6)."""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.custom_data import CustomFieldDefinition


@pytest.mark.asyncio
async def test_create_custom_field(client: AsyncClient):
    resp = await client.post("/v1/analytics/custom-fields", json={
        "name": "PE Relative",
        "expression": "PE_RATIO / 15",
        "field_type": "NUMERIC",
        "scope": "PRIVATE",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "PE Relative"
    assert data["is_valid"] is True
    assert "PE_RATIO" in (data.get("depends_on") or [])


@pytest.mark.asyncio
async def test_create_invalid_field(client: AsyncClient):
    resp = await client.post("/v1/analytics/custom-fields", json={
        "name": "Bad Field",
        "expression": "1 + + 2",
        "field_type": "NUMERIC",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["is_valid"] is False
    assert data["validation_error"] is not None


@pytest.mark.asyncio
async def test_list_custom_fields(client: AsyncClient, session: AsyncSession):
    field = CustomFieldDefinition(
        field_id=uuid.uuid4(),
        name="Test List Field",
        expression="1 + 1",
        field_type="NUMERIC",
        scope="SHARED",
        is_valid=True,
    )
    session.add(field)
    await session.commit()

    resp = await client.get("/v1/analytics/custom-fields", params={"scope": "SHARED"})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1


@pytest.mark.asyncio
async def test_get_custom_field(client: AsyncClient, session: AsyncSession):
    fid = uuid.uuid4()
    field = CustomFieldDefinition(
        field_id=fid,
        name="Test Get Field",
        expression="42",
        field_type="NUMERIC",
        scope="PRIVATE",
        is_valid=True,
    )
    session.add(field)
    await session.commit()

    resp = await client.get(f"/v1/analytics/custom-fields/{fid}")
    assert resp.status_code == 200
    assert resp.json()["name"] == "Test Get Field"


@pytest.mark.asyncio
async def test_get_custom_field_not_found(client: AsyncClient):
    fake_id = uuid.uuid4()
    resp = await client.get(f"/v1/analytics/custom-fields/{fake_id}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_validate_expression(client: AsyncClient):
    resp = await client.get(
        "/v1/analytics/custom-fields/validate",
        params={"expression": "PE_RATIO * 2"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_valid"] is True
    assert "PE_RATIO" in data["dependencies"]


@pytest.mark.asyncio
async def test_validate_invalid_expression(client: AsyncClient):
    resp = await client.get(
        "/v1/analytics/custom-fields/validate",
        params={"expression": "1 / / 2"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_valid"] is False


@pytest.mark.asyncio
async def test_compute_field_value(client: AsyncClient, session: AsyncSession):
    fid = uuid.uuid4()
    field = CustomFieldDefinition(
        field_id=fid,
        name="Computable",
        expression="2 + 3",
        field_type="NUMERIC",
        scope="PRIVATE",
        is_valid=True,
    )
    session.add(field)
    await session.commit()

    resp = await client.post(f"/v1/analytics/custom-fields/{fid}/compute")
    assert resp.status_code == 200
    data = resp.json()
    assert data["value_numeric"] == pytest.approx(5.0)


@pytest.mark.asyncio
async def test_delete_custom_field(client: AsyncClient, session: AsyncSession):
    fid = uuid.uuid4()
    field = CustomFieldDefinition(
        field_id=fid,
        name="To Delete",
        expression="1",
        field_type="NUMERIC",
        scope="PRIVATE",
        is_valid=True,
    )
    session.add(field)
    await session.commit()

    resp = await client.delete(f"/v1/analytics/custom-fields/{fid}")
    assert resp.status_code == 204
