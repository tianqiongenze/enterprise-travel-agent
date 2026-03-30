import axios from 'axios';
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

function createTraceId() {
  return `web-${Date.now()}-${Math.random().toString(16).slice(2, 10)}`;
}

export function saveAuthToken(token) {
  if (!token) {
    localStorage.removeItem('travel_web_auth_token');
    return;
  }
  localStorage.setItem('travel_web_auth_token', token);
}

export function readSessionDefaults() {
  try {
    const raw = localStorage.getItem('travel_web_form_defaults');
    if (!raw) {
      return null;
    }
    return JSON.parse(raw);
  } catch (error) {
    return null;
  }
}

export function saveSessionDefaults(payload) {
  localStorage.setItem('travel_web_form_defaults', JSON.stringify(payload));
}

function mapError(error) {
  if (error.code === 'ECONNABORTED') {
    return new Error('Request timeout. Check gateway availability and retry.');
  }
  if (!error.response) {
    return new Error('Network unavailable or gateway unreachable.');
  }
  const { status, data } = error.response;
  if (status === 400) {
    return new Error(`Bad request: ${JSON.stringify(data)}`);
  }
  if (status === 401 || status === 403) {
    return new Error('Unauthorized request. Check token or gateway policy.');
  }
  if (status === 429) {
    return new Error('Rate limited. Please retry later.');
  }
  if (status >= 500) {
    return new Error(`Server error ${status}. Please retry or rollback release.`);
  }
  return new Error(`Request failed ${status}: ${JSON.stringify(data)}`);
}

client.interceptors.request.use((config) => {
  const token = getToken();
  const headers = {
    ...config.headers,
    'X-Trace-Id': createTraceId(),
  };
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }
  return {
    ...config,
    headers,
  };
});

client.interceptors.response.use(
  (response) => response,
  async (error) => {
    const cfg = error.config || {};
    const status = error.response?.status;
    if (!cfg.__retried && (status === 502 || status === 503 || status === 504 || !status)) {
      cfg.__retried = true;
      return client(cfg);
    }
    throw mapError(error);
  }
);

export async function recommendTravel(payload) {
  const response = await client.post('/api/v1/travel/recommend', payload);
  return response.data;
}
