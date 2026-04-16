"use client"

import Link from "next/link"
import { usePathname, useRouter } from "next/navigation"
import {
  LayoutDashboard, MessageSquare, Heart, Target,
  Eye, Plug, Settings, LogOut, Bell, User, Sun, Moon, Search,
  Plus, Pencil, Trash2, Check, X, FileText, FolderOpen, CheckSquare,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { useAuth } from "@/hooks/useAuth"
import { useTheme } from "next-themes"
import { useEffect, useState, useCallback, useSyncExternalStore } from "react"
import { api } from "@/lib/api"
import { UserStatus } from "@/components/UserStatus"

interface Conversation {
  id: string
  title: string
  updated_at: string
}

function groupByDate(convs: Conversation[]) {
  const today = new Date()
  const yesterday = new Date(today); yesterday.setDate(today.getDate() - 1)
  const week = new Date(today); week.setDate(today.getDate() - 7)

  const groups: { label: string; items: Conversation[] }[] = [
    { label: 'Today', items: [] },
    { label: 'Yesterday', items: [] },
    { label: 'Previous 7 days', items: [] },
    { label: 'Older', items: [] },
  ]

  for (const c of convs) {
    const d = new Date(c.updated_at)
    if (d.toDateString() === today.toDateString()) groups[0].items.push(c)
    else if (d.toDateString() === yesterday.toDateString()) groups[1].items.push(c)
    else if (d >= week) groups[2].items.push(c)
    else groups[3].items.push(c)
  }

  return groups.filter(g => g.items.length > 0)
}

const NAV_ITEMS = [
  { href: "/dashboard",              label: "Dashboard",    icon: LayoutDashboard, exact: true },
  { href: "/dashboard/chat",         label: "Chat",         icon: MessageSquare },
  { href: "/dashboard/values",       label: "Values",       icon: Heart },
  { href: "/dashboard/goals",        label: "Goals",        icon: Target },
  { href: "/dashboard/projects",     label: "Projects",     icon: FolderOpen },
  { href: "/dashboard/tasks",        label: "Tasks",        icon: CheckSquare },
  { href: "/dashboard/transparency", label: "Transparency", icon: Eye },
  { href: "/dashboard/integrations", label: "Integrations", icon: Plug },
  { href: "/dashboard/documents",    label: "Documents",    icon: FileText },
  { href: "/dashboard/notifications",label: "Notifications",icon: Bell },
  { href: "/dashboard/search",       label: "Search",        icon: Search },
]

interface SidebarNavProps {
  onClose?: () => void
}

// SSR-safe mount detection without setState-in-effect: server snapshot is
// false; client snapshot is true, so the value flips on hydration.
const subscribeNoop = () => () => {}
const getMountedSnapshot = () => true
const getMountedServerSnapshot = () => false

export function SidebarNav({ onClose }: SidebarNavProps = {}) {
  const pathname = usePathname()
  const router = useRouter()
  const { signOut, user } = useAuth()
  const { resolvedTheme, setTheme } = useTheme()
  const mounted = useSyncExternalStore(subscribeNoop, getMountedSnapshot, getMountedServerSnapshot)
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editTitle, setEditTitle] = useState('')
  const [unreadNotifications, setUnreadNotifications] = useState(0)

  const refreshConversations = useCallback(() => {
    api.chat.conversations.list()
      .then(r => setConversations(r.conversations))
      .catch(() => {})
  }, [])

  useEffect(() => { refreshConversations() }, [pathname, refreshConversations])

  // Refresh immediately when a new conversation is created (e.g., first message sent)
  useEffect(() => {
    window.addEventListener('ec:conversation-created', refreshConversations)
    return () => window.removeEventListener('ec:conversation-created', refreshConversations)
  }, [refreshConversations])

  useEffect(() => {
    const fetchCount = () => {
      api.notifications.count()
        .then(r => setUnreadNotifications(r.unread_count))
        .catch(() => {})
    }
    fetchCount()
    const interval = setInterval(fetchCount, 60_000)
    return () => clearInterval(interval)
  }, [])

  // While viewing the notifications page, hide the unread badge by deriving
  // the visible count instead of resetting state in an effect.
  const visibleUnreadCount = pathname.includes('/notifications') ? 0 : unreadNotifications

  const handleNewChat = () => {
    router.push('/dashboard/chat')
    onClose?.()
  }

  const handleDelete = async (id: string) => {
    await api.chat.conversations.delete(id).catch(() => {})
    setConversations(prev => prev.filter(c => c.id !== id))
    if (pathname === `/dashboard/chat/${id}`) router.push('/dashboard/chat')
  }

  const handleRename = async (id: string) => {
    if (!editTitle.trim()) return
    await api.chat.conversations.rename(id, editTitle).catch(() => {})
    setConversations(prev => prev.map(c => c.id === id ? { ...c, title: editTitle } : c))
    setEditingId(null)
  }

  const initials = user?.email
    ? user.email.split('@')[0].substring(0, 2).toUpperCase()
    : 'U'

  const isActive = (href: string, exact?: boolean) =>
    exact ? pathname === href : pathname === href || pathname.startsWith(href + "/")

  const isDark = resolvedTheme === "dark"

  return (
    <aside
      className="flex flex-col h-screen w-[220px] shrink-0 border-r"
      style={{ background: "var(--ec-sidebar-bg)", borderColor: "var(--ec-sidebar-border)" }}
    >
      {/* Logo */}
      <div className="flex items-center gap-2.5 h-14 px-4 border-b shrink-0" style={{ borderColor: "var(--ec-sidebar-border)" }}>
        <div
          className="w-8 h-8 rounded-lg flex items-center justify-center text-[11px] font-bold tracking-tight shrink-0"
          style={{ background: "var(--ec-text)", color: "var(--ec-sidebar-bg)" }}
        >
          EC
        </div>
        <span className="text-sm font-semibold tracking-tight" style={{ color: "var(--ec-text)" }}>
          Ethic Companion
        </span>
      </div>

      {/* Primary nav */}
      <nav className="flex-1 flex flex-col gap-0.5 px-2 py-3 overflow-y-auto">
        {NAV_ITEMS.map(({ href, label, icon: Icon, exact }) => {
          const active = isActive(href, exact)
          return (
            <Link
              key={href}
              href={href}
              onClick={onClose}
              className={cn(
                "flex items-center gap-3 h-9 px-3 rounded-lg text-sm transition-colors duration-100",
                !active && "hover:opacity-80"
              )}
              style={{
                background: active ? "var(--ec-sidebar-active)" : undefined,
                color: active ? "var(--ec-sidebar-text)" : "var(--ec-sidebar-muted)",
                fontWeight: active ? 500 : undefined,
              }}
            >
              <span className="relative">
                <Icon size={16} strokeWidth={active ? 2.2 : 1.8} />
                {href === '/dashboard/notifications' && visibleUnreadCount > 0 && (
                  <span
                    className="absolute -top-1.5 -right-1.5 min-w-[14px] h-[14px] rounded-full flex items-center justify-center text-[9px] font-bold leading-none px-0.5"
                    style={{ background: '#B04A3A', color: '#fff' }}
                  >
                    {visibleUnreadCount > 9 ? '9+' : visibleUnreadCount}
                  </span>
                )}
              </span>
              {label}
            </Link>
          )
        })}

        {/* Conversation history */}
        {conversations.length > 0 && (
          <div className="mt-2 px-2">
            <div className="flex items-center justify-between mb-1 px-1">
              <span className="text-[10px] font-medium uppercase tracking-wider" style={{ color: 'var(--ec-text-subtle)' }}>
                Chats
              </span>
              <button
                onClick={handleNewChat}
                className="w-5 h-5 flex items-center justify-center rounded hover:bg-[rgba(0,0,0,0.06)]"
                title="New chat"
              >
                <Plus size={11} style={{ color: 'var(--ec-text-subtle)' }} />
              </button>
            </div>

            {groupByDate(conversations).map(group => (
              <div key={group.label} className="mb-2">
                <p className="text-[9px] font-medium px-1 mb-0.5 uppercase tracking-wider" style={{ color: 'var(--ec-text-subtle)', opacity: 0.6 }}>
                  {group.label}
                </p>
                {group.items.map(conv => {
                  const isActive = pathname === `/dashboard/chat/${conv.id}`
                  const isEditing = editingId === conv.id
                  return (
                    <div
                      key={conv.id}
                      className="group flex items-center gap-1 rounded-lg px-2 py-1 text-xs cursor-pointer transition-colors"
                      style={{
                        background: isActive ? 'var(--ec-nav-active-bg, var(--ec-sidebar-active))' : 'transparent',
                        color: isActive ? 'var(--ec-nav-active-text, var(--ec-sidebar-text))' : 'var(--ec-text-subtle)',
                      }}
                      onClick={() => !isEditing && router.push(`/dashboard/chat/${conv.id}`)}
                    >
                      {isEditing ? (
                        <input
                          autoFocus
                          value={editTitle}
                          onChange={e => setEditTitle(e.target.value)}
                          onKeyDown={e => {
                            if (e.key === 'Enter') handleRename(conv.id)
                            if (e.key === 'Escape') setEditingId(null)
                          }}
                          className="flex-1 bg-transparent outline-none text-xs"
                          style={{ color: 'var(--ec-text)' }}
                          onClick={e => e.stopPropagation()}
                        />
                      ) : (
                        <span className="flex-1 truncate">{conv.title}</span>
                      )}
                      {isEditing ? (
                        <div className="flex gap-0.5 shrink-0">
                          <button onClick={e => { e.stopPropagation(); handleRename(conv.id) }}><Check size={10} /></button>
                          <button onClick={e => { e.stopPropagation(); setEditingId(null) }}><X size={10} /></button>
                        </div>
                      ) : (
                        <div className="hidden group-hover:flex gap-0.5 shrink-0">
                          <button
                            onClick={e => { e.stopPropagation(); setEditingId(conv.id); setEditTitle(conv.title) }}
                            className="p-0.5 rounded hover:bg-[rgba(0,0,0,0.08)]"
                          >
                            <Pencil size={10} />
                          </button>
                          <button
                            onClick={e => { e.stopPropagation(); handleDelete(conv.id) }}
                            className="p-0.5 rounded hover:bg-[rgba(0,0,0,0.08)]"
                          >
                            <Trash2 size={10} />
                          </button>
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
            ))}
          </div>
        )}
      </nav>

      {/* Bottom section */}
      <div className="px-2 pb-3 border-t pt-3" style={{ borderColor: "var(--ec-sidebar-border)" }}>
        <Link
          href="/dashboard/settings"
          onClick={onClose}
          className={cn(
            "flex items-center gap-3 h-9 px-3 rounded-lg text-sm transition-colors duration-100",
            pathname !== "/dashboard/settings" && "hover:opacity-80"
          )}
          style={{
            background: pathname === "/dashboard/settings" ? "var(--ec-sidebar-active)" : undefined,
            color: pathname === "/dashboard/settings" ? "var(--ec-sidebar-text)" : "var(--ec-sidebar-muted)",
            fontWeight: pathname === "/dashboard/settings" ? 500 : undefined,
          }}
        >
          <Settings size={16} strokeWidth={pathname === "/dashboard/settings" ? 2.2 : 1.8} />
          Settings
        </Link>

        {/* Theme toggle */}
        {mounted && (
          <button
            onClick={() => setTheme(isDark ? "light" : "dark")}
            className="flex items-center gap-3 h-9 px-3 rounded-lg text-sm w-full transition-colors hover:opacity-80"
            style={{ color: "var(--ec-sidebar-muted)" }}
          >
            {isDark ? <Sun size={16} strokeWidth={1.8} /> : <Moon size={16} strokeWidth={1.8} />}
            {isDark ? "Light mode" : "Dark mode"}
          </button>
        )}

        <button
          onClick={() => signOut().catch(console.error)}
          className="flex items-center gap-3 h-9 px-3 rounded-lg text-sm w-full transition-colors hover:opacity-80"
          style={{ color: "var(--ec-sidebar-muted)" }}
        >
          <LogOut size={16} strokeWidth={1.8} />
          Sign out
        </button>

        {/* User status picker */}
        <div className="px-1 mt-1">
          <UserStatus />
        </div>

        {/* User row — links to profile */}
        <Link
          href="/dashboard/profile"
          onClick={onClose}
          className="flex items-center gap-2.5 px-3 mt-2 pt-2 border-t transition-opacity hover:opacity-70"
          style={{ borderColor: "var(--ec-sidebar-border)" }}
        >
          <div
            className="w-7 h-7 rounded-full flex items-center justify-center text-xs font-semibold shrink-0"
            style={{ background: "var(--ec-text)", color: "var(--ec-sidebar-bg)" }}
          >
            {initials}
          </div>
          <div className="min-w-0">
            <p className="text-xs truncate" style={{ color: "var(--ec-text)" }}>
              {user?.email?.split('@')[0] ?? 'My Account'}
            </p>
            <p className="text-[10px] truncate" style={{ color: "var(--ec-text-subtle)" }}>View profile</p>
          </div>
          <User size={12} className="ml-auto shrink-0" style={{ color: "var(--ec-text-subtle)" }} />
        </Link>
      </div>
    </aside>
  )
}

export function MobileSidebarTrigger() { return null }
