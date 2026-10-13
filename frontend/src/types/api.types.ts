export interface ApiResponse<T = unknown> {
  data: T;
  status: number;
  headers?: Record<string, string>;
}

export interface ApiError {
  status: number;
  message: string;
  raw?: unknown;
}
