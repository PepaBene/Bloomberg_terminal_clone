"""Tests for Pillar 3 Phase 4A — Company Primer Engine."""

import json

from src.engines.company_primer_engine import (
    BusinessModelProfile,
    CatalystEvent,
    CompanyPrimerResult,
    CompetitiveLandscapeProfile,
    FinancialHealthSnapshot,
    PromptContext,
    RiskFactor,
    StrategicInitiative,
    assemble_primer_prompt,
    build_catalyst_calendar,
    build_company_primer,
    compute_data_completeness,
    compute_financial_health,
    extract_business_model,
    extract_competitive_landscape,
    extract_risk_factors,
    extract_strategic_initiatives,
    parse_primer_response,
)


# ── 1. Extract Business Model Tests ─────────────────────────────────────


class TestExtractBusinessModel:
    """Tests for extract_business_model()."""

    def test_full_filing_and_segment_data(self):
        """MSFT-like: multiple revenue streams, global geography."""
        filing = {
            "revenue_streams": ["Cloud Services", "Office 365", "Windows OEM"],
            "customer_segments": ["Enterprise", "SMB", "Consumer", "Government"],
            "key_partnerships": ["OpenAI", "SAP", "Accenture"],
        }
        segments = {
            "geographic": ["United States", "EMEA", "Asia-Pacific", "Other Americas"],
            "product_segments": ["Intelligent Cloud", "Productivity", "Personal Computing"],
        }
        result = extract_business_model(filing, segments)
        assert isinstance(result, BusinessModelProfile)
        assert "Cloud Services" in result.revenue_streams
        # Product segments supplement revenue_streams
        assert "Intelligent Cloud" in result.revenue_streams
        assert len(result.geographic_exposure) == 4
        assert "Enterprise" in result.customer_segments
        assert "OpenAI" in result.key_partnerships

    def test_no_segment_data(self):
        """Filing only, no segment breakdown."""
        filing = {
            "revenue_streams": ["Advertising"],
            "customer_segments": ["Advertisers"],
        }
        result = extract_business_model(filing, None)
        assert result.revenue_streams == ["Advertising"]
        assert result.geographic_exposure == []
        assert result.key_partnerships == []

    def test_empty_filing(self):
        """Empty data returns empty lists."""
        result = extract_business_model({}, None)
        assert result.revenue_streams == []
        assert result.customer_segments == []
        assert result.geographic_exposure == []

    def test_no_duplicate_revenue_streams(self):
        """Product segment already in revenue_streams should not duplicate."""
        filing = {"revenue_streams": ["Cloud"]}
        segments = {"product_segments": ["Cloud", "Licensing"], "geographic": []}
        result = extract_business_model(filing, segments)
        assert result.revenue_streams.count("Cloud") == 1
        assert "Licensing" in result.revenue_streams


# ── 2. Extract Competitive Landscape Tests ───────────────────────────────


class TestExtractCompetitiveLandscape:
    """Tests for extract_competitive_landscape()."""

    def test_leader_position_largest_market_cap(self):
        """Company with largest market cap among peers = leader."""
        company = {
            "market_cap": 2800e9,
            "revenue": 230e9,
            "revenue_growth_pct": 15.0,
            "operating_margin": 44.0,
            "competitive_advantages": ["Cloud platform scale"],
        }
        peers = [
            {"name": "AAPL", "market_cap": 2700e9, "revenue": 380e9,
             "revenue_growth_pct": 5.0, "operating_margin": 30.0},
            {"name": "GOOG", "market_cap": 1800e9, "revenue": 300e9,
             "revenue_growth_pct": 12.0, "operating_margin": 28.0},
            {"name": "AMZN", "market_cap": 1600e9, "revenue": 570e9,
             "revenue_growth_pct": 11.0, "operating_margin": 6.0},
        ]
        result = extract_competitive_landscape(company, peers)
        assert isinstance(result, CompetitiveLandscapeProfile)
        assert result.market_position == "leader"
        assert "AAPL" in result.direct_competitors
        assert "Superior margins" in result.competitive_advantages
        assert "Above-peer growth" in result.competitive_advantages

    def test_challenger_position(self):
        """Mid-tier company = challenger."""
        company = {
            "market_cap": 500e9, "revenue": 50e9,
            "operating_margin": 20.0, "revenue_growth_pct": 8.0,
        }
        peers = [
            {"name": "A", "market_cap": 2000e9, "revenue": 200e9,
             "operating_margin": 25.0, "revenue_growth_pct": 10.0},
            {"name": "B", "market_cap": 1000e9, "revenue": 100e9,
             "operating_margin": 22.0, "revenue_growth_pct": 9.0},
            {"name": "C", "market_cap": 300e9, "revenue": 30e9,
             "operating_margin": 18.0, "revenue_growth_pct": 6.0},
        ]
        result = extract_competitive_landscape(company, peers)
        assert result.market_position == "challenger"

    def test_niche_position(self):
        """Smallest company = niche."""
        company = {"market_cap": 10e9, "revenue": 2e9, "operating_margin": 10.0}
        peers = [
            {"name": "A", "market_cap": 500e9, "revenue": 100e9, "operating_margin": 20.0},
            {"name": "B", "market_cap": 300e9, "revenue": 60e9, "operating_margin": 18.0},
            {"name": "C", "market_cap": 200e9, "revenue": 40e9, "operating_margin": 15.0},
        ]
        result = extract_competitive_landscape(company, peers)
        assert result.market_position == "niche"

    def test_no_peers(self):
        """No peer data defaults to niche."""
        result = extract_competitive_landscape({"market_cap": 100e9}, [])
        assert result.market_position == "niche"
        assert result.direct_competitors == []


# ── 3. Compute Financial Health Tests ────────────────────────────────────


class TestComputeFinancialHealth:
    """Tests for compute_financial_health()."""

    def test_msft_like_financials(self):
        """MSFT: $230B revenue, 44% op margin, strong FCF."""
        financials = {
            "revenue_ttm": 230e9,
            "cost_of_revenue": 74e9,
            "operating_income": 101e9,
            "net_income": 82e9,
            "total_debt": 47e9,
            "cash": 80e9,
            "ebitda": 120e9,
            "free_cash_flow": 70e9,
        }
        result = compute_financial_health(financials)
        assert isinstance(result, FinancialHealthSnapshot)
        assert result.revenue_ttm == 230e9
        # Gross margin: (230 - 74) / 230 ~= 0.6783
        assert 0.67 < result.gross_margin < 0.69
        # Operating margin: 101 / 230 ~= 0.4391
        assert 0.43 < result.operating_margin < 0.45
        # Net margin: 82 / 230 ~= 0.3565
        assert result.net_margin is not None
        assert 0.35 < result.net_margin < 0.37
        # Net debt to EBITDA: (47 - 80) / 120 ~= -0.275 (net cash)
        assert result.net_debt_to_ebitda is not None
        assert result.net_debt_to_ebitda < 0  # Net cash position
        # FCF margin: 70 / 230 ~= 0.3043
        assert result.fcf_margin is not None
        assert 0.30 < result.fcf_margin < 0.31

    def test_leveraged_company(self):
        """High-debt company: positive net_debt_to_ebitda."""
        financials = {
            "revenue_ttm": 50e9,
            "cost_of_revenue": 30e9,
            "operating_income": 8e9,
            "total_debt": 60e9,
            "cash": 5e9,
            "ebitda": 12e9,
        }
        result = compute_financial_health(financials)
        assert result.net_debt_to_ebitda is not None
        # (60 - 5) / 12 ~= 4.58
        assert result.net_debt_to_ebitda > 4.0

    def test_zero_revenue(self):
        """Pre-revenue company: margins default to zero."""
        result = compute_financial_health({"revenue_ttm": 0})
        assert result.gross_margin == 0.0
        assert result.operating_margin == 0.0
        assert result.net_margin is None

    def test_minimal_data(self):
        """Only revenue provided."""
        result = compute_financial_health({"revenue_ttm": 10e9, "cost_of_revenue": 6e9})
        assert result.gross_margin == 0.4
        assert result.net_debt_to_ebitda is None
        assert result.fcf_margin is None


# ── 4. Extract Strategic Initiatives Tests ───────────────────────────────


class TestExtractStrategicInitiatives:
    """Tests for extract_strategic_initiatives()."""

    def test_from_eight_k_events(self):
        """Strategic 8-K events are extracted."""
        events = [
            {
                "title": "Major Acquisition of Activision Blizzard",
                "description": "Transformative acquisition in gaming",
                "date": "2024-10-13",
                "event_type": "acquisition",
            },
            {
                "title": "Quarterly Dividend Declaration",
                "description": "Routine quarterly dividend",
                "date": "2024-11-01",
                "event_type": "dividend",
            },
        ]
        result = extract_strategic_initiatives(events, None)
        assert len(result) == 1
        assert result[0].name == "Major Acquisition of Activision Blizzard"
        assert result[0].potential_impact == "high"

    def test_from_guidance(self):
        """Guidance initiatives are extracted."""
        guidance = {
            "initiatives": [
                {
                    "name": "AI Copilot Rollout",
                    "description": "Enterprise-wide AI assistant deployment",
                    "timeline": "FY2025",
                    "potential_impact": "high",
                },
            ],
        }
        result = extract_strategic_initiatives([], guidance)
        assert len(result) == 1
        assert result[0].name == "AI Copilot Rollout"
        assert result[0].timeline == "FY2025"

    def test_combined_sources(self):
        """Both 8-K and guidance initiatives combined."""
        events = [
            {"title": "New Partnership", "description": "Strategic partnership launch",
             "date": "2024-06-01", "event_type": "partnership"},
        ]
        guidance = {
            "initiatives": [
                {"name": "Cloud Expansion", "description": "Expand cloud regions",
                 "timeline": "2025", "potential_impact": "medium"},
            ],
        }
        result = extract_strategic_initiatives(events, guidance)
        assert len(result) == 2

    def test_empty_inputs(self):
        """No events, no guidance."""
        result = extract_strategic_initiatives([], None)
        assert result == []

    def test_non_strategic_events_filtered(self):
        """Non-strategic event types are filtered out."""
        events = [
            {"title": "Board Meeting", "description": "Routine minor update",
             "date": "2024-01-01", "event_type": "routine"},
        ]
        result = extract_strategic_initiatives(events, None)
        assert len(result) == 0


# ── 5. Extract Risk Factors Tests ────────────────────────────────────────


class TestExtractRiskFactors:
    """Tests for extract_risk_factors()."""

    def test_categorizes_risks_by_keywords(self):
        """Risks are categorized by description keywords."""
        risks = [
            {"description": "Regulatory compliance with new EU legislation could pose challenges"},
            {"description": "Intense competition from new market entrants"},
            {"description": "Supply chain cyber security talent operational risk exposure"},
            {"description": "Macroeconomic recession and interest rate risk exposure"},
        ]
        result = extract_risk_factors(risks, None)
        assert len(result) == 4
        categories = [r.category for r in result]
        assert "regulatory" in categories
        assert "competitive" in categories
        assert "operational" in categories
        assert "market" in categories

    def test_explicit_category_and_severity(self):
        """Pre-classified risks used as-is."""
        risks = [
            {"description": "Patent expiration", "category": "regulatory",
             "severity": "critical", "mitigation": "Filing extensions"},
        ]
        result = extract_risk_factors(risks, None)
        assert result[0].category == "regulatory"
        assert result[0].severity == "critical"
        assert result[0].mitigation_status == "Filing extensions"

    def test_credit_data_augments_risks(self):
        """Credit risks and watchlist create additional risk factors."""
        credit_data = {
            "credit_rating": "BBB-",
            "outlook": "negative",
            "watchlist": True,
            "credit_risks": [
                {"description": "Leverage above target range", "severity": "high"},
            ],
        }
        result = extract_risk_factors([], credit_data)
        assert len(result) == 2  # credit_risk + watchlist
        assert any("watchlist" in r.description.lower() for r in result)

    def test_sorted_by_severity(self):
        """Results are sorted critical > high > medium > low."""
        risks = [
            {"description": "Minor issue", "severity": "low"},
            {"description": "Material adverse impact", "severity": "critical"},
            {"description": "Moderate concern", "severity": "medium"},
        ]
        result = extract_risk_factors(risks, None)
        severities = [r.severity for r in result]
        assert severities == ["critical", "medium", "low"]

    def test_empty_inputs(self):
        """No risks, no credit data."""
        result = extract_risk_factors([], None)
        assert result == []


# ── 6. Build Catalyst Calendar Tests ─────────────────────────────────────


class TestBuildCatalystCalendar:
    """Tests for build_catalyst_calendar()."""

    def test_events_and_earnings_combined(self):
        """Events + earnings dates produce sorted catalysts."""
        events = [
            {"date": "2025-03-15", "event": "Investor Day",
             "market_reaction_pct": None, "strategic_significance": "high"},
            {"date": "2025-01-10", "event": "Product Launch",
             "market_reaction_pct": 2.5, "strategic_significance": "medium"},
        ]
        earnings = ["2025-01-25", "2025-04-25"]
        result = build_catalyst_calendar(events, earnings)
        assert len(result) == 4
        # Should be sorted by date
        dates = [c.date for c in result]
        assert dates == sorted(dates)
        # Earnings entries have high significance
        earnings_events = [c for c in result if c.event == "Earnings Release"]
        assert len(earnings_events) == 2
        assert all(e.strategic_significance == "high" for e in earnings_events)

    def test_events_only(self):
        """No earnings dates."""
        events = [{"date": "2025-05-01", "event": "FDA Approval"}]
        result = build_catalyst_calendar(events, [])
        assert len(result) == 1
        assert result[0].event == "FDA Approval"

    def test_earnings_only(self):
        """No events, just earnings dates."""
        result = build_catalyst_calendar([], ["2025-07-20"])
        assert len(result) == 1
        assert result[0].event == "Earnings Release"

    def test_empty(self):
        """No events, no earnings."""
        result = build_catalyst_calendar([], [])
        assert result == []


# ── 7. Compute Data Completeness Tests ───────────────────────────────────


class TestComputeDataCompleteness:
    """Tests for compute_data_completeness()."""

    def test_full_data_high_score(self):
        """All sections populated => high completeness."""
        primer = {
            "business_model": {
                "revenue_streams": ["Cloud"],
                "customer_segments": ["Enterprise"],
                "geographic_exposure": ["US", "EU"],
                "key_partnerships": ["Partner A"],
            },
            "financial_health": {
                "revenue_ttm": 100e9,
                "gross_margin": 0.65,
                "operating_margin": 0.40,
                "net_margin": 0.30,
                "net_debt_to_ebitda": 1.5,
                "fcf_margin": 0.25,
            },
            "competitive": {
                "direct_competitors": ["A", "B"],
                "competitive_advantages": ["Scale", "Brand"],
                "market_position": "leader",
            },
            "risks": [
                {"description": "Risk 1", "severity": "high"},
                {"description": "Risk 2", "severity": "medium"},
                {"description": "Risk 3", "severity": "low"},
                {"description": "Risk 4", "severity": "low"},
                {"description": "Risk 5", "severity": "low"},
            ],
            "catalysts": [
                {"date": "2025-01-01", "event": "Earnings"},
                {"date": "2025-04-01", "event": "Investor Day"},
                {"date": "2025-07-01", "event": "Product Launch"},
                {"date": "2025-10-01", "event": "Earnings"},
            ],
        }
        score = compute_data_completeness(primer)
        assert score >= 90.0

    def test_empty_data_zero_score(self):
        """No data => 0 completeness."""
        score = compute_data_completeness({})
        assert score == 0.0

    def test_partial_data(self):
        """Some sections populated, others missing."""
        primer = {
            "business_model": {"revenue_streams": ["SaaS"]},
            "financial_health": {"revenue_ttm": 50e9, "gross_margin": 0.70},
            "competitive": {},
            "risks": [],
            "catalysts": [],
        }
        score = compute_data_completeness(primer)
        assert 10.0 < score < 30.0


# ── 8. Assemble Primer Prompt Tests ──────────────────────────────────────


class TestAssemblePrimerPrompt:
    """Tests for assemble_primer_prompt()."""

    def test_full_context(self):
        """Full data produces complete prompt context."""
        news = [
            {"headline": "MSFT beats earnings", "date": "2025-01-24", "source": "BBG"},
            {"headline": "Cloud growth accelerates", "date": "2025-01-25", "source": "Reuters"},
        ]
        peers = [
            {"name": "GOOG", "market_cap": 1800e9, "revenue": 300e9},
        ]
        result = assemble_primer_prompt(
            entity_name="MSFT",
            filing_text="Microsoft Corporation... 10-K annual report...",
            transcript="Good morning, thank you for joining...",
            news=news,
            peer_data=peers,
        )
        assert isinstance(result, PromptContext)
        assert result.entity_name == "MSFT"
        assert "equity research analyst" in result.system_prompt.lower()
        assert "MSFT" in result.user_prompt
        assert "earnings transcript" in result.user_prompt
        assert len(result.data_context["recent_news"]) == 2
        assert result.data_context["filing_excerpt"] != ""

    def test_no_transcript(self):
        """Without transcript, prompt adapts."""
        result = assemble_primer_prompt("AAPL", "Filing text", None, [], [])
        assert "transcript" not in result.user_prompt.lower()

    def test_truncation_of_long_filing(self):
        """Very long filing text is truncated to 5000 chars."""
        long_text = "A" * 10000
        result = assemble_primer_prompt("TEST", long_text, None, [], [])
        assert len(result.data_context["filing_excerpt"]) == 5000


# ── 9. Parse Primer Response Tests ───────────────────────────────────────


class TestParsePrimerResponse:
    """Tests for parse_primer_response()."""

    def test_valid_json(self):
        """Clean JSON parses correctly."""
        data = {"business_model": "SaaS", "revenue": 100}
        result = parse_primer_response(json.dumps(data))
        assert result["business_model"] == "SaaS"

    def test_json_in_markdown_code_block(self):
        """JSON wrapped in ```json ``` parses."""
        data = {"key": "value"}
        raw = f"```json\n{json.dumps(data)}\n```"
        result = parse_primer_response(raw)
        assert result["key"] == "value"

    def test_trailing_commas(self):
        """Trailing commas before } are cleaned."""
        raw = '{"name": "test", "value": 42,}'
        result = parse_primer_response(raw)
        assert result["name"] == "test"

    def test_json_embedded_in_text(self):
        """JSON object embedded in surrounding text."""
        raw = 'Here is the analysis:\n{"sector": "tech", "score": 85}\nEnd of analysis.'
        result = parse_primer_response(raw)
        assert result["sector"] == "tech"

    def test_unparseable_returns_raw(self):
        """Completely unparseable text returns raw_text + parse_error."""
        raw = "This is just plain text with no JSON at all."
        result = parse_primer_response(raw)
        assert "raw_text" in result
        assert "parse_error" in result


# ── 10. Build Company Primer (Orchestrator) Tests ────────────────────────


class TestBuildCompanyPrimer:
    """Tests for build_company_primer() orchestrator."""

    def _msft_entity(self):
        return {
            "name": "Microsoft Corporation",
            "market_cap": 2800e9,
            "revenue": 230e9,
            "revenue_growth_pct": 15.0,
            "operating_margin": 44.0,
            "competitive_advantages": ["Cloud platform scale", "Enterprise distribution"],
        }

    def _msft_filings(self):
        return {
            "revenue_streams": ["Intelligent Cloud", "Productivity & Business", "More Personal Computing"],
            "customer_segments": ["Enterprise", "SMB", "Consumer", "Government"],
            "key_partnerships": ["OpenAI", "SAP"],
            "segment_data": {
                "geographic": ["United States", "EMEA", "Asia-Pacific"],
                "product_segments": ["Azure", "Office 365", "Windows"],
            },
            "financial_data": {
                "revenue_ttm": 230e9,
                "cost_of_revenue": 74e9,
                "operating_income": 101e9,
                "net_income": 82e9,
                "total_debt": 47e9,
                "cash": 80e9,
                "ebitda": 120e9,
                "free_cash_flow": 70e9,
            },
            "eight_k_events": [
                {"title": "Activision Blizzard Acquisition Closed",
                 "description": "Transformative gaming acquisition",
                 "date": "2023-10-13", "event_type": "acquisition"},
            ],
            "guidance": {
                "initiatives": [
                    {"name": "Copilot Enterprise", "description": "AI assistant for enterprise",
                     "timeline": "FY2025", "potential_impact": "high"},
                ],
            },
            "risks": [
                {"description": "Regulatory scrutiny of market dominance in cloud"},
                {"description": "Intense competition in AI from Google and Amazon"},
            ],
            "credit_data": None,
            "catalyst_events": [
                {"date": "2025-04-20", "event": "Build Conference",
                 "strategic_significance": "high"},
            ],
            "earnings_dates": ["2025-01-28", "2025-04-22"],
            "filing_text": "Microsoft Corporation Annual Report 10-K...",
        }

    def _msft_peers(self):
        return [
            {"name": "AAPL", "market_cap": 2700e9, "revenue": 380e9,
             "revenue_growth_pct": 5.0, "operating_margin": 30.0},
            {"name": "GOOG", "market_cap": 1800e9, "revenue": 300e9,
             "revenue_growth_pct": 12.0, "operating_margin": 28.0},
            {"name": "AMZN", "market_cap": 1600e9, "revenue": 570e9,
             "revenue_growth_pct": 11.0, "operating_margin": 6.0},
        ]

    def test_full_msft_primer(self):
        """Full MSFT data produces comprehensive primer."""
        result = build_company_primer(
            entity_data=self._msft_entity(),
            filings=self._msft_filings(),
            transcripts=[{"text": "Good morning, Satya Nadella here...", "date": "2025-01-28"}],
            news=[{"headline": "MSFT beats Q2 estimates", "date": "2025-01-28", "source": "BBG"}],
            peers=self._msft_peers(),
        )
        assert isinstance(result, CompanyPrimerResult)
        assert result.entity_name == "Microsoft Corporation"

        # Business model
        assert len(result.business_model.revenue_streams) >= 3
        assert "Enterprise" in result.business_model.customer_segments
        assert len(result.business_model.geographic_exposure) == 3

        # Competitive
        assert result.competitive.market_position == "leader"
        assert len(result.competitive.direct_competitors) == 3

        # Financial health
        assert result.financial_health.revenue_ttm == 230e9
        assert result.financial_health.operating_margin > 0.43
        assert result.financial_health.net_debt_to_ebitda < 0  # Net cash

        # Initiatives
        assert len(result.initiatives) >= 2  # 1 from 8-K + 1 from guidance

        # Risks
        assert len(result.risks) >= 2

        # Catalysts
        assert len(result.catalysts) >= 3  # 1 event + 2 earnings

        # Data completeness
        assert result.data_completeness >= 70.0

        # Prompt context
        assert result.prompt_context is not None
        assert result.prompt_context.entity_name == "Microsoft Corporation"

    def test_minimal_data(self):
        """Minimal data still produces valid result."""
        result = build_company_primer(
            entity_data={"name": "Unknown Corp"},
            filings={},
            transcripts=None,
            news=[],
            peers=[],
        )
        assert isinstance(result, CompanyPrimerResult)
        assert result.entity_name == "Unknown Corp"
        assert result.data_completeness < 10.0
        assert result.business_model.revenue_streams == []
        assert result.competitive.market_position == "niche"
        assert result.financial_health.revenue_ttm == 0.0

    def test_no_transcripts(self):
        """Primer builds without transcripts."""
        result = build_company_primer(
            entity_data=self._msft_entity(),
            filings=self._msft_filings(),
            transcripts=None,
            news=[],
            peers=self._msft_peers(),
        )
        assert result.prompt_context is not None
        assert "transcript" not in result.prompt_context.user_prompt.lower()

    def test_catalysts_sorted_by_date(self):
        """Catalysts are sorted chronologically."""
        result = build_company_primer(
            entity_data=self._msft_entity(),
            filings=self._msft_filings(),
            transcripts=None,
            news=[],
            peers=[],
        )
        dates = [c.date for c in result.catalysts]
        assert dates == sorted(dates)

    def test_risks_sorted_by_severity(self):
        """Risks are sorted by severity (most severe first)."""
        filings = self._msft_filings()
        filings["risks"] = [
            {"description": "Minor routine issue", "severity": "low"},
            {"description": "Material adverse regulatory action", "severity": "critical"},
            {"description": "Moderate competitive concern", "severity": "medium"},
        ]
        result = build_company_primer(
            entity_data=self._msft_entity(),
            filings=filings,
            transcripts=None,
            news=[],
            peers=[],
        )
        severities = [r.severity for r in result.risks]
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        severity_ints = [severity_order.get(s, 2) for s in severities]
        assert severity_ints == sorted(severity_ints)
