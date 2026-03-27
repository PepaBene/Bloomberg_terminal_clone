export interface PaginatedMeta {
  request_id: string;
  processing_time_ms: number;
  cache_hit: boolean;
  total_count: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface PaginatedResponse<T> {
  data: T[];
  meta: PaginatedMeta;
}

export interface ApiError {
  detail: string;
  status_code: number;
}

export interface PaginationParams {
  page?: number;
  page_size?: number;
}
