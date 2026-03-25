import { NextRequest, NextResponse } from 'next/server'

export async function middleware(request: NextRequest) {
  // Skip auth in development
  if (process.env.NEXT_PUBLIC_ENVIRONMENT === 'development') {
    return NextResponse.next()
  }

  // Only protect /dashboard routes
  if (!request.nextUrl.pathname.startsWith('/dashboard')) {
    return NextResponse.next()
  }

  // Check for Supabase session cookie (sb-*-auth-token)
  const cookieHeader = request.headers.get('cookie') ?? ''
  const hasAuthCookie = cookieHeader
    .split(';')
    .some(c => c.trim().startsWith('sb-') && c.includes('auth-token'))

  if (!hasAuthCookie) {
    return NextResponse.redirect(new URL('/login', request.url))
  }

  return NextResponse.next()
}

export const config = {
  matcher: ['/dashboard/:path*'],
}
