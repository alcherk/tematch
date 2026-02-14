const BASE = '';

export async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const resp = await fetch(`${BASE}${path}`, {
    credentials: 'include',
    ...options,
  });
  if (resp.status === 401) {
    window.location.href = '/login';
    throw new Error('Unauthorized');
  }
  if (!resp.ok) throw new Error(`API error: ${resp.status}`);
  return resp.json();
}
