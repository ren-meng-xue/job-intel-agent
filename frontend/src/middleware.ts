import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'

const AUTH_ROUTES = ['/auth', '/design']
const PUBLIC_EXTENSIONS = /\.(ico|png|svg|jpg|jpeg|gif|css|js|woff2?|html)$/

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl

  // 静态资源放行
  if (PUBLIC_EXTENSIONS.test(pathname)) return NextResponse.next()

  // auth 页面放行
  if (AUTH_ROUTES.some((r) => pathname.startsWith(r))) return NextResponse.next()

  // 检查 refresh_token cookie 是否存在
  const refreshToken = request.cookies.get('refresh_token')
  if (!refreshToken?.value) {
    const loginUrl = new URL('/auth', request.url)
    loginUrl.searchParams.set('redirect', pathname)
    return NextResponse.redirect(loginUrl)
  }

  return NextResponse.next()
}

export const config = {
  matcher: ['/((?!_next/static|_next/image|api|favicon.ico).*)'],
}
