export interface CountryRiskScore {
  country_code: string;
  country_name: string;
  composite_risk_score: number;
  risk_classification: string;
  risk_trend: string;
  political_risk_score: number;
  economic_risk_score: number;
}

export interface CentralBank {
  bank_code: string;
  bank_name: string;
  current_rate: number;
  policy_stance: string;
  next_meeting_date: string | null;
}

export interface CommodityProfile {
  commodity_code: string;
  commodity_name: string;
  category: string;
  current_price: number | null;
}

export interface GeopoliticalEvent {
  id: string;
  event_type: string;
  title: string;
  severity: string;
  countries_involved: string[];
  start_date: string;
}
