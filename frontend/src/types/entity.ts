export interface Entity {
  entity_id: string;
  entity_name: string;
  entity_type: string;
  cik: string | null;
  lei: string | null;
  country: string | null;
  gics_sector: string | null;
  gics_industry_group: string | null;
  gics_industry: string | null;
  gics_sub_industry: string | null;
  sic_code: string | null;
  status: string;
}
