"use client"

import Link from "next/link"
import { usePathname, useRouter } from "next/navigation"
import {
  MessageSquare, Plug, Settings, LogOut, User, Sun, Moon,
  Plus, Pencil, Trash2, Check, X, FolderPlus, Folder as FolderIcon,
  ChevronRight, ChevronDown, Bell, Eye, UserCircle,
  LayoutDashboard, MoreHorizontal, Target, CheckSquare, FolderOpen,
  Heart, FileText,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { useAuth } from "@/hooks/useAuth"
import { useTheme } from "next-themes"
import { useEffect, useState, useCallback, useRef } from "react"
import { useQuery, useQueryClient } from "@tanstack/react-query"
import { api } from "@/lib/api"
import type { Folder } from "@/lib/api"
import { toast } from "@/lib/toast"
import { UserStatus } from "@/components/UserStatus"

interface Conversation {
  id: string
  title: string
  folder_id: string | null
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
  { href: "/dashboard/chat",         label: "Chat",         icon: MessageSquare },
  { href: "/dashboard/integrations", label: "Integrations", icon: Plug },
  { href: "/dashboard",              label: "Dashboard",    icon: LayoutDashboard, exact: true },
]

// Power-user pages, revealed under the "More" disclosure.
const MORE_ITEMS = [
  { href: "/dashboard/goals",         label: "Goals",         icon: Target },
  { href: "/dashboard/tasks",         label: "Tasks",         icon: CheckSquare },
  { href: "/dashboard/projects",      label: "Projects",      icon: FolderOpen },
  { href: "/dashboard/values",        label: "Values",        icon: Heart },
  { href: "/dashboard/documents",     label: "Documents",     icon: FileText },
  { href: "/dashboard/transparency",  label: "Transparency",  icon: Eye },
  { href: "/dashboard/notifications", label: "Notifications", icon: Bell },
]

interface SidebarNavProps {
  onClose?: () => void
}

export function SidebarNav({ onClose }: SidebarNavProps = {}) {
  const pathname = usePathname()
  const router = useRouter()
  const { signOut, user } = useAuth()
  const { resolvedTheme, setTheme } = useTheme()
  const [mounted, setMounted] = useState(false)
  const qc = useQueryClient()
  const { data: convData } = useQuery({
    queryKey: ["conversations"],
    queryFn: () => api.chat.conversations.list(),
  })
  const { data: folderData } = useQuery({
    queryKey: ["folders"],
    queryFn: () => api.folders.list(),
  })
  const conversations: Conversation[] = convData?.conversations ?? []
  const folders: Folder[] = folderData?.folders ?? []

  const [editingId, setEditingId] = useState<string | null>(null)
  const [editTitle, setEditTitle] = useState('')

  // Folder optimistic expansion (track newly created folder name to expand it once data arrives)
  const pendingExpandName = useRef<string | null>(null)
  const [expandedFolders, setExpandedFolders] = useState<Set<string>>(new Set())
  const [creatingFolder, setCreatingFolder] = useState(false)
  const [newFolderName, setNewFolderName] = useState('')
  const [editingFolderId, setEditingFolderId] = useState<string | null>(null)
  const [editFolderName, setEditFolderName] = useState('')
  const [dragOverFolder, setDragOverFolder] = useState<string | null>(null) // null = ungrouped target; string = folder id
  // Right-click context menu for conversation rows. Acts as a
  // keyboard/touch-friendly alternative to drag-and-drop: any user
  // who can't (or doesn't want to) drag still has a way to move a
  // chat between folders. Positioned at the click coordinates with
  // edge-snapping so it never clips out of the viewport.
  const [convCtxMenu, setConvCtxMenu] = useState<{
    x: number
    y: number
    convId: string
    currentFolderId: string | null
  } | null>(null)
  // Power-user "More" disclosure — persisted across sessions so users
  // who use these pages regularly aren't forced to re-open the section
  // on every reload. We default to closed (the SSR/first-render output)
  // and hydrate from localStorage after mount, keeping the server and
  // first client render identical.
  const [moreOpen, setMoreOpen] = useState(false)
  useEffect(() => {
    try {
      if (localStorage.getItem('ec:sidebar:moreOpen') === '1') setMoreOpen(true)
    } catch {
      // localStorage may be unavailable (SSR-edge, privacy mode) — ignore.
    }
  }, [])
  // Auto-open if the user is on one of the hidden pages. This wins over
  // the persisted preference: if a user deep-links into /goals we should
  // always reveal where it lives in the nav, not leave them stranded.
  useEffect(() => {
    if (MORE_ITEMS.some(m => pathname === m.href || pathname.startsWith(m.href + '/'))) {
      setMoreOpen(true)
    }
  }, [pathname])
  // Persist whenever the user toggles. Skipped during the initial paint
  // (the value still equals the default `false`), so we don't clobber
  // a `'1'` already in storage with a false write before hydration.
  const moreOpenInitialized = useRef(false)
  useEffect(() => {
    if (!moreOpenInitialized.current) {
      moreOpenInitialized.current = true
      return
    }
    try {
      localStorage.setItem('ec:sidebar:moreOpen', moreOpen ? '1' : '0')
    } catch {
      // Same as above — silently ignore storage failures.
    }
  }, [moreOpen])

  // Avatar menu (dropdown)
  const [avatarMenuOpen, setAvatarMenuOpen] = useState(false)
  useEffect(() => {
    if (!avatarMenuOpen) return
    const onClick = (e: MouseEvent) => {
      const target = e.target as HTMLElement
      if (!target.closest('[data-avatar-menu]')) setAvatarMenuOpen(false)
    }
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setAvatarMenuOpen(false)
    }
    window.addEventListener('mousedown', onClick)
    window.addEventListener('keydown', onKey)
    return () => {
      window.removeEventListener('mousedown', onClick)
      window.removeEventListener('keydown', onKey)
    }
  }, [avatarMenuOpen])

  // Move focus into the menu when it opens so keyboard users land
  // on the first item rather than staying on the trigger.
  const avatarMenuRef = useRef<HTMLDivElement | null>(null)
  useEffect(() => {
    if (!avatarMenuOpen) return
    const first = avatarMenuRef.current?.querySelector<HTMLElement>(
      '[role="menuitem"]'
    )
    first?.focus()
  }, [avatarMenuOpen])

  // Up/Down arrow + Home/End nav inside the avatar menu — completes
  // the WAI-ARIA menu pattern (Esc-to-close + initial focus already
  // wired above). Tab still works as a fallback because each menuitem
  // is a real focusable Link/button.
  const handleAvatarMenuKey = (e: React.KeyboardEvent<HTMLDivElement>) => {
    if (!['ArrowDown', 'ArrowUp', 'Home', 'End'].includes(e.key)) return
    const items = Array.from(
      avatarMenuRef.current?.querySelectorAll<HTMLElement>('[role="menuitem"]') ?? [],
    )
    if (items.length === 0) return
    e.preventDefault()
    const active = document.activeElement as HTMLElement | null
    const currentIdx = active ? items.indexOf(active) : -1
    let nextIdx: number
    if (e.key === 'Home') nextIdx = 0
    else if (e.key === 'End') nextIdx = items.length - 1
    else if (e.key === 'ArrowDown') nextIdx = (currentIdx + 1) % items.length
    else nextIdx = currentIdx <= 0 ? items.length - 1 : currentIdx - 1
    items[nextIdx]?.focus()
  }

  // Unread notifications — polled once per minute + cleared on notifications page
  const [unreadNotifs, setUnreadNotifs] = useState(0)
  useEffect(() => {
    const fetchCount = () => {
      api.notifications.count()
        .then(r => setUnreadNotifs(r.unread_count ?? 0))
        .catch(() => {})
    }
    fetchCount()
    const id = setInterval(fetchCount, 60_000)
    return () => clearInterval(id)
  }, [])
  useEffect(() => {
    if (pathname.includes('/notifications')) setUnreadNotifs(0)
  }, [pathname])

  // Classic hydration gate: flip to true after mount so the first client
  // render matches the server output. The single extra render is the
  // intended behavior.
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { setMounted(true) }, [])

  // Re-validate when navigating to a new route
  useEffect(() => {
    qc.invalidateQueries({ queryKey: ["conversations"] })
    qc.invalidateQueries({ queryKey: ["folders"] })
  }, [pathname, qc])

  // Expand a newly created folder once its data arrives from the cache refetch
  useEffect(() => {
    if (!pendingExpandName.current) return
    const match = folders.find(f => f.name === pendingExpandName.current)
    if (match) {
      setExpandedFolders(prev => new Set(prev).add(match.id))
      pendingExpandName.current = null
    }
  }, [folders])

  // Refresh immediately when a new conversation is created (e.g., first message sent)
  useEffect(() => {
    const h = () => qc.invalidateQueries({ queryKey: ["conversations"] })
    window.addEventListener('ec:conversation-created', h)
    return () => window.removeEventListener('ec:conversation-created', h)
  }, [qc])



  const handleNewChat = () => {
    // If already on the base chat page, the router.push is a no-op and the
    // chat state wouldn't reset. Dispatch a sibling event that the chat page
    // listens for and clears its own state.
    if (pathname === '/dashboard/chat') {
      window.dispatchEvent(new Event('ec:new-chat'))
    } else {
      router.push('/dashboard/chat')
    }
    onClose?.()
  }

  const handleDelete = async (id: string) => {
    await api.chat.conversations.delete(id).catch(() => {})
    qc.invalidateQueries({ queryKey: ["conversations"] })
    if (pathname === `/dashboard/chat/${id}`) router.push('/dashboard/chat')
  }

  const handleRename = async (id: string) => {
    if (!editTitle.trim()) return
    await api.chat.conversations.rename(id, editTitle).catch(() => {})
    qc.invalidateQueries({ queryKey: ["conversations"] })
    setEditingId(null)
  }

  // ─── Conversation context menu ─────────────────────────────────────
  const handleConvContextMenu = (
    e: React.MouseEvent,
    convId: string,
    currentFolderId: string | null,
  ) => {
    e.preventDefault()
    e.stopPropagation()
    setConvCtxMenu({ x: e.clientX, y: e.clientY, convId, currentFolderId })
  }

  const closeCtxMenu = useCallback(() => setConvCtxMenu(null), [])

  // Close on Escape, outside-click, scroll, or route change.
  useEffect(() => {
    if (!convCtxMenu) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') closeCtxMenu()
    }
    const onClick = (e: MouseEvent) => {
      const target = e.target as HTMLElement
      if (!target.closest('[data-conv-ctx-menu]')) closeCtxMenu()
    }
    const onScroll = () => closeCtxMenu()
    window.addEventListener('keydown', onKey)
    window.addEventListener('mousedown', onClick)
    window.addEventListener('scroll', onScroll, true)
    return () => {
      window.removeEventListener('keydown', onKey)
      window.removeEventListener('mousedown', onClick)
      window.removeEventListener('scroll', onScroll, true)
    }
  }, [convCtxMenu, closeCtxMenu])
  useEffect(() => {
    closeCtxMenu()
  }, [pathname, closeCtxMenu])

  const handleMoveConv = async (convId: string, folderId: string | null) => {
    closeCtxMenu()
    if (folderId) setExpandedFolders(prev => new Set(prev).add(folderId))
    try {
      await api.folders.moveConversation(convId, folderId)
    } finally {
      qc.invalidateQueries({ queryKey: ["conversations"] })
    }
  }

  // ─── Folder CRUD ────────────────────────────────────────────────────
  const handleCreateFolder = async () => {
    const name = newFolderName.trim()
    if (!name) { setCreatingFolder(false); setNewFolderName(''); return }
    try {
      await api.folders.create(name)
      pendingExpandName.current = name   // expand once query refetch delivers the new folder
      qc.invalidateQueries({ queryKey: ["folders"] })
      toast.success("Folder created", name)
      setCreatingFolder(false)
      setNewFolderName('')
    } catch (e) {
      console.error('create folder failed', e)
      toast.error("Couldn't create folder", e instanceof Error ? e.message : undefined)
      // Keep the input open so the user can retry
    }
  }

  const handleRenameFolder = async (id: string) => {
    const name = editFolderName.trim()
    if (!name) { setEditingFolderId(null); return }
    try {
      await api.folders.update(id, { name })
      qc.invalidateQueries({ queryKey: ["folders"] })
      toast.success("Folder renamed", name)
      setEditingFolderId(null)
      setEditFolderName('')
    } catch (e) {
      console.error('rename folder failed', e)
      toast.error("Couldn't rename folder", e instanceof Error ? e.message : undefined)
    }
  }

  // ─── Folder color ──────────────────────────────────────────────────
  // 8-swatch palette + "no color". Backend already accepts {color: string|null}
  // on PATCH /api/folders/:id; this just exposes it in the sidebar.
  const FOLDER_COLORS: { name: string; value: string }[] = [
    { name: "Red",    value: "#E5484D" },
    { name: "Orange", value: "#E58E26" },
    { name: "Yellow", value: "#D5AE2A" },
    { name: "Green",  value: "#46A758" },
    { name: "Teal",   value: "#12A594" },
    { name: "Blue",   value: "#3D63DD" },
    { name: "Purple", value: "#8E4EC6" },
    { name: "Pink",   value: "#D6409F" },
  ]
  const [colorPickerFolderId, setColorPickerFolderId] = useState<string | null>(null)

  // Close the color picker on outside-click — same pattern as the avatar menu.
  useEffect(() => {
    if (!colorPickerFolderId) return
    const onClick = (e: MouseEvent) => {
      const target = e.target as HTMLElement
      if (!target.closest('[data-folder-color-picker]')) setColorPickerFolderId(null)
    }
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setColorPickerFolderId(null)
    }
    window.addEventListener('mousedown', onClick)
    window.addEventListener('keydown', onKey)
    return () => {
      window.removeEventListener('mousedown', onClick)
      window.removeEventListener('keydown', onKey)
    }
  }, [colorPickerFolderId])

  const handleSetFolderColor = async (id: string, color: string | null) => {
    setColorPickerFolderId(null)
    try {
      await api.folders.update(id, { color })
      qc.invalidateQueries({ queryKey: ["folders"] })
    } catch (e) {
      console.error('set folder color failed', e)
      toast.error("Couldn't update folder color", e instanceof Error ? e.message : undefined)
    }
  }

  const handleDeleteFolder = async (folder: Folder) => {
    const convCount = conversations.filter(c => c.folder_id === folder.id).length
    const msg = convCount > 0
      ? `Delete "${folder.name}"? Its ${convCount} conversation${convCount === 1 ? '' : 's'} will be unfoldered (not deleted).`
      : `Delete "${folder.name}"?`
    if (!window.confirm(msg)) return

    try {
      await api.folders.delete(folder.id)
      qc.invalidateQueries({ queryKey: ["folders"] })
      qc.invalidateQueries({ queryKey: ["conversations"] })
      toast.success("Folder deleted", folder.name)
    } catch (e) {
      console.error('delete folder failed', e)
      toast.error("Couldn't delete folder", e instanceof Error ? e.message : undefined)
    }
  }

  const toggleFolder = (id: string) => {
    setExpandedFolders(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id); else next.add(id)
      return next
    })
  }

  // ─── Drag & drop: move conversation into folder ─────────────────────
  const handleDragStart = (e: React.DragEvent, convId: string) => {
    e.dataTransfer.setData('text/ec-conversation', convId)
    e.dataTransfer.effectAllowed = 'move'
  }

  const handleDragOverFolder = (e: React.DragEvent, folderId: string | null) => {
    if (!e.dataTransfer.types.includes('text/ec-conversation')) return
    e.preventDefault()
    e.dataTransfer.dropEffect = 'move'
    setDragOverFolder(folderId ?? '__ungrouped__')
  }

  const handleDropOnFolder = async (e: React.DragEvent, folderId: string | null) => {
    e.preventDefault()
    const convId = e.dataTransfer.getData('text/ec-conversation')
    setDragOverFolder(null)
    if (!convId) return
    if (folderId) setExpandedFolders(prev => new Set(prev).add(folderId))
    try {
      await api.folders.moveConversation(convId, folderId)
    } finally {
      // Always refetch to get truth (handles both success and failure)
      qc.invalidateQueries({ queryKey: ["conversations"] })
    }
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
              <Icon size={16} strokeWidth={active ? 2.2 : 1.8} />
              {label}
            </Link>
          )
        })}

        {/* More — power-user disclosure */}
        <button
          onClick={() => setMoreOpen(v => !v)}
          aria-expanded={moreOpen}
          className="flex items-center gap-3 h-9 px-3 rounded-lg text-sm w-full transition-colors duration-100 hover:opacity-80"
          style={{ color: "var(--ec-sidebar-muted)" }}
        >
          <MoreHorizontal size={16} strokeWidth={1.8} />
          More
          <ChevronDown
            size={12}
            className={`ml-auto transition-transform ${moreOpen ? 'rotate-180' : ''}`}
            style={{ color: 'var(--ec-text-subtle)' }}
          />
        </button>

        {moreOpen && (
          <div className="ml-3 pl-2 border-l flex flex-col gap-0.5" style={{ borderColor: 'var(--ec-border)' }}>
            {MORE_ITEMS.map(({ href, label, icon: Icon }) => {
              const active = isActive(href)
              return (
                <Link
                  key={href}
                  href={href}
                  onClick={onClose}
                  className={cn(
                    "flex items-center gap-3 h-8 px-3 rounded-lg text-xs transition-colors duration-100",
                    !active && "hover:opacity-80"
                  )}
                  style={{
                    background: active ? "var(--ec-sidebar-active)" : undefined,
                    color: active ? "var(--ec-sidebar-text)" : "var(--ec-sidebar-muted)",
                    fontWeight: active ? 500 : undefined,
                  }}
                >
                  <Icon size={13} strokeWidth={active ? 2.2 : 1.8} />
                  {label}
                </Link>
              )
            })}
          </div>
        )}

        {/* Helper: render a single conversation row */}
        {(() => null)()}

        {/* Folders */}
        <div className="mt-4 px-2">
          <div className="flex items-center justify-between mb-1 px-1">
            <span className="text-[10px] font-medium uppercase tracking-wider" style={{ color: 'var(--ec-text-subtle)' }}>
              Folders
            </span>
            <button
              onClick={() => { setCreatingFolder(true); setNewFolderName('') }}
              className="w-5 h-5 flex items-center justify-center rounded hover:bg-[rgba(0,0,0,0.06)]"
              title="New folder"
            >
              <FolderPlus size={11} style={{ color: 'var(--ec-text-subtle)' }} />
            </button>
          </div>

          {/* Inline new-folder input */}
          {creatingFolder && (
            <div className="flex items-center gap-1 px-1 mb-1">
              <FolderIcon size={11} style={{ color: 'var(--ec-text-subtle)' }} />
              <input
                autoFocus
                value={newFolderName}
                onChange={e => setNewFolderName(e.target.value)}
                onKeyDown={e => {
                  if (e.key === 'Enter') handleCreateFolder()
                  if (e.key === 'Escape') { setCreatingFolder(false); setNewFolderName('') }
                }}
                onBlur={handleCreateFolder}
                placeholder="Folder name"
                className="flex-1 bg-transparent outline-none text-xs border-b"
                style={{ color: 'var(--ec-text)', borderColor: 'var(--ec-border)' }}
              />
            </div>
          )}

          {folders.length === 0 && !creatingFolder && (
            <p className="text-[10px] px-1 italic" style={{ color: 'var(--ec-text-subtle)', opacity: 0.6 }}>
              No folders yet
            </p>
          )}

          {folders.map(folder => {
            const isExpanded = expandedFolders.has(folder.id)
            const isEditingFolder = editingFolderId === folder.id
            const isDropTarget = dragOverFolder === folder.id
            const convsInFolder = conversations.filter(c => c.folder_id === folder.id)

            return (
              <div
                key={folder.id}
                onDragOver={e => handleDragOverFolder(e, folder.id)}
                onDragLeave={() => setDragOverFolder(null)}
                onDrop={e => handleDropOnFolder(e, folder.id)}
                className="rounded transition-colors"
                style={{ background: isDropTarget ? 'var(--ec-sidebar-active)' : undefined }}
              >
                <div
                  className="group flex items-center gap-1 px-1 py-1 rounded cursor-pointer hover:bg-[rgba(0,0,0,0.04)]"
                  onClick={() => !isEditingFolder && toggleFolder(folder.id)}
                >
                  {isExpanded
                    ? <ChevronDown size={11} style={{ color: 'var(--ec-text-subtle)' }} />
                    : <ChevronRight size={11} style={{ color: 'var(--ec-text-subtle)' }} />}
                  <FolderIcon size={11} style={{ color: folder.color ?? 'var(--ec-text-subtle)' }} />

                  {isEditingFolder ? (
                    <input
                      autoFocus
                      value={editFolderName}
                      onChange={e => setEditFolderName(e.target.value)}
                      onKeyDown={e => {
                        if (e.key === 'Enter') handleRenameFolder(folder.id)
                        if (e.key === 'Escape') setEditingFolderId(null)
                      }}
                      onBlur={() => handleRenameFolder(folder.id)}
                      onClick={e => e.stopPropagation()}
                      className="flex-1 bg-transparent outline-none text-xs"
                      style={{ color: 'var(--ec-text)' }}
                    />
                  ) : (
                    <span className="flex-1 text-xs truncate" style={{ color: 'var(--ec-sidebar-text)' }}>
                      {folder.name}
                    </span>
                  )}

                  {!isEditingFolder && convsInFolder.length > 0 && (
                    <span className="text-[10px] mr-1" style={{ color: 'var(--ec-text-subtle)' }}>
                      {convsInFolder.length}
                    </span>
                  )}

                  {!isEditingFolder && (
                    <div className="relative hidden group-hover:flex gap-0.5 shrink-0" data-folder-color-picker={colorPickerFolderId === folder.id ? "" : undefined}>
                      <button
                        onClick={e => {
                          e.stopPropagation()
                          setColorPickerFolderId(prev => prev === folder.id ? null : folder.id)
                        }}
                        className="p-0.5 rounded hover:bg-[rgba(0,0,0,0.08)]"
                        title="Folder color"
                        aria-label="Change folder color"
                        aria-haspopup="menu"
                        aria-expanded={colorPickerFolderId === folder.id}
                      >
                        <span
                          className="block w-2.5 h-2.5 rounded-full border"
                          style={{
                            background: folder.color ?? 'transparent',
                            borderColor: folder.color ? folder.color : 'var(--ec-text-subtle)',
                          }}
                        />
                      </button>
                      <button
                        onClick={e => {
                          e.stopPropagation()
                          setEditingFolderId(folder.id)
                          setEditFolderName(folder.name)
                        }}
                        className="p-0.5 rounded hover:bg-[rgba(0,0,0,0.08)]"
                        title="Rename"
                      >
                        <Pencil size={10} style={{ color: 'var(--ec-text-subtle)' }} />
                      </button>
                      <button
                        onClick={e => { e.stopPropagation(); handleDeleteFolder(folder) }}
                        className="p-0.5 rounded hover:bg-[rgba(0,0,0,0.08)]"
                        title="Delete folder"
                      >
                        <Trash2 size={10} style={{ color: 'var(--ec-text-subtle)' }} />
                      </button>

                      {colorPickerFolderId === folder.id && (
                        <div
                          role="menu"
                          aria-label="Folder color"
                          onClick={e => e.stopPropagation()}
                          className="absolute right-0 top-full mt-1 z-20 rounded-lg p-2 shadow-lg"
                          style={{
                            background: 'var(--ec-card-bg)',
                            border: '1px solid var(--ec-card-border)',
                            boxShadow: '0 4px 16px rgba(0,0,0,0.10)',
                          }}
                        >
                          <div className="flex gap-1.5">
                            {FOLDER_COLORS.map(c => (
                              <button
                                key={c.value}
                                role="menuitem"
                                onClick={() => handleSetFolderColor(folder.id, c.value)}
                                title={c.name}
                                aria-label={c.name}
                                className="w-5 h-5 rounded-full transition-transform hover:scale-110"
                                style={{
                                  background: c.value,
                                  outline: folder.color === c.value
                                    ? `2px solid var(--ec-text)`
                                    : 'none',
                                  outlineOffset: '2px',
                                }}
                              />
                            ))}
                            <button
                              role="menuitem"
                              onClick={() => handleSetFolderColor(folder.id, null)}
                              title="No color"
                              aria-label="No color"
                              className="w-5 h-5 rounded-full transition-transform hover:scale-110 flex items-center justify-center"
                              style={{
                                background: 'transparent',
                                border: '1px dashed var(--ec-text-subtle)',
                                outline: folder.color == null
                                  ? `2px solid var(--ec-text)`
                                  : 'none',
                                outlineOffset: '2px',
                              }}
                            >
                              <X size={10} style={{ color: 'var(--ec-text-subtle)' }} />
                            </button>
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>

                {/* Conversations inside this folder */}
                {isExpanded && (
                  <div className="ml-3 pl-2 border-l" style={{ borderColor: 'var(--ec-border)' }}>
                    {convsInFolder.length === 0 ? (
                      <p className="text-[10px] italic px-2 py-1" style={{ color: 'var(--ec-text-subtle)', opacity: 0.6 }}>
                        Drop chats here
                      </p>
                    ) : (
                      convsInFolder.map(conv => {
                        const isActive = pathname === `/dashboard/chat/${conv.id}`
                        const isEditing = editingId === conv.id
                        return (
                          <div
                            key={conv.id}
                            draggable={!isEditing}
                            onDragStart={e => handleDragStart(e, conv.id)}
                            onContextMenu={e => !isEditing && handleConvContextMenu(e, conv.id, conv.folder_id)}
                            className="group flex items-center gap-1 rounded-lg px-2 py-1 text-xs cursor-pointer transition-colors"
                            style={{
                              background: isActive ? 'var(--ec-sidebar-active)' : 'transparent',
                              color: isActive ? 'var(--ec-sidebar-text)' : 'var(--ec-text-subtle)',
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
                      })
                    )}
                  </div>
                )}
              </div>
            )
          })}
        </div>

        {/* Unfoldered conversations */}
        {(() => {
          const ungrouped = conversations.filter(c => !c.folder_id)
          if (ungrouped.length === 0) return null
          const isDropTarget = dragOverFolder === '__ungrouped__'
          return (
            <div
              onDragOver={e => handleDragOverFolder(e, null)}
              onDragLeave={() => setDragOverFolder(null)}
              onDrop={e => handleDropOnFolder(e, null)}
              className="mt-4 px-2 rounded transition-colors"
              style={{ background: isDropTarget ? 'var(--ec-sidebar-active)' : undefined }}
            >
              <div className="flex items-center justify-between mb-1 px-1">
                <span className="text-[10px] font-medium uppercase tracking-wider" style={{ color: 'var(--ec-text-subtle)' }}>
                  Conversations
                </span>
                <button
                  onClick={handleNewChat}
                  className="w-5 h-5 flex items-center justify-center rounded hover:bg-[rgba(0,0,0,0.06)]"
                  title="New chat"
                >
                  <Plus size={11} style={{ color: 'var(--ec-text-subtle)' }} />
                </button>
              </div>

              {groupByDate(ungrouped).map(group => (
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
                        draggable={!isEditing}
                        onDragStart={e => handleDragStart(e, conv.id)}
                        onContextMenu={e => !isEditing && handleConvContextMenu(e, conv.id, conv.folder_id)}
                        className="group flex items-center gap-1 rounded-lg px-2 py-1 text-xs cursor-pointer transition-colors"
                        style={{
                          background: isActive ? 'var(--ec-sidebar-active)' : 'transparent',
                          color: isActive ? 'var(--ec-sidebar-text)' : 'var(--ec-text-subtle)',
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
          )
        })()}
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

        {/* User status picker */}
        <div className="px-1 mt-1">
          <UserStatus />
        </div>

        {/* Avatar row — opens dropdown */}
        <div className="relative mt-2 pt-2 border-t" data-avatar-menu style={{ borderColor: "var(--ec-sidebar-border)" }}>

          {/* Dropdown — opens above the avatar */}
          {avatarMenuOpen && (
            <div
              ref={avatarMenuRef}
              role="menu"
              aria-orientation="vertical"
              aria-label="Account menu"
              onKeyDown={handleAvatarMenuKey}
              className="absolute left-2 right-2 bottom-[52px] rounded-xl overflow-hidden z-10"
              style={{
                background: "var(--ec-card-bg)",
                border: "1px solid var(--ec-card-border)",
                boxShadow: "0 4px 16px rgba(0,0,0,0.08)",
              }}
            >
              <Link
                href="/dashboard/profile"
                role="menuitem"
                onClick={() => { setAvatarMenuOpen(false); onClose?.() }}
                className="flex items-center gap-2.5 px-3 h-9 text-xs transition-colors hover:bg-[rgba(0,0,0,0.04)]"
                style={{ color: "var(--ec-text)" }}
              >
                <UserCircle size={14} style={{ color: "var(--ec-text-muted)" }} />
                Profile
              </Link>
              <Link
                href="/dashboard/notifications"
                role="menuitem"
                onClick={() => { setAvatarMenuOpen(false); onClose?.() }}
                className="flex items-center gap-2.5 px-3 h-9 text-xs transition-colors hover:bg-[rgba(0,0,0,0.04)]"
                style={{ color: "var(--ec-text)" }}
              >
                <Bell size={14} style={{ color: "var(--ec-text-muted)" }} />
                Notifications
                {unreadNotifs > 0 && (
                  <span
                    className="ml-auto min-w-[18px] h-[18px] rounded-full flex items-center justify-center text-[10px] font-semibold px-1.5"
                    style={{ background: '#B04A3A', color: '#fff' }}
                  >
                    {unreadNotifs > 99 ? '99+' : unreadNotifs}
                  </span>
                )}
              </Link>
              <Link
                href="/dashboard/transparency"
                role="menuitem"
                onClick={() => { setAvatarMenuOpen(false); onClose?.() }}
                className="flex items-center gap-2.5 px-3 h-9 text-xs transition-colors hover:bg-[rgba(0,0,0,0.04)]"
                style={{ color: "var(--ec-text)" }}
              >
                <Eye size={14} style={{ color: "var(--ec-text-muted)" }} />
                Transparency log
              </Link>
              <div className="h-px" role="separator" style={{ background: "var(--ec-card-border)" }} />
              <button
                role="menuitem"
                onClick={() => { setAvatarMenuOpen(false); signOut().catch(console.error) }}
                className="w-full flex items-center gap-2.5 px-3 h-9 text-xs transition-colors hover:bg-[rgba(0,0,0,0.04)]"
                style={{ color: "#B04A3A" }}
              >
                <LogOut size={14} />
                Sign out
              </button>
            </div>
          )}

          <button
            onClick={() => setAvatarMenuOpen(v => !v)}
            className="w-full flex items-center gap-2.5 px-3 py-1.5 rounded-lg transition-opacity hover:opacity-80 text-left"
            aria-expanded={avatarMenuOpen}
            aria-haspopup="menu"
          >
            <div className="relative shrink-0">
              <div
                className="w-7 h-7 rounded-full flex items-center justify-center text-xs font-semibold"
                style={{ background: "var(--ec-text)", color: "var(--ec-sidebar-bg)" }}
              >
                {initials}
              </div>
              {unreadNotifs > 0 && (
                <span
                  className="absolute -top-0.5 -right-0.5 w-2.5 h-2.5 rounded-full border-2"
                  style={{ background: '#B04A3A', borderColor: 'var(--ec-sidebar-bg)' }}
                  aria-label={`${unreadNotifs} unread notifications`}
                />
              )}
            </div>
            <div className="min-w-0 flex-1">
              <p className="text-xs truncate" style={{ color: "var(--ec-text)" }}>
                {user?.email?.split('@')[0] ?? 'My Account'}
              </p>
              <p className="text-[10px] truncate" style={{ color: "var(--ec-text-subtle)" }}>
                {avatarMenuOpen ? 'Close menu' : 'Account menu'}
              </p>
            </div>
            <ChevronDown
              size={12}
              className={`ml-auto shrink-0 transition-transform ${avatarMenuOpen ? 'rotate-180' : ''}`}
              style={{ color: "var(--ec-text-subtle)" }}
            />
          </button>
        </div>
      </div>

      {/* ─── Conversation right-click menu ─────────────────────────── */}
      {convCtxMenu && (() => {
        // Edge-snap so the menu never clips off the right/bottom of the
        // viewport. We approximate the menu size from the folder count
        // (header + "No folder" + each folder + separator + 2 actions).
        const MENU_W = 220
        const ROW_H = 32
        const HEADER_H = 26
        const SEPARATOR_H = 9
        const itemCount = 1 /* No folder */ + folders.length + 2 /* rename/delete */
        const approxH = HEADER_H + itemCount * ROW_H + SEPARATOR_H + 8
        const x =
          typeof window !== 'undefined'
            ? Math.min(convCtxMenu.x, window.innerWidth - MENU_W - 8)
            : convCtxMenu.x
        const y =
          typeof window !== 'undefined'
            ? Math.min(convCtxMenu.y, window.innerHeight - approxH - 8)
            : convCtxMenu.y
        const conv = conversations.find(c => c.id === convCtxMenu.convId)
        return (
          <div
            data-conv-ctx-menu
            role="menu"
            aria-label="Conversation actions"
            className="fixed z-50 rounded-xl overflow-hidden text-xs"
            style={{
              left: Math.max(x, 8),
              top: Math.max(y, 8),
              width: MENU_W,
              background: 'var(--ec-card-bg)',
              border: '1px solid var(--ec-card-border)',
              boxShadow: '0 8px 24px rgba(0,0,0,0.12)',
              color: 'var(--ec-text)',
            }}
          >
            <div
              className="px-3 py-1.5 text-[10px] font-medium uppercase tracking-wider"
              style={{ color: 'var(--ec-text-subtle)' }}
            >
              Move to folder
            </div>
            <button
              role="menuitem"
              disabled={convCtxMenu.currentFolderId === null}
              onClick={() => handleMoveConv(convCtxMenu.convId, null)}
              className="w-full text-left px-3 py-1.5 flex items-center gap-2 hover:bg-[rgba(0,0,0,0.04)] disabled:opacity-40 disabled:cursor-default"
            >
              <FolderIcon size={11} style={{ color: 'var(--ec-text-subtle)' }} />
              <span className="italic" style={{ color: 'var(--ec-text-muted)' }}>
                No folder
              </span>
              {convCtxMenu.currentFolderId === null && (
                <Check size={10} className="ml-auto" style={{ color: 'var(--ec-text-subtle)' }} />
              )}
            </button>
            {folders.map(f => {
              const isCurrent = convCtxMenu.currentFolderId === f.id
              return (
                <button
                  key={f.id}
                  role="menuitem"
                  disabled={isCurrent}
                  onClick={() => handleMoveConv(convCtxMenu.convId, f.id)}
                  className="w-full text-left px-3 py-1.5 flex items-center gap-2 hover:bg-[rgba(0,0,0,0.04)] disabled:opacity-50 disabled:cursor-default"
                >
                  <FolderIcon size={11} style={{ color: f.color ?? 'var(--ec-text-subtle)' }} />
                  <span className="truncate flex-1">{f.name}</span>
                  {isCurrent && (
                    <Check size={10} className="shrink-0" style={{ color: 'var(--ec-text-subtle)' }} />
                  )}
                </button>
              )
            })}
            <div role="separator" className="h-px my-1" style={{ background: 'var(--ec-card-border)' }} />
            <button
              role="menuitem"
              onClick={() => {
                if (conv) {
                  setEditingId(conv.id)
                  setEditTitle(conv.title)
                }
                closeCtxMenu()
              }}
              className="w-full text-left px-3 py-1.5 flex items-center gap-2 hover:bg-[rgba(0,0,0,0.04)]"
            >
              <Pencil size={11} style={{ color: 'var(--ec-text-subtle)' }} />
              Rename
            </button>
            <button
              role="menuitem"
              onClick={() => {
                handleDelete(convCtxMenu.convId)
                closeCtxMenu()
              }}
              className="w-full text-left px-3 py-1.5 flex items-center gap-2 hover:bg-[rgba(0,0,0,0.04)]"
              style={{ color: '#B04A3A' }}
            >
              <Trash2 size={11} />
              Delete
            </button>
          </div>
        )
      })()}
    </aside>
  )
}

export function MobileSidebarTrigger() { return null }
