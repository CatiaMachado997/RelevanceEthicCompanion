"use client"

import { usePathname } from "next/navigation"
import { MobileSidebarTrigger } from "@/components/sidebar"

const PAGE_TITLES: Record<string, string> = {
  "/dashboard": "Dashboard",
  "/dashboard/chat": "Chat",
  "/dashboard/values": "Values",
  "/dashboard/goals": "Goals",
  "/dashboard/transparency": "Transparency",
}

export function TopBar() {
  const pathname = usePathname()
  const title = PAGE_TITLES[pathname] ?? "Ethic Companion"

  const hour = new Date().getHours()
  const greeting =
    hour < 12 ? "Good morning" : hour < 18 ? "Good afternoon" : "Good evening"

  return (
    <header
      className="h-14 flex items-center justify-between px-8 shrink-0 border-b border-black/5"
      style={{ background: "#FAF8F5" }}
    >
      <div className="flex items-center gap-3">
        <MobileSidebarTrigger />
        <h1 className="text-[15px] font-semibold" style={{ color: "#1C1917" }}>
          {title}
        </h1>
      </div>

      <div className="flex items-center gap-3">
        <span className="text-sm hidden sm:block" style={{ color: "#78716C" }}>
          {greeting}
        </span>
        <div className="w-px h-4 bg-black/10" />
        <span
          className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium"
          style={{
            background: "rgba(74,124,89,0.10)",
            color: "#4A7C59",
            border: "1px solid rgba(74,124,89,0.20)",
          }}
        >
          <span
            className="w-1.5 h-1.5 rounded-full animate-pulse"
            style={{ background: "#4A7C59" }}
          />
          ESL Active
        </span>
      </div>
    </header>
  )
}
