import axios, { AxiosError } from 'axios';
import type { AxiosResponse, InternalAxiosRequestConfig } from 'axios';
import { getToken } from './auth';

const apiBaseUrl = import.meta.env.VITE_TRAVEL_API_BASE_URL || 'http://localhost:8080';
const requestTimeout = Number(import.meta.env.VITE_TRAVEL_API_TIMEOUT_MS || 20000);

const client = axios.create({
  baseURL: apiBaseUrl,
  timeout: requestTimeout,
  headers: {
    'Content-Type': 'application/json',
  },
});

function createTraceId(): string {
  return `web-${Date.now()}-${Math.random().toString(16).slice(2, 10)}`;
}

export interface RecommendItem {
  name?: string;
  day?: string | number;
  price?: number | string;
  score?: number | string;
  rating?: number | string;
  reason?: string;
}

export interface RecommendResponse {
  traceId?: string;
  aiRationale?: string;
  hotelOptions?: RecommendItem[];
  transportOptions?: RecommendItem[];
  itinerary?: RecommendItem[];
  engagementRecommendations?: RecommendItem[];
  auditLogs?: Record<string, unknown>[];
  a2aLogs?: Record<string, unknown>[];
  memoryBefore?: Record<string, unknown>;
  memoryAfter?: Record<string, unknown>;
  memoryHits?: Record<string, unknown>[];
  registeredAgents?: Record<string, unknown>[];
  registeredTools?: string[];
}

export interface RecommendRequest {
  tenantId: string;
  userId: string;
  policyId: string;
  conversationId: string;
  idempotencyKey: string;
  city: string;
  days: number;
  budget: number;
  travelers: number;
  preferences: string[];
  maxAgentSteps: number;
  maxToolCalls: number;
  allowedTools: string[];
  authToken?: string;
}

export class ApiError extends Error {
  readonly status?: number;

  constructor(message: string, status?: number) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

export function saveAuthToken(token: string): void {
  if (!token) {
    localStorage.removeItem('travel_web_auth_token');
    return;
  }
  localStorage.setItem('travel_web_auth_token', token);
}

export function readSessionDefaults<T>(): T | null {
  try {
    const raw = localStorage.getItem('travel_web_form_defaults');
    if (!raw) {
      return null;
    }
    return JSON.parse(raw) as T;
  } catch {
    return null;
  }
}

export function saveSessionDefaults(payload: unknown): void {
  localStorage.setItem('travel_web_form_defaults', JSON.stringify(payload));
}

function mapError(error: AxiosError): ApiError {
  if (error.code === 'ECONNABORTED') {
    return new ApiError('Request timeout. Check gateway availability and retry.');
  }
  if (!error.response) {
    return new ApiError('Network unavailable or gateway unreachable.');
  }
  const { status, data } = error.response;
  if (status === 400) {
    return new ApiError(`Bad request: ${JSON.stringify(data)}`, status);
  }
  if (status === 401 || status === 403) {
    return new ApiError('Unauthorized request. Check token or gateway policy.', status);
  }
  if (status === 429) {
    return new ApiError('Rate limited. Please retry later.', status);
  }
  if (status >= 500) {
    return new ApiError(`Server error ${status}. Please retry or rollback release.`, status);
  }
  return new ApiError(`Request failed ${status}: ${JSON.stringify(data)}`, status);
}

interface RetriableRequestConfig extends InternalAxiosRequestConfig {
  __retried?: boolean;
}

client.interceptors.request.use((config) => {
  const token = getToken();
  const headers: Record<string, string> = {
    ...(config.headers as Record<string, string>),
    'X-Trace-Id': createTraceId(),
  };
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }
  return {
    ...config,
    headers,
  } as InternalAxiosRequestConfig;
});

client.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const cfg = (error.config || {}) as RetriableRequestConfig;
    const status = error.response?.status;
    if (!cfg.__retried && (status === 502 || status === 503 || status === 504 || !status)) {
      cfg.__retried = true;
      return client(cfg);
    }
    throw mapError(error);
  }
);

export async function recommendTravel(payload: RecommendRequest): Promise<RecommendResponse> {
  const response: AxiosResponse<RecommendResponse> = await client.post<
    RecommendResponse
  >('/api/v1/travel/recommend', payload);
  return response.data;
}
