import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { TOKEN_KEY } from './auth.js';
import { getToken, isAuthenticated, setToken } from './auth.js';

describe('auth token storage', () => {
  beforeEach(() => {
    localStorage.removeItem(TOKEN_KEY);
  });

  afterEach(() => {
    localStorage.removeItem(TOKEN_KEY);
  });

  it('stores and reads the bearer token', () => {
    setToken('jwt-value');
    expect(getToken()).toBe('jwt-value');
    expect(isAuthenticated()).toBe(true);
  });

  it('clears the token when setToken receives an empty value', () => {
    setToken('jwt-value');
    setToken('');
    expect(getToken()).toBe('');
    expect(isAuthenticated()).toBe(false);
  });

  it('is unauthenticated by default', () => {
    expect(isAuthenticated()).toBe(false);
  });
});
