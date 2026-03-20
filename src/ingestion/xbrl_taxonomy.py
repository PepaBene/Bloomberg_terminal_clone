"""XBRL taxonomy mapping utility for US-GAAP tags to internal model fields.

Maps SEC EDGAR XBRL tags (e.g. us-gaap:Revenues) to standardized field names
used in IncomeStatement, BalanceSheet, and CashFlowStatement models.
"""

# ---------------------------------------------------------------------------
# Income Statement: XBRL tag -> IncomeStatement field name
# ---------------------------------------------------------------------------
INCOME_STATEMENT_MAP: dict[str, str] = {
    # Revenue
    "us-gaap:Revenues": "total_revenue",
    "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax": "total_revenue",
    "us-gaap:SalesRevenueNet": "total_revenue",
    "us-gaap:RevenueFromContractWithCustomerIncludingAssessedTax": "total_revenue",
    "us-gaap:CostOfRevenue": "cost_of_revenue",
    "us-gaap:CostOfGoodsAndServicesSold": "cost_of_revenue",
    "us-gaap:CostOfGoodsSold": "cost_of_revenue",
    "us-gaap:GrossProfit": "gross_profit",

    # Operating expenses
    "us-gaap:ResearchAndDevelopmentExpense": "research_development",
    "us-gaap:SellingGeneralAndAdministrativeExpense": "selling_general_admin",
    "us-gaap:DepreciationDepletionAndAmortization": "depreciation_amortization",
    "us-gaap:DepreciationAndAmortization": "depreciation_amortization",
    "us-gaap:OtherOperatingIncomeExpenseNet": "other_operating_expense",
    "us-gaap:OperatingExpenses": "total_operating_expense",
    "us-gaap:CostsAndExpenses": "total_operating_expense",
    "us-gaap:OperatingIncomeLoss": "operating_income",

    # Non-operating
    "us-gaap:InvestmentIncomeInterest": "interest_income",
    "us-gaap:InterestIncomeExpenseNet": "net_interest",
    "us-gaap:InterestExpense": "interest_expense",
    "us-gaap:OtherNonoperatingIncomeExpense": "other_income_expense",
    "us-gaap:NonoperatingIncomeExpense": "other_income_expense",
    "us-gaap:IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest": "pretax_income",
    "us-gaap:IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments": "pretax_income",

    # Tax
    "us-gaap:IncomeTaxExpenseBenefit": "income_tax_expense",
    "us-gaap:EffectiveIncomeTaxRateContinuingOperations": "effective_tax_rate",

    # Net income
    # NOTE: NetIncomeLoss and ProfitLoss also appear in CASH_FLOW_MAP (cash flow
    # starts with net income). Each map is used independently, so no ambiguity.
    "us-gaap:IncomeLossFromDiscontinuedOperationsNetOfTax": "discontinued_operations",
    "us-gaap:IncomeLossFromContinuingOperations": "net_income_continuing",
    "us-gaap:NetIncomeLoss": "net_income",
    "us-gaap:ProfitLoss": "net_income",
    "us-gaap:NetIncomeLossAvailableToCommonStockholdersBasic": "net_income_to_common",
    "us-gaap:NetIncomeLossAttributableToNoncontrollingInterest": "net_income_to_noncontrolling",
    "us-gaap:PreferredStockDividendsIncomeStatementImpact": "preferred_dividends",

    # Per share
    "us-gaap:WeightedAverageNumberOfShareOutstandingBasicAndDiluted": "basic_shares_outstanding",
    "us-gaap:WeightedAverageNumberOfSharesOutstandingBasic": "basic_shares_outstanding",
    "us-gaap:WeightedAverageNumberOfDilutedSharesOutstanding": "diluted_shares_outstanding",
    "us-gaap:EarningsPerShareBasic": "basic_eps",
    "us-gaap:EarningsPerShareDiluted": "diluted_eps",

    # Non-GAAP adjustments
    "us-gaap:ShareBasedCompensation": "stock_based_compensation",
    "us-gaap:AllocatedShareBasedCompensationExpense": "stock_based_compensation",
    "us-gaap:RestructuringCharges": "restructuring_charges",
    "us-gaap:AssetImpairmentCharges": "impairment_charges",
    "us-gaap:GoodwillImpairmentLoss": "impairment_charges",
    "us-gaap:BusinessCombinationAcquisitionRelatedCosts": "acquisition_costs",
    "us-gaap:LitigationSettlementAmountAwardedToOtherParty": "litigation_settlements",
}

# ---------------------------------------------------------------------------
# Balance Sheet: XBRL tag -> BalanceSheet field name
# ---------------------------------------------------------------------------
BALANCE_SHEET_MAP: dict[str, str] = {
    # Current assets
    "us-gaap:CashAndCashEquivalentsAtCarryingValue": "cash_and_equivalents",
    "us-gaap:CashCashEquivalentsAndShortTermInvestments": "cash_and_short_term",
    "us-gaap:ShortTermInvestments": "short_term_investments",
    "us-gaap:MarketableSecuritiesCurrent": "short_term_investments",
    "us-gaap:AccountsReceivableNetCurrent": "accounts_receivable",
    "us-gaap:AccountsReceivableNet": "accounts_receivable",
    "us-gaap:InventoryNet": "inventory",
    "us-gaap:PrepaidExpenseAndOtherAssetsCurrent": "prepaid_expenses",
    "us-gaap:PrepaidExpenseCurrent": "prepaid_expenses",
    "us-gaap:OtherAssetsCurrent": "other_current_assets",
    "us-gaap:AssetsCurrent": "total_current_assets",

    # Non-current assets
    "us-gaap:PropertyPlantAndEquipmentGross": "ppe_gross",
    "us-gaap:AccumulatedDepreciationDepletionAndAmortizationPropertyPlantAndEquipment": "accumulated_depreciation",
    "us-gaap:PropertyPlantAndEquipmentNet": "ppe_net",
    "us-gaap:Goodwill": "goodwill",
    "us-gaap:IntangibleAssetsNetExcludingGoodwill": "intangible_assets",
    "us-gaap:FiniteLivedIntangibleAssetsNet": "intangible_assets",
    "us-gaap:LongTermInvestments": "long_term_investments",
    "us-gaap:DeferredIncomeTaxAssetsNet": "deferred_tax_assets",
    "us-gaap:OtherAssetsNoncurrent": "other_non_current_assets",
    "us-gaap:AssetsNoncurrent": "total_non_current_assets",
    "us-gaap:Assets": "total_assets",

    # Current liabilities
    "us-gaap:AccountsPayableCurrent": "accounts_payable",
    "us-gaap:ShortTermBorrowings": "short_term_debt",
    "us-gaap:LongTermDebtCurrent": "current_portion_ltd",
    "us-gaap:AccruedLiabilitiesCurrent": "accrued_liabilities",
    "us-gaap:ContractWithCustomerLiabilityCurrent": "deferred_revenue_current",
    "us-gaap:DeferredRevenueCurrent": "deferred_revenue_current",
    "us-gaap:OtherLiabilitiesCurrent": "other_current_liabilities",
    "us-gaap:LiabilitiesCurrent": "total_current_liabilities",

    # Non-current liabilities
    "us-gaap:LongTermDebtNoncurrent": "long_term_debt",
    "us-gaap:LongTermDebt": "long_term_debt",
    "us-gaap:DeferredIncomeTaxLiabilitiesNet": "deferred_tax_liabilities",
    "us-gaap:ContractWithCustomerLiabilityNoncurrent": "deferred_revenue_nc",
    "us-gaap:DeferredRevenueNoncurrent": "deferred_revenue_nc",
    "us-gaap:PensionAndOtherPostretirementDefinedBenefitPlansLiabilitiesNoncurrent": "pension_liabilities",
    "us-gaap:OtherLiabilitiesNoncurrent": "other_nc_liabilities",
    "us-gaap:LiabilitiesNoncurrent": "total_nc_liabilities",
    "us-gaap:Liabilities": "total_liabilities",

    # Equity
    "us-gaap:CommonStockValue": "common_stock",
    "us-gaap:CommonStocksIncludingAdditionalPaidInCapital": "common_stock",
    "us-gaap:AdditionalPaidInCapital": "additional_paid_in_capital",
    "us-gaap:AdditionalPaidInCapitalCommonStock": "additional_paid_in_capital",
    "us-gaap:RetainedEarningsAccumulatedDeficit": "retained_earnings",
    "us-gaap:TreasuryStockValue": "treasury_stock",
    "us-gaap:AccumulatedOtherComprehensiveIncomeLossNetOfTax": "aoci",
    "us-gaap:StockholdersEquity": "total_common_equity",
    "us-gaap:PreferredStockValue": "preferred_equity",
    "us-gaap:MinorityInterest": "noncontrolling_interest",
    "us-gaap:StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest": "total_equity",
    "us-gaap:LiabilitiesAndStockholdersEquity": "total_liabilities_and_equity",
}

# ---------------------------------------------------------------------------
# Cash Flow Statement: XBRL tag -> CashFlowStatement field name
# ---------------------------------------------------------------------------
CASH_FLOW_MAP: dict[str, str] = {
    # Operating
    # NOTE: NetIncomeLoss and ProfitLoss also appear in INCOME_STATEMENT_MAP.
    # This is intentional — cash flow starts with net income. Each map is used
    # independently by EdgarXBRLConnector._extract_period_values(), so there is
    # no ambiguity at extraction time.
    "us-gaap:NetIncomeLoss": "net_income",
    "us-gaap:ProfitLoss": "net_income",
    "us-gaap:DepreciationDepletionAndAmortization": "depreciation_amortization",
    "us-gaap:DepreciationAmortizationAndAccretionNet": "depreciation_amortization",
    "us-gaap:ShareBasedCompensation": "stock_based_comp",
    "us-gaap:DeferredIncomeTaxExpenseBenefit": "deferred_taxes",
    "us-gaap:AssetImpairmentCharges": "impairment_charges",
    "us-gaap:OtherNoncashIncomeExpense": "other_non_cash",
    "us-gaap:IncreaseDecreaseInAccountsReceivable": "change_in_receivables",
    "us-gaap:IncreaseDecreaseInInventories": "change_in_inventory",
    "us-gaap:IncreaseDecreaseInAccountsPayable": "change_in_payables",
    "us-gaap:IncreaseDecreaseInOtherOperatingLiabilities": "change_in_other_wc",
    "us-gaap:NetCashProvidedByUsedInOperatingActivities": "cash_from_operations",

    # Investing
    "us-gaap:PaymentsToAcquirePropertyPlantAndEquipment": "capital_expenditures",
    "us-gaap:PaymentsToAcquireBusinessesNetOfCashAcquired": "acquisitions",
    "us-gaap:ProceedsFromDivestitureOfBusinesses": "divestitures",
    "us-gaap:PaymentsToAcquireInvestments": "investment_purchases",
    "us-gaap:ProceedsFromSaleAndMaturityOfMarketableSecurities": "investment_sales",
    "us-gaap:ProceedsFromSaleOfInvestments": "investment_sales",
    "us-gaap:PaymentsForProceedsFromOtherInvestingActivities": "other_investing",
    "us-gaap:NetCashProvidedByUsedInInvestingActivities": "cash_from_investing",

    # Financing
    "us-gaap:ProceedsFromIssuanceOfLongTermDebt": "debt_issued",
    "us-gaap:ProceedsFromIssuanceOfDebt": "debt_issued",
    "us-gaap:RepaymentsOfLongTermDebt": "debt_repaid",
    "us-gaap:RepaymentsOfDebt": "debt_repaid",
    "us-gaap:ProceedsFromIssuanceOfCommonStock": "stock_issued",
    "us-gaap:ProceedsFromStockOptionsExercised": "stock_issued",
    "us-gaap:PaymentsForRepurchaseOfCommonStock": "stock_repurchased",
    "us-gaap:PaymentsOfDividendsCommonStock": "dividends_paid",
    "us-gaap:PaymentsOfDividends": "dividends_paid",
    "us-gaap:ProceedsFromPaymentsForOtherFinancingActivities": "other_financing",
    "us-gaap:NetCashProvidedByUsedInFinancingActivities": "cash_from_financing",

    # Net
    "us-gaap:EffectOfExchangeRateOnCashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents": "fx_effect",
    "us-gaap:EffectOfExchangeRateOnCashAndCashEquivalents": "fx_effect",
    "us-gaap:CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalentsPeriodIncreaseDecreaseIncludingExchangeRateEffect": "net_change_in_cash",
    "us-gaap:CashAndCashEquivalentsPeriodIncreaseDecrease": "net_change_in_cash",
    "us-gaap:CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents": "ending_cash",
    "us-gaap:CashAndCashEquivalentsAtCarryingValue": "ending_cash",
}


def resolve_xbrl_tag(tag: str, statement_type: str) -> str | None:
    """Resolve an XBRL tag to a model field name for the given statement type.

    Args:
        tag: Full XBRL tag, e.g. 'us-gaap:Revenues'
        statement_type: One of 'income_statement', 'balance_sheet', 'cash_flow'

    Returns:
        Model field name or None if tag is not mapped.
    """
    maps = {
        "income_statement": INCOME_STATEMENT_MAP,
        "balance_sheet": BALANCE_SHEET_MAP,
        "cash_flow": CASH_FLOW_MAP,
    }
    mapping = maps.get(statement_type)
    if mapping is None:
        return None
    return mapping.get(tag)
