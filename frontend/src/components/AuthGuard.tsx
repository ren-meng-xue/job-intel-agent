'use client'

import { useEffect, useState } from 'react'
import { usePathname, useRouter } from 'next/navigation'
import { getAccessToken } from '../lib/session'
import { refreshAccessToken } from '../lib/http'

// middleware.ts 已检查 refresh_token cookie，这里再验证 access_token 是否存在。
// 双重守卫：middleware 挡掉无 cookie 请求，AuthGuard 挡掉 token 过期但 cookie 还在的情况。
export function AuthGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter()
  const pathname = usePathname()
  const isPublic = pathname?.startsWith('/auth') || pathname?.startsWith('/design')
  const [ready, setReady] = useState(isPublic || false)

  useEffect(() => {
    if (pathname?.startsWith('/auth') || pathname?.startsWith('/design')) {
      setReady(true)
      return
    }
    let cancelled = false

    async function ensureSession() {
      if (getAccessToken()) {
        if (!cancelled) setReady(true)
        return
      }

      const token = await refreshAccessToken()
      if (cancelled) return
      if (token) {
        setReady(true)
      } else {
        router.replace('/auth')
      }
    }

    void ensureSession()
    return () => {
      cancelled = true
    }
  }, [pathname, router])

  if (!ready) return null
  return <>{children}</>
}
