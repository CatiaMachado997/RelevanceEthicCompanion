import { IconSidebar } from "@/components/icon-sidebar"
import { TopHeader } from "@/components/top-header"

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <div className="flex h-screen bg-background">
      {/* Icon Sidebar - 80px */}
      <IconSidebar />

      {/* Main Content Area */}
      <div className="flex flex-1 min-w-0 overflow-hidden">
        {children}
      </div>
    </div>
  )
}
