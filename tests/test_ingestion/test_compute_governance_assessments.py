"""Unit tests for scripts/compute_governance_assessments.py's
_build_governance_data -- the one piece of new logic here (combines
already-tested engine functions with ORM field extraction); the engine
itself (compute_governance_score/compute_board_diversity) is fully
covered by tests/test_engines/test_governance_scoring.py. The rest of the
script (run/_upsert) is DB orchestration via get_session_factory(),
untestable against this suite's SQLite engine -- same situation as
scripts/interpret_batch.py/backfill.py, verified via py_compile/ast only.

_mine_red_flags_for_proxy is the exception: it only needs a fake
connector (duck-typed async _fetch_body) and a plain ProxyFiling object
with a filing_url, neither of which touches a DB session -- so it's
tested directly, same as the pure text-mining it wraps
(tests/test_ingestion/test_proxy_red_flags.py).
"""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest

from src.models.governance_intelligence import BoardMember, ExecutiveCompensation, ProxyFiling

# Import via importlib since "scripts" isn't a package with an __init__.py
# on the normal import path in this test run.
import importlib.util
import sys
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "compute_governance_assessments",
    Path(__file__).resolve().parent.parent.parent / "scripts" / "compute_governance_assessments.py",
)
_MODULE = importlib.util.module_from_spec(_SPEC)
sys.modules["compute_governance_assessments"] = _MODULE
_SPEC.loader.exec_module(_MODULE)
_build_governance_data = _MODULE._build_governance_data
_mine_red_flags_for_proxy = _MODULE._mine_red_flags_for_proxy


def _board_member(**kwargs) -> BoardMember:
    defaults = dict(
        person_name="Jane Doe", is_independent=True, is_chair=False,
        tenure_years=5, age=55, gender="F", expertise_areas=[], other_boards=[],
    )
    defaults.update(kwargs)
    return BoardMember(**defaults)


def _exec_comp(**kwargs) -> ExecutiveCompensation:
    defaults = dict(
        person_name="John Smith", role="CEO", fiscal_year=2025,
        total_compensation=Decimal("10000000"),
    )
    defaults.update(kwargs)
    return ExecutiveCompensation(**defaults)


class TestBuildGovernanceData:

    def test_derives_board_independence_and_tenure(self):
        board = [
            _board_member(person_name="A", is_independent=True, tenure_years=4),
            _board_member(person_name="B", is_independent=True, tenure_years=6),
            _board_member(person_name="C", is_independent=False, tenure_years=10),
        ]
        governance_data, diversity = _build_governance_data(board, [])
        assert governance_data["board_independence_pct"] == round(2 / 3 * 100, 1)
        assert governance_data["avg_board_tenure"] == round((4 + 6 + 10) / 3, 1)
        assert diversity["total_directors"] == 3

    def test_no_ceo_omits_ceo_specific_keys(self):
        board = [_board_member()]
        governance_data, _ = _build_governance_data(board, [])
        assert "ceo_is_chair" not in governance_data
        assert "ceo_pay_ratio" not in governance_data
        assert "long_term_incentive_pct" not in governance_data

    def test_ceo_is_chair_true_when_names_match(self):
        board = [_board_member(person_name="John Smith", is_chair=True)]
        exec_comp = [_exec_comp(person_name="John Smith", role="CEO")]
        governance_data, _ = _build_governance_data(board, exec_comp)
        assert governance_data["ceo_is_chair"] is True

    def test_ceo_is_chair_false_when_names_differ(self):
        board = [_board_member(person_name="Someone Else", is_chair=True)]
        exec_comp = [_exec_comp(person_name="John Smith", role="CEO")]
        governance_data, _ = _build_governance_data(board, exec_comp)
        assert governance_data["ceo_is_chair"] is False

    def test_ceo_pay_ratio_passed_through(self):
        exec_comp = [_exec_comp(pay_ratio_to_median=Decimal("350.5"))]
        governance_data, _ = _build_governance_data([], exec_comp)
        assert governance_data["ceo_pay_ratio"] == 350.5

    def test_long_term_incentive_pct_computed_from_stock_and_option_awards(self):
        exec_comp = [_exec_comp(
            total_compensation=Decimal("10000000"),
            stock_awards=Decimal("3000000"), option_awards=Decimal("1000000"),
        )]
        governance_data, _ = _build_governance_data([], exec_comp)
        assert governance_data["long_term_incentive_pct"] == 40.0

    def test_zero_total_compensation_skips_ltip_computation(self):
        exec_comp = [_exec_comp(total_compensation=Decimal("0"))]
        governance_data, _ = _build_governance_data([], exec_comp)
        assert "long_term_incentive_pct" not in governance_data

    def test_non_ceo_roles_ignored_for_ceo_specific_fields(self):
        exec_comp = [_exec_comp(person_name="A CFO", role="CFO", pay_ratio_to_median=Decimal("50"))]
        governance_data, _ = _build_governance_data([], exec_comp)
        assert "ceo_pay_ratio" not in governance_data

    def test_structural_flags_never_fabricated(self):
        """dual_class/poison_pill/staggered_board/related_party/majority_voting
        are never in the returned dict -- the engine's own .get() defaults
        (no evidence = flag not raised, except majority_voting) apply.
        (Mining them from DEF 14A body text is a separate step --
        _mine_red_flags_for_proxy, tested below -- run() merges its
        result into governance_data after this function returns.)"""
        board = [_board_member()]
        exec_comp = [_exec_comp()]
        governance_data, _ = _build_governance_data(board, exec_comp)
        for key in ("dual_class", "has_poison_pill", "has_staggered_board", "has_majority_voting", "related_party_flag"):
            assert key not in governance_data


def _proxy_filing(**kwargs) -> ProxyFiling:
    defaults = dict(
        id=uuid.uuid4(), entity_id=uuid.uuid4(), fiscal_year=2025,
        filing_date=date(2026, 1, 1), filing_url="https://www.sec.gov/Archives/edgar/data/1/def14a.htm",
    )
    defaults.update(kwargs)
    return ProxyFiling(**defaults)


class _FakeConnector:
    def __init__(self, body: str | None):
        self._body = body
        self.fetched_urls: list[str] = []

    async def _fetch_body(self, url: str) -> str | None:
        self.fetched_urls.append(url)
        return self._body


@pytest.mark.asyncio
class TestMineRedFlagsForProxy:

    async def test_mines_flags_from_fetched_body(self):
        proxy = _proxy_filing()
        connector = _FakeConnector("There were no related party transactions during fiscal year 2025.")

        result = await _mine_red_flags_for_proxy(connector, proxy)

        assert result == {"related_party_flag": False}
        assert connector.fetched_urls == [proxy.filing_url]

    async def test_no_filing_url_skips_fetch_entirely(self):
        proxy = _proxy_filing(filing_url=None)
        connector = _FakeConnector("There were no related party transactions during fiscal year 2025.")

        result = await _mine_red_flags_for_proxy(connector, proxy)

        assert result == {}
        assert connector.fetched_urls == []

    async def test_failed_fetch_returns_empty_dict(self):
        proxy = _proxy_filing()
        connector = _FakeConnector(None)  # simulates edgar_proxy.py's own _fetch_body failure contract

        result = await _mine_red_flags_for_proxy(connector, proxy)

        assert result == {}

    async def test_body_with_html_is_stripped_before_mining(self):
        proxy = _proxy_filing()
        connector = _FakeConnector(
            "<html><body><p>Our board of directors is <b>divided into three classes</b> "
            "with staggered terms.</p></body></html>"
        )

        result = await _mine_red_flags_for_proxy(connector, proxy)

        assert result == {"has_staggered_board": True}
