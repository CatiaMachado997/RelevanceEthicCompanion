import { createServerClient } from '@supabase/ssr'
import { NextRequest, NextResponse } from 'next/server'

export async function proxy(request: NextRequest) {
  const isProtectedRoute =
    request.nextUrl.pathname.startsWith('/dashboard') ||
    request.nextUrl.pathname.startsWith('/onboarding')

  if (!isProtectedRoute) {
    return NextResponse.next()
  }

  let response = NextResponse.next({ request })

  // Use @supabase/ssr to verify the session from cookies (set on this domain)
  // This works across any hosting setup — no dependency on the backend cookie
  const supabase = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll: () => request.cookies.getAll(),
        setAll: (cookiesToSet) => {
          cookiesToSet.forEach(({ name, value }) => request.cookies.set(name, value))
          response = NextResponse.next({ request })
          cookiesToSet.forEach(({ name, value, options }) => {
            response.cookies.set(name, value, options)
          })
        },
      },
    }
  )

  // Validate with Supabase instead of trusting the cookie payload alone.
  // getUser also refreshes an expired session through setAll when possible.
  const { data: { user }, error } = await supabase.auth.getUser()

  if (error || !user) {
    // Save the attempted URL so we can redirect after login
    const loginUrl = new URL('/login', request.url)
    return NextResponse.redirect(loginUrl)
  }

  return response
}

export const config = {
  matcher: ['/dashboard/:path*', '/onboarding/:path*'],
}
