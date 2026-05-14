import { http } from '../lib/http'
import { clearSession, setSessionTokens } from '../lib/session'
import type { LoginResponse, UserInfo } from '../lib/types'

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000/api/v1'

export async function login(email: string, password: string): Promise<LoginResponse> {
  // login 直接 fetch，绕过 http()（避免未登录时发 Bearer 头触发 refresh 循环）
  const res = await fetch(`${BASE_URL}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
    credentials: 'include',
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error((err as { detail?: string }).detail ?? '登录失败')
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
    const err = await res.json().catch(() => ({}))
    throw new Error((err as { detail?: string }).detail ?? '注册失败')
  }
}

export async function logout(): Promise<void> {
  await http('/auth/logout', { method: 'POST' })
  clearSession()
}

export async function getMe(): Promise<UserInfo> {
  const res = await http('/auth/me')
  if (!res.ok) throw new Error('未授权')
  return res.json() as Promise<UserInfo>
}
