"""Tests for Pillar 3 Phase 4A — Morning Briefing Engine."""

from src.engines.morning_briefing_engine import (
    ActionableInsight,
    MacroContext,
    MorningBriefingResult,
    NewsItem,
    PortfolioImpact,
    PortfolioMover,
    SectorPerformance,
    ThesisUpdate,
    assemble_briefing_prompt,
    assess_thesis_impact,
    build_morning_briefing,
    compile_macro_context,
    compute_briefing_priority,
    compute_portfolio_impact,
    filter_by_preferences,
    format_text_briefing,
    generate_actionable_insights,
    rank_news_by_relevance,
)


# ── Shared Fixtures ──────────────────────────────────────────────────────


def _sample_holdings():
    """5-stock portfolio: ~$500K across tech, healthcare, financials."""
    return [
        {"ticker": "MSFT", "name": "Microsoft", "weight_pct": 25.0, "shares": 250},
        {"ticker": "AAPL", "name": "Apple", "weight_pct": 20.0, "shares": 400},
        {"ticker": "JNJ", "name": "Johnson & Johnson", "weight_pct": 20.0, "shares": 500},
        {"ticker": "JPM", "name": "JPMorgan Chase", "weight_pct": 20.0, "shares": 300},
        {"ticker": "NVDA", "name": "NVIDIA", "weight_pct": 15.0, "shares": 100},
    ]


def _sample_market_data():
    """Overnight market data: tech up, healthcare flat, financials down."""
    return {
        "MSFT": {"price_change_pct": 2.5, "volume_change_pct": 30.0,
                  "sector": "Technology", "primary_driver": "AI revenue beat",
                  "analyst_view": "Outperform"},
        "AAPL": {"price_change_pct": -1.2, "volume_change_pct": 10.0,
                  "sector": "Technology", "primary_driver": "China sales concern",
                  "analyst_view": "Neutral"},
        "JNJ": {"price_change_pct": 0.3, "volume_change_pct": -5.0,
                 "sector": "Healthcare", "primary_driver": None,
                 "analyst_view": None},
        "JPM": {"price_change_pct": -2.1, "volume_change_pct": 20.0,
                 "sector": "Financials", "primary_driver": "NIM compression fears",
                 "analyst_view": "Hold"},
        "NVDA": {"price_change_pct": 5.8, "volume_change_pct": 80.0,
                  "sector": "Technology", "primary_driver": "Data center demand surge",
                  "analyst_view": "Strong Buy"},
    }


def _sample_news():
    """Mix of portfolio-relevant, watchlist, and general news."""
    return [
        {"headline": "NVDA reports record data center revenue",
         "source": "Bloomberg", "date": "2025-03-24",
         "impact_assessment": "high", "affected_tickers": ["NVDA"],
         "ai_synthesis": "NVIDIA data center revenue exceeded expectations",
         "sentiment": "positive"},
        {"headline": "Fed signals rate cuts unlikely before September",
         "source": "Reuters", "date": "2025-03-24",
         "impact_assessment": "high", "affected_tickers": ["JPM", "BAC"],
         "sentiment": "negative"},
        {"headline": "MSFT Copilot enterprise adoption accelerates",
         "source": "TechCrunch", "date": "2025-03-24",
         "impact_assessment": "medium", "affected_tickers": ["MSFT"],
         "sentiment": "positive"},
        {"headline": "Tesla recalls 500K vehicles over software issue",
         "source": "CNBC", "date": "2025-03-24",
         "impact_assessment": "medium", "affected_tickers": ["TSLA"],
         "sentiment": "negative"},
        {"headline": "Global chip shortage easing per industry report",
         "source": "Nikkei", "date": "2025-03-24",
         "impact_assessment": "low", "affected_tickers": ["INTC", "AMD"],
         "sentiment": "positive"},
    ]


# ── 1. Compute Portfolio Impact Tests ────────────────────────────────────


class TestComputePortfolioImpact:
    """Tests for compute_portfolio_impact()."""

    def test_weighted_net_change(self):
        """Net change is weight-adjusted sum of individual moves."""
        holdings = _sample_holdings()
        market_data = _sample_market_data()
        result = compute_portfolio_impact(holdings, market_data)
        assert isinstance(result, PortfolioImpact)
        # Manual: 25*2.5 + 20*(-1.2) + 20*0.3 + 20*(-2.1) + 15*5.8
        # = 62.5 - 24 + 6 - 42 + 87 = 89.5 => /100 = 0.895
        expected = (25 * 2.5 + 20 * (-1.2) + 20 * 0.3 + 20 * (-2.1) + 15 * 5.8) / 100.0
        assert abs(result.net_change_pct - round(expected, 4)) < 0.01

    def test_top_movers_sorted_by_abs_change(self):
        """Top movers sorted by absolute price change descending."""
        result = compute_portfolio_impact(_sample_holdings(), _sample_market_data())
        assert len(result.top_movers) == 5
        abs_changes = [abs(m.price_change_pct) for m in result.top_movers]
        assert abs_changes == sorted(abs_changes, reverse=True)
        assert result.top_movers[0].ticker == "NVDA"  # +5.8%

    def test_top_movers_capped_at_5(self):
        """With 10 holdings, only top 5 movers returned."""
        holdings = [
            {"ticker": f"T{i}", "name": f"Stock {i}", "weight_pct": 10.0, "shares": 100}
            for i in range(10)
        ]
        md = {f"T{i}": {"price_change_pct": i * 0.5, "sector": "Tech"} for i in range(10)}
        result = compute_portfolio_impact(holdings, md)
        assert len(result.top_movers) == 5

    def test_sector_aggregation(self):
        """Sectors are aggregated from market data."""
        result = compute_portfolio_impact(_sample_holdings(), _sample_market_data())
        sector_names = [s.sector for s in result.sectors]
        assert "Technology" in sector_names
        assert "Healthcare" in sector_names
        assert "Financials" in sector_names

    def test_empty_holdings(self):
        """No holdings returns empty result."""
        result = compute_portfolio_impact([], {})
        assert result.net_change_pct == 0.0
        assert result.top_movers == []
        assert result.sectors == []

    def test_missing_market_data(self):
        """Holding without market data treated as 0% change."""
        holdings = [{"ticker": "XYZ", "name": "Unknown", "weight_pct": 100.0, "shares": 10}]
        result = compute_portfolio_impact(holdings, {})
        assert result.net_change_pct == 0.0


# ── 2. Rank News by Relevance Tests ─────────────────────────────────────


class TestRankNewsByRelevance:
    """Tests for rank_news_by_relevance()."""

    def test_portfolio_tickers_score_highest(self):
        """News affecting portfolio tickers ranks above watchlist."""
        news = _sample_news()
        portfolio = ["NVDA", "MSFT", "JPM", "AAPL", "JNJ"]
        watchlist = ["TSLA"]
        result = rank_news_by_relevance(news, portfolio, watchlist)
        assert isinstance(result[0], NewsItem)
        # NVDA news: 3pts(portfolio) + 1pt(high impact) = 4
        # Fed news: 3pts(JPM) + 1pt(high impact) = 4
        # These should be top 2
        top_headlines = [r.headline for r in result[:2]]
        assert any("NVDA" in h for h in top_headlines)

    def test_watchlist_scores_medium(self):
        """Watchlist tickers score 2pts each."""
        news = [
            {"headline": "TSLA recall", "affected_tickers": ["TSLA"],
             "impact_assessment": "medium"},
        ]
        result = rank_news_by_relevance(news, [], ["TSLA"])
        assert len(result) == 1

    def test_empty_news(self):
        """No news returns empty list."""
        result = rank_news_by_relevance([], ["MSFT"], [])
        assert result == []

    def test_all_low_relevance(self):
        """News with no ticker overlap still returned, just lowest rank."""
        news = [
            {"headline": "Unrelated story", "affected_tickers": ["ZZZ"],
             "impact_assessment": "low"},
        ]
        result = rank_news_by_relevance(news, ["MSFT"], [])
        assert len(result) == 1
        assert result[0].headline == "Unrelated story"


# ── 3. Assess Thesis Impact Tests ────────────────────────────────────────


class TestAssessThesisImpact:
    """Tests for assess_thesis_impact()."""

    def test_thesis_reinforced(self):
        """Positive event matching thesis driver => reinforced."""
        thesis = [{
            "ticker": "MSFT",
            "thesis_statement": "AI-driven revenue growth",
            "key_drivers": ["AI", "cloud", "copilot"],
            "bull_case": "AI adoption accelerates enterprise revenue",
            "bear_case": "Regulatory backlash limits growth",
        }]
        events = [{
            "headline": "MSFT Copilot AI adoption surges among enterprise clients",
            "affected_tickers": ["MSFT"],
            "event_type": "news",
            "sentiment": "positive",
        }]
        result = assess_thesis_impact(thesis, events)
        assert len(result) == 1
        assert result[0].ticker == "MSFT"
        assert result[0].thesis_change == "reinforced"

    def test_thesis_challenged(self):
        """Negative event matching bear case => challenged."""
        thesis = [{
            "ticker": "JPM",
            "thesis_statement": "NIM expansion from higher rates",
            "key_drivers": ["NIM", "rates", "lending"],
            "bull_case": "Rate environment supports NIM expansion",
            "bear_case": "Rate cuts compress NIM significantly",
        }]
        events = [{
            "headline": "Fed signals aggressive rate cuts ahead, NIM pressure expected",
            "affected_tickers": ["JPM"],
            "event_type": "macro",
            "sentiment": "negative",
        }]
        result = assess_thesis_impact(thesis, events)
        assert len(result) == 1
        assert result[0].thesis_change == "challenged"
        assert result[0].recommended_action == "research_further"

    def test_no_matching_events(self):
        """No events for thesis ticker => no update generated."""
        thesis = [{"ticker": "XYZ", "key_drivers": ["growth"]}]
        events = [{"headline": "AAPL news", "affected_tickers": ["AAPL"],
                    "sentiment": "positive"}]
        result = assess_thesis_impact(thesis, events)
        assert result == []

    def test_empty_inputs(self):
        """Empty thesis or events."""
        assert assess_thesis_impact([], []) == []
        assert assess_thesis_impact([{"ticker": "X", "key_drivers": []}], []) == []


# ── 4. Compile Macro Context Tests ───────────────────────────────────────


class TestCompileMacroContext:
    """Tests for compile_macro_context()."""

    def test_full_macro_data(self):
        """All macro categories populated."""
        cb = [{"bank": "Fed", "action": "Held rates at 5.25-5.50%"}]
        econ = [
            {"indicator": "CPI", "actual": 3.2, "expected": 3.1,
             "prior": 3.0, "surprise_direction": "above"},
        ]
        geo = [
            {"headline": "Escalation in Middle East", "region": "Middle East",
             "severity": "high"},
        ]
        result = compile_macro_context(cb, econ, geo)
        assert isinstance(result, MacroContext)
        assert "Fed" in result.central_bank_news
        assert len(result.economic_data) == 1
        assert result.economic_data[0]["indicator"] == "CPI"
        assert len(result.geopolitical_alerts) == 1
        assert "HIGH" in result.geopolitical_alerts[0]

    def test_no_central_bank(self):
        """No central bank data => None."""
        result = compile_macro_context([], [], [])
        assert result.central_bank_news is None

    def test_multiple_central_banks(self):
        """Multiple CB actions joined by semicolon."""
        cb = [
            {"bank": "Fed", "action": "Held rates"},
            {"bank": "ECB", "action": "Cut 25bps"},
        ]
        result = compile_macro_context(cb, [], [])
        assert "Fed" in result.central_bank_news
        assert "ECB" in result.central_bank_news
        assert ";" in result.central_bank_news


# ── 5. Generate Actionable Insights Tests ────────────────────────────────


class TestGenerateActionableInsights:
    """Tests for generate_actionable_insights()."""

    def test_big_movers_generate_insights(self):
        """Movers > 3% trigger research insights."""
        pi = PortfolioImpact(
            net_change_pct=0.89,
            top_movers=[
                PortfolioMover(ticker="NVDA", name="NVIDIA",
                               price_change_pct=5.8, primary_driver="Data center surge"),
                PortfolioMover(ticker="MSFT", name="Microsoft",
                               price_change_pct=2.5, primary_driver="AI beat"),
            ],
            sectors=[],
        )
        result = generate_actionable_insights(pi, [], MacroContext())
        # NVDA > 5% => critical, MSFT < 3% => no insight
        nvda_insights = [i for i in result if "NVDA" in i.insight]
        assert len(nvda_insights) == 1
        assert nvda_insights[0].priority == "critical"

    def test_sector_divergence_insight(self):
        """Large sector spread generates rotation insight."""
        pi = PortfolioImpact(
            net_change_pct=0.0,
            top_movers=[],
            sectors=[
                SectorPerformance(sector="Technology", performance_pct=3.0),
                SectorPerformance(sector="Energy", performance_pct=-1.5),
            ],
        )
        result = generate_actionable_insights(pi, [], MacroContext())
        rotation_insights = [i for i in result if "divergence" in i.insight.lower()]
        assert len(rotation_insights) == 1

    def test_high_impact_news_insight(self):
        """High-impact news triggers follow-up insight."""
        news = [NewsItem(headline="Major regulatory action", impact_assessment="high",
                         affected_tickers=["MSFT"])]
        result = generate_actionable_insights(PortfolioImpact(), news, MacroContext())
        news_insights = [i for i in result if "regulatory" in i.insight.lower()]
        assert len(news_insights) == 1

    def test_geopolitical_alert_insight(self):
        """Geopolitical alerts trigger insights."""
        macro = MacroContext(geopolitical_alerts=["[HIGH] Middle East: Conflict escalation"])
        result = generate_actionable_insights(PortfolioImpact(), [], macro)
        geo_insights = [i for i in result if "eopolitical" in i.insight.lower()]
        assert len(geo_insights) == 1

    def test_no_insights_on_quiet_day(self):
        """Flat portfolio with no significant news => minimal insights."""
        pi = PortfolioImpact(
            net_change_pct=0.01,
            top_movers=[PortfolioMover(ticker="A", price_change_pct=0.1)],
            sectors=[SectorPerformance(sector="Tech", performance_pct=0.2)],
        )
        result = generate_actionable_insights(pi, [], MacroContext())
        # No big movers, no divergence, no macro => empty
        assert len(result) == 0


# ── 6. Assemble Briefing Prompt Tests ────────────────────────────────────


class TestAssembleBriefingPrompt:
    """Tests for assemble_briefing_prompt()."""

    def test_prompt_structure(self):
        """Prompt has system_prompt, user_prompt, data_context."""
        pi = PortfolioImpact(
            net_change_pct=0.89,
            top_movers=[PortfolioMover(ticker="NVDA", price_change_pct=5.8)],
            sectors=[],
        )
        news = [NewsItem(headline="Test headline")]
        macro = MacroContext(central_bank_news="Fed held rates")
        prefs = {"name": "John", "focus_areas": ["AI", "Cloud"], "tone": "concise"}
        result = assemble_briefing_prompt(prefs, pi, news, macro)
        assert "system_prompt" in result
        assert "user_prompt" in result
        assert "data_context" in result
        assert "John" in result["system_prompt"]
        assert "NVDA" in result["user_prompt"]

    def test_no_macro_news(self):
        """Without macro news, prompt says no activity."""
        result = assemble_briefing_prompt(
            {}, PortfolioImpact(), [], MacroContext(),
        )
        assert "No central bank activity" in result["user_prompt"]


# ── 7. Filter by Preferences Tests ──────────────────────────────────────


class TestFilterByPreferences:
    """Tests for filter_by_preferences()."""

    def test_sector_focus_filters_news(self):
        """Only news matching sector focus kept (plus high impact)."""
        content = {
            "news": [
                {"headline": "Tech rally", "sector": "technology",
                 "impact_assessment": "medium", "affected_tickers": []},
                {"headline": "Oil spike", "sector": "energy",
                 "impact_assessment": "medium", "affected_tickers": []},
                {"headline": "Critical event", "sector": "energy",
                 "impact_assessment": "high", "affected_tickers": []},
            ],
            "sectors": [
                {"sector": "technology"},
                {"sector": "energy"},
            ],
        }
        prefs = {"sector_focus": ["Technology"]}
        result = filter_by_preferences(content, prefs)
        # Tech news + high-impact energy news
        assert len(result["news"]) == 2
        # Only technology sector kept
        assert len(result["sectors"]) == 1

    def test_portfolio_only(self):
        """Only news affecting portfolio tickers kept."""
        content = {
            "news": [
                {"headline": "MSFT news", "affected_tickers": ["MSFT"]},
                {"headline": "TSLA news", "affected_tickers": ["TSLA"]},
            ],
        }
        prefs = {"portfolio_only": True, "portfolio_tickers": ["MSFT", "AAPL"]}
        result = filter_by_preferences(content, prefs)
        assert len(result["news"]) == 1
        assert result["news"][0]["headline"] == "MSFT news"

    def test_max_news_items(self):
        """News list truncated to max_news_items."""
        content = {"news": [{"headline": f"News {i}"} for i in range(20)]}
        result = filter_by_preferences(content, {"max_news_items": 5})
        assert len(result["news"]) == 5

    def test_no_preferences(self):
        """Empty preferences pass through all content."""
        content = {"news": [{"headline": "A"}], "sectors": [{"sector": "X"}]}
        result = filter_by_preferences(content, {})
        assert len(result["news"]) == 1


# ── 8. Compute Briefing Priority Tests ───────────────────────────────────


class TestComputeBriefingPriority:
    """Tests for compute_briefing_priority()."""

    def test_critical_from_large_move(self):
        """Net change > 2% => CRITICAL."""
        pi = PortfolioImpact(net_change_pct=2.5)
        assert compute_briefing_priority(pi, []) == "CRITICAL"

    def test_critical_from_negative_large_move(self):
        """Net change < -2% => CRITICAL."""
        pi = PortfolioImpact(net_change_pct=-3.0)
        assert compute_briefing_priority(pi, []) == "CRITICAL"

    def test_critical_from_high_news(self):
        """Any HIGH impact news => CRITICAL."""
        pi = PortfolioImpact(net_change_pct=0.1)
        news = [NewsItem(impact_assessment="high")]
        assert compute_briefing_priority(pi, news) == "CRITICAL"

    def test_high_from_moderate_move(self):
        """1% < |net_change| <= 2% => HIGH."""
        pi = PortfolioImpact(net_change_pct=1.5)
        assert compute_briefing_priority(pi, []) == "HIGH"

    def test_normal(self):
        """Small move, no high news => NORMAL."""
        pi = PortfolioImpact(net_change_pct=0.3)
        news = [NewsItem(impact_assessment="low")]
        assert compute_briefing_priority(pi, news) == "NORMAL"


# ── 9. Format Text Briefing Tests ───────────────────────────────────────


class TestFormatTextBriefing:
    """Tests for format_text_briefing()."""

    def test_contains_all_sections(self):
        """Formatted briefing contains all major sections."""
        briefing = MorningBriefingResult(
            briefing_priority="HIGH",
            executive_summary_template="Markets moved sharply on Fed news.",
            portfolio_impact=PortfolioImpact(
                net_change_pct=1.5,
                top_movers=[
                    PortfolioMover(ticker="NVDA", price_change_pct=5.8,
                                   primary_driver="Data center"),
                ],
                sectors=[
                    SectorPerformance(sector="Technology", performance_pct=2.0,
                                      key_catalyst="AI demand"),
                ],
            ),
            key_news=[
                NewsItem(headline="NVDA beats estimates", impact_assessment="high",
                         affected_tickers=["NVDA"]),
            ],
            thesis_updates=[
                ThesisUpdate(ticker="NVDA", thesis_change="reinforced",
                             recommended_action="hold"),
            ],
            macro_context=MacroContext(
                central_bank_news="Fed held rates",
                geopolitical_alerts=["[HIGH] Middle East: Tensions rise"],
            ),
            insights=[
                ActionableInsight(insight="NVDA needs review", priority="critical",
                                  suggested_research=["Check data center orders"]),
            ],
        )
        text = format_text_briefing(briefing)
        assert "MORNING BRIEFING [HIGH]" in text
        assert "EXECUTIVE SUMMARY" in text
        assert "PORTFOLIO IMPACT" in text
        assert "NVDA" in text
        assert "SECTOR PERFORMANCE" in text
        assert "KEY NEWS" in text
        assert "THESIS UPDATES" in text
        assert "MACRO CONTEXT" in text
        assert "ACTIONABLE INSIGHTS" in text

    def test_empty_briefing(self):
        """Empty briefing still produces valid output."""
        text = format_text_briefing(MorningBriefingResult())
        assert "MORNING BRIEFING" in text
        assert "PORTFOLIO IMPACT" in text


# ── 10. Build Morning Briefing (Orchestrator) Tests ──────────────────────


class TestBuildMorningBriefing:
    """Tests for build_morning_briefing() orchestrator."""

    def _full_prefs(self):
        return {
            "name": "Sarah",
            "focus_areas": ["AI", "Semiconductors"],
            "tone": "concise",
            "watchlist": ["TSLA", "AMD"],
            "thesis_data": [
                {
                    "ticker": "NVDA",
                    "thesis_statement": "AI infrastructure leader",
                    "key_drivers": ["data center", "AI", "GPU"],
                    "bull_case": "Data center demand exceeds expectations",
                    "bear_case": "GPU supply glut and competition from custom chips",
                },
                {
                    "ticker": "MSFT",
                    "thesis_statement": "AI monetization via Copilot",
                    "key_drivers": ["copilot", "AI", "enterprise"],
                    "bull_case": "Enterprise AI adoption drives revenue growth",
                    "bear_case": "Cloud growth deceleration",
                },
            ],
        }

    def _full_macro(self):
        return {
            "central_bank": [
                {"bank": "Fed", "action": "Held rates at 5.25-5.50%, hawkish tone"},
            ],
            "economic_releases": [
                {"indicator": "CPI YoY", "actual": 3.2, "expected": 3.1,
                 "prior": 3.0, "surprise_direction": "above"},
                {"indicator": "Jobless Claims", "actual": 215000, "expected": 220000,
                 "prior": 218000, "surprise_direction": "below"},
            ],
            "geopolitical": [
                {"headline": "New trade tariffs announced", "region": "US-China",
                 "severity": "medium"},
            ],
        }

    def test_full_briefing(self):
        """Full data produces comprehensive briefing."""
        result = build_morning_briefing(
            user_prefs=self._full_prefs(),
            holdings=_sample_holdings(),
            market_data=_sample_market_data(),
            news=_sample_news(),
            macro_data=self._full_macro(),
        )
        assert isinstance(result, MorningBriefingResult)

        # Portfolio impact
        assert result.portfolio_impact.net_change_pct != 0.0
        assert len(result.portfolio_impact.top_movers) == 5
        assert len(result.portfolio_impact.sectors) >= 2

        # News ranked
        assert len(result.key_news) == 5  # All 5 news items

        # Thesis updates (NVDA and MSFT should match events)
        tickers_updated = [t.ticker for t in result.thesis_updates]
        assert "NVDA" in tickers_updated  # NVDA news is positive + matches driver

        # Macro context
        assert result.macro_context.central_bank_news is not None
        assert "Fed" in result.macro_context.central_bank_news
        assert len(result.macro_context.economic_data) == 2
        assert len(result.macro_context.geopolitical_alerts) == 1

        # Insights generated
        assert len(result.insights) >= 1

        # Priority
        assert result.briefing_priority in ("CRITICAL", "HIGH", "NORMAL")

        # Executive summary template
        assert result.executive_summary_template != ""

    def test_minimal_data(self):
        """Empty inputs produce valid but empty briefing."""
        result = build_morning_briefing(
            user_prefs={},
            holdings=[],
            market_data={},
            news=[],
            macro_data={},
        )
        assert isinstance(result, MorningBriefingResult)
        assert result.portfolio_impact.net_change_pct == 0.0
        assert result.key_news == []
        assert result.thesis_updates == []
        assert result.briefing_priority == "NORMAL"

    def test_critical_priority_on_big_move(self):
        """Large portfolio move triggers CRITICAL priority."""
        holdings = [{"ticker": "MSFT", "name": "Microsoft", "weight_pct": 100.0, "shares": 1000}]
        market_data = {"MSFT": {"price_change_pct": 8.0, "sector": "Tech",
                                "primary_driver": "Massive beat"}}
        result = build_morning_briefing(
            user_prefs={},
            holdings=holdings,
            market_data=market_data,
            news=[],
            macro_data={},
        )
        # net_change = 100 * 8 / 100 = 8.0% => CRITICAL
        assert result.briefing_priority == "CRITICAL"

    def test_critical_priority_on_high_news(self):
        """HIGH impact news triggers CRITICAL priority even with small move."""
        news = [{"headline": "Breaking: major event", "impact_assessment": "high",
                 "affected_tickers": ["MSFT"], "sentiment": "negative"}]
        result = build_morning_briefing(
            user_prefs={},
            holdings=[{"ticker": "MSFT", "name": "MSFT", "weight_pct": 10.0, "shares": 10}],
            market_data={"MSFT": {"price_change_pct": 0.1, "sector": "Tech"}},
            news=news,
            macro_data={},
        )
        assert result.briefing_priority == "CRITICAL"
