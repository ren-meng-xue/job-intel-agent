// access token 存 localStorage；refresh token 由服务端通过 HttpOnly Cookie 管理

const KEY = 'jia_access_token'

export function getAccessToken(): string | null {
  if (typeof window === 'undefined') return null
  return localStorage.getItem(KEY)
}

export function setSessionTokens(accessToken: string): void {
  localStorage.setItem(KEY, accessToken)
}

export function clearSession(): void {
  localStorage.removeItem(KEY)
}

// 页面加载时恢复 session，返回当前 token 或 null
export function restoreSession(): string | null {
  return getAccessToken()
}
