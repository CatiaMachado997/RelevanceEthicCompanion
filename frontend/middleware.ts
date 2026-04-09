import { NextRequest, NextResponse } from 'next/server'

export async function middleware(request: NextRequest) {
  // Only protect /dashboard routes
  if (!request.nextUrl.pathname.startsWith('/dashboard')) {
    return NextResponse.next()
  }

  // Check for our HttpOnly session cookie (set by POST /api/auth/session)
  const cookieHeader = request.headers.get('cookie') ?? ''
  const hasSessionCookie = cookieHeader
    .split(';')
    .some(c => c.trim().startsWith('ec_session='))

  if (!hasSessionCookie) {
    return NextResponse.redirect(new URL('/login', request.url))
  }

  return NextResponse.next()
}

export const config = {
  matcher: ['/dashboard/:path*'],
}
