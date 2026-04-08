'use client'

interface Props {
  toolName: string
  actionName: string
  preview: string
  onAllowOnce: () => void
  onAlwaysAllow: () => void
  onDeny: () => void
}

export function ToolConfirmation({ toolName, actionName, preview, onAllowOnce, onAlwaysAllow, onDeny }: Props) {
  return (
    <div className="rounded-lg border border-amber-700 bg-gray-900 p-4 my-2">
      <p className="text-xs font-semibold text-amber-400 mb-2">
        {toolName} wants to: {actionName}
      </p>
      <p className="text-sm text-gray-300 mb-3 whitespace-pre-wrap">{preview}</p>
      <div className="flex gap-2 flex-wrap">
        <button
          onClick={onAllowOnce}
          className="rounded bg-green-700 px-3 py-1 text-xs text-white hover:bg-green-600"
        >
          Allow once
        </button>
        <button
          onClick={onAlwaysAllow}
          className="rounded bg-indigo-600 px-3 py-1 text-xs text-white hover:bg-indigo-500"
        >
          Always allow
        </button>
        <button
          onClick={onDeny}
          className="rounded bg-red-800 px-3 py-1 text-xs text-white hover:bg-red-700"
        >
          Don&apos;t do this
        </button>
      </div>
    </div>
  )
}
