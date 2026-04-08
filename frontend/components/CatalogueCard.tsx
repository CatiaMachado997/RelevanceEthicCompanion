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
    <div className="flex items-center justify-between rounded-lg border border-gray-800 bg-gray-900 px-4 py-3">
      <div className="flex items-center gap-3">
        {tool.icon_url ? (
          <img src={tool.icon_url} alt={tool.name} className="h-8 w-8 rounded" />
        ) : (
          <div className="flex h-8 w-8 items-center justify-center rounded bg-gray-700 text-sm text-white">
            {tool.name[0]}
          </div>
        )}
        <div>
          <p className="text-sm font-medium text-white">{tool.name}</p>
          <p className="text-xs text-gray-400">{tool.description}</p>
        </div>
      </div>
      {isConnected ? (
        <button
          onClick={() => onDisconnect(tool.id)}
          className="rounded px-3 py-1 text-xs text-red-400 hover:bg-red-900/30 border border-red-800"
        >
          Disconnect
        </button>
      ) : (
        <button
          onClick={() => onConnect(tool.id)}
          className="rounded bg-indigo-600 px-3 py-1 text-xs text-white hover:bg-indigo-500"
        >
          + Connect
        </button>
      )}
    </div>
  )
}
