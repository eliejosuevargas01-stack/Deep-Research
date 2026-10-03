import { clearAllDrCache } from './research-utils.ts'

let csrf = ''

export class ApiError extends Error {
  readonly status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

export function getCsrfToken(): string {
  return csrf
}

export function setCsrfToken(token: string): void {
  csrf = token
}

export function clearSession(): void {
  csrf = ''
  clearAllDrCache()
}

export function prepareHeaders(method?: string, customHeaders?: HeadersInit): Headers {
  const headers = new Headers(customHeaders)
  // CRITERIA A4: Nunca enviar X-Tenant-ID
  headers.delete('X-Tenant-ID')
  headers.delete('x-tenant-id')

  const upperMethod = (method || 'GET').toUpperCase()
  if (upperMethod !== 'GET' && upperMethod !== 'HEAD' && csrf) {
    headers.set('X-CSRF-Token', csrf)
  }
  return headers
}

export function buildResearchPayload(theme: string): { theme: string } {
  const trimmedTheme = theme.trim()
  if (trimmedTheme.length < 3) {
    throw new Error('Tema deve conter no mínimo 3 caracteres')
  }
  // CRITERIA A2 & A4: Cookie HttpOnly handles session; browser payload contains only theme
  return {
    theme: trimmedTheme,
  }
}

export async function initializeSession(): Promise<{ authenticated: boolean; role: string }> {
  try {
    const session = await api<{ authenticated: boolean; role: string }>('/api/auth/me')
    if (!session.authenticated) throw new Error('Sessão não autenticada')
    const result = await api<{ csrf_token: string }>('/api/auth/csrf')
    if (!result.csrf_token) throw new Error('Token CSRF ausente')
    setCsrfToken(result.csrf_token)
    return session
  } catch (error) {
    clearSession()
    throw error
  }
}

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = prepareHeaders(options.method, options.headers)
  if (options.body && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }

  let response = await fetch(path, { ...options, credentials: 'same-origin', headers })

  // Auto-reauth on CSRF failure: se 403 em mutação, atualiza CSRF e tenta novamente
  const isMutation =
    options.method &&
    options.method.toUpperCase() !== 'GET' &&
    options.method.toUpperCase() !== 'HEAD'
  if (
    response.status === 403 &&
    isMutation &&
    path !== '/api/auth/csrf' &&
    path !== '/api/auth/login' &&
    path !== '/api/auth/logout'
  ) {
    try {
      const csrfRes = await fetch('/api/auth/csrf', { credentials: 'same-origin' })
      if (csrfRes.ok) {
        const csrfData = (await csrfRes.json()) as { csrf_token?: string }
        if (csrfData.csrf_token) {
          csrf = csrfData.csrf_token
          headers.set('X-CSRF-Token', csrf)
          response = await fetch(path, { ...options, credentials: 'same-origin', headers })
        }
      }
    } catch {
      // Falha na renovação do CSRF segue para tratamento de erro
    }
  }

  if (response.status === 401 || response.status === 403) {
    if (path !== '/api/auth/me' && path !== '/api/auth/login' && path !== '/api/auth/logout') {
      if (typeof window !== 'undefined') {
        window.dispatchEvent(new CustomEvent('auth-expired'))
      }
    }
  }

  if (!response.ok) {
    const error = (await response.json().catch(() => ({}))) as { detail?: string }
    throw new ApiError(typeof error.detail === 'string' ? error.detail : 'HTTP ' + response.status, response.status)
  }
  return response.status === 204 ? (undefined as T) : response.json()
}

export async function logoutUser(): Promise<void> {
  if (!csrf) {
    const res = await api<{ csrf_token: string }>('/api/auth/csrf').catch(() => null)
    if (res?.csrf_token) setCsrfToken(res.csrf_token)
  }
  try {
    await api('/api/auth/logout', { method: 'POST' })
  } catch (err) {
    // A 401 means server session is already absent; other failures must not pretend revocation succeeded.
    if (err instanceof ApiError && err.status === 401) {
      clearSession()
      return
    }
    throw err
  }
  clearSession()
}
