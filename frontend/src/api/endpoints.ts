// =============================================================================
// Bloomberg Data Fabric — API Endpoint Constants
// Organized by Pillar / Domain
// =============================================================================

// ---------------------------------------------------------------------------
// Pillar 1: Data Foundation
// ---------------------------------------------------------------------------

export const ENTITIES = {
  list: '/v1/entities',
  detail: (id: string) => `/v1/entities/${id}`,
  search: '/v1/entities/search',
  create: '/v1/entities',
  update: (id: string) => `/v1/entities/${id}`,
  delete: (id: string) => `/v1/entities/${id}`,
  relationships: (id: string) => `/v1/entities/${id}/relationships`,
  subsidiaries: (id: string) => `/v1/entities/${id}/hierarchy`,
  parentChain: (id: string) => `/v1/entities/${id}/hierarchy`,
  officers: (id: string) => `/v1/entities/${id}/executives?role_type=EXECUTIVE`,
  boardMembers: (id: string) => `/v1/entities/${id}/executives?role_type=DIRECTOR`,
  history: (id: string) => `/v1/entities/${id}/history`,
  identifiers: (id: string) => `/v1/entities/${id}/identifiers`,
  classifications: (id: string) => `/v1/entities/${id}/classifications`,
} as const;

export const SECURITIES = {
  list: '/v1/securities',
  detail: (id: string) => `/v1/securities/${id}`,
  search: '/v1/securities/search',
  find: '/v1/securities/find',
  prices: (id: string) => `/v1/securities/${id}/prices`,
  pricesIntraday: (id: string) => `/v1/securities/${id}/prices/intraday`,
  pricesHistory: (id: string) => `/v1/securities/${id}/prices/history`,
  bulkLookup: '/v1/securities/bulk-lookup',
  translate: '/v1/securities/translate',
  institutionalHoldings: (id: string) => `/v1/securities/${id}/ownership/institutional`,
  insiderHoldings: (id: string) => `/v1/securities/${id}/ownership/insider`,
  ownershipSummary: (id: string) => `/v1/securities/${id}/ownership/summary`,
  shortInterest: (id: string) => `/v1/securities/${id}/short-interest`,
  technicals: (id: string) => `/v1/securities/${id}/technicals`,
  dividends: (id: string) => `/v1/securities/${id}/dividends`,
  splits: (id: string) => `/v1/securities/${id}/splits`,
  corporateActions: (id: string) => `/v1/securities/${id}/corporate-actions`,
  identifiers: (id: string) => `/v1/securities/${id}/identifiers`,
  exchanges: '/v1/securities/exchanges',
  sectors: '/v1/securities/sectors',
} as const;

export const FUNDAMENTALS = {
  incomeStatements: (entityId: string) => `/v1/entities/${entityId}/fundamentals/income-statement`,
  balanceSheets: (entityId: string) => `/v1/entities/${entityId}/fundamentals/balance-sheet`,
  cashFlows: (entityId: string) => `/v1/entities/${entityId}/fundamentals/cash-flow`,
  filings: (entityId: string) => `/v1/entities/${entityId}/filings`,
  segments: (entityId: string) => `/v1/entities/${entityId}/segments`,
  ratios: (entityId: string) => `/v1/entities/${entityId}/ratios`,
  revenueBreakdown: (entityId: string) => `/v1/entities/${entityId}/segments?segment_type=PRODUCT`,
  geographicBreakdown: (entityId: string) => `/v1/entities/${entityId}/segments?segment_type=GEOGRAPHIC`,
  quarterlyTrends: (entityId: string) => `/v1/entities/${entityId}/quarterly-trends`,
  annualSummary: (entityId: string) => `/v1/entities/${entityId}/annual-summary`,
  kpis: (entityId: string) => `/v1/entities/${entityId}/kpis`,
} as const;

// ---------------------------------------------------------------------------
// Pillar 2: Analytics
// ---------------------------------------------------------------------------

export const ANALYTICS = {
  // --- Ratios & Scores (paths fixed to match backend router) ---
  ratios: (secId: string) => `/v2/analytics/ratios/${secId}`,
  compositeScores: (secId: string) => `/v2/analytics/scores/${secId}/composites`,
  allScores: (secId: string) => `/v2/analytics/scores/${secId}`,
  dupont: (secId: string) => `/v2/analytics/dupont/${secId}`,
  dupontHistory: (secId: string) => `/v2/analytics/dupont/${secId}/history`,
  multiplesHistory: (secId: string) => `/v2/analytics/multiples/${secId}/history`,
  historicalMultiples: (secId: string) => `/v2/analytics/multiples/${secId}`,
  peerGroup: (secId: string) => `/v2/analytics/peers/${secId}`,
  peerComparison: (secId: string) => `/v2/analytics/ratios/${secId}/vs-peers`,
  peerRanking: (secId: string) => `/v2/analytics/peers/${secId}/ranking`,
  peerCustomSave: (secId: string) => `/v2/analytics/peers/${secId}/custom`,
  dcf: (secId: string) => `/v2/analytics/dcf/${secId}/default`,
  dcfPost: (secId: string) => `/v2/analytics/dcf/${secId}`,
  dcfSensitivity: (secId: string) => `/v2/analytics/dcf/${secId}/sensitivity`,
  footballField: (secId: string) => `/v2/analytics/valuation/${secId}/summary`,

  // --- Screening (paths fixed) ---
  screen: '/v2/analytics/screen',
  screenFields: '/v2/analytics/screen/fields',
  screenPrebuilt: '/v2/analytics/screens/library',
  screenSave: '/v2/analytics/screens/save',
  screenHistory: '/v2/analytics/screens/saved',

  // --- Individual sub-scores (mapped to composites endpoint) ---
  qualityScore: (secId: string) => `/v2/analytics/scores/${secId}/piotroski`,
  valueScore: (secId: string) => `/v2/analytics/scores/${secId}/composites`,
  growthScore: (secId: string) => `/v2/analytics/scores/${secId}/composites`,
  momentumScore: (secId: string) => `/v2/analytics/scores/${secId}/composites`,
  volatilityScore: (secId: string) => `/v2/analytics/scores/${secId}/composites`,

  // --- Individual quality scores ---
  piotroski: (secId: string) => `/v2/analytics/scores/${secId}/piotroski`,
  altman: (secId: string) => `/v2/analytics/scores/${secId}/altman`,
  beneish: (secId: string) => `/v2/analytics/scores/${secId}/beneish`,
  scoreHistory: (secId: string) => `/v2/analytics/scores/${secId}/history`,

  // --- WACC ---
  wacc: (secId: string) => `/v2/analytics/wacc/${secId}`,
  waccHistory: (secId: string) => `/v2/analytics/wacc/${secId}/history`,
  waccComponents: (secId: string) => `/v2/analytics/wacc/${secId}/components`,

  // --- TTM ---
  ttm: (secId: string) => `/v2/analytics/ttm/${secId}`,

  // --- Comps ---
  comps: (secId: string) => `/v2/analytics/comps/${secId}`,
  compsSummary: (secId: string) => `/v2/analytics/comps/${secId}/summary`,

  // --- Industry KPIs ---
  industryKpis: (secId: string) => `/v2/analytics/kpis/${secId}`,
  industryKpisHistory: (secId: string) => `/v2/analytics/kpis/${secId}/history`,

  // --- Trends ---
  trends: (secId: string) => `/v2/analytics/trends/${secId}`,

  // --- Audit / Lineage ---
  audit: (secId: string, metric: string) => `/v2/analytics/audit/${secId}/${metric}`,

  // --- Ranking ---
  rank: '/v2/analytics/rank',

  // --- Ratio detail endpoints ---
  ratioPercentile: (secId: string) => `/v2/analytics/ratios/${secId}/percentile`,
  ratioHistory: (secId: string) => `/v2/analytics/ratios/${secId}/history`,

  // --- These have no backend yet — hooks disabled until endpoints exist ---
  sectorRelative: (secId: string) => `/v2/analytics/sector-relative/${secId}`,
  fairValue: (secId: string) => `/v2/analytics/fair-value/${secId}`,
  technicalSignals: (secId: string) => `/v2/analytics/technical-signals/${secId}`,
  seasonality: (secId: string) => `/v2/analytics/seasonality/${secId}`,
  correlation: '/v2/analytics/correlation',
  factorExposure: (secId: string) => `/v2/analytics/factor-exposure/${secId}`,

  // --- Universe ---
  universeUsEquities: '/v2/analytics/universe/us-equities',
  universeSp500: '/v2/analytics/universe/sp500',
  universeRussell1000: '/v2/analytics/universe/russell1000',
} as const;

// Fixed Income
export const FI = {
  bonds: {
    list: '/v1/fi/bonds',
    detail: (cusip: string) => `/v1/fi/bonds/${cusip}`,
    prices: (cusip: string) => `/v1/fi/bonds/${cusip}/prices`,
    spreads: (cusip: string) => `/v1/fi/bonds/${cusip}/spreads`,
    byIssuer: (entityId: string) => `/v1/fi/bonds/issuer/${entityId}`,
    search: '/v1/fi/bonds/search',
    cashFlows: (cusip: string) => `/v1/fi/bonds/${cusip}/cash-flows`,
    callSchedule: (cusip: string) => `/v1/fi/bonds/${cusip}/call-schedule`,
    covenants: (cusip: string) => `/v1/fi/bonds/${cusip}/covenants`,
    comparables: (cusip: string) => `/v1/fi/bonds/${cusip}/comparables`,
  },
  treasuries: {
    list: '/v1/fi/treasuries',
    detail: (cusip: string) => `/v1/fi/treasuries/${cusip}`,
    onTheRun: '/v1/fi/treasuries/on-the-run',
    auction: '/v1/fi/treasuries/auction',
    auctionHistory: '/v1/fi/treasuries/auction/history',
  },
  yieldCurve: {
    current: '/v1/fi/yield-curve',
    spreads: '/v1/fi/yield-curve/spreads',
    history: '/v1/fi/yield-curve/history',
    forward: '/v1/fi/yield-curve/forward',
    real: '/v1/fi/yield-curve/real',
    breakeven: '/v1/fi/yield-curve/breakeven',
    swap: '/v1/fi/yield-curve/swap',
    sovereign: (countryCode: string) => `/v1/fi/yield-curve/sovereign/${countryCode}`,
  },
  ratings: {
    byEntity: (entityId: string) => `/v1/fi/ratings/${entityId}`,
    history: (entityId: string) => `/v1/fi/ratings/${entityId}/history`,
    recentChanges: '/v1/fi/ratings/changes',
    distribution: '/v1/fi/ratings/distribution',
    transitionMatrix: '/v1/fi/ratings/transition-matrix',
    outlook: (entityId: string) => `/v1/fi/ratings/${entityId}/outlook`,
  },
  credit: {
    score: (entityId: string) => `/v1/fi/credit/${entityId}/score`,
    ratios: (entityId: string) => `/v1/fi/credit/${entityId}/ratios`,
    peers: (entityId: string) => `/v1/fi/credit/${entityId}/peers`,
    trend: (entityId: string) => `/v1/fi/credit/${entityId}/trend`,
    sectorSpreads: '/v1/fi/credit/sector-spreads',
    distressed: '/v1/fi/credit/distressed',
    defaultProbability: (entityId: string) => `/v1/fi/credit/${entityId}/default-probability`,
    recoveryRate: (entityId: string) => `/v1/fi/credit/${entityId}/recovery-rate`,
    cds: (entityId: string) => `/v1/fi/credit/${entityId}/cds`,
    cdsCurve: (entityId: string) => `/v1/fi/credit/${entityId}/cds/curve`,
  },
  analytics: {
    price: '/v1/fi/analytics/price',
    yield: '/v1/fi/analytics/yield',
    duration: '/v1/fi/analytics/duration',
    oas: '/v1/fi/analytics/oas',
    spread: '/v1/fi/analytics/spread',
    convexity: '/v1/fi/analytics/convexity',
    keyRate: '/v1/fi/analytics/key-rate',
    totalReturn: '/v1/fi/analytics/total-return',
    scenario: '/v1/fi/analytics/scenario',
    rollDown: '/v1/fi/analytics/roll-down',
  },
  screen: '/v1/fi/screen/bonds',
  newIssues: '/v1/fi/new-issues',
  newIssuesPipeline: '/v1/fi/new-issues/pipeline',
  indices: {
    list: '/v1/fi/indices',
    detail: (indexId: string) => `/v1/fi/indices/${indexId}`,
    constituents: (indexId: string) => `/v1/fi/indices/${indexId}/constituents`,
    returns: (indexId: string) => `/v1/fi/indices/${indexId}/returns`,
  },
  muni: {
    list: '/v1/fi/muni',
    detail: (cusip: string) => `/v1/fi/muni/${cusip}`,
    byState: (state: string) => `/v1/fi/muni/state/${state}`,
    yields: '/v1/fi/muni/yields',
  },
  mortgage: {
    pools: '/v1/fi/mortgage/pools',
    prepayment: (poolId: string) => `/v1/fi/mortgage/pools/${poolId}/prepayment`,
    cashFlows: (poolId: string) => `/v1/fi/mortgage/pools/${poolId}/cash-flows`,
  },
} as const;

// ---------------------------------------------------------------------------
// Pillar 3: Intelligence
// ---------------------------------------------------------------------------

export const NEWS = {
  byEntity: (entityId: string) => `/v3/news/${entityId}`,
  latest: '/v3/news/latest',
  search: '/v3/news/search',
  trending: '/v3/news/trending',
  bySector: (sector: string) => `/v3/news/sector/${sector}`,
  byTopic: (topic: string) => `/v3/news/topic/${topic}`,
  detail: (articleId: string) => `/v3/news/article/${articleId}`,
  sources: '/v3/news/sources',
} as const;

export const ALERTS = {
  list: '/v3/alerts',
  acknowledge: (id: string) => `/v3/alerts/acknowledge/${id}`,
  rules: '/v3/alerts/config',
  create: '/v3/alerts/config',
  update: (ruleId: string) => `/v3/alerts/config/${ruleId}`,
  delete: (ruleId: string) => `/v3/alerts/config/${ruleId}`,
  history: '/v3/alerts/history',
  fi: {
    ratings: '/v3/alerts/fi/ratings',
    fallenAngels: '/v3/alerts/fi/fallen-angels',
    risingStars: '/v3/alerts/fi/rising-stars',
    spreadMoves: '/v3/alerts/fi/spread-moves',
    maturityAlerts: '/v3/alerts/fi/maturity',
    covenantBreaches: '/v3/alerts/fi/covenant-breaches',
  },
  equity: {
    priceAlerts: '/v3/alerts/equity/price',
    volumeAlerts: '/v3/alerts/equity/volume',
    earningsAlerts: '/v3/alerts/equity/earnings',
    dividendAlerts: '/v3/alerts/equity/dividend',
  },
} as const;

export const FILING_INTELLIGENCE = {
  events: (entityId: string) => `/v3/filings/${entityId}/events`,
  eventsToday: '/v3/filings/events/today',
  diff: (entityId: string) => `/v3/filings/${entityId}/diff/latest`,
  insiders: (entityId: string) => `/v3/filings/${entityId}/insiders`,
  detail: (entityId: string, filingId: string) => `/v3/filings/${entityId}/${filingId}`,
  summary: (entityId: string, filingId: string) => `/v3/filings/${entityId}/${filingId}/summary`,
  riskFactors: (entityId: string) => `/v3/filings/${entityId}/risk-factors`,
  mdna: (entityId: string) => `/v3/filings/${entityId}/mdna`,
  search: '/v3/filings/search',
} as const;

export const GOVERNANCE = {
  proxy: (entityId: string) => `/v3/filings/${entityId}/proxy`,
  compensation: (entityId: string) => `/v3/filings/${entityId}/compensation`,
  governance: (entityId: string) => `/v3/filings/${entityId}/governance`,
  board: (entityId: string) => `/v3/filings/${entityId}/board`,
  esg: (entityId: string) => `/v3/filings/${entityId}/esg`,
  esgScores: (entityId: string) => `/v3/filings/${entityId}/esg/scores`,
  esgHistory: (entityId: string) => `/v3/filings/${entityId}/esg/history`,
  shareholderProposals: (entityId: string) => `/v3/filings/${entityId}/shareholder-proposals`,
} as const;

export const SENTIMENT = {
  byEntity: (entityId: string) => `/v3/sentiment/${entityId}`,
  history: (entityId: string) => `/v3/sentiment/${entityId}/history`,
  peers: (entityId: string) => `/v3/sentiment/${entityId}/peers`,
  anomalies: (entityId: string) => `/v3/sentiment/${entityId}/anomalies`,
  social: (entityId: string) => `/v3/sentiment/${entityId}/social`,
  analystConsensus: (entityId: string) => `/v3/sentiment/${entityId}/analyst-consensus`,
  priceTargets: (entityId: string) => `/v3/sentiment/${entityId}/price-targets`,
  shortInterestSentiment: (entityId: string) => `/v3/sentiment/${entityId}/short-interest`,
  optionsFlow: (entityId: string) => `/v3/sentiment/${entityId}/options-flow`,
  sectorSentiment: '/v3/sentiment/sectors',
  marketSentiment: '/v3/sentiment/market',
} as const;

export const COMPETITIVE = {
  moat: (entityId: string) => `/v3/competitive/${entityId}/moat`,
  concentration: (entityId: string) => `/v3/competitive/${entityId}/concentration`,
  landscape: (entityId: string) => `/v3/competitive/${entityId}/landscape`,
  peers: (entityId: string) => `/v3/competitive/${entityId}/peers`,
  marketShare: (entityId: string) => `/v3/competitive/${entityId}/market-share`,
  swot: (entityId: string) => `/v3/competitive/${entityId}/swot`,
  porterForces: (entityId: string) => `/v3/competitive/${entityId}/porter-forces`,
  supplyChain: (entityId: string) => `/v3/competitive/${entityId}/supply-chain`,
  customers: (entityId: string) => `/v3/competitive/${entityId}/customers`,
  suppliers: (entityId: string) => `/v3/competitive/${entityId}/suppliers`,
} as const;

export const INDUSTRY = {
  overview: (gicsCode: string) => `/v3/industry/${gicsCode}/overview`,
  economics: (gicsCode: string) => `/v3/industry/${gicsCode}/economics`,
  cycle: (gicsCode: string) => `/v3/industry/${gicsCode}/cycle`,
  compare: '/v3/industry/compare',
  rankings: '/v3/industry/rankings',
  leaders: (gicsCode: string) => `/v3/industry/${gicsCode}/leaders`,
  trends: (gicsCode: string) => `/v3/industry/${gicsCode}/trends`,
  valuationBands: (gicsCode: string) => `/v3/industry/${gicsCode}/valuation-bands`,
  constituents: (gicsCode: string) => `/v3/industry/${gicsCode}/constituents`,
  flows: (gicsCode: string) => `/v3/industry/${gicsCode}/flows`,
  list: '/v3/industry/list',
  gicsTree: '/v3/industry/gics',
} as const;

export const GLOBAL = {
  countries: '/v3/global/countries',
  countryDetail: (code: string) => `/v3/global/countries/${code}`,
  countryRisk: (code: string) => `/v3/global/countries/${code}/risk`,
  countryEconomics: (code: string) => `/v3/global/countries/${code}/economics`,
  events: '/v3/global/events/geopolitical',
  macroDashboard: '/v3/global/macro/dashboard',
  centralBanks: '/v3/global/macro/central-banks',
  centralBankDetail: (bankId: string) => `/v3/global/macro/central-banks/${bankId}`,
  inflation: '/v3/global/macro/inflation',
  recessionProb: '/v3/global/macro/recession-probability',
  commodities: '/v3/global/commodities',
  commodityDetail: (symbol: string) => `/v3/global/commodities/${symbol}`,
  commodityPrices: (symbol: string) => `/v3/global/commodities/${symbol}/prices`,
  bills: '/v3/global/political/us/bills',
  sanctions: '/v3/global/political/sanctions',
  tradeData: '/v3/global/trade',
  fxRates: '/v3/global/fx/rates',
  fxHistory: (pair: string) => `/v3/global/fx/${pair}/history`,
  fxForward: (pair: string) => `/v3/global/fx/${pair}/forward`,
  globalIndices: '/v3/global/indices',
} as const;

export const COMPANY_INTEL = {
  overview: (entityId: string) => `/v3/intelligence/${entityId}`,
  businessModel: (entityId: string) => `/v3/intelligence/${entityId}/business-model`,
  capitalAllocation: (entityId: string) => `/v3/intelligence/${entityId}/capital-allocation`,
  management: (entityId: string) => `/v3/intelligence/${entityId}/management`,
  balanceSheetRisk: (entityId: string) => `/v3/intelligence/${entityId}/balance-sheet-risk`,
  revenueDrivers: (entityId: string) => `/v3/intelligence/${entityId}/revenue-drivers`,
  costStructure: (entityId: string) => `/v3/intelligence/${entityId}/cost-structure`,
  growthProfile: (entityId: string) => `/v3/intelligence/${entityId}/growth-profile`,
  qualityMetrics: (entityId: string) => `/v3/intelligence/${entityId}/quality-metrics`,
  riskProfile: (entityId: string) => `/v3/intelligence/${entityId}/risk-profile`,
  operatingLeverage: (entityId: string) => `/v3/intelligence/${entityId}/operating-leverage`,
  marginAnalysis: (entityId: string) => `/v3/intelligence/${entityId}/margin-analysis`,
  workingCapital: (entityId: string) => `/v3/intelligence/${entityId}/working-capital`,
} as const;

export const EARNINGS = {
  transcripts: (entityId: string) => `/v3/earnings/${entityId}/transcripts`,
  transcriptDetail: (entityId: string, transcriptId: string) => `/v3/earnings/${entityId}/transcripts/${transcriptId}`,
  surprises: (entityId: string) => `/v3/earnings/${entityId}/surprises`,
  guidance: (entityId: string) => `/v3/earnings/${entityId}/guidance`,
  calendar: '/v3/earnings/calendar',
  calendarByDate: (date: string) => `/v3/earnings/calendar/${date}`,
  quality: (entityId: string) => `/v3/earnings/${entityId}/quality`,
  seasonality: (entityId: string) => `/v3/earnings/${entityId}/seasonality`,
} as const;

// FI Intelligence (Pillar 3)
export const FI_INTELLIGENCE = {
  yieldCurveBriefing: '/v3/fi/yield-curve/briefing',
  creditBriefing: '/v3/fi/credit/briefing',
  issuanceToday: '/v3/fi/issuance/today',
  crossAssetSignals: '/v3/fi/cross-asset/signals',
  issuerCredit: (entityId: string) => `/v3/fi/issuers/${entityId}/credit-intelligence`,
  sectorOutlook: (sector: string) => `/v3/fi/sectors/${sector}/outlook`,
  relativeValue: '/v3/fi/relative-value',
  marketConditions: '/v3/fi/market-conditions',
  flowsAnalysis: '/v3/fi/flows',
  liquidityIndex: '/v3/fi/liquidity-index',
  technicalLevels: '/v3/fi/technical-levels',
} as const;

// ---------------------------------------------------------------------------
// Pillar 4: Portfolio & Risk
// ---------------------------------------------------------------------------

export const PORTFOLIOS = {
  list: '/v4/portfolios',
  detail: (id: string) => `/v4/portfolios/${id}`,
  create: '/v4/portfolios',
  update: (id: string) => `/v4/portfolios/${id}`,
  delete: (id: string) => `/v4/portfolios/${id}`,
  positions: (id: string) => `/v4/portfolios/${id}/positions`,
  positionDetail: (id: string, posId: string) => `/v4/portfolios/${id}/positions/${posId}`,
  transactions: (id: string) => `/v4/portfolios/${id}/transactions`,
  addTransaction: (id: string) => `/v4/portfolios/${id}/transactions`,
  nav: (id: string) => `/v4/portfolios/${id}/nav`,
  navHistory: (id: string) => `/v4/portfolios/${id}/nav/history`,
  uploadPreview: '/v4/portfolios/upload/preview',
  uploadCommit: '/v4/portfolios/upload/commit',
  clone: (id: string) => `/v4/portfolios/${id}/clone`,
  snapshot: (id: string) => `/v4/portfolios/${id}/snapshot`,
  allocations: (id: string) => `/v4/portfolios/${id}/allocations`,
  allocationsBySector: (id: string) => `/v4/portfolios/${id}/allocations/sector`,
  allocationsByCountry: (id: string) => `/v4/portfolios/${id}/allocations/country`,
  allocationsByAssetClass: (id: string) => `/v4/portfolios/${id}/allocations/asset-class`,
  rebalance: (id: string) => `/v4/portfolios/${id}/rebalance`,
  optimize: (id: string) => `/v4/portfolios/${id}/optimize`,
  whatIf: (id: string) => `/v4/portfolios/${id}/what-if`,
  taxLotAnalysis: (id: string) => `/v4/portfolios/${id}/tax-lots`,
  income: (id: string) => `/v4/portfolios/${id}/income`,
  incomeProjection: (id: string) => `/v4/portfolios/${id}/income/projection`,
  dividendCalendar: (id: string) => `/v4/portfolios/${id}/dividends/calendar`,
} as const;

export const PORTFOLIO_PERFORMANCE = {
  summary: (id: string) => `/v4/portfolios/${id}/performance`,
  returns: (id: string) => `/v4/portfolios/${id}/performance/returns`,
  calendarReturns: (id: string) => `/v4/portfolios/${id}/performance/returns/calendar`,
  attribution: (id: string) => `/v4/portfolios/${id}/attribution`,
  attributionBySector: (id: string) => `/v4/portfolios/${id}/attribution/sector`,
  attributionByFactor: (id: string) => `/v4/portfolios/${id}/attribution/factor`,
  attributionByCountry: (id: string) => `/v4/portfolios/${id}/attribution/country`,
  benchmark: (id: string) => `/v4/portfolios/${id}/performance/benchmark`,
  riskMetrics: (id: string) => `/v4/portfolios/${id}/performance/risk-metrics`,
  compare: '/v4/portfolios/performance/compare',
  drawdown: (id: string) => `/v4/portfolios/${id}/performance/drawdown`,
  rollingReturns: (id: string) => `/v4/portfolios/${id}/performance/rolling-returns`,
  alpha: (id: string) => `/v4/portfolios/${id}/performance/alpha`,
  sharpeHistory: (id: string) => `/v4/portfolios/${id}/performance/sharpe-history`,
  trackingError: (id: string) => `/v4/portfolios/${id}/performance/tracking-error`,
  informationRatio: (id: string) => `/v4/portfolios/${id}/performance/information-ratio`,
  upDownCapture: (id: string) => `/v4/portfolios/${id}/performance/capture-ratio`,
  holdingPeriodReturns: (id: string) => `/v4/portfolios/${id}/performance/holding-period`,
} as const;

export const PORTFOLIO_RISK = {
  dashboard: (id: string) => `/v4/portfolios/${id}/risk`,
  var: (id: string) => `/v4/portfolios/${id}/risk/var`,
  varDecomposition: (id: string) => `/v4/portfolios/${id}/risk/var/decomposition`,
  varBacktest: (id: string) => `/v4/portfolios/${id}/risk/var/backtest`,
  cvar: (id: string) => `/v4/portfolios/${id}/risk/cvar`,
  concentration: (id: string) => `/v4/portfolios/${id}/risk/concentration`,
  factors: (id: string) => `/v4/portfolios/${id}/risk/factors`,
  factorExposure: (id: string) => `/v4/portfolios/${id}/risk/factor-exposure`,
  stressHistorical: (id: string) => `/v4/portfolios/${id}/risk/stress/historical`,
  stressHypothetical: (id: string) => `/v4/portfolios/${id}/risk/stress/hypothetical`,
  stressCustom: (id: string) => `/v4/portfolios/${id}/risk/stress/custom`,
  scenarios: '/v4/portfolios/risk/scenarios',
  scenarioDetail: (scenarioId: string) => `/v4/portfolios/risk/scenarios/${scenarioId}`,
  compliance: (id: string) => `/v4/portfolios/${id}/compliance`,
  complianceRules: (id: string) => `/v4/portfolios/${id}/compliance/rules`,
  complianceAddRule: (id: string) => `/v4/portfolios/${id}/compliance/rules`,
  complianceHistory: (id: string) => `/v4/portfolios/${id}/compliance/history`,
  preTradeCheck: (id: string) => `/v4/portfolios/${id}/compliance/pre-trade-check`,
  drift: (id: string) => `/v4/portfolios/${id}/drift`,
  driftRebalance: (id: string) => `/v4/portfolios/${id}/drift/rebalance`,
  driftHistory: (id: string) => `/v4/portfolios/${id}/drift/history`,
  liquidity: (id: string) => `/v4/portfolios/${id}/risk/liquidity`,
  correlation: (id: string) => `/v4/portfolios/${id}/risk/correlation`,
  tailRisk: (id: string) => `/v4/portfolios/${id}/risk/tail`,
  beta: (id: string) => `/v4/portfolios/${id}/risk/beta`,
  volatility: (id: string) => `/v4/portfolios/${id}/risk/volatility`,
  creditRisk: (id: string) => `/v4/portfolios/${id}/risk/credit`,
  interestRateRisk: (id: string) => `/v4/portfolios/${id}/risk/interest-rate`,
  currencyRisk: (id: string) => `/v4/portfolios/${id}/risk/currency`,
  marginRequirements: (id: string) => `/v4/portfolios/${id}/risk/margin`,
} as const;

export const WATCHLISTS = {
  list: '/v4/portfolios/watchlists',
  create: '/v4/portfolios/watchlists',
  detail: (id: string) => `/v4/portfolios/watchlists/${id}`,
  update: (id: string) => `/v4/portfolios/watchlists/${id}`,
  delete: (id: string) => `/v4/portfolios/watchlists/${id}`,
  addItem: (id: string) => `/v4/portfolios/watchlists/${id}/items`,
  removeItem: (id: string, itemId: string) => `/v4/portfolios/watchlists/${id}/items/${itemId}`,
  alerts: (id: string) => `/v4/portfolios/watchlists/${id}/alerts`,
  digest: (id: string) => `/v4/portfolios/watchlists/${id}/alerts/digest`,
  performance: (id: string) => `/v4/portfolios/watchlists/${id}/performance`,
  heatmap: (id: string) => `/v4/portfolios/watchlists/${id}/heatmap`,
} as const;

// ---------------------------------------------------------------------------
// Research (Pillar 3 Phase 4)
// ---------------------------------------------------------------------------

export const RESEARCH = {
  primers: {
    recent: '/v4/research/primers/recent',
    byEntity: (entityId: string) => `/v4/research/primers/${entityId}`,
    refresh: (entityId: string) => `/v4/research/primers/${entityId}/refresh`,
    download: (entityId: string) => `/v4/research/primers/${entityId}/download`,
  },
  briefings: {
    today: '/v4/research/briefings/today',
    history: '/v4/research/briefings/history',
    preferences: '/v4/research/briefings/preferences',
    updatePreferences: '/v4/research/briefings/preferences',
    generate: '/v4/research/briefings/generate',
  },
  anomalies: {
    active: '/v4/research/anomalies/active',
    critical: '/v4/research/anomalies/critical',
    byEntity: (entityId: string) => `/v4/research/anomalies/${entityId}`,
    acknowledge: (anomalyId: string) => `/v4/research/anomalies/${anomalyId}/acknowledge`,
    history: '/v4/research/anomalies/history',
  },
  search: {
    query: '/v4/research/search',
    history: '/v4/research/search/history',
    suggested: '/v4/research/search/suggested',
    savedQueries: '/v4/research/search/saved',
    saveCriteria: '/v4/research/search/save',
  },
  thesis: {
    recent: '/v4/research/thesis/recent',
    byEntity: (entityId: string) => `/v4/research/thesis/${entityId}`,
    generate: '/v4/research/thesis/generate',
    update: (thesisId: string) => `/v4/research/thesis/${thesisId}`,
    validate: (thesisId: string) => `/v4/research/thesis/${thesisId}/validate`,
  },
  qa: {
    ask: '/v4/research/qa/ask',
    history: '/v4/research/qa/history',
    followUp: '/v4/research/qa/follow-up',
    sources: '/v4/research/qa/sources',
  },
  themes: {
    // Themes are labels the scoring engine assigns per entity
    // (macro_theme_scores is keyed by entity_id + theme, not by a
    // standalone theme id), so there's no create/update — themes aren't
    // user-authored resources. `detail`/`securities` below are real
    // aggregate/list-by-theme-label endpoints, not a theme catalog CRUD.
    list: '/v4/research/themes/dashboard',
    detail: (themeId: string) => `/v4/research/themes/summary/${themeId}`,
    scenarios: '/v4/research/scenarios',
    screen: '/v4/research/themes/screen',
    securities: (themeId: string) => `/v4/research/themes/${themeId}/securities`,
  },
  notes: {
    list: '/v4/research/notes',
    byEntity: (entityId: string) => `/v4/research/notes/${entityId}`,
    create: '/v4/research/notes',
    update: (noteId: string) => `/v4/research/notes/${noteId}`,
    delete: (noteId: string) => `/v4/research/notes/${noteId}`,
  },
} as const;

// ---------------------------------------------------------------------------
// Macro & Economic Data
// ---------------------------------------------------------------------------

export const MACRO = {
  indicators: '/v1/macro/indicators',
  indicatorDetail: (indicatorId: string) => `/v1/macro/indicators/${indicatorId}`,
  indicatorHistory: (indicatorId: string) => `/v1/macro/indicators/${indicatorId}/history`,
  gdp: '/v1/macro/gdp',
  gdpByCountry: (code: string) => `/v1/macro/gdp/${code}`,
  inflation: '/v1/macro/inflation',
  inflationByCountry: (code: string) => `/v1/macro/inflation/${code}`,
  employment: '/v1/macro/employment',
  employmentByCountry: (code: string) => `/v1/macro/employment/${code}`,
  yieldCurve: '/v1/yield-curve',
  pmi: '/v1/macro/pmi',
  consumerConfidence: '/v1/macro/consumer-confidence',
  housingStarts: '/v1/macro/housing-starts',
  retailSales: '/v1/macro/retail-sales',
  industrialProduction: '/v1/macro/industrial-production',
  tradeBalance: '/v1/macro/trade-balance',
  moneySupply: '/v1/macro/money-supply',
  dashboard: '/v1/macro/dashboard',
} as const;

// ---------------------------------------------------------------------------
// Flows & Ownership
// ---------------------------------------------------------------------------

export const FLOWS = {
  institutional: '/v1/flows/institutional',
  institutionalDetail: (fundId: string) => `/v1/flows/institutional/${fundId}`,
  sectors: '/v1/flows/sectors',
  styles: '/v1/flows/styles',
  etf: '/v1/flows/etf',
  etfDetail: (etfId: string) => `/v1/flows/etf/${etfId}`,
  mutualFund: '/v1/flows/mutual-fund',
  mutualFundDetail: (fundId: string) => `/v1/flows/mutual-fund/${fundId}`,
  whaleAlerts: '/v1/alerts/whale-moves',
  activistActivity: '/v1/alerts/activist-activity',
  darkPool: '/v1/flows/dark-pool',
  optionsFlow: '/v1/flows/options',
  insiderFlow: '/v1/flows/insider',
  foreignFlow: '/v1/flows/foreign',
  retailFlow: '/v1/flows/retail',
} as const;

// ---------------------------------------------------------------------------
// Economic Calendar
// ---------------------------------------------------------------------------

export const ECONOMIC_CALENDAR = {
  upcoming: '/v3/economic-calendar/upcoming',
  releases: '/v3/economic-calendar/releases',
  byDate: (date: string) => `/v3/economic-calendar/${date}`,
  byCountry: (code: string) => `/v3/economic-calendar/country/${code}`,
  byImportance: '/v3/economic-calendar/high-impact',
  ipoCalendar: '/v3/economic-calendar/ipo',
  dividendCalendar: '/v3/economic-calendar/dividends',
  splitCalendar: '/v3/economic-calendar/splits',
  fedMeetings: '/v3/economic-calendar/fed',
  centralBankMeetings: '/v3/economic-calendar/central-banks',
  optionsExpiry: '/v3/economic-calendar/options-expiry',
} as const;

// ---------------------------------------------------------------------------
// Market Data (Real-time / Streaming)
// ---------------------------------------------------------------------------

export const MARKET_DATA = {
  quote: (symbol: string) => `/v1/market-data/quote/${symbol}`,
  quotes: '/v1/market-data/quotes',
  depth: (symbol: string) => `/v1/market-data/depth/${symbol}`,
  trades: (symbol: string) => `/v1/market-data/trades/${symbol}`,
  ohlcv: (symbol: string) => `/v1/market-data/ohlcv/${symbol}`,
  snapshot: '/v1/market-data/snapshot',
  marketStatus: '/v1/market-data/status',
  indices: '/v1/market-data/indices',
  indexDetail: (indexId: string) => `/v1/market-data/indices/${indexId}`,
  indexConstituents: (indexId: string) => `/v1/market-data/indices/${indexId}/constituents`,
  futures: '/v1/market-data/futures',
  futureDetail: (symbol: string) => `/v1/market-data/futures/${symbol}`,
  options: (underlyer: string) => `/v1/market-data/options/${underlyer}`,
  optionChain: (underlyer: string) => `/v1/market-data/options/${underlyer}/chain`,
  impliedVolatility: (underlyer: string) => `/v1/market-data/options/${underlyer}/iv`,
  volumeProfile: (symbol: string) => `/v1/market-data/volume-profile/${symbol}`,
  heatmap: '/v1/market-data/heatmap',
  movers: '/v1/market-data/movers',
  moversBySector: (sector: string) => `/v1/market-data/movers/${sector}`,
  highs52w: '/v1/market-data/highs-52w',
  lows52w: '/v1/market-data/lows-52w',
  mostActive: '/v1/market-data/most-active',
  advancersDecliners: '/v1/market-data/breadth',
  vix: '/v1/market-data/vix',
  stream: '/v1/market-data/stream',
} as const;

// ---------------------------------------------------------------------------
// Capital Structure & Debt
// ---------------------------------------------------------------------------

export const CAPITAL_STRUCTURE = {
  overview: (entityId: string) => `/v1/entities/${entityId}/capital-structure`,
  debtBreakdown: (entityId: string) => `/v1/entities/${entityId}/capital-structure/debt`,
  equityBreakdown: (entityId: string) => `/v1/entities/${entityId}/capital-structure/equity`,
  history: (entityId: string) => `/v1/entities/${entityId}/capital-structure/history`,
} as const;

export const DEBT_MATURITY = {
  profile: (entityId: string) => `/v1/entities/${entityId}/debt-maturity`,
  schedule: (entityId: string) => `/v1/entities/${entityId}/debt-maturity/schedule`,
  refinancingRisk: (entityId: string) => `/v1/entities/${entityId}/debt-maturity/refinancing-risk`,
} as const;

// ---------------------------------------------------------------------------
// Corporate Actions
// ---------------------------------------------------------------------------

export const CORPORATE_ACTIONS = {
  byEntity: (entityId: string) => `/v1/entities/${entityId}/corporate-actions`,
  calendar: '/v1/corporate-actions/calendar',
  upcoming: '/v1/corporate-actions/upcoming',
  dividends: (entityId: string) => `/v1/entities/${entityId}/corporate-actions/dividends`,
  splits: (entityId: string) => `/v1/entities/${entityId}/corporate-actions/splits`,
  spinoffs: (entityId: string) => `/v1/entities/${entityId}/corporate-actions/spinoffs`,
} as const;

// ---------------------------------------------------------------------------
// IPO Monitor
// ---------------------------------------------------------------------------

export const IPO = {
  upcoming: '/v3/ipo/upcoming',
  recent: '/v3/ipo/recent',
  detail: (ipoId: string) => `/v3/ipo/${ipoId}`,
  pipeline: '/v3/ipo/pipeline',
  performance: '/v3/ipo/performance',
  calendar: '/v3/ipo/calendar',
} as const;

// ---------------------------------------------------------------------------
// Fund Holdings
// ---------------------------------------------------------------------------

export const FUND_HOLDINGS = {
  byFund: (fundId: string) => `/v1/funds/${fundId}/holdings`,
  nPort: (fundId: string) => `/v1/funds/${fundId}/n-port`,
  topHoldings: (fundId: string) => `/v1/funds/${fundId}/top-holdings`,
  sectorAllocation: (fundId: string) => `/v1/funds/${fundId}/sector-allocation`,
  overlap: '/v1/funds/overlap',
} as const;

// ---------------------------------------------------------------------------
// Money Market
// ---------------------------------------------------------------------------

export const MONEY_MARKET = {
  rates: '/v1/money-market/rates',
  sofr: '/v1/money-market/sofr',
  effr: '/v1/money-market/effr',
  repoRates: '/v1/money-market/repo',
  tBills: '/v1/money-market/t-bills',
  commercialPaper: '/v1/money-market/commercial-paper',
  history: (rateType: string) => `/v1/money-market/${rateType}/history`,
} as const;

// ---------------------------------------------------------------------------
// M&A / Deals
// ---------------------------------------------------------------------------

export const DEALS = {
  list: '/v3/deals',
  detail: (dealId: string) => `/v3/deals/${dealId}`,
  search: '/v3/deals/search',
  byEntity: (entityId: string) => `/v3/deals/entity/${entityId}`,
  pipeline: '/v3/deals/pipeline',
  completed: '/v3/deals/completed',
  rumored: '/v3/deals/rumored',
  statistics: '/v3/deals/statistics',
  advisors: (dealId: string) => `/v3/deals/${dealId}/advisors`,
  timeline: (dealId: string) => `/v3/deals/${dealId}/timeline`,
} as const;

// ---------------------------------------------------------------------------
// FI Agency Bonds
// ---------------------------------------------------------------------------

export const FI_AGENCY = {
  list: '/v1/fi/agency',
  detail: (cusip: string) => `/v1/fi/agency/${cusip}`,
  byIssuer: (issuerId: string) => `/v1/fi/agency/issuer/${issuerId}`,
  spreads: '/v1/fi/agency/spreads',
  newIssues: '/v1/fi/agency/new-issues',
} as const;

// ---------------------------------------------------------------------------
// Custom Classifications
// ---------------------------------------------------------------------------

export const CUSTOM_CLASSIFICATIONS = {
  list: '/v1/classifications/custom',
  create: '/v1/classifications/custom',
  detail: (id: string) => `/v1/classifications/custom/${id}`,
  update: (id: string) => `/v1/classifications/custom/${id}`,
  delete: (id: string) => `/v1/classifications/custom/${id}`,
  assign: (id: string) => `/v1/classifications/custom/${id}/assign`,
} as const;

// ---------------------------------------------------------------------------
// Backtesting
// ---------------------------------------------------------------------------

export const BACKTESTING = {
  strategies: '/v2/analytics/backtest/strategies',
  run: '/v2/analytics/backtest/run',
  result: (backtestId: string) => `/v2/analytics/backtest/${backtestId}`,
  history: '/v2/analytics/backtest/history',
  compare: '/v2/analytics/backtest/compare',
} as const;

// ---------------------------------------------------------------------------
// User / System
// ---------------------------------------------------------------------------

export const AUTH = {
  login: '/v1/auth/login',
  logout: '/v1/auth/logout',
  refresh: '/v1/auth/refresh',
  profile: '/v1/auth/profile',
  updateProfile: '/v1/auth/profile',
  changePassword: '/v1/auth/change-password',
  apiKeys: '/v1/auth/api-keys',
  createApiKey: '/v1/auth/api-keys',
  revokeApiKey: (keyId: string) => `/v1/auth/api-keys/${keyId}`,
} as const;

export const SYSTEM = {
  health: '/v1/system/health',
  version: '/v1/system/version',
  status: '/v1/system/status',
  config: '/v1/system/config',
  features: '/v1/system/features',
  audit: '/v1/system/audit',
  metrics: '/v1/system/metrics',
} as const;

// ---------------------------------------------------------------------------
// Benchmarks
// ---------------------------------------------------------------------------

export const BENCHMARKS = {
  list: '/v1/benchmarks',
  detail: (id: string) => `/v1/benchmarks/${id}`,
  returns: (id: string) => `/v1/benchmarks/${id}/returns`,
  constituents: (id: string) => `/v1/benchmarks/${id}/constituents`,
  compare: '/v1/benchmarks/compare',
  create: '/v1/benchmarks/create',
  factSheets: (id: string) => `/v1/benchmarks/${id}/fact-sheet`,
} as const;

// ---------------------------------------------------------------------------
// ETF Analytics
// ---------------------------------------------------------------------------

export const ETF = {
  list: '/v1/etf',
  detail: (id: string) => `/v1/etf/${id}`,
  holdings: (id: string) => `/v1/etf/${id}/holdings`,
  flows: (id: string) => `/v1/etf/${id}/flows`,
  flowsHistory: (id: string) => `/v1/etf/${id}/flows/history`,
  premium: (id: string) => `/v1/etf/${id}/premium-discount`,
  tracking: (id: string) => `/v1/etf/${id}/tracking-error`,
  compare: '/v1/etf/compare',
  screen: '/v1/etf/screen',
  search: '/v1/etf/search',
} as const;

// ---------------------------------------------------------------------------
// Derivatives / Options
// ---------------------------------------------------------------------------

export const OPTIONS = {
  chain: (underlyer: string) => `/v1/options/${underlyer}/chain`,
  greeks: (underlyer: string) => `/v1/options/${underlyer}/greeks`,
  impliedVol: (underlyer: string) => `/v1/options/${underlyer}/implied-vol`,
  volSurface: (underlyer: string) => `/v1/options/${underlyer}/vol-surface`,
  skew: (underlyer: string) => `/v1/options/${underlyer}/skew`,
  openInterest: (underlyer: string) => `/v1/options/${underlyer}/open-interest`,
  unusualActivity: '/v1/options/unusual-activity',
  expirationCalendar: '/v1/options/expirations',
  calculator: '/v1/options/calculator',
  strategies: '/v1/options/strategies',
  strategyBuilder: '/v1/options/strategy-builder',
} as const;

// ---------------------------------------------------------------------------
// Alternative Data
// ---------------------------------------------------------------------------

export const ALT_DATA = {
  satelliteImagery: (entityId: string) => `/v3/alt-data/${entityId}/satellite`,
  webTraffic: (entityId: string) => `/v3/alt-data/${entityId}/web-traffic`,
  appUsage: (entityId: string) => `/v3/alt-data/${entityId}/app-usage`,
  creditCardSpending: (entityId: string) => `/v3/alt-data/${entityId}/credit-card`,
  jobPostings: (entityId: string) => `/v3/alt-data/${entityId}/job-postings`,
  patentFilings: (entityId: string) => `/v3/alt-data/${entityId}/patents`,
  socialMedia: (entityId: string) => `/v3/alt-data/${entityId}/social-media`,
  congressTrades: '/v3/alt-data/congress-trades',
  lobbyingSpend: (entityId: string) => `/v3/alt-data/${entityId}/lobbying`,
  supplyChainSignals: (entityId: string) => `/v3/alt-data/${entityId}/supply-chain-signals`,
} as const;

// ---------------------------------------------------------------------------
// Exports / Reports
// ---------------------------------------------------------------------------

export const EXPORTS = {
  generateReport: '/v4/exports/report',
  reportStatus: (reportId: string) => `/v4/exports/report/${reportId}/status`,
  downloadReport: (reportId: string) => `/v4/exports/report/${reportId}/download`,
  templates: '/v4/exports/templates',
  templateDetail: (templateId: string) => `/v4/exports/templates/${templateId}`,
  scheduleReport: '/v4/exports/schedule',
  scheduledReports: '/v4/exports/schedule/list',
  exportCsv: '/v4/exports/csv',
  exportExcel: '/v4/exports/excel',
  exportPdf: '/v4/exports/pdf',
} as const;
