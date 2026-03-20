"""Full end-to-end API test with seeded data against SQLite."""

import asyncio
import os
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

DB_PATH = Path("e2e_api_test.db")
DB_PATH.unlink(missing_ok=True)  # Clean start

os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{DB_PATH}"

from sqlalchemy import event
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.types import JSON

from src.models.base import Base

import src.models.reference  # noqa: F401
import src.models.entity  # noqa: F401
import src.models.security  # noqa: F401
import src.models.quality  # noqa: F401
import src.models.governance  # noqa: F401


@event.listens_for(Base.metadata, "before_create")
def remap(target, connection, **kw):
    if connection.dialect.name == "sqlite":
        for table in target.tables.values():
            for col in table.columns:
                if isinstance(col.type, JSONB):
                    col.type = JSON()


async def main():
    engine = create_async_engine(f"sqlite+aiosqlite:///{DB_PATH}", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # Seed reference data
    from src.ingestion.reference_loader import load_all_reference_data

    async with sf() as session:
        await load_all_reference_data(session)

    # Seed entity + security
    from src.models.entity import Entity, EntityIdentifier
    from src.models.security import Security, SecurityIdentifier

    entity_id = uuid.uuid4()
    security_id = uuid.uuid4()

    async with sf() as session:
        entity = Entity(
            entity_id=entity_id,
            entity_type="PUBLIC_COMPANY",
            legal_name="Apple Inc.",
            short_name="Apple",
            status="ACTIVE",
            incorporation_country="US",
            source="SEC_EDGAR",
            confidence_score=0.99,
        )
        session.add(entity)
        session.add(
            EntityIdentifier(
                entity_id=entity_id,
                identifier_type="CIK",
                identifier_value="0000320193",
                source="SEC",
            )
        )
        session.add(
            EntityIdentifier(
                entity_id=entity_id,
                identifier_type="LEI",
                identifier_value="HWUPKR0MPOU8FGXBT394",
                source="GLEIF",
            )
        )

        security = Security(
            security_id=security_id,
            security_type="COMMON_STOCK",
            name="Apple Inc. Common Stock",
            short_name="AAPL",
            status="ACTIVE",
            asset_class="EQUITY",
            issuer_entity_id=entity_id,
            primary_exchange_mic="XNAS",
            primary_currency="USD",
        )
        session.add(security)
        session.add(
            SecurityIdentifier(
                security_id=security_id,
                identifier_type="TICKER",
                identifier_value="AAPL",
                source="OPENFIGI",
            )
        )
        session.add(
            SecurityIdentifier(
                security_id=security_id,
                identifier_type="FIGI",
                identifier_value="BBG000B9XRY4",
                source="OPENFIGI",
            )
        )
        await session.commit()

    # Test the API
    from httpx import ASGITransport, AsyncClient
    from src.api.app import create_app
    from src.api.deps import get_session

    app = create_app()

    async def override():
        async with sf() as s:
            yield s

    app.dependency_overrides[get_session] = override

    passed = 0
    failed = 0

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:

        async def check(method, path, expected_status, description, **kwargs):
            nonlocal passed, failed
            if method == "GET":
                r = await client.get(path)
            else:
                r = await client.post(path, **kwargs)

            if r.status_code == expected_status:
                passed += 1
                print(f"  PASS  {method} {path} -> {r.status_code} ({description})")
                return r.json()
            else:
                failed += 1
                print(
                    f"  FAIL  {method} {path} -> {r.status_code} expected {expected_status} ({description})"
                )
                print(f"        Response: {r.text[:200]}")
                return None

        print("=== D8 Reference Data ===")
        await check("GET", "/health", 200, "health check")

        data = await check("GET", "/v1/reference/countries", 200, "list countries")
        if data:
            print(f"        -> {data['meta']['total_count']} countries")

        await check("GET", "/v1/reference/countries/US", 200, "get US")
        await check("GET", "/v1/reference/countries/ZZ", 404, "country not found")

        data = await check("GET", "/v1/reference/currencies", 200, "list currencies")
        if data:
            print(f"        -> {data['meta']['total_count']} currencies")

        await check("GET", "/v1/reference/currencies/USD", 200, "get USD")

        data = await check("GET", "/v1/reference/exchanges", 200, "list exchanges")
        if data:
            print(f"        -> {data['meta']['total_count']} exchanges")

        await check("GET", "/v1/reference/exchanges/XNYS", 200, "get NYSE")

        data = await check("GET", "/v1/reference/gics", 200, "list GICS")
        if data:
            print(f"        -> {data['meta']['total_count']} classifications")

        data = await check("GET", "/v1/reference/gics/sectors", 200, "GICS sectors")
        if data:
            print(f"        -> {len(data['data'])} sectors")

        await check("GET", "/v1/reference/regions", 200, "list regions")
        await check("GET", "/v1/reference/sic", 200, "list SIC")
        await check("GET", "/v1/reference/naics", 200, "list NAICS")

        print("\n=== D1 Entity Master ===")
        data = await check(
            "GET", f"/v1/entities/{entity_id}", 200, "get entity by ID"
        )
        if data:
            print(f"        -> {data['legal_name']}")

        await check(
            "GET",
            "00000000-0000-0000-0000-000000000000".join(
                ["/v1/entities/", ""]
            ),
            404,
            "entity not found",
        )

        data = await check("GET", "/v1/entities", 200, "list entities")
        if data:
            print(f"        -> {data['meta']['total_count']} entities")

        data = await check(
            "GET", "/v1/entities/search?q=Apple", 200, "search entities"
        )
        if data:
            print(f"        -> {len(data['results'])} results")

        data = await check(
            "POST",
            "/v1/entities/resolve",
            200,
            "resolve entity",
            json={"legal_name": "Apple Inc", "country": "US"},
        )
        if data:
            print(
                f"        -> confidence={data['confidence']}, method={data['match_method']}"
            )

        await check(
            "GET", f"/v1/entities/{entity_id}/hierarchy", 200, "entity hierarchy"
        )

        data = await check(
            "GET",
            f"/v1/entities/{entity_id}/securities",
            200,
            "entity securities",
        )
        if data:
            print(f"        -> {len(data['data'])} securities")

        await check(
            "GET", f"/v1/entities/{entity_id}/history", 200, "entity history"
        )

        await check(
            "GET",
            f"/v1/entities/{entity_id}/relationships",
            200,
            "entity relationships",
        )

        data = await check(
            "POST",
            "/v1/entities/bulk-lookup",
            200,
            "bulk lookup",
            json={"identifiers": [{"type": "CIK", "value": "0000320193"}]},
        )
        if data:
            print(f"        -> {len(data['results'])} results")

        print("\n=== D2 Security Master ===")
        data = await check(
            "GET", f"/v1/securities/{security_id}", 200, "get security by ID"
        )
        if data:
            print(f"        -> {data['name']}")

        data = await check("GET", "/v1/securities", 200, "list securities")
        if data:
            print(f"        -> {data['meta']['total_count']} securities")

        data = await check(
            "GET", "/v1/securities/search?q=AAPL", 200, "search securities"
        )
        if data:
            print(f"        -> {len(data['results'])} results")

        data = await check(
            "GET",
            f"/v1/securities/{security_id}/identifiers",
            200,
            "security identifiers",
        )
        if data:
            print(f"        -> {len(data)} identifiers")

        data = await check(
            "GET",
            f"/v1/securities/{security_id}/issuer",
            200,
            "security issuer",
        )
        if data:
            print(f"        -> issuer: {data['legal_name']}")

        await check(
            "GET",
            f"/v1/securities/{security_id}/related",
            200,
            "related securities",
        )

        data = await check(
            "POST",
            "/v1/securities/translate",
            200,
            "translate TICKER->FIGI",
            json={
                "source_type": "TICKER",
                "source_value": "AAPL",
                "target_types": ["FIGI"],
            },
        )
        if data:
            print(f"        -> translations: {data['translations']}")

        data = await check(
            "POST",
            "/v1/securities/bulk-lookup",
            200,
            "security bulk lookup",
            json={
                "identifiers": [{"type": "TICKER", "value": "AAPL"}]
            },
        )
        if data:
            print(f"        -> {len(data['results'])} results")

    # Summary
    print(f"\n{'='*50}")
    print(f"PASSED: {passed}")
    print(f"FAILED: {failed}")
    print(f"TOTAL:  {passed + failed}")
    print(f"{'='*50}")

    # Cleanup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()
    DB_PATH.unlink(missing_ok=True)

    if failed > 0:
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
