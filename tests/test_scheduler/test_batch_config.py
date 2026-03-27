"""Tests for batch scheduling configuration."""

import re

import pytest

from src.scheduler.batch_config import BATCH_JOBS, BATCH_JOBS_BY_NAME, BatchJob


# ---------------------------------------------------------------------------
# Valid cron regex (5-field: minute hour dom month dow)
# ---------------------------------------------------------------------------

_CRON_FIELD = r"(\*|[0-9,*/\-]+)"
_CRON_RE = re.compile(
    rf"^{_CRON_FIELD}\s+{_CRON_FIELD}\s+{_CRON_FIELD}\s+{_CRON_FIELD}\s+{_CRON_FIELD}$"
)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestBatchJobRegistry:
    """Ensure the BATCH_JOBS registry is well-formed."""

    def test_registry_not_empty(self):
        assert len(BATCH_JOBS) > 0

    def test_all_expected_jobs_present(self):
        """The four new analytics jobs must be registered."""
        expected = {
            "analytics_quality_scoring",
            "analytics_risk_var",
            "analytics_quant_weekly",
            "analytics_institutional_flows",
        }
        actual = {j.name for j in BATCH_JOBS}
        assert expected.issubset(actual), f"Missing: {expected - actual}"

    def test_original_jobs_still_present(self):
        """Existing jobs must not have been removed."""
        expected = {
            "reference_data_refresh",
            "fred_macro_ingest",
            "edgar_xbrl_ingest",
            "polygon_eod_ingest",
            "analytics_ratios",
            "analytics_multiples",
            "analytics_wacc",
            "quality_check",
        }
        actual = {j.name for j in BATCH_JOBS}
        assert expected.issubset(actual)

    def test_unique_job_names(self):
        """Every job name must be unique."""
        names = [j.name for j in BATCH_JOBS]
        assert len(names) == len(set(names)), "Duplicate job names found"

    def test_lookup_dict_matches_list(self):
        """BATCH_JOBS_BY_NAME must contain all list entries."""
        assert len(BATCH_JOBS_BY_NAME) == len(BATCH_JOBS)
        for j in BATCH_JOBS:
            assert j.name in BATCH_JOBS_BY_NAME
            assert BATCH_JOBS_BY_NAME[j.name] is j


class TestCronExpressions:
    """Validate cron syntax for every job."""

    @pytest.mark.parametrize("job", BATCH_JOBS, ids=lambda j: j.name)
    def test_cron_is_valid_five_field(self, job: BatchJob):
        assert _CRON_RE.match(job.cron), f"{job.name}: invalid cron '{job.cron}'"


class TestSLAValues:
    """SLA durations must be reasonable."""

    @pytest.mark.parametrize("job", BATCH_JOBS, ids=lambda j: j.name)
    def test_sla_positive(self, job: BatchJob):
        assert job.sla_minutes > 0

    @pytest.mark.parametrize("job", BATCH_JOBS, ids=lambda j: j.name)
    def test_sla_under_24_hours(self, job: BatchJob):
        assert job.sla_minutes <= 1440, f"{job.name} SLA exceeds 24 h"

    def test_analytics_quality_scoring_sla(self):
        job = BATCH_JOBS_BY_NAME["analytics_quality_scoring"]
        assert job.sla_minutes == 45

    def test_analytics_risk_var_sla(self):
        job = BATCH_JOBS_BY_NAME["analytics_risk_var"]
        assert job.sla_minutes == 60


class TestDependencyChains:
    """Dependency relationships must be correct and acyclic."""

    def test_e3_depends_on_e1(self):
        job = BATCH_JOBS_BY_NAME["analytics_quality_scoring"]
        assert "analytics_ratios" in job.depends_on

    def test_e5_depends_on_e1(self):
        job = BATCH_JOBS_BY_NAME["analytics_risk_var"]
        assert "analytics_ratios" in job.depends_on

    def test_e2_multiples_depends_on_e1(self):
        job = BATCH_JOBS_BY_NAME["analytics_multiples"]
        assert "analytics_ratios" in job.depends_on

    def test_e2_wacc_depends_on_e1(self):
        job = BATCH_JOBS_BY_NAME["analytics_wacc"]
        assert "analytics_ratios" in job.depends_on

    def test_no_circular_dependencies(self):
        """Walk each dependency chain and verify no cycles exist."""
        by_name = BATCH_JOBS_BY_NAME

        def _walk(name: str, visited: set[str]) -> None:
            if name in visited:
                pytest.fail(f"Circular dependency detected involving '{name}'")
            visited.add(name)
            job = by_name.get(name)
            if job:
                for dep in job.depends_on:
                    _walk(dep, visited.copy())

        for job in BATCH_JOBS:
            _walk(job.name, set())

    def test_all_dependencies_reference_known_jobs(self):
        """Every depends_on entry must point to a job that exists."""
        known = {j.name for j in BATCH_JOBS}
        for job in BATCH_JOBS:
            for dep in job.depends_on:
                assert dep in known, f"{job.name} depends on unknown job '{dep}'"


class TestEngineReferences:
    """Verify that analytics jobs reference engine scripts that could exist."""

    def test_analytics_jobs_have_engine_scripts(self):
        analytics_jobs = [j for j in BATCH_JOBS if j.domain == "ANALYTICS"]
        assert len(analytics_jobs) >= 7  # ratios, multiples, wacc, quality, risk, quant, flows
        for j in analytics_jobs:
            assert j.script.startswith("scripts/"), f"{j.name} script path unexpected"

    def test_quality_scoring_references_e3(self):
        job = BATCH_JOBS_BY_NAME["analytics_quality_scoring"]
        assert "e3" in job.script

    def test_risk_var_references_e5(self):
        job = BATCH_JOBS_BY_NAME["analytics_risk_var"]
        assert "e5" in job.script

    def test_quant_references_e7(self):
        job = BATCH_JOBS_BY_NAME["analytics_quant_weekly"]
        assert "e7" in job.script

    def test_flows_references_e6(self):
        job = BATCH_JOBS_BY_NAME["analytics_institutional_flows"]
        assert "e6" in job.script
