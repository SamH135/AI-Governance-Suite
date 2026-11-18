// @vitest-environment happy-dom
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';

vi.mock('../utils/logger.js', () => ({
  default: { info: vi.fn(), debug: vi.fn(), warn: vi.fn(), error: vi.fn() },
}));

// Import after the mock — the module instantiates axios at import time.
const { default: api, authService } = await import('./authService.js');

beforeEach(() => {
  localStorage.clear();
});

afterEach(() => {
  delete api.defaults.adapter;
});

describe('authService request interceptor', () => {
  it('attaches the bearer token when one is stored', async () => {
    localStorage.setItem('token', 'jwt123');
    let seen;
    api.defaults.adapter = async (config) => {
      seen = config;
      return { data: { token: 'x' }, status: 200, statusText: 'OK', headers: {}, config };
    };
    await authService.login({ username: 'u', password: 'p' });
    expect(seen.headers.Authorization).toBe('Bearer jwt123');
  });

  it('sends no Authorization header without a stored token', async () => {
    let seen;
    api.defaults.adapter = async (config) => {
      seen = config;
      return { data: {}, status: 200, statusText: 'OK', headers: {}, config };
    };
    await authService.login({ username: 'u', password: 'p' });
    expect(seen.headers.Authorization).toBeUndefined();
  });
});

describe('authService response interceptor', () => {
  it('clears the stored token on a 401 outside auth endpoints', async () => {
    localStorage.setItem('token', 'expired');
    api.defaults.adapter = async (_config) => {
      const err = new Error('unauthorized');
      err.response = { status: 401, data: {} };
      err.config = { method: 'get', url: '/systems' };
      throw err;
    };
    await expect(api.get('/systems')).rejects.toThrow('unauthorized');
    expect(localStorage.getItem('token')).toBeNull();
  });

  it('keeps the token when login itself returns 401', async () => {
    localStorage.setItem('token', 'keepme');
    api.defaults.adapter = async (_config) => {
      const err = new Error('bad credentials');
      err.response = { status: 401, data: {} };
      err.config = { method: 'post', url: '/auth/login' };
      throw err;
    };
    await expect(
      authService.login({ username: 'u', password: 'wrong' })
    ).rejects.toThrow('bad credentials');
    expect(localStorage.getItem('token')).toBe('keepme');
  });
});
