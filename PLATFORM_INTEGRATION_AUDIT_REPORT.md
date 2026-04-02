# Bloomberg Data Fabric — Platform Integration Audit Report
## Full Feature Inventory, Gap Analysis & Integration Plan
### Generated: 2026-03-30 (v2 — includes helper classification, missing pages, broken UI)

---

## Executive Summary

This report audits every feature specified across the 8 platform specification documents against what is built in the backend (88 routers, 109 engines, 502 Python files) and what is wired into the frontend (48 pages, 34 hook files, 350+ endpoint constants).

**Key Findings:**

1. **Backend is ~95% complete** relative to spec. Nearly every specified feature has a router and engine.
2. **Frontend API layer is ~85% complete.** Hooks and endpoint constants exist for most features.
3. **Only 5 of 48 pages call the backend** (10.4%). The other 43 render hardcoded mock data.
4. **~92 of 109 engines are internal helpers** (NLP pipelines, data processing, calculation utilities). Only ~17 engines produce directly user-visible output. All 87 routers are user-facing.
5. **6 stub/broken UI elements** exist (buttons that do nothing, links that don't navigate, filters that don't filter).
6. **8+ backend features have no frontend page at all** — new pages must be created.
7. **No 404 page exists** — unmatched routes render blank.

### Scorecard

| Layer | Built | Wired to Frontend | % Integrated |
|-------|-------|-------------------|--------------|
| Backend Routers | 88 | — | — |
| Backend Engines (total) | 109 | — | — |
| Backend Engines (user-facing) | 17 | — | — |
| Backend Engines (internal/helper) | 92 | — | — |
| Frontend Endpoint Constants | 350+ paths | — | — |
| Frontend React Query Hooks | 34 files (~150+ hooks) | — | — |
| Frontend Pages with API calls | 5 of 48 | 5 | **10.4%** |
| Frontend Pages pure mock data | 43 of 48 | 0 | **0%** |
| Stub/broken UI elements | 6 | — | — |
| Backend features with no page | 8+ | — | — |

---

## Part 1: Internal vs User-Facing Feature Classification

Not every backend file represents a feature the user should see directly. Many engines are internal helpers — NLP preprocessing, data transformation, calculation utilities — that feed into user-facing routers.

### 1.1 Internal/Helper Engines (NOT user-facing — 92 engines)

These should NOT appear as frontend features. They are computation infrastructure:

| Category | Engines | Purpose |
|----------|---------|---------|
| **Framework** | base.py | Abstract BaseEngine class, utility helpers (safe_divide, pct_change, cagr) |
| **NLP Pipeline** | news_entity_linker.py, news_dedup.py, finbert_sentiment.py, sentiment_analysis.py, transcript_engine.py | Text processing, entity linking, sentiment scoring — feeds into user-facing news/sentiment endpoints |
| **Data Parsing** | csv_upload_engine.py, portfolio_parser.py, expression_parser.py, security_finder.py | Input validation, CSV parsing, formula evaluation — infrastructure for user actions |
| **Scoring Internals** | governance_scoring.py, insider_signals.py, eight_k_engine.py, filing_diff.py | Signal extraction from filings — feeds into filing intelligence and alert endpoints |
| **Intelligence Assembly** | company_intelligence.py, company_primer.py, company_primer_engine.py, business_model_engine.py, capital_allocation_engine.py, balance_sheet_risk_engine.py, management_quality_engine.py | Data assembly engines — their output is exposed via company_intelligence router |
| **Risk Internals** | e5_stress_scenarios.py, e5_fi_rate_shocks.py, portfolio_risk_engine.py, compliance_engine.py, drift_engine.py, concentration_risk.py, whatif_engine.py, trade_list_engine.py | Computation engines — output exposed via portfolio_risk and risk routers |
| **FI Internals** | e9_bond_pricing.py, e10_duration.py, e11_spread_analytics.py, e12_fi_risk.py, e13_credit_quality.py, e14_issuer_profile.py, e15_cross_asset.py, bond_analytics.py, credit_rating_analytics.py, credit_spread_analytics.py, issuance_analytics.py, issuer_linkage.py, yield_curve_bootstrap.py, yield_curve_analytics.py, treasury_analytics.py, fi_intelligence.py, cross_asset_narrative.py | FI calculation engines — output exposed via fi_* routers |
| **Scenario Internals** | e8_scenario.py, e8_prebuilt_scenarios.py, e8_fi_scenarios.py, macro_scenario_engine.py, macro_thematic_engine.py | Scenario modeling — output exposed via scenario router |
| **Intelligence Assembly** | morning_briefing_engine.py, investment_thesis_engine.py, analyst_qa_engine.py, semantic_search_engine.py, anomaly_detection_engine.py, intelligent_alert_engine.py, alert_engine.py, alert_expansion.py, earnings_surprise_engine.py, earnings_surprise_intelligence.py | AI/ML engines — output exposed via research_* and alerts routers |
| **Industry/Macro** | industry_economics.py, industry_cycle.py, moat_assessment.py, competitive_landscape.py, country_risk.py, commodity_intelligence.py, global_macro.py, political_intelligence.py, economic_calendar_engine.py, news_propagation.py | Analysis engines — output exposed via industry, global_intelligence, competitive routers |
| **Portfolio Internals** | nav_engine.py, performance_engine.py, attribution_engine.py, portfolio_analytics.py, corporate_action_engine.py, watchlist_monitoring.py, reporting_engine.py, pdf_report_engine.py | Portfolio computation — output exposed via portfolio_*, portfolios routers |
| **Backtesting** | backtester.py, technical_backtester.py, custom_index.py, technical_studies.py, esg_temperature.py, default_risk.py, market_movers.py, events_calendar.py | Specialized computations — exposed via corresponding routers |
| **Peer/Screening** | peer_service.py, e4_screening.py, e4_fi_screening.py, e4_screens_library.py, e6_institution_service.py | Screening/peer selection logic — exposed via screening and analytics routers |

### 1.2 User-Facing Engines (17 engines)

These are BaseEngine subclasses that directly produce metrics/scores users see:

| Engine | What Users See | Frontend Page |
|--------|---------------|---------------|
| e1_ratios.py | 400+ financial ratios | CompanyOverview, FinancialStatements |
| e1_dupont.py | DuPont ROE decomposition tree | ValuationDashboard |
| e1_ttm.py | TTM-adjusted metrics | CompanyOverview (embedded in ratios) |
| e1_trends.py | Historical metric trends | CompanyOverview, FinancialStatements |
| e1_industry_kpis.py | Industry-specific KPIs | CompanyOverview, IndustryDetail |
| e2_dcf.py | DCF valuation model results | ValuationDashboard |
| e2_multiples.py | Valuation multiples (P/E, EV/EBITDA) | ValuationDashboard |
| e2_comps.py | Comparable company analysis | ValuationDashboard |
| e2_football_field.py | Football field valuation summary | ValuationDashboard |
| e2_wacc.py | WACC calculation breakdown | ValuationDashboard |
| e3_piotroski.py | Piotroski F-Score (0-9) | CompanyOverview |
| e3_altman.py | Altman Z-Score | CompanyOverview |
| e3_beneish.py | Beneish M-Score | CompanyOverview |
| e3_composites.py | Composite quality/value/growth scores | CompanyOverview |
| e5_risk.py | VaR, volatility, Sharpe, drawdown | RiskPage, RiskDashboard |
| e6_flows.py | Fund flows, institutional activity | FlowsDashboard |
| e7_quant.py | Factor analysis, momentum, regression | QuantDashboard |

### 1.3 User-Facing Routers (87 routers)

All routers expose API endpoints that the frontend should call. The routers aggregate output from multiple internal engines into user-consumable responses. Every router = a feature the user should be able to access.

---

## Part 2: Complete Feature Status Matrix

Legend:
- **Spec**: Feature in specification docs | **Router**: Backend router exists | **Endpoint**: Frontend constant defined
- **Hook**: React Query hook exists | **Page**: UI page exists | **Wired**: Page actually calls API (not mock)

### Pillar 1: Data Fabric (User-Facing Features Only)

| # | Feature | Router | Endpoint | Hook | Page | Wired |
|---|---------|--------|----------|------|------|-------|
| D1 | Entity Master (CRUD, search, relationships) | entities.py | ENTITIES (14) | useEntities | CompanyOverview | PARTIAL |
| D1+ | Executive & Director Database | executives.py | ENTITIES.officers/board | useEntities | OwnershipDashboard | NO |
| D2 | Equity Security Master | securities.py | SECURITIES (18) | useSecurities | CompanyOverview | NO |
| D2+ | Bond Security Master | fi_bonds.py | FI.bonds (10) | useFiBonds | BondDetail | NO |
| D3 | Company Fundamentals (IS/BS/CF) | fundamentals.py | FUNDAMENTALS (14) | useFundamentals | FinancialStatements | NO |
| D3+ | Capital Structure Analysis | capital_structure.py | — | — | CreditProfile | NO |
| D3+ | Debt Maturity Profile | debt_maturity.py | — | — | CreditProfile | NO |
| D3+ | Credit Rating History | credit_rating.py + fi_ratings.py | FI.ratings (6) | useFiCredit | CreditProfile | NO |
| D4 | Consensus Estimates | estimates.py | FUNDAMENTALS.estimates (3) | useFundamentals | CompanyOverview | PARTIAL |
| D4+ | Earnings Intelligence | earnings_intelligence.py + earnings_p2.py | EARNINGS (10) | useEarnings | CompanyOverview | NO |
| D5 | Corporate Actions | corporate_actions.py | SECURITIES.corporateActions | useSecurities | **NO PAGE** | NO |
| D5+ | M&A Deal Database | ma_deals.py | DEALS (10) | useDeals | **NO PAGE** | NO |
| D5+ | IPO Monitor | ipo.py | — | — | **NO PAGE** | NO |
| D5+ | Corporate Actions Calendar | events_calendar_engine.py | ECONOMIC_CALENDAR (11) | useEconomicCalendar | MorningBrief | PARTIAL |
| D6 | Ownership & Holdings | ownership.py + flows.py | SECURITIES.inst* + FLOWS (15) | useOwnership | OwnershipDashboard | NO |
| D6+ | Fund Holdings (N-PORT) | fund_holdings.py | — | — | **NO PAGE** | NO |
| D7 | Macroeconomic Data | macro.py | MACRO (16) | useMacro | MacroDashboard | NO |
| D7+ | Yield Curve Data | yield_curve.py + fi_yield_curve.py | FI.yieldCurve (8) | useFiTreasuries | FIDashboard | PARTIAL |
| D7+ | Central Bank Monitor | fed_meeting.py | GLOBAL.centralBanks | useMacro | CentralBankMonitor | NO |
| D7+ | Money Market Rates | money_market.py | — | — | **NO PAGE** | NO |
| D8 | Reference Data (GICS) | reference.py | — | — | (internal) | N/A |
| D8+ | Custom Classifications | custom_classifications.py | — | — | **NO PAGE** | NO |
| D9 | ESG Data | esg.py | — | useEsg | **NO PAGE** | NO |
| D9+ | ESG Temperature Scoring | esg_temperature.py | — | — | **NO PAGE** | NO |
| D10 | Business Relationships | relationships.py | COMPETITIVE.supplyChain | useCompetitive | CompanyIntelligence | NO |
| D11.1 | Treasury Securities | fi_treasuries.py | FI.treasuries (5) | useFiTreasuries | TreasuryDashboard | NO |
| D11.2 | Yield Curve Engine | fi_yield_curve.py + yield_curve_analytics.py | FI.yieldCurve (8) | useFiTreasuries | YieldCurveDeepDive | NO |
| D11.3 | Corporate Bond Reference | fi_bonds.py | FI.bonds (10) | useFiBonds | BondDetail | NO |
| D11.4 | TRACE Trade & Price Data | fi_bonds.py (prices) | FI.bonds.prices | useFiBonds | BondDetail | NO |
| D11.5 | Credit Ratings History | fi_ratings.py | FI.ratings (6) | useFiCredit | CreditProfile | NO |
| D11.6 | Credit Spread Indices | fi_spreads.py + fi_spread_analytics.py | FI.credit (10) | useFiSpreads | CreditMarket | NO |
| D11.7 | Bond Issuance Database | fi_issuances.py | FI.newIssues (2) | useFiIntelligence | IssuanceMonitor | NO |
| D11.8 | Agency Bond Reference | fi_agency_bonds.py | — | — | **NO PAGE** | NO |
| Tech | Technical Studies Library | technical_studies.py | ANALYTICS.technicalSignals | useAnalytics | CompanyOverview | NO |

### Pillar 2: Analytics Engines (User-Facing Features Only)

| # | Feature | Router | Endpoint | Hook | Page | Wired |
|---|---------|--------|----------|------|------|-------|
| E1 | Financial Ratios (400+) | analytics.py | ANALYTICS.ratios | useAnalytics | CompanyOverview | PARTIAL |
| E1 | DuPont Decomposition | analytics.py | ANALYTICS.dupont | useAnalytics | ValuationDashboard | NO |
| E1 | Peer Comparison | analytics.py | ANALYTICS.peerGroup (3) | useAnalytics | ValuationDashboard | NO |
| E2 | DCF (FCFF/FCFE) | analytics.py | ANALYTICS.dcf + dcfSensitivity | useAnalytics | ValuationDashboard | NO |
| E2 | WACC Engine | analytics.py | — | — | ValuationDashboard | NO |
| E2 | Comparable Multiples | analytics.py | ANALYTICS.multiplesHistory | useAnalytics | ValuationDashboard | NO |
| E2 | Football Field | analytics.py | ANALYTICS.footballField | useAnalytics | ValuationDashboard | NO |
| E2 | Reverse DCF | analytics.py | — | — | **NO UI SECTION** | NO |
| E3 | Piotroski F-Score | analytics.py | ANALYTICS.qualityScore | useAnalytics | CompanyOverview | PARTIAL |
| E3 | Altman Z-Score | analytics.py | ANALYTICS.qualityScore | useAnalytics | CompanyOverview | PARTIAL |
| E3 | Beneish M-Score | analytics.py | ANALYTICS.qualityScore | useAnalytics | CompanyOverview | PARTIAL |
| E3 | Composite Scores (5 types) | analytics.py | ANALYTICS.compositeScores | useAnalytics | CompanyOverview | NO |
| E4 | Equity Screening (500+ fields) | screening.py | ANALYTICS.screen (5) | useScreening | ScreenerDashboard | NO |
| E4 | Pre-Built Screens (12+) | screening.py | ANALYTICS.screenPrebuilt | useScreening | ScreenerDashboard | NO |
| E4+ | FI Screener | fi_screening.py | FI.screen | useFiBonds | FIScreenerDashboard | NO |
| E5 | VaR / CVaR / Stress Testing | risk.py | PORTFOLIO_RISK.var+ | useRiskAnalytics | RiskPage + RiskDashboard | NO |
| E5 | Factor Risk Model | risk.py | PORTFOLIO_RISK.factorExposure | useRiskAnalytics | RiskDashboard | NO |
| E6 | Ownership Analytics / Flows | flows.py | FLOWS (15) | useOwnership | FlowsDashboard | NO |
| E7 | Statistical / Factor Analysis | quant.py | ANALYTICS.correlation + factorExposure | useQuant | QuantDashboard | NO |
| E8 | Scenario & Sensitivity | scenario.py | — | — | ValuationDashboard | NO |
| — | Equity Backtester | backtesting.py | — | — | **NO PAGE** | NO |
| — | Custom Index Builder | custom_index.py | — | — | **NO PAGE** | NO |
| — | Technical Backtester | technical_backtest.py | — | — | **NO PAGE** | NO |
| — | Default Risk Scoring | default_risk.py | FI.credit.defaultProbability | useFiCredit | CreditProfile | NO |

### Pillar 3: Research Intelligence (User-Facing Features Only)

| # | Feature | Router | Endpoint | Hook | Page | Wired |
|---|---------|--------|----------|------|------|-------|
| M1 | News Feed & Search | news.py | NEWS (8) | useNews | NewsView | NO |
| M1 | Sentiment Scores | sentiment.py + sentiment_p2.py | SENTIMENT (11) | useSentiment | CompanyOverview | NO |
| M2 | Filing Intelligence (diff) | filing_intelligence.py | FILING_INTELLIGENCE (9) | useFilingIntelligence | FilingsView | NO |
| M2 | 8-K Material Event Alerts | alerts.py | ALERTS (11) | useAlerts | AlertsView | NO |
| M2 | Insider Transaction Intelligence | filing_intelligence.py | FILING_INTELLIGENCE.insiders | useFilingIntelligence | FilingsView | NO |
| M2 | Proxy / Governance Analysis | governance_intelligence.py | GOVERNANCE (8) | useGovernance | **NO PAGE** | NO |
| M3 | Earnings Transcripts | earnings_p2.py | EARNINGS.transcripts | useEarnings | CompanyOverview | NO |
| M3 | Earnings Surprises | earnings_intelligence.py | EARNINGS.surprises | useEarnings | CompanyOverview | NO |
| M3 | Guidance Tracking | earnings_intelligence.py | EARNINGS.guidance | useEarnings | CompanyOverview | NO |
| M4 | Business Model Analysis | company_intelligence.py | COMPANY_INTEL (13) | useCompanyIntel | CompanyIntelligence | NO |
| M4 | Capital Allocation Intel | company_intelligence.py | COMPANY_INTEL.capitalAllocation | useCompanyIntel | CompanyIntelligence | NO |
| M4 | Management Quality | company_intelligence.py | COMPANY_INTEL.management | useCompanyIntel | CompanyIntelligence | NO |
| M4 | Balance Sheet Risk | company_intelligence.py | COMPANY_INTEL.balanceSheetRisk | useCompanyIntel | CompanyIntelligence | NO |
| M5 | Industry Economics & Cycle | industry.py | INDUSTRY (11) | useIndustry | SectorView + IndustryDetail | NO |
| M6 | Moat Assessment | competitive.py | COMPETITIVE (10) | useCompetitive | CompanyIntelligence | NO |
| M7 | Company Primer (BICO) | research_primers.py | RESEARCH.primers (4) | useResearch | PrimerView | NO |
| M7 | Morning Briefing | research_briefings.py | RESEARCH.briefings (5) | useResearch | BriefingView | NO |
| M7 | Anomaly Detection | research_anomalies.py | RESEARCH.anomalies (5) | useResearch | AnomalyView | NO |
| M7 | Semantic Search | research_search.py | RESEARCH.search (5) | useResearch | SemanticSearch | NO |
| M7 | Investment Thesis | research_thesis.py | RESEARCH.thesis (5) | useResearch | ThesisBuilder | NO |
| M7 | Research Q&A | research_qa.py | RESEARCH.qa (4) | useResearch | AnalystQA | NO |
| M7 | Research Themes | research_themes.py | RESEARCH.themes (7) | useResearch | ThemesDashboard | NO |
| M7 | Research Notes | research_notes.py | RESEARCH.notes (5) | useResearch | **NO UI SECTION** | NO |
| M8 | Alerting Engine | alerts.py + alerts_expansion.py | ALERTS (11) | useAlerts | AlertsView | NO |
| M9 | Country Risk Intelligence | global_intelligence.py | GLOBAL (14) | useGlobalIntel | CountryRisk + GlobalDashboard | NO |
| M9 | Commodity Intelligence | global_intelligence.py | GLOBAL.commodities | useGlobalIntel | CommodityDashboard | NO |
| M9 | Political Intelligence | global_intelligence.py | GLOBAL.bills + sanctions | useGlobalIntel | PoliticalMonitor | NO |
| M10 | Yield Curve Narrative | fi_intelligence.py | FI_INTELLIGENCE (11) | useFiIntelligence | FIDashboard | NO |
| M10 | Credit Market Intelligence | fi_intelligence.py | FI_INTELLIGENCE.creditBriefing | useFiIntelligence | CreditMarket | NO |
| M10 | New Issuance Intelligence | fi_issuances.py | FI_INTELLIGENCE.issuanceToday | useFiIntelligence | IssuanceMonitor | NO |

### Pillar 4: Portfolio & Risk (User-Facing Features Only)

| # | Feature | Router | Endpoint | Hook | Page | Wired |
|---|---------|--------|----------|------|------|-------|
| M1 | Portfolio CRUD | portfolios.py | PORTFOLIOS (27) | usePortfolios | PortfolioList | PARTIAL |
| M1 | CSV/Excel Upload | portfolio_upload.py | PORTFOLIOS.uploadPreview | usePortfolios | **NO UI** | NO |
| M1 | Position Management | portfolios.py | PORTFOLIOS.positions | usePortfolios | PortfolioDetail | NO |
| M1 | NAV Calculation | portfolios.py | PORTFOLIOS.nav | usePortfolios | PortfolioDetail | NO |
| M2 | TWR/MWR Performance | portfolio_performance.py | PORTFOLIO_PERFORMANCE (17) | usePortfolioPerformance | PerformancePage | NO |
| M2 | Brinson Attribution | portfolio_performance.py | PORTFOLIO_PERFORMANCE.attribution (4) | usePortfolioPerformance | PerformancePage | NO |
| M2 | Calendar Returns | portfolio_performance.py | PORTFOLIO_PERFORMANCE.calendarReturns | usePortfolioPerformance | PerformancePage | NO |
| M3 | Portfolio VaR | portfolio_risk.py | PORTFOLIO_RISK (30) | useRiskAnalytics | RiskPage | NO |
| M3 | Stress Testing | portfolio_risk.py | PORTFOLIO_RISK.stress* | useRiskAnalytics | RiskPage | NO |
| M3 | Factor Exposure | portfolio_risk.py | PORTFOLIO_RISK.factorExposure | useRiskAnalytics | RiskDashboard | NO |
| M4 | Drift Monitoring | portfolio_risk.py | PORTFOLIO_RISK.drift | useRiskAnalytics | **NO UI SECTION** | NO |
| M4 | What-If Analysis | portfolios.py | PORTFOLIOS.whatIf | usePortfolios | **NO UI SECTION** | NO |
| M4 | Rebalancing / Trade List | portfolios.py | PORTFOLIOS.rebalance | usePortfolios | **NO UI SECTION** | NO |
| M5 | Compliance Rules | portfolio_risk.py | PORTFOLIO_RISK.compliance | useRiskAnalytics | RiskPage | NO |
| M6 | Report Export (PDF/Excel) | — | EXPORTS (10) | — | **NO PAGE** | NO |
| M7 | Watchlist Management | portfolio_watchlists.py | WATCHLISTS (11) | usePortfolioWatchlists | WatchlistView | NO |

---

## Part 3: Missing Frontend Pages & UI Sections

### 3.1 Backend Features That Have NO Frontend Page

These backend routers/features have no corresponding page. New pages must be created:

| Feature | Backend Router | Suggested Route | Priority |
|---------|---------------|-----------------|----------|
| **ESG Dashboard** | esg.py + esg_temperature.py | /company/:id/esg | HIGH |
| **M&A Deals** | ma_deals.py | /deals (or /company/:id/deals) | MEDIUM |
| **IPO Monitor** | ipo.py | /market/ipo | MEDIUM |
| **Equity Backtester** | backtesting.py | /quant/backtest | MEDIUM |
| **Custom Index Builder** | custom_index.py | /quant/custom-index | LOW |
| **Technical Backtester** | technical_backtest.py | /quant/technical-backtest (or tab in QuantDashboard) | LOW |
| **Report Export** | (EXPORTS endpoints) | Modal/drawer accessible globally | HIGH |
| **Corporate Actions Timeline** | corporate_actions.py | /company/:id/actions (or section in CompanyOverview) | LOW |
| **Fund Holdings (N-PORT)** | fund_holdings.py | Section in OwnershipDashboard | LOW |
| **Money Market Rates** | money_market.py | Section in TreasuryDashboard or MacroDashboard | LOW |
| **Agency Bonds** | fi_agency_bonds.py | Section in FIDashboard or /fi/agency | LOW |
| **Custom Classifications** | custom_classifications.py | Section in Settings | LOW |
| **Governance / Proxy** | governance_intelligence.py | /company/:id/governance (or section in CompanyIntelligence) | MEDIUM |

### 3.2 Missing UI Sections Within Existing Pages

These features have a page but the page lacks sections to display backend output:

| Page | Missing Section | Backend Source | Priority |
|------|----------------|----------------|----------|
| **ValuationDashboard** | Reverse DCF (implied growth rate) | analytics.py | MEDIUM |
| **ValuationDashboard** | Editable DCF inputs (currently read-only) | analytics.py (POST) | HIGH |
| **CompanyOverview** | Earnings surprises + guidance tracker | earnings_intelligence.py | HIGH |
| **CompanyOverview** | Sentiment trend chart | sentiment.py | MEDIUM |
| **CompanyOverview** | Technical signals summary | technical_studies.py | LOW |
| **CompanyIntelligence** | Moat assessment + SWOT + Porter's Forces | competitive.py | HIGH |
| **CompanyIntelligence** | Revenue drivers + cost structure + margin analysis | company_intel_p2.py | HIGH |
| **PortfolioDetail** | What-if scenario panel | portfolios.py (whatIf) | MEDIUM |
| **PortfolioDetail** | Income projection + dividend calendar | portfolios.py | LOW |
| **PerformancePage** | Attribution breakdown (Brinson + factor) | portfolio_performance.py | HIGH |
| **PerformancePage** | Drawdown analysis + rolling returns | portfolio_performance.py | MEDIUM |
| **RiskPage** | Factor exposure table | portfolio_risk.py | HIGH |
| **RiskPage** | Correlation matrix | portfolio_risk.py | MEDIUM |
| **RiskPage** | Drift monitoring panel | portfolio_risk.py | MEDIUM |
| **PortfolioList** | CSV upload modal | portfolio_upload.py | HIGH |
| **FIDashboard** | Yield curve narrative (AI) | fi_intelligence.py | MEDIUM |
| **FIDashboard** | Credit briefing (AI) | fi_intelligence.py | MEDIUM |
| **QuantDashboard** | Regression tool + PCA | quant.py | MEDIUM |
| **ResearchHub** | Research notes panel | research_notes.py | LOW |

### 3.3 Missing Infrastructure

| Item | Description | Priority |
|------|-------------|----------|
| **404 Page** | No catch-all route exists — unmatched URLs render blank | HIGH |
| **Missing hooks for capital_structure, debt_maturity, money_market, fi_agency, custom_classifications, ipo, corporate_actions, exports, fund_holdings** | Endpoint constants and/or hooks need to be created for these routers | MEDIUM |

---

## Part 4: Broken/Stub UI Elements

These interactive elements exist in the UI but don't work:

### 4.1 Buttons That Do Nothing

| Page | Element | Current Behavior | Fix Required |
|------|---------|-----------------|--------------|
| **ResearchHub** | 6 "Launch" buttons on research cards | onClick is empty/undefined — buttons do nothing | Wire to `navigate('/research/primers')`, `/research/briefings`, etc. |
| **WatchlistView** | "Add" button | Placeholder callback with comment "would open an entity search dialog" | Build entity search dialog, wire to security finder |
| **Settings** | Theme selector (Dark/Light/System) | Has cursor:pointer but no onClick handler | Wire to theme store or CSS variable toggle |
| **Settings** | Notification toggles | Shows ON/OFF state but cannot be toggled | Wire to user preferences API |

### 4.2 Links That Don't Navigate

| Page | Element | Current Behavior | Fix Required |
|------|---------|-----------------|--------------|
| **CompanyOverview** | "View All →" in Filings section | No onClick handler | Wire to `navigate('/company/filings')` |
| **CompanyOverview** | "View All →" in Top Holders section | No onClick handler | Wire to `navigate('/company/ownership')` |
| **FIDashboard** | 4 Quick Links (Treasury, Credit, Screener, Monitor) | Have cursor:pointer style but no onClick | Wire to `/fi/treasuries`, `/fi/credit`, `/screener/fi`, `/fi/issuance` |

### 4.3 Filters That Don't Filter

| Page | Element | Current Behavior | Fix Required |
|------|---------|-----------------|--------------|
| **NewsView** | 6 filter pills (All, Earnings, M&A, Macro, Regulatory, Insider) | Hardcoded to "All", no filter state management | Add filter state, wire to `NEWS.byTopic()` or local filtering |

### 4.4 Read-Only Pages That Should Be Interactive

| Page | Missing Interaction | Fix Required |
|------|-------------------|--------------|
| **ValuationDashboard** | DCF inputs are display-only, not editable | Add input fields for WACC, growth rate, terminal multiple; POST to analytics endpoint |
| **ThesisBuilder** | Thesis is read-only display, cannot create/edit | Add form for generating thesis via `RESEARCH.thesis.generate` |
| **AnalystQA** | Chat is display-only, cannot type questions | Add input field + submit to `RESEARCH.qa.ask` |
| **SemanticSearch** | Search query is display-only | Add search input + submit to `RESEARCH.search.query` |
| **PortfolioDetail** | No add/edit/remove positions | Add position management UI wired to `PORTFOLIOS.positions` |
| **PortfolioList** | No CSV upload option | Add upload button + modal wired to `PORTFOLIOS.uploadPreview` |
| **RiskPage** | No custom stress test input | Add scenario builder wired to `PORTFOLIO_RISK.stressCustom` |
| **ScreenerDashboard** | Screener works locally but doesn't call backend | Wire ScreenBuilder to `ANALYTICS.screen` POST endpoint |
| **FIScreenerDashboard** | Same — local filtering only | Wire to `FI.screen` endpoint |

---

## Part 5: Comprehensive Integration Plan

### Phase 0: Infrastructure Fixes (do first)
**Priority: CRITICAL**

| Task | Details |
|------|---------|
| **0.1 Add 404 page** | Create NotFound.tsx, add `<Route path="*" element={<NotFound />} />` to router |
| **0.2 Fix ResearchHub launch buttons** | Wire 6 buttons to navigate to their sub-routes: `/research/primers`, `/research/briefings`, `/research/anomalies`, `/research/search`, `/research/thesis`, `/research/qa` |
| **0.3 Fix FIDashboard quick links** | Wire 4 links to `/fi/treasuries`, `/fi/credit`, `/screener/fi`, `/fi/issuance` |
| **0.4 Fix CompanyOverview "View All" links** | Wire to `/company/filings` and `/company/ownership` |
| **0.5 Fix NewsView filter pills** | Add filter state management, filter mock/API data by category |
| **0.6 Fix Settings controls** | Wire theme selector to CSS variable toggle, wire notification toggles to state |
| **0.7 Fix WatchlistView "Add" button** | Build simple entity search dialog (can use CommandBar pattern) |
| **0.8 Create missing hooks** | Add hooks for: useCapitalStructure, useDebtMaturity, useExports, useCorporateActions, useIpo, useFundHoldings, useMoneyMarket |

### Phase 1: Company Module — Wire API + Fix Interactivity
**Priority: CRITICAL — highest user traffic**

| Task | Page | What to Do |
|------|------|------------|
| 1.1 | FinancialStatements | Replace mock IS/BS/CF with `useFundamentals` hooks; add segments + revenue breakdown sections |
| 1.2 | ValuationDashboard | Wire DuPont/multiples/peers/DCF/sensitivity/football-field to `useAnalytics`; make DCF inputs editable with POST to backend |
| 1.3 | CreditProfile | Wire ratings/scores/spreads/bonds/maturity to `useFiCredit` + `useFiBonds`; add default probability + CDS sections |
| 1.4 | CompanyIntelligence | Wire all 13 COMPANY_INTEL endpoints via `useCompanyIntel`; add moat/SWOT/Porter sections from `useCompetitive` |
| 1.5 | OwnershipDashboard | Wire holdings/insider/short-interest to `useOwnership` + `useSecurities`; add fund holdings if available |
| 1.6 | FilingsView | Wire filings/diff/insiders to `useFilingIntelligence`; add risk factors + MD&A sections |
| 1.7 | CompanyOverview | Enhance: add sentiment chart (`useSentiment`), earnings surprises (`useEarnings`), technical signals (`useAnalytics`), all composite scores |
| 1.8 | **NEW: ESG page** | Create ESGDashboard.tsx at /company/:id/esg; wire to `useEsg` + ESG temperature endpoints; add route |
| 1.9 | **NEW: Governance page** | Create GovernanceDashboard.tsx at /company/:id/governance (or add section to CompanyIntelligence); wire to `useGovernance` |

### Phase 2: Portfolio Module — Wire API + Add Missing Interactions
**Priority: HIGH**

| Task | Page | What to Do |
|------|------|------------|
| 2.1 | PortfolioDetail | Wire holdings/NAV/allocations to `usePortfolios`; add position add/edit/remove UI; add what-if panel |
| 2.2 | PerformancePage | Wire returns/calendar/risk-metrics/benchmark to `usePortfolioPerformance`; add attribution section (Brinson + factor); add drawdown + rolling returns |
| 2.3 | RiskPage | Wire VaR/CVaR/concentration/stress/compliance to `useRiskAnalytics`; add factor exposure table + correlation matrix + drift panel; add custom stress test input |
| 2.4 | PortfolioList | Enhance: add CSV upload modal wired to `PORTFOLIOS.uploadPreview` + `uploadCommit`; show real NAV/returns per portfolio |
| 2.5 | **NEW: Export/Report modal** | Create ReportExportModal component; wire to EXPORTS endpoints; accessible from portfolio and company pages via Ctrl+E |

### Phase 3: Fixed Income Module — Wire All 6 Pages
**Priority: HIGH**

| Task | Page | What to Do |
|------|------|------------|
| 3.1 | FIDashboard | Wire treasury table + key spreads + new issues to FI hooks; add AI narrative sections |
| 3.2 | BondDetail | Wire bond data/pricing/spreads/cash-flows/call-schedule/covenants/comparables to `useFiBonds`; add duration/convexity/OAS sections |
| 3.3 | CreditMarket | Wire CDX indices + sector spreads + distressed list to `useFiSpreads` + `useFiCredit`; add AI credit briefing |
| 3.4 | TreasuryDashboard | Wire yield curve + auctions + on-the-run to `useFiTreasuries`; add forward/real/breakeven curves |
| 3.5 | IssuanceMonitor | Wire new issues + pipeline to `useFiBonds` + `useFiIntelligence` |
| 3.6 | FIIntelligence | Wire cross-asset signals + issuer credit to `useFiIntelligence` |
| 3.7 | FIScreenerDashboard | Wire to `FI.screen` backend endpoint |
| 3.8 | YieldCurveDeepDive | Wire all FI.yieldCurve.* endpoints (current, history, forward, real, breakeven, swap) |

### Phase 4: Screener Module — Wire Backend Screening
**Priority: HIGH**

| Task | Page | What to Do |
|------|------|------------|
| 4.1 | ScreenerDashboard | Wire ScreenBuilder to POST `ANALYTICS.screen`; wire prebuilt screens from `ANALYTICS.screenPrebuilt`; add save/load via `ANALYTICS.screenSave` + `screenHistory` |
| 4.2 | FIScreenerDashboard | Wire to `FI.screen` endpoint |

### Phase 5: Research Module — Wire AI Features + Fix Interactivity
**Priority: MEDIUM-HIGH**

| Task | Page | What to Do |
|------|------|------------|
| 5.1 | PrimerView | Wire to `RESEARCH.primers.byEntity`; add download + refresh buttons |
| 5.2 | BriefingView | Wire to `RESEARCH.briefings.today`; add generate button |
| 5.3 | AnomalyView | Wire to `RESEARCH.anomalies.active` + `.critical`; add acknowledge action |
| 5.4 | SemanticSearch | **Add search input field + submit**; wire to `RESEARCH.search.query` POST |
| 5.5 | ThesisBuilder | **Add thesis creation form**; wire generate to `RESEARCH.thesis.generate` POST; add validate button |
| 5.6 | AnalystQA | **Add chat input field + submit**; wire to `RESEARCH.qa.ask` POST; add follow-up support |
| 5.7 | ThemesDashboard | Wire to `RESEARCH.themes.list` + scenarios |
| 5.8 | ResearchHub | Wire quick intelligence card to actual data |

### Phase 6: Macro Module
**Priority: MEDIUM**

| Task | Page | What to Do |
|------|------|------------|
| 6.1 | MacroDashboard | Wire GDP/inflation/employment/indicators to `useMacro`; add PMI + consumer confidence |
| 6.2 | CentralBankMonitor | Wire to `GLOBAL.centralBanks` + `ECONOMIC_CALENDAR.centralBankMeetings` |
| 6.3 | YieldCurveDeepDive | (covered in Phase 3) |

### Phase 7: Remaining Pages
**Priority: MEDIUM**

| Task | Page | What to Do |
|------|------|------------|
| 7.1 | RiskDashboard | Wire VaR/concentration/factors to `useRiskAnalytics` (standalone, not portfolio-specific) |
| 7.2 | FlowsDashboard | Wire institutional flows + sector + whale alerts to FLOWS endpoints |
| 7.3 | QuantDashboard | Wire factor performance + correlation + regression to `useQuant` + `useAnalytics` |
| 7.4 | AlertsView | Wire to `useAlerts` — list, acknowledge, rules CRUD |
| 7.5 | NewsView | Wire to `useNews` — latest, search, trending; fix filter pills |
| 7.6 | WatchlistView | Wire to `usePortfolioWatchlists` — CRUD, alerts, performance |
| 7.7 | SectorView + IndustryDetail | Wire to `useIndustry` — overview, economics, cycle, rankings |
| 7.8 | GlobalDashboard + CountryRisk + CommodityDashboard + PoliticalMonitor | Wire to `useGlobalIntel` — countries, risk, commodities, events |
| 7.9 | CustomData | Wire to custom_data router |
| 7.10 | Settings | Wire theme toggle, notification prefs, API key management to `AUTH.*` |

### Phase 8: New Pages for Backend Features Without UI
**Priority: MEDIUM-LOW**

| Task | New Page | Route | Backend Source |
|------|----------|-------|----------------|
| 8.1 | ESGDashboard.tsx | /company/:id/esg | esg.py + esg_temperature.py |
| 8.2 | GovernanceDashboard.tsx | /company/:id/governance | governance_intelligence.py |
| 8.3 | DealsView.tsx | /deals | ma_deals.py |
| 8.4 | IPOMonitor.tsx | /market/ipo | ipo.py |
| 8.5 | BacktestDashboard.tsx | /quant/backtest | backtesting.py |
| 8.6 | NotFound.tsx (404) | * (catch-all) | — |
| 8.7 | Add CSV Upload modal | (in PortfolioList) | portfolio_upload.py |
| 8.8 | Add Export modal | (global) | EXPORTS endpoints |

### Phase 9: Polish & Missing Hooks
**Priority: LOW**

| Task | Details |
|------|---------|
| 9.1 | Create missing endpoint constants for: capital_structure, debt_maturity, money_market, fi_agency, custom_classifications, ipo, corporate_actions, fund_holdings, exports |
| 9.2 | Create missing hooks for the above |
| 9.3 | Add money market rates section to TreasuryDashboard |
| 9.4 | Add agency bonds section to FIDashboard |
| 9.5 | Add fund holdings section to OwnershipDashboard |
| 9.6 | Add custom classifications management to Settings |
| 9.7 | Add corporate actions timeline to CompanyOverview |
| 9.8 | Add Custom Index Builder page |
| 9.9 | Add Technical Backtester tab in QuantDashboard |

---

## Part 6: Implementation Pattern

Every page should follow this consistent pattern (established in MorningBrief and CompanyOverview):

```typescript
import { useQuery } from '@tanstack/react-query';
import { api } from '@/api/client';
import { ENDPOINTS } from '@/api/endpoints';

// Keep mock data as fallback
const MOCK_DATA = { /* existing mock constants */ };

export default function PageComponent() {
  const { id } = useParams();

  const { data: liveData, isLoading } = useQuery({
    queryKey: ['domain', 'resource', id],
    queryFn: () => api.get(ENDPOINTS.path(id!)),
    enabled: !!id,
    retry: 0,
    staleTime: 30_000,
  });

  const data = liveData ?? MOCK_DATA;

  if (isLoading) return <Skeleton />;
  return <ActualUI data={data} />;
}
```

For POST/mutation actions (create, generate, submit):

```typescript
const mutation = useMutation({
  mutationFn: (payload: T) => api.post(ENDPOINTS.path, payload),
  onSuccess: (data) => { /* update UI */ },
  onError: (err) => { /* show error toast */ },
});

<button onClick={() => mutation.mutate(payload)} disabled={mutation.isPending}>
  {mutation.isPending ? 'Processing...' : 'Submit'}
</button>
```

---

## Summary Statistics (Final)

| Metric | Count |
|--------|-------|
| Total user-facing features in spec | ~120 |
| Internal/helper engines (no direct UI needed) | 92 |
| User-facing engines | 17 |
| Backend routers (all user-facing) | 88 |
| Frontend pages existing | 48 |
| Frontend pages with real API calls | 5 (10.4%) |
| Frontend pages mock-only | 43 (89.6%) |
| Backend features with NO frontend page | 8 |
| Missing UI sections in existing pages | 19 |
| Broken/stub interactive elements | 13 |
| Missing frontend hooks | ~9 endpoint groups |
| New pages needed | 6-8 |
| Total integration tasks (Phases 0-10) | ~90 |

---

## Phase 10: Remove All Mock Data — Real Empty States & Error Handling
**Priority: FINAL — run after all pages are wired to API**

### Rationale

Phases 0–9 follow a "graceful migration" pattern: every page keeps its hardcoded mock data as fallback via `??` (nullish coalescing). This was intentional — it allows incremental integration without blank screens while the backend is being connected. Once **all pages are wired**, the mock data becomes misleading: users see fake numbers when the API is down or returns empty results, with no way to distinguish real data from fallback.

Phase 10 removes every inline mock constant and replaces the `?? MOCK_*` fallbacks with proper empty-state UI and error-state UI, so the platform only ever shows real data or an explicit "no data" / "something went wrong" message.

### 10.0 Shared Infrastructure (do first)

| Task | Details |
|------|---------|
| **10.0.1 Create `<EmptyState>` component** | Reusable component: icon + heading + optional description + optional CTA button. Variants: `no-data` (gray), `no-results` (filter-specific), `not-configured` (needs setup). Place in `@/components/ui/EmptyState.tsx`. |
| **10.0.2 Create `<ErrorState>` component** | Reusable component: error icon + message + "Retry" button (calls `refetch()`). Variants: `network` (connection lost), `server` (500), `not-found` (404), `forbidden` (403). Place in `@/components/ui/ErrorState.tsx`. |
| **10.0.3 Create `<LoadingSkeleton>` variants** | Skeleton loaders matching common page layouts: `table`, `card-grid`, `chart`, `kpi-row`, `detail-page`. Place in `@/components/ui/LoadingSkeleton.tsx`. |
| **10.0.4 Create `<DataGuard>` wrapper** | HOC/wrapper that takes `{ data, isLoading, error, emptyMessage }` and renders `<LoadingSkeleton>` / `<ErrorState>` / `<EmptyState>` / `children` automatically. Reduces per-page boilerplate. Place in `@/components/ui/DataGuard.tsx`. |
| **10.0.5 Add global error boundary** | Wrap `<AppRouter>` in a React error boundary that catches render crashes and shows a recovery UI instead of a white screen. Place in `@/components/ErrorBoundary.tsx`. |
| **10.0.6 Remove all `as any` casts** | Every Phase 1–9 page casts API hook returns with `as any` or `as any[]` to bridge untyped responses. Define proper TypeScript interfaces for each hook's return type in `@/types/api.ts` (or per-domain files like `@/types/company.ts`, `@/types/fi.ts`, etc.), update hook signatures to return typed data, and remove all `as any` casts from page components. This restores full type safety and enables IDE autocompletion. |

### 10.1 Company Module (9 pages)

| Task | Page | Mock Data to Remove | Empty/Error Handling to Add |
|------|------|---------------------|-----------------------------|
| 10.1.1 | CompanyOverview | `indices`, `watchlistQuick`, `recentFilings`, `topHolders`, `sectorPerformance`, `analystRatings`, inline score/earnings/sentiment/technical arrays | Show `<EmptyState>` per section when API returns empty; show `<ErrorState>` with retry on failure; remove all `?? mock` fallbacks |
| 10.1.2 | FinancialStatements | `incomeData`, `balanceData`, `cashFlowData`, `ratioData` | Empty table with "No financial data available" message; error banner above table on failure |
| 10.1.3 | ValuationDashboard | `multiplesData`, `peersData`, `dcfResult`, `footballData`, `dupontData`, `historicalMultiples` | "No valuation data" empty state per panel; disable DCF inputs when no base model returned |
| 10.1.4 | CreditProfile | `creditOverview`, `ratingHistory`, `spreadData`, `debtMaturity`, `bondList`, `cdsData` | "No credit profile available" with suggestion to check entity has rated debt |
| 10.1.5 | CompanyIntelligence | `businessModel`, `capitalAllocation`, `revenueDrivers`, `costStructure`, `qualityMetrics`, `moatData`, `swotData`, `porterData` | "Intelligence report not yet generated" empty state with "Generate Report" CTA |
| 10.1.6 | OwnershipDashboard | `institutionalHolders`, `insiderTransactions`, `ownershipSummary`, `shortInterestData`, `fundHoldings` | "No ownership data" per section; "No insider activity" for empty insider table |
| 10.1.7 | FilingsView | `recentFilings`, `filingTypes`, `filingCalendar`, `riskFactors`, `mdnaHighlights` | "No filings found" with filter-reset CTA if filters active; "Risk factors unavailable" |
| 10.1.8 | ESGDashboard | `mockEsgData`, `mockEsgScores`, `mockControversies` | "No ESG data available" — entity may not have ESG coverage |
| 10.1.9 | GovernanceDashboard | `mockGovernance`, `mockBoard`, `mockCompensation`, `mockProxy`, `mockProposals` | "No governance data" — entity may not be publicly traded |

### 10.2 Portfolio Module (4 pages)

| Task | Page | Mock Data to Remove | Empty/Error Handling to Add |
|------|------|---------------------|-----------------------------|
| 10.2.1 | PortfolioList | `samplePortfolios` | "No portfolios yet" with "Create Portfolio" CTA button |
| 10.2.2 | PortfolioDetail | `positions`, `allocations`, `navHistory`, `transactions` | "Portfolio is empty — add positions to get started" with "Add Position" CTA |
| 10.2.3 | PerformancePage | `returnsData`, `calendarReturns`, `attributionData`, `benchmarkData` | "Not enough history to calculate performance" when < 1 data point |
| 10.2.4 | RiskPage | `varData`, `stressResults`, `factorExposure`, `correlationMatrix` | "No risk metrics available" — portfolio may be empty or too new |

### 10.3 Fixed Income Module (6 pages)

| Task | Page | Mock Data to Remove | Empty/Error Handling to Add |
|------|------|---------------------|-----------------------------|
| 10.3.1 | FIDashboard | `treasuryYields`, `keyRates`, `spreadSnapshot`, `recentIssuance`, `fiNews` | Per-widget empty states: "Yield data unavailable", "No recent issuance" |
| 10.3.2 | BondDetail | `bondInfo`, `cashFlows`, `comparables`, `priceHistory` | "Bond not found" when CUSIP doesn't match; 404-style for invalid CUSIP |
| 10.3.3 | CreditMarket | `cdxIndices`, `sectorSpreads`, `distressedList`, `ratingChanges` | "Credit market data loading" skeleton; "Data temporarily unavailable" on error |
| 10.3.4 | TreasuryDashboard | `curveData`, `auctionSchedule`, `onTheRun`, `historicalCurves` | "Yield curve data unavailable" with retry |
| 10.3.5 | IssuanceMonitor | `newIssues`, `pipeline`, `pricingHistory` | "No new issuance today" — show last available date |
| 10.3.6 | FIIntelligence | `crossAssetSignals`, `issuerIntel`, `narratives` | "Intelligence briefing not yet generated" |

### 10.4 Research Module (8 pages)

| Task | Page | Mock Data to Remove | Empty/Error Handling to Add |
|------|------|---------------------|-----------------------------|
| 10.4.1 | ResearchHub | `quickIntel`, `recentPrimers`, `recentBriefings` | "No recent research" with links to generate primers/briefings |
| 10.4.2 | PrimerView | `primerContent`, `primerMeta` | "No primer available for this entity — click Generate to create one" |
| 10.4.3 | BriefingView | `briefingContent`, `marketOverview` | "No briefing for today — click Generate" with last-available date shown |
| 10.4.4 | AnomalyView | `activeAnomalies`, `anomalyHistory` | "No anomalies detected" (this is actually good news — style accordingly with a green check) |
| 10.4.5 | SemanticSearch | `searchResults` | "Enter a query to search" (initial state); "No results found" (after search) |
| 10.4.6 | ThesisBuilder | `thesisContent`, `supportingData` | "No thesis yet — describe your investment thesis to get started" |
| 10.4.7 | AnalystQA | `chatHistory`, `suggestedQuestions` | "Ask a question about any company, sector, or market" (initial state) |
| 10.4.8 | ThemesDashboard | `activeThemes`, `themeHistory` | "No active themes detected" |

### 10.5 Screener Module (2 pages)

| Task | Page | Mock Data to Remove | Empty/Error Handling to Add |
|------|------|---------------------|-----------------------------|
| 10.5.1 | ScreenerDashboard | `screenResults`, `prebuiltScreens`, `recentScreens` | "Add criteria and run screen" (initial); "No matches found — try relaxing filters" (empty result) |
| 10.5.2 | FIScreenerDashboard | `fiBondResults`, `fiPrebuiltScreens` | Same pattern as equity screener |

### 10.6 Macro & Global Module (7 pages)

| Task | Page | Mock Data to Remove | Empty/Error Handling to Add |
|------|------|---------------------|-----------------------------|
| 10.6.1 | MacroDashboard | `gdpData`, `inflationData`, `employmentData`, `indicators`, `pmiData` | Per-indicator empty states; "Data delayed" warning if stale > 24h |
| 10.6.2 | CentralBankMonitor | `centralBanks`, `meetingCalendar`, `rateDecisions` | "No upcoming meetings" with last-decision summary |
| 10.6.3 | YieldCurveDeepDive | `curveSnapshots`, `forwardCurves`, `realCurves`, `spreadHistory` | "Yield curve data unavailable" with retry; "Select curves to compare" initial state |
| 10.6.4 | GlobalDashboard | `globalIndices`, `fxRates`, `commodityPrices`, `heatmapData` | Per-widget empty states matching FI dashboard pattern |
| 10.6.5 | CountryRisk | `countryScores`, `riskBreakdown`, `sovereignSpreads` | "Select a country to view risk profile" initial state |
| 10.6.6 | CommodityDashboard | `commodityPrices`, `supplyDemand`, `seasonality` | "Commodity data unavailable" with retry |
| 10.6.7 | PoliticalMonitor | `events`, `riskMap`, `electionCalendar` | "No active political events" with date of last update |

### 10.7 Remaining Pages (7 pages)

| Task | Page | Mock Data to Remove | Empty/Error Handling to Add |
|------|------|---------------------|-----------------------------|
| 10.7.1 | RiskDashboard | `portfolioRisk`, `varSummary`, `concentrationData` | "No portfolio selected" initial state; "Select a portfolio to view risk" |
| 10.7.2 | FlowsDashboard | `institutionalFlows`, `sectorFlows`, `whaleAlerts` | "No flow data available for this period" |
| 10.7.3 | QuantDashboard | `factorReturns`, `correlationData`, `regressionResults`, `backtestResults` | "Configure and run analysis" initial state; "No results" after empty run |
| 10.7.4 | AlertsView | `activeAlerts`, `alertHistory`, `alertRules` | "No alerts — configure alert rules to get started" with "Create Rule" CTA |
| 10.7.5 | NewsView | `newsItems` | "No news matching your filters" with filter-reset CTA; "Breaking news unavailable" on error |
| 10.7.6 | WatchlistView | `watchlistItems`, `earningsCalendar`, `SEARCH_SUGGESTIONS` | "Your watchlist is empty — add securities to start monitoring" with "Add" CTA |
| 10.7.7 | SectorView + IndustryDetail | `sectorData`, `industryBreakdown`, `sectorPerformance` | "Select a sector" initial; "No industry data available" |

### 10.8 Home & Settings (3 pages)

| Task | Page | Mock Data to Remove | Empty/Error Handling to Add |
|------|------|---------------------|-----------------------------|
| 10.8.1 | MorningBrief (Home) | `marketSnapshot`, `topMovers`, `briefingContent`, `watchlistSummary` | "Morning briefing is loading..." skeleton; "Briefing generation failed — showing last available" on error with stale timestamp |
| 10.8.2 | Settings | `currentTheme`, `notifications` config | Settings page keeps local defaults (theme=dark, notifications=all-on) — these are user preferences, not mock data. Only remove if a user preferences API is wired. |
| 10.8.3 | CustomData | `customDataSets`, `uploadHistory` | "No custom data uploaded — drag & drop a CSV to get started" |

### Implementation Pattern for Phase 10

Every page transformation follows this pattern:

```typescript
// BEFORE (Phases 0-9 pattern):
const MOCK_ITEMS = [{ ticker: 'AAPL', price: 178.72, ... }, ...];

export default function SomePage() {
  const { data: apiData, isLoading } = useSomeHook(entityId);
  const items = apiData?.items ?? MOCK_ITEMS;  // ← fallback hides failures
  return <Table data={items} />;
}

// AFTER (Phase 10 pattern):
export default function SomePage() {
  const { data: apiData, isLoading, error, refetch } = useSomeHook(entityId);

  if (isLoading) return <LoadingSkeleton variant="table" />;
  if (error) return <ErrorState error={error} onRetry={refetch} />;
  if (!apiData?.items?.length) return <EmptyState icon="table" heading="No data available" />;

  return <Table data={apiData.items} />;
}
```

For pages with multiple independent data sections, use `<DataGuard>` per section rather than one guard for the whole page:

```typescript
export default function DashboardPage() {
  const scores = useCompositeScores(id);
  const earnings = useEarningsSurprises(id);
  const sentiment = useSentimentHistory(id);

  return (
    <div>
      <DataGuard query={scores} skeleton="kpi-row" emptyMessage="No scores available">
        <ScoresGrid data={scores.data} />
      </DataGuard>
      <DataGuard query={earnings} skeleton="table" emptyMessage="No earnings data">
        <EarningsTable data={earnings.data} />
      </DataGuard>
      <DataGuard query={sentiment} skeleton="chart" emptyMessage="No sentiment data">
        <SentimentChart data={sentiment.data} />
      </DataGuard>
    </div>
  );
}
```

### Checklist Before Starting Phase 10

- [ ] All pages from Phases 1-9 are wired to API hooks (no page still purely mock-only)
- [ ] Backend is running and returning real responses (even if empty)
- [ ] `<EmptyState>`, `<ErrorState>`, `<LoadingSkeleton>`, `<DataGuard>` components are built and tested (task 10.0)
- [ ] Global error boundary is in place (task 10.0.5)

### Total Phase 10 Tasks: ~48 page transformations + 5 infrastructure tasks = **53 tasks**
