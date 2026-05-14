import { getAccessToken, setSessionTokens } from './session'

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000/api/v1'

// 直接调 refresh 端点，不经过 http() 避免循环
async function doRefresh(): Promise<string | null> {
  const res = await fetch(`${BASE_URL}/auth/refresh-token`, {
    method: 'POST',
    credentials: 'include',
  })
  if (!res.ok) return null
  const data = (await res.json()) as { access_token: string }
  setSessionTokens(data.access_token)
  return data.access_token
}

export async function http(path: string, init: RequestInit = {}): Promise<Response> {
  const token = getAccessToken()
  const headers = new Headers(init.headers as HeadersInit)

  // FormData 让浏览器自动设置 multipart boundary，其余请求加 JSON header
  if (init.body && !(init.body instanceof FormData) && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }
  if (token) headers.set('Authorization', `Bearer ${token}`)

  const res = await fetch(`${BASE_URL}${path}`, {
    ...init,
    headers,
    credentials: 'include',
  })

  if (res.status !== 401) return res

  // 401：刷新 token 后重试一次
  const newToken = await doRefresh()
  if (!newToken) return res

  headers.set('Authorization', `Bearer ${newToken}`)
  return fetch(`${BASE_URL}${path}`, { ...init, headers, credentials: 'include' })
}
