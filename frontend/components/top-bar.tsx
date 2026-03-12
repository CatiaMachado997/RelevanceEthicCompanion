"use client"

import { usePathname } from "next/navigation"

const PAGE_META: Record<string, { title: string; subtitle: string }> = {
  "/dashboard": { title: "Dashboard", subtitle: "Overview of your activity" },
  "/dashboard/chat": { title: "Chat", subtitle: "Message your companion" },
  "/dashboard/values": { title: "Values", subtitle: "Manage your personal values" },
  "/dashboard/goals": { title: "Goals", subtitle: "Track your active goals" },
  "/dashboard/transparency": { title: "Transparency", subtitle: "ESL audit and decisions" },
}

export function TopBar() {
  const pathname = usePathname()
  const meta = PAGE_META[pathname] ?? { title: "Ethic Companion", subtitle: "" }

  return (
    <header
      className="h-[72px] flex items-center px-8 shrink-0 border-b"
      style={{
        background: "#ffffff",
        borderColor: "rgba(0,0,0,0.08)",
      }}
    >
      <div>
        <h1
          className="font-semibold text-xl leading-7"
          style={{ color: "#0a0a0a" }}
        >
          {meta.title}
        </h1>
        {meta.subtitle && (
          <p className="text-xs mt-0.5" style={{ color: "#9e9e9e" }}>
            {meta.subtitle}
          </p>
        )}
      </div>
    </header>
  )
}
