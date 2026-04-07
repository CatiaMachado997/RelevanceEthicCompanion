"use client"

import { useState, useEffect, useCallback } from 'react'
import { api, Project } from '@/lib/api'
import { FolderOpen, Archive, AlertCircle, RefreshCw, Plus } from 'lucide-react'
import { ProjectDrawer } from '@/components/drawers/ProjectDrawer'

function formatDate(dateStr: string | null): string {
  if (!dateStr) return '—'
  return new Date(dateStr).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  })
}

function StatusBadge({ status }: { status: Project['status'] }) {
  if (status === 'active') {
    return (
      <span
        className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium"
        style={{ background: '#e6f4ee', color: '#2d6a4f', border: '1px solid #c8e6d3' }}
      >
        Active
      </span>
    )
  }
  if (status === 'completed') {
    return (
      <span
        className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium"
        style={{ background: '#e8f0fe', color: '#1a56db', border: '1px solid #c3d3fb' }}
      >
        Completed
      </span>
    )
  }
  return (
    <span
      className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium"
      style={{ background: 'var(--ec-surface-2, #f5f2ef)', color: 'var(--ec-text-muted)', border: '1px solid var(--ec-card-border)' }}
    >
      Archived
    </span>
  )
}

export default function ProjectsPage() {
  const [projects, setProjects] = useState<Project[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [archivingId, setArchivingId] = useState<string | null>(null)
  const [selectedProject, setSelectedProject] = useState<Project | null>(null)
  const [drawerOpen, setDrawerOpen]           = useState(false)

  // Create form state
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [creating, setCreating] = useState(false)
  const [createError, setCreateError] = useState<string | null>(null)

  const loadProjects = useCallback(async () => {
    try {
      const data = await api.projects.list()
      setProjects(data)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load projects')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { loadProjects() }, [loadProjects])

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!title.trim()) return
    setCreating(true)
    setCreateError(null)
    try {
      const project = await api.projects.create({
        title: title.trim(),
        description: description.trim() || undefined,
      })
      setProjects(prev => [project, ...prev])
      setTitle('')
      setDescription('')
    } catch (e) {
      console.error('Project create failed:', e)
      setCreateError(e instanceof Error ? e.message : 'Failed to create project')
    } finally {
      setCreating(false)
    }
  }

  const handleArchive = async (id: string) => {
    setArchivingId(id)
    try {
      await api.projects.archive(id)
      setProjects(prev => prev.filter(p => p.id !== id))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to archive project')
    } finally {
      setArchivingId(null)
    }
  }

  return (
    <div className="space-y-6 max-w-3xl">
      {/* Page header */}
      <div>
        <h2 className="text-lg font-semibold" style={{ color: 'var(--ec-text)' }}>Projects</h2>
        <p className="text-sm mt-0.5" style={{ color: 'var(--ec-text-muted)' }}>
          Organise your work into projects and track progress.
        </p>
      </div>

      {/* Error banner */}
      {error && (
        <div
          className="flex items-center justify-between gap-2 px-4 py-3 rounded-xl text-sm"
          style={{ background: 'rgba(176,74,58,0.07)', border: '1px solid rgba(176,74,58,0.25)', color: '#B04A3A' }}
        >
          <div className="flex items-center gap-2">
            <AlertCircle size={15} />
            <span>{error}</span>
          </div>
          <button
            onClick={() => setError(null)}
            className="shrink-0 opacity-50 hover:opacity-100 transition-opacity text-base leading-none"
          >
            ×
          </button>
        </div>
      )}

      {/* Create form */}
      <div
        className="px-4 py-4 rounded-xl"
        style={{
          background: 'var(--ec-card-bg)',
          border: '1px solid var(--ec-card-border)',
          boxShadow: 'var(--ec-card-shadow)',
        }}
      >
        <p className="text-xs font-medium uppercase tracking-wider mb-3" style={{ color: 'var(--ec-text-subtle)' }}>
          New project
        </p>
        <form onSubmit={handleCreate} className="space-y-2">
          {createError && (
            <p className="text-xs" style={{ color: '#B04A3A' }}>{createError}</p>
          )}
          <input
            type="text"
            placeholder="Project title"
            value={title}
            onChange={e => setTitle(e.target.value)}
            required
            className="w-full px-3 py-2 rounded-lg text-sm outline-none"
            style={{
              background: 'var(--ec-surface-2, #f5f2ef)',
              border: '1px solid var(--ec-card-border)',
              color: 'var(--ec-text)',
            }}
          />
          <input
            type="text"
            placeholder="Description (optional)"
            value={description}
            onChange={e => setDescription(e.target.value)}
            className="w-full px-3 py-2 rounded-lg text-sm outline-none"
            style={{
              background: 'var(--ec-surface-2, #f5f2ef)',
              border: '1px solid var(--ec-card-border)',
              color: 'var(--ec-text)',
            }}
          />
          <button
            type="submit"
            disabled={creating || !title.trim()}
            className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium transition-opacity disabled:opacity-40"
            style={{ background: 'var(--ec-text)', color: 'var(--ec-sidebar-bg)' }}
          >
            {creating ? <RefreshCw size={13} className="animate-spin" /> : <Plus size={13} />}
            {creating ? 'Creating…' : 'Create project'}
          </button>
        </form>
      </div>

      {/* Project list */}
      <div>
        {loading ? (
          <div className="flex items-center justify-center py-12 gap-2" style={{ color: 'var(--ec-text-subtle)' }}>
            <RefreshCw size={16} className="animate-spin" />
            <span className="text-sm">Loading projects…</span>
          </div>
        ) : projects.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 gap-3">
            <div
              className="w-12 h-12 rounded-xl flex items-center justify-center"
              style={{ background: 'var(--ec-surface-2, #f5f2ef)', border: '1px solid var(--ec-card-border)' }}
            >
              <FolderOpen size={20} style={{ color: 'var(--ec-text-subtle)' }} />
            </div>
            <div className="text-center">
              <p className="text-sm font-medium" style={{ color: 'var(--ec-text)' }}>No projects yet</p>
              <p className="text-xs mt-0.5" style={{ color: 'var(--ec-text-subtle)' }}>
                Create your first project above to get started.
              </p>
            </div>
          </div>
        ) : (
          <div className="space-y-2">
            <p className="text-xs font-medium uppercase tracking-wider mb-2" style={{ color: 'var(--ec-text-subtle)' }}>
              {projects.length} project{projects.length !== 1 ? 's' : ''}
            </p>
            {projects.map(project => (
              <div
                key={project.id}
                className="flex items-start gap-4 px-4 py-3 rounded-xl cursor-pointer hover:ring-1 hover:ring-[var(--ec-card-border)]"
                style={{
                  background: 'var(--ec-card-bg)',
                  border: '1px solid var(--ec-card-border)',
                  boxShadow: 'var(--ec-card-shadow)',
                }}
                onClick={() => { setSelectedProject(project); setDrawerOpen(true) }}
              >
                {/* Icon */}
                <div
                  className="w-9 h-9 rounded-lg flex items-center justify-center shrink-0 mt-0.5"
                  style={{ background: 'var(--ec-surface-2, #f5f2ef)', border: '1px solid var(--ec-card-border)' }}
                >
                  <FolderOpen size={16} style={{ color: 'var(--ec-text-muted)' }} />
                </div>

                {/* Info */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-sm font-medium truncate" style={{ color: 'var(--ec-text)' }}>
                      {project.title}
                    </span>
                    <StatusBadge status={project.status} />
                  </div>
                  {project.description && (
                    <p className="text-xs mt-0.5 line-clamp-2" style={{ color: 'var(--ec-text-muted)' }}>
                      {project.description}
                    </p>
                  )}
                  <p className="text-xs mt-1" style={{ color: 'var(--ec-text-subtle)' }}>
                    Created {formatDate(project.created_at)}
                  </p>
                </div>

                {/* Archive button */}
                <button
                  onClick={e => { e.stopPropagation(); handleArchive(project.id) }}
                  disabled={archivingId === project.id || project.status === 'archived'}
                  className="w-8 h-8 rounded-lg flex items-center justify-center transition-opacity disabled:opacity-30 hover:opacity-70 shrink-0"
                  style={{ background: 'var(--ec-surface-2, #f5f2ef)', border: '1px solid var(--ec-card-border)' }}
                  title="Archive project"
                  aria-label={`Archive ${project.title}`}
                >
                  {archivingId === project.id
                    ? <RefreshCw size={13} className="animate-spin" style={{ color: 'var(--ec-text-muted)' }} />
                    : <Archive size={13} style={{ color: 'var(--ec-text-muted)' }} />
                  }
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      <ProjectDrawer
        project={selectedProject}
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        onSaved={loadProjects}
      />
    </div>
  )
}
