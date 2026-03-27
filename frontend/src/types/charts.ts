export type TimeRange = '1M' | '3M' | '6M' | '1Y' | '3Y' | '5Y' | '10Y' | 'Max';

export interface TimeSeriesPoint {
  date: string;
  value: number;
}

export interface OHLCPoint {
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume?: number;
}

export interface ChartEvent {
  date: string;
  type: 'earnings' | 'filing' | 'dividend' | 'management' | 'ma' | 'rating' | 'macro';
  label: string;
  description?: string;
}
