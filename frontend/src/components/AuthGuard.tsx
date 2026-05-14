'use client'

import { useEffect, useState } from 'react'
import { usePathname, useRouter } from 'next/navigation'
import { getAccessToken } from '../lib/session'

// 包裹需要鉴权的页面；/auth 路由自动跳过
export function AuthGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter()
  const pathname = usePathname()
  const [ready, setReady] = useState(false)

  useEffect(() => {
    if (pathname?.startsWith('/auth')) {
      setReady(true)
      return
    }
    if (!getAccessToken()) {
      router.replace('/auth')
    } else {
      setReady(true)
    }
  }, [pathname, router])

  // 鉴权检查期间不渲染内容，避免未授权内容闪烁
  if (!ready) return null
  return <>{children}</>
}
