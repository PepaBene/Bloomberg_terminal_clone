"""Pillar 3 Phase 4A — Morning Briefing Engine.

Pure computation engine for assembling daily morning briefings.
Computes portfolio impact, ranks news by relevance, assesses thesis
updates, compiles macro context, and generates actionable insights.

No database access — all functions accept and return plain data.
"""

from __future__ import annotations

from dataclasses import dataclass, field


# ── Dataclasses ───────────────────────────────────────────────────────────


@dataclass
class PortfolioMover:
    """A significant mover in the portfolio."""

    ticker: str = ""
    name: str = ""
    price_change_pct: float = 0.0
    primary_driver: str = ""
    analyst_view: str | None = None


@dataclass
class SectorPerformance:
    """Sector-level performance summary."""

    sector: str = ""
    performance_pct: float = 0.0
    key_catalyst: str | None = None


@dataclass
class PortfolioImpact:
    """Portfolio-level impact assessment."""

    net_change_pct: float = 0.0
    top_movers: list[PortfolioMover] = field(default_factory=list)
    sectors: list[SectorPerformance] = field(default_factory=list)


@dataclass
class NewsItem:
    """A ranked news item."""

    headline: str = ""
    source: str = ""
    date: str = ""
    impact_assessment: str = "low"  # high / medium / low
    affected_tickers: list[str] = field(default_factory=list)
    ai_synthesis: str | None = None


@dataclass
class ThesisUpdate:
    """An investment thesis update."""

    ticker: str = ""
    thesis_change: str = "neutral"  # reinforced / challenged / neutral
    reasoning: str = ""
    recommended_action: str = "hold"  # buy / hold / sell / research_further


@dataclass
class MacroContext:
    """Macroeconomic context summary."""

    central_bank_news: str | None = None
    economic_data: list[dict] = field(default_factory=list)
    geopolitical_alerts: list[str] = field(default_factory=list)


@dataclass
class ActionableInsight:
    """An actionable research insight."""

    insight: str = ""
    priority: str = "medium"  # critical / high / medium
    suggested_research: list[str] = field(default_factory=list)


@dataclass
class MorningBriefingResult:
    """Complete morning briefing result."""

    executive_summary_template: str = ""
    portfolio_impact: PortfolioImpact = field(default_factory=PortfolioImpact)
    key_news: list[NewsItem] = field(default_factory=list)
    thesis_updates: list[ThesisUpdate] = field(default_factory=list)
    macro_context: MacroContext = field(default_factory=MacroContext)
    insights: list[ActionableInsight] = field(default_factory=list)
    briefing_priority: str = "NORMAL"  # CRITICAL / HIGH / NORMAL


# ── 1. Compute Portfolio Impact ──────────────────────────────────────────


def compute_portfolio_impact(
    holdings: list[dict],
    market_data: dict,
) -> PortfolioImpact:
    """Compute portfolio-level P&L impact from overnight market moves.

    Parameters
    ----------
    holdings : list[dict]
        Each holding: ticker (str), name (str), weight_pct (float), shares (int).
    market_data : dict
        Keyed by ticker: {price_change_pct (float), volume_change_pct (float),
        sector (str), primary_driver (str | None), analyst_view (str | None)}.
    """
    if not holdings:
        return PortfolioImpact()

    # Compute weighted net change
    net_change = 0.0
    movers: list[PortfolioMover] = []
    sector_impacts: dict[str, list[float]] = {}
    sector_catalysts: dict[str, str | None] = {}

    for h in holdings:
        ticker = h.get("ticker", "")
        name = h.get("name", ticker)
        weight = h.get("weight_pct", 0.0)
        md = market_data.get(ticker, {})
        price_change = md.get("price_change_pct", 0.0)
        sector = md.get("sector", "Unknown")

        # Weighted contribution
        contribution = weight * price_change / 100.0
        net_change += contribution

        movers.append(PortfolioMover(
            ticker=ticker,
            name=name,
            price_change_pct=price_change,
            primary_driver=md.get("primary_driver", ""),
            analyst_view=md.get("analyst_view"),
        ))

        # Sector aggregation
        if sector not in sector_impacts:
            sector_impacts[sector] = []
            sector_catalysts[sector] = None
        sector_impacts[sector].append(price_change)
        if md.get("primary_driver"):
            sector_catalysts[sector] = md["primary_driver"]

    # Sort movers by absolute change, pick top 5
    movers.sort(key=lambda m: abs(m.price_change_pct), reverse=True)
    top_movers = movers[:5]

    # Build sector performance
    sectors: list[SectorPerformance] = []
    for sector_name, changes in sector_impacts.items():
        avg_change = sum(changes) / len(changes) if changes else 0.0
        sectors.append(SectorPerformance(
            sector=sector_name,
            performance_pct=round(avg_change, 2),
            key_catalyst=sector_catalysts.get(sector_name),
        ))
    sectors.sort(key=lambda s: abs(s.performance_pct), reverse=True)

    return PortfolioImpact(
        net_change_pct=round(net_change, 4),
        top_movers=top_movers,
        sectors=sectors,
    )


# ── 2. Rank News by Relevance ────────────────────────────────────────────


def rank_news_by_relevance(
    news_items: list[dict],
    portfolio_tickers: list[str],
    watchlist: list[str],
) -> list[NewsItem]:
    """Score and rank news items by portfolio relevance.

    Scoring: 3pts per portfolio ticker hit, 2pts per watchlist hit,
    1pt for sector/general market match.  Sort descending.

    Parameters
    ----------
    news_items : list[dict]
        Each: headline (str), source (str), date (str),
        impact_assessment (str), affected_tickers (list[str]),
        ai_synthesis (str | None), sector (str | None).
    portfolio_tickers : list[str]
        Tickers in the portfolio.
    watchlist : list[str]
        Tickers on the watchlist.
    """
    portfolio_set = set(t.upper() for t in portfolio_tickers)
    watchlist_set = set(t.upper() for t in watchlist)

    scored: list[tuple[float, NewsItem]] = []
    for item in news_items:
        tickers = [t.upper() for t in item.get("affected_tickers", [])]
        score = 0.0

        for t in tickers:
            if t in portfolio_set:
                score += 3.0
            elif t in watchlist_set:
                score += 2.0

        # Impact assessment boost
        impact = item.get("impact_assessment", "low")
        if impact == "high":
            score += 1.0
        elif impact == "medium":
            score += 0.5

        news_obj = NewsItem(
            headline=item.get("headline", ""),
            source=item.get("source", ""),
            date=item.get("date", ""),
            impact_assessment=impact,
            affected_tickers=item.get("affected_tickers", []),
            ai_synthesis=item.get("ai_synthesis"),
        )
        scored.append((score, news_obj))

    # Sort descending by score, then by impact
    impact_order = {"high": 0, "medium": 1, "low": 2}
    scored.sort(key=lambda x: (-x[0], impact_order.get(x[1].impact_assessment, 2)))

    return [item for _, item in scored]


# ── 3. Assess Thesis Impact ──────────────────────────────────────────────


def assess_thesis_impact(
    thesis_data: list[dict],
    overnight_events: list[dict],
) -> list[ThesisUpdate]:
    """Match overnight events to investment thesis drivers.

    Parameters
    ----------
    thesis_data : list[dict]
        Each thesis: ticker (str), thesis_statement (str),
        key_drivers (list[str]), bull_case (str), bear_case (str).
    overnight_events : list[dict]
        Each event: headline (str), affected_tickers (list[str]),
        event_type (str), sentiment (str: positive/negative/neutral).
    """
    updates: list[ThesisUpdate] = []

    for thesis in thesis_data:
        ticker = thesis.get("ticker", "")
        drivers = [d.lower() for d in thesis.get("key_drivers", [])]
        bull_case = thesis.get("bull_case", "").lower()
        bear_case = thesis.get("bear_case", "").lower()

        matched_events = []
        for evt in overnight_events:
            evt_tickers = [t.upper() for t in evt.get("affected_tickers", [])]
            if ticker.upper() in evt_tickers:
                matched_events.append(evt)

        if not matched_events:
            continue

        # Determine thesis change based on event sentiment vs. drivers
        reinforced_count = 0
        challenged_count = 0
        reasons: list[str] = []

        for evt in matched_events:
            headline = evt.get("headline", "").lower()
            sentiment = evt.get("sentiment", "neutral")

            # Check if event relates to key drivers
            driver_match = any(d in headline for d in drivers)

            if sentiment == "positive":
                if driver_match or any(kw in headline for kw in bull_case.split()[:5] if len(kw) > 3):
                    reinforced_count += 1
                    reasons.append(f"Positive: {evt.get('headline', '')}")
                else:
                    reinforced_count += 0.5
                    reasons.append(f"Positive (indirect): {evt.get('headline', '')}")
            elif sentiment == "negative":
                if driver_match or any(kw in headline for kw in bear_case.split()[:5] if len(kw) > 3):
                    challenged_count += 1
                    reasons.append(f"Negative: {evt.get('headline', '')}")
                else:
                    challenged_count += 0.5
                    reasons.append(f"Negative (indirect): {evt.get('headline', '')}")
            else:
                reasons.append(f"Neutral: {evt.get('headline', '')}")

        # Classify change
        if reinforced_count > challenged_count:
            change = "reinforced"
            action = "hold"
        elif challenged_count > reinforced_count:
            change = "challenged"
            action = "research_further"
        else:
            change = "neutral"
            action = "hold"

        updates.append(ThesisUpdate(
            ticker=ticker,
            thesis_change=change,
            reasoning="; ".join(reasons),
            recommended_action=action,
        ))

    return updates


# ── 4. Compile Macro Context ─────────────────────────────────────────────


def compile_macro_context(
    central_bank_data: list[dict],
    economic_releases: list[dict],
    geopolitical: list[dict],
) -> MacroContext:
    """Summarize overnight macro events.

    Parameters
    ----------
    central_bank_data : list[dict]
        Each: bank (str), action (str), detail (str).
    economic_releases : list[dict]
        Each: indicator (str), actual (float|str), expected (float|str),
        prior (float|str), surprise_direction (str).
    geopolitical : list[dict]
        Each: headline (str), region (str), severity (str).
    """
    # Central bank summary
    cb_news = None
    if central_bank_data:
        summaries = []
        for cb in central_bank_data:
            bank = cb.get("bank", "")
            action = cb.get("action", "")
            summaries.append(f"{bank}: {action}")
        cb_news = "; ".join(summaries)

    # Economic data pass-through
    econ_data = []
    for rel in economic_releases:
        econ_data.append({
            "indicator": rel.get("indicator", ""),
            "actual": rel.get("actual"),
            "expected": rel.get("expected"),
            "prior": rel.get("prior"),
            "surprise_direction": rel.get("surprise_direction", "inline"),
        })

    # Geopolitical alerts
    geo_alerts = []
    for g in geopolitical:
        headline = g.get("headline", "")
        region = g.get("region", "")
        severity = g.get("severity", "low")
        geo_alerts.append(f"[{severity.upper()}] {region}: {headline}")

    return MacroContext(
        central_bank_news=cb_news,
        economic_data=econ_data,
        geopolitical_alerts=geo_alerts,
    )


# ── 5. Generate Actionable Insights ─────────────────────────────────────


def generate_actionable_insights(
    portfolio_impact: PortfolioImpact,
    news: list[NewsItem],
    macro: MacroContext,
) -> list[ActionableInsight]:
    """Generate research actions from portfolio impact, news, and macro.

    Rules:
    - Big movers (|change| > 3%) need deep-dive review
    - Sector rotation signals (sectors diverging)
    - Macro impact on holdings
    - High-impact news items need follow-up
    """
    insights: list[ActionableInsight] = []

    # Big movers need review
    for mover in portfolio_impact.top_movers:
        if abs(mover.price_change_pct) > 3.0:
            priority = "critical" if abs(mover.price_change_pct) > 5.0 else "high"
            insights.append(ActionableInsight(
                insight=(
                    f"{mover.ticker} moved {mover.price_change_pct:+.1f}%"
                    f"{' — ' + mover.primary_driver if mover.primary_driver else ''}"
                ),
                priority=priority,
                suggested_research=[
                    f"Review {mover.ticker} position sizing",
                    f"Check {mover.ticker} news flow and analyst updates",
                ],
            ))

    # Sector rotation signals
    if len(portfolio_impact.sectors) >= 2:
        sorted_sectors = sorted(
            portfolio_impact.sectors,
            key=lambda s: s.performance_pct,
        )
        worst = sorted_sectors[0]
        best = sorted_sectors[-1]
        spread = best.performance_pct - worst.performance_pct
        if spread > 2.0:
            insights.append(ActionableInsight(
                insight=(
                    f"Sector divergence: {best.sector} ({best.performance_pct:+.1f}%) "
                    f"vs {worst.sector} ({worst.performance_pct:+.1f}%)"
                ),
                priority="high" if spread > 4.0 else "medium",
                suggested_research=[
                    f"Review {worst.sector} sector exposure",
                    f"Evaluate rotation into {best.sector}",
                ],
            ))

    # High-impact news follow-up
    for item in news[:5]:  # Top 5 news items
        if item.impact_assessment == "high":
            insights.append(ActionableInsight(
                insight=f"High-impact news: {item.headline}",
                priority="high",
                suggested_research=[
                    f"Assess impact on {', '.join(item.affected_tickers[:3])}",
                ],
            ))

    # Macro impact
    if macro.geopolitical_alerts:
        insights.append(ActionableInsight(
            insight=f"Geopolitical alert(s): {len(macro.geopolitical_alerts)} event(s) overnight",
            priority="high" if len(macro.geopolitical_alerts) > 1 else "medium",
            suggested_research=["Review geographic exposure of portfolio"],
        ))

    if macro.central_bank_news:
        insights.append(ActionableInsight(
            insight=f"Central bank activity: {macro.central_bank_news}",
            priority="high",
            suggested_research=["Review rate-sensitive holdings", "Check duration exposure"],
        ))

    return insights


# ── 6. Assemble Briefing Prompt ──────────────────────────────────────────


def assemble_briefing_prompt(
    user_prefs: dict,
    portfolio_impact: PortfolioImpact,
    news: list[NewsItem],
    macro: MacroContext,
) -> dict:
    """Build an LLM prompt for executive summary generation.

    Parameters
    ----------
    user_prefs : dict
        Keys: name (str), focus_areas (list[str]), tone (str).
    portfolio_impact : PortfolioImpact
    news : list[NewsItem]
    macro : MacroContext
    """
    user_name = user_prefs.get("name", "Analyst")
    focus = user_prefs.get("focus_areas", [])
    tone = user_prefs.get("tone", "professional")

    top_movers_text = ", ".join(
        f"{m.ticker} ({m.price_change_pct:+.1f}%)"
        for m in portfolio_impact.top_movers[:3]
    )

    top_news_text = "; ".join(
        n.headline for n in news[:3]
    )

    macro_text = macro.central_bank_news or "No central bank activity"

    return {
        "system_prompt": (
            f"You are a senior portfolio strategist briefing {user_name}. "
            f"Tone: {tone}. "
            f"Focus areas: {', '.join(focus) if focus else 'general market overview'}."
        ),
        "user_prompt": (
            f"Generate a concise morning briefing executive summary. "
            f"Portfolio net change: {portfolio_impact.net_change_pct:+.2f}%. "
            f"Top movers: {top_movers_text}. "
            f"Key news: {top_news_text}. "
            f"Macro: {macro_text}."
        ),
        "data_context": {
            "portfolio_net_change_pct": portfolio_impact.net_change_pct,
            "top_movers_count": len(portfolio_impact.top_movers),
            "news_count": len(news),
            "has_macro_alerts": bool(macro.geopolitical_alerts),
        },
    }


# ── 7. Filter by Preferences ────────────────────────────────────────────


def filter_by_preferences(
    all_content: dict,
    preferences: dict,
) -> dict:
    """Apply user preferences to filter briefing content.

    Parameters
    ----------
    all_content : dict
        Keys: news (list[dict]), insights (list[dict]), sectors (list[dict]).
    preferences : dict
        Keys: sector_focus (list[str] | None), risk_tolerance (str),
        portfolio_only (bool), max_news_items (int | None).
    """
    result = dict(all_content)

    sector_focus = preferences.get("sector_focus")
    portfolio_only = preferences.get("portfolio_only", False)
    max_news = preferences.get("max_news_items")

    # Filter news by sector focus
    if sector_focus:
        sector_set = set(s.lower() for s in sector_focus)
        filtered_news = []
        for n in result.get("news", []):
            # Keep if any affected ticker's sector matches, or if it's high impact
            n_sector = n.get("sector", "").lower() if isinstance(n, dict) else ""
            n_impact = n.get("impact_assessment", "low") if isinstance(n, dict) else "low"
            if n_sector in sector_set or n_impact == "high":
                filtered_news.append(n)
        result["news"] = filtered_news

    # Filter for portfolio-only news
    if portfolio_only:
        portfolio_tickers = set(
            t.upper() for t in preferences.get("portfolio_tickers", [])
        )
        filtered_news = []
        for n in result.get("news", []):
            tickers = n.get("affected_tickers", []) if isinstance(n, dict) else []
            if any(t.upper() in portfolio_tickers for t in tickers):
                filtered_news.append(n)
        result["news"] = filtered_news

    # Limit news count
    if max_news is not None:
        result["news"] = result.get("news", [])[:max_news]

    # Filter sectors
    if sector_focus:
        sector_set = set(s.lower() for s in sector_focus)
        result["sectors"] = [
            s for s in result.get("sectors", [])
            if s.get("sector", "").lower() in sector_set
        ]

    return result


# ── 8. Compute Briefing Priority ─────────────────────────────────────────


def compute_briefing_priority(
    portfolio_impact: PortfolioImpact,
    news: list[NewsItem],
) -> str:
    """Determine briefing priority level.

    CRITICAL: |net_change| > 2% or any HIGH impact news
    HIGH: |net_change| > 1%
    NORMAL: otherwise
    """
    net = abs(portfolio_impact.net_change_pct)
    has_high_news = any(n.impact_assessment == "high" for n in news)

    if net > 2.0 or has_high_news:
        return "CRITICAL"
    elif net > 1.0:
        return "HIGH"
    return "NORMAL"


# ── 9. Format Text Briefing ─────────────────────────────────────────────


def format_text_briefing(briefing: MorningBriefingResult) -> str:
    """Format briefing as a ~500-word narrative text template.

    Parameters
    ----------
    briefing : MorningBriefingResult
        Complete briefing data.
    """
    lines: list[str] = []

    # Header
    lines.append(f"=== MORNING BRIEFING [{briefing.briefing_priority}] ===")
    lines.append("")

    # Executive summary
    if briefing.executive_summary_template:
        lines.append("EXECUTIVE SUMMARY")
        lines.append(briefing.executive_summary_template)
        lines.append("")

    # Portfolio impact
    pi = briefing.portfolio_impact
    lines.append("PORTFOLIO IMPACT")
    lines.append(f"Net portfolio change: {pi.net_change_pct:+.2f}%")
    if pi.top_movers:
        lines.append("Top movers:")
        for m in pi.top_movers[:5]:
            driver_text = f" ({m.primary_driver})" if m.primary_driver else ""
            lines.append(f"  {m.ticker}: {m.price_change_pct:+.1f}%{driver_text}")
    lines.append("")

    # Sector performance
    if pi.sectors:
        lines.append("SECTOR PERFORMANCE")
        for s in pi.sectors:
            catalyst_text = f" — {s.key_catalyst}" if s.key_catalyst else ""
            lines.append(f"  {s.sector}: {s.performance_pct:+.1f}%{catalyst_text}")
        lines.append("")

    # Key news
    if briefing.key_news:
        lines.append("KEY NEWS")
        for n in briefing.key_news[:5]:
            tickers_text = f" [{', '.join(n.affected_tickers[:3])}]" if n.affected_tickers else ""
            lines.append(f"  [{n.impact_assessment.upper()}] {n.headline}{tickers_text}")
        lines.append("")

    # Thesis updates
    if briefing.thesis_updates:
        lines.append("THESIS UPDATES")
        for t in briefing.thesis_updates:
            lines.append(
                f"  {t.ticker}: {t.thesis_change.upper()} — "
                f"Action: {t.recommended_action.upper()}"
            )
        lines.append("")

    # Macro context
    mc = briefing.macro_context
    if mc.central_bank_news or mc.geopolitical_alerts:
        lines.append("MACRO CONTEXT")
        if mc.central_bank_news:
            lines.append(f"  Central Banks: {mc.central_bank_news}")
        for alert in mc.geopolitical_alerts[:3]:
            lines.append(f"  {alert}")
        lines.append("")

    # Actionable insights
    if briefing.insights:
        lines.append("ACTIONABLE INSIGHTS")
        for i in briefing.insights[:5]:
            lines.append(f"  [{i.priority.upper()}] {i.insight}")
            for r in i.suggested_research[:2]:
                lines.append(f"    -> {r}")
        lines.append("")

    return "\n".join(lines)


# ── 10. Build Morning Briefing (Orchestrator) ────────────────────────────


def build_morning_briefing(
    user_prefs: dict,
    holdings: list[dict],
    market_data: dict,
    news: list[dict],
    macro_data: dict,
) -> MorningBriefingResult:
    """Full orchestrator: assemble a complete morning briefing.

    Parameters
    ----------
    user_prefs : dict
        Keys: name (str), focus_areas (list[str]), tone (str),
        watchlist (list[str]), thesis_data (list[dict]),
        sector_focus (list[str] | None), risk_tolerance (str),
        portfolio_only (bool), max_news_items (int | None).
    holdings : list[dict]
        Portfolio holdings.
    market_data : dict
        Keyed by ticker with price changes.
    news : list[dict]
        Raw news items.
    macro_data : dict
        Keys: central_bank (list[dict]), economic_releases (list[dict]),
        geopolitical (list[dict]).
    """
    # 1. Portfolio impact
    portfolio_impact = compute_portfolio_impact(holdings, market_data)

    # 2. Rank news
    portfolio_tickers = [h.get("ticker", "") for h in holdings]
    watchlist = user_prefs.get("watchlist", [])
    ranked_news = rank_news_by_relevance(news, portfolio_tickers, watchlist)

    # 3. Thesis updates
    thesis_data = user_prefs.get("thesis_data", [])
    overnight_events = [
        {
            "headline": n.get("headline", ""),
            "affected_tickers": n.get("affected_tickers", []),
            "event_type": n.get("event_type", ""),
            "sentiment": n.get("sentiment", "neutral"),
        }
        for n in news
    ]
    thesis_updates = assess_thesis_impact(thesis_data, overnight_events)

    # 4. Macro context
    macro_context = compile_macro_context(
        central_bank_data=macro_data.get("central_bank", []),
        economic_releases=macro_data.get("economic_releases", []),
        geopolitical=macro_data.get("geopolitical", []),
    )

    # 5. Insights
    insights = generate_actionable_insights(portfolio_impact, ranked_news, macro_context)

    # 6. Briefing priority
    briefing_priority = compute_briefing_priority(portfolio_impact, ranked_news)

    # 7. Prompt for executive summary
    prompt = assemble_briefing_prompt(user_prefs, portfolio_impact, ranked_news, macro_context)
    executive_summary_template = prompt.get("user_prompt", "")

    return MorningBriefingResult(
        executive_summary_template=executive_summary_template,
        portfolio_impact=portfolio_impact,
        key_news=ranked_news,
        thesis_updates=thesis_updates,
        macro_context=macro_context,
        insights=insights,
        briefing_priority=briefing_priority,
    )
