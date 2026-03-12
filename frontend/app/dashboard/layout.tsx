import { SidebarProvider, SidebarNav } from "@/components/sidebar"
import { TopBar } from "@/components/top-bar"

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <SidebarProvider>
      <div className="flex h-screen" style={{ background: "#FAF8F5" }}>
        <SidebarNav />
        <div className="flex flex-1 flex-col min-w-0 overflow-hidden">
          <TopBar />
          <main className="flex-1 overflow-y-auto">
            <div className="max-w-[1100px] mx-auto px-8 py-6">
              {children}
            </div>
          </main>
        </div>
      </div>
    </SidebarProvider>
  )
}
