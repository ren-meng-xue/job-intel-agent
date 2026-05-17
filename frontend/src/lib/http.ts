import { ApiError, parseApiError } from './errors'
import { clearSession, getAccessToken, setSessionTokens } from './session'

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8001/api/v1'
const TIMEOUT_MS = 30_000

export async function refreshAccessToken(): Promise<string | null> {
  const res = await fetch(`${BASE_URL}/auth/refresh-token`, {
    method: 'POST',
    credentials: 'include',
  })
  if (!res.ok) return null
  const data = (await res.json()) as { access_token: string }
  setSessionTokens(data.access_token)
  return data.access_token
}

function redirectToLogin(): void {
  clearSession()
  if (typeof window !== 'undefined') {
    window.location.replace('/auth')
  }
}

export async function http(path: string, init: RequestInit = {}): Promise<Response> {
  const token = getAccessToken()
  const headers = new Headers(init.headers as HeadersInit)

  if (init.body && !(init.body instanceof FormData) && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }
  if (token) headers.set('Authorization', `Bearer ${token}`)

  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), TIMEOUT_MS)
  const signal = init.signal ? init.signal : controller.signal

  try {
    const res = await fetch(`${BASE_URL}${path}`, {
      ...init,
      headers,
      credentials: 'include',
      signal,
    })

    if (res.status !== 401) return res

    // 401：尝试刷新，失败则清 session 并跳转登录
    const newToken = await refreshAccessToken()
    if (!newToken) {
      redirectToLogin()
      throw await parseApiError(res)
    }

    headers.set('Authorization', `Bearer ${newToken}`)
    const retried = await fetch(`${BASE_URL}${path}`, {
      ...init,
      headers,
      credentials: 'include',
      signal,
    })

    if (retried.status === 401) {
      redirectToLogin()
      throw await parseApiError(retried)
    }
    return retried
  } catch (err) {
    if (err instanceof ApiError) throw err
    if (err instanceof DOMException && err.name === 'AbortError') {
      throw new ApiError(408, { code: 'INTERNAL_ERROR', message: '请求超时' })
    }
    throw new ApiError(0, { code: 'INTERNAL_ERROR', message: '网络错误，请检查连接' })
  } finally {
    clearTimeout(timeoutId)
  }
}
