import { NextRequest, NextResponse } from 'next/server'

export async function middleware(request: NextRequest) {
  // Only protect /dashboard routes
  if (!request.nextUrl.pathname.startsWith('/dashboard')) {
    return NextResponse.next()
  }

  // Use Next.js cookies API for robust cookie parsing
  const sessionCookie = request.cookies.get('ec_session')
  if (!sessionCookie?.value) {
    return NextResponse.redirect(new URL('/login', request.url))
  }

  return NextResponse.next()
}

export const config = {
  matcher: ['/dashboard/:path*'],
}
