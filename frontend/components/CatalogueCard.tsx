'use client'

import { ToolDefinition } from '@/lib/api'

interface Props {
  tool: ToolDefinition
  isConnected: boolean
  onConnect: (toolId: string) => void
  onDisconnect: (toolId: string) => void
}

export function CatalogueCard({ tool, isConnected, onConnect, onDisconnect }: Props) {
  return (
    <div
      className="flex items-center justify-between rounded-2xl p-4 transition-all"
      style={{
        background: isConnected ? 'linear-gradient(135deg, #f0f7f2 0%, #f9fff9 100%)' : '#ffffff',
        border: isConnected ? '1px solid #c8e6d3' : '1px solid #e4dee7',
      }}
    >
      {/* Left: icon + info */}
      <div className="flex items-center gap-3 min-w-0">
        <div
          className="w-10 h-10 rounded-xl flex items-center justify-center shrink-0"
          style={{ background: '#f5f2ef', border: '1px solid rgba(0,0,0,0.08)' }}
        >
          {tool.icon_url ? (
            <img src={tool.icon_url} alt={tool.name} className="w-6 h-6 rounded" />
          ) : (
            <span className="text-sm font-semibold" style={{ color: '#695e6e' }}>
              {tool.name[0]}
            </span>
          )}
        </div>
        <div className="min-w-0">
          <p className="text-sm font-semibold truncate" style={{ color: '#1c1520' }}>
            {tool.name}
          </p>
          <p className="text-xs truncate" style={{ color: '#695e6e' }}>
            {tool.description}
          </p>
        </div>
      </div>

      {/* Right: action button */}
      <div className="shrink-0 ml-3">
        {isConnected ? (
          <button
            onClick={() => onDisconnect(tool.id)}
            className="px-3 py-1.5 rounded-lg text-xs font-medium transition-colors hover:opacity-90"
            style={{
              background: 'rgba(176,74,58,0.07)',
              border: '1px solid rgba(176,74,58,0.2)',
              color: '#B04A3A',
            }}
          >
            Disconnect
          </button>
        ) : (
          <button
            onClick={() => onConnect(tool.id)}
            className="px-3 py-1.5 rounded-xl text-xs font-semibold transition-all hover:opacity-90 active:scale-[0.98]"
            style={{ background: '#4A7C59', color: '#ffffff' }}
          >
            + Connect
          </button>
        )}
      </div>
    </div>
  )
}
