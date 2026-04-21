"use client"

import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { ReactQueryDevtools } from "@tanstack/react-query-devtools"
import { useState } from "react"


export function QueryProvider({ children }: { children: React.ReactNode }) {
  // One client per app session; stateful so StrictMode double-invocations don't churn it.
  const [client] = useState(() => new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 30_000,           // 30s — most dashboard data is safe to reuse
        refetchOnWindowFocus: false, // opt in per-query when needed
        retry: 1,
      },
    },
  }))

  return (
    <QueryClientProvider client={client}>
      {children}
      {process.env.NODE_ENV === "development" && <ReactQueryDevtools initialIsOpen={false} />}
    </QueryClientProvider>
  )
}
