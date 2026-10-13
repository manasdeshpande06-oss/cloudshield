/**
 * CloudShield FairGuard API Client
 * 
 * Uses JWT Bearer tokens when available (from auth-context).
 * Falls back to the platform admin key for backward compatibility.
 */

export const API_BASE =
  typeof window !== 'undefined' && window.location.hostname === 'localhost'
    ? 'http://127.0.0.1:8000/api'
    : '/api';

export const ADMIN_API_KEY = 'fg_admin_platform_demo_key';

/** Get the current auth token from localStorage (set by auth-context). */
function getAuthToken(): string {
  if (typeof window === 'undefined') return ADMIN_API_KEY;
  try {
    const stored = localStorage.getItem('fg_auth');
    if (stored) {
      const parsed = JSON.parse(stored);
      if (parsed?.token) return parsed.token;
    }
  } catch {
    // ignore
  }
  return ADMIN_API_KEY;
}

export async function fetchApi<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const url = endpoint.startsWith('http')
    ? endpoint
    : `${API_BASE}${endpoint.startsWith('/') ? endpoint : `/${endpoint}`}`;

  const token = getAuthToken();

  const headers: Record<string, string> = {
    Authorization: `Bearer ${token}`,
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string>),
  };

  try {
    const res = await fetch(url, { ...options, headers });
    if (!res.ok) {
      const errText = await res.text().catch(() => '');
      throw new Error(`API Error ${res.status}: ${errText || res.statusText}`);
    }
    return (await res.json()) as T;
  } catch (err: any) {
    // If direct 8000 fails (e.g. CORS or network), try relative /api fallback
    if (url.includes('127.0.0.1:8000') && typeof window !== 'undefined') {
      const fallbackUrl = `/api${endpoint.startsWith('/') ? endpoint : `/${endpoint}`}`;
      const res = await fetch(fallbackUrl, { ...options, headers });
      if (!res.ok) {
        throw new Error(`API fallback error: ${res.statusText}`);
      }
      return (await res.json()) as T;
    }
    throw err;
  }
}
