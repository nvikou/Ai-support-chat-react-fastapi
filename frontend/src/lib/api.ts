export type User = {
  id: string
  email: string
  full_name: string | null
  role: 'user' | 'admin'
}

let accessToken: string | null = null
let refreshPromise: Promise<string | null> | null = null

export function getAccessToken(): string | null {
  return accessToken
}

export function setAccessToken(token: string | null) {
  accessToken = token
}

export async function refreshAccessToken(): Promise<string | null> {
  if (refreshPromise) return refreshPromise

  refreshPromise = (async () => {
    try {
      const res = await fetch('/api/auth/refresh', {
        method: 'POST',
        credentials: 'include',
      })
      if (!res.ok) {
        setAccessToken(null)
        return null
      }
      const data = await res.json()
      setAccessToken(data.access_token)
      return data.access_token
    } catch {
      setAccessToken(null)
      return null
    } finally {
      refreshPromise = null
    }
  })()

  return refreshPromise
}

export async function apiFetch(
  path: string,
  options: RequestInit = {},
  retry = true,
): Promise<Response> {
  const headers = new Headers(options.headers)
  const token = getAccessToken()
  if (token) {
    headers.set('Authorization', `Bearer ${token}`)
  }
  if (
    options.body &&
    !(options.body instanceof FormData) &&
    !headers.has('Content-Type')
  ) {
    headers.set('Content-Type', 'application/json')
  }

  const res = await fetch(`/api${path}`, {
    ...options,
    headers,
    credentials: 'include',
  })

  if (res.status === 401 && retry && !path.startsWith('/auth/')) {
    const newToken = await refreshAccessToken()
    if (newToken) return apiFetch(path, options, false)
  }

  return res
}

export async function apiJson<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const res = await apiFetch(path, options)
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Request failed' }))
    throw new Error(err.detail || 'Request failed')
  }
  return res.json()
}
