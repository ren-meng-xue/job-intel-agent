import { http } from '../lib/http'
import { parseApiError } from '../lib/errors'
import { clearSession, setSessionTokens } from '../lib/session'
import type { LoginResponse, UserInfo } from '../lib/types'

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8001/api/v1'

export async function login(email: string, password: string): Promise<LoginResponse> {
  // login 直接 fetch，绕过 http()（避免未登录时发 Bearer 头触发 refresh 循环）
  const res = await fetch(`${BASE_URL}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
    credentials: 'include',
  })
  if (!res.ok) {
    throw await parseApiError(res)
  }
  const data = (await res.json()) as LoginResponse
  setSessionTokens(data.access_token)
  return data
}

export async function register(
  email: string,
  username: string,
  password: string
): Promise<void> {
  const res = await fetch(`${BASE_URL}/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, username, password }),
  })
  if (!res.ok) {
    throw await parseApiError(res)
  }
}

export async function logout(): Promise<void> {
  try {
    await http('/auth/logout', { method: 'POST' })
  } finally {
    clearSession()
  }
}

export async function getMe(): Promise<UserInfo> {
  const res = await http('/auth/me')
  if (!res.ok) throw new Error('未授权')
  return res.json() as Promise<UserInfo>
}
