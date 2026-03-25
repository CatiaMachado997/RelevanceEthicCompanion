/**
 * API Client for Backend Communication
 * 
 * Handles authenticated requests to the FastAPI backend.
 */

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
const DEFAULT_TIMEOUT_MS = 30000 // 30 second timeout

type AccessTokenProvider = () => string | null | Promise<string | null>
type UnauthorizedHandler = () => void

const authConfig: {
  getAccessToken: AccessTokenProvider | null
  onUnauthorized: UnauthorizedHandler | null
} = {
  getAccessToken: null,
  onUnauthorized: null,
}

export function configureApiAuth(config: {
  getAccessToken?: AccessTokenProvider
  onUnauthorized?: UnauthorizedHandler
}) {
  if (config.getAccessToken) authConfig.getAccessToken = config.getAccessToken
  if (config.onUnauthorized) authConfig.onUnauthorized = config.onUnauthorized
}

async function resolveAccessToken(): Promise<string | null> {
  if (authConfig.getAccessToken) {
    return authConfig.getAccessToken()
  }

  if (typeof window === 'undefined') return null
  return localStorage.getItem('access_token')
}

/**
 * Make an API request with timeout
 */
async function apiRequest<T>(
  endpoint: string,
  options: RequestInit = {},
  timeoutMs: number = DEFAULT_TIMEOUT_MS
): Promise<T> {
  const { signal, ...fetchOptions } = options
  const token = await resolveAccessToken()

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  }

  if (token && !headers.Authorization) {
    headers.Authorization = `Bearer ${token}`
  }

  // Copy existing headers
  if (fetchOptions.headers) {
    const existingHeaders = new Headers(fetchOptions.headers)
    existingHeaders.forEach((value, key) => {
      headers[key] = value
    })
  }

  // Create AbortController for timeout
  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs)

  // Combine with any existing signal
  const combinedSignal = signal
    ? AbortSignal.any([signal, controller.signal])
    : controller.signal

  try {
    const response = await fetch(`${API_URL}${endpoint}`, {
      ...fetchOptions,
      headers,
      signal: combinedSignal,
    })

    if (response.status === 401) {
      if (authConfig.onUnauthorized) {
        authConfig.onUnauthorized()
      }
      throw new Error('Unauthorized')
    }

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Request failed' }))
      throw new Error(error.detail || `HTTP ${response.status}`)
    }

    return response.json()
  } catch (error) {
    if (error instanceof Error && error.name === 'AbortError') {
      throw new Error(`Request timeout after ${timeoutMs}ms`)
    }
    throw error
  } finally {
    clearTimeout(timeoutId)
  }
}

// ==================== Values API ====================

export interface UserValue {
  id: string
  user_id: string
  type: 'boundary' | 'preference' | 'topic_filter' | 'time_window'
  value: string
  priority: number
  metadata?: Record<string, unknown>
  created_at: string
  updated_at: string
}

export const valuesApi = {
  /**
   * Get all user values
   */
  list: async () => {
    const response = await apiRequest<{
      status: string
      count: number
      data: UserValue[]
    }>('/api/values/')

    return {
      values: response.data || [],
      total_count: response.count || 0,
    }
  },

  /**
   * Create a new value
   */
  create: async (data: {
    type: string
    value: string
    priority: number
    metadata?: Record<string, unknown>
  }) => {
    const response = await apiRequest<{
      status: string
      message: string
      data: UserValue
    }>('/api/values/', {
      method: 'POST',
      body: JSON.stringify(data),
    })

    return response.data
  },

  /**
   * Update a value
   */
  update: async (id: string, data: Partial<UserValue>) => {
    const response = await apiRequest<{
      status: string
      message: string
      data: UserValue
    }>(`/api/values/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    })

    return response.data
  },

  /**
   * Delete a value
   */
  delete: async (id: string) => {
    const response = await apiRequest<{
      status: string
      message: string
      data: UserValue
    }>(`/api/values/${id}`, {
      method: 'DELETE',
    })

    return { message: response.message }
  },

  /**
   * Reorder values by updating priorities
   */
  reorder: async (valueIds: string[]) => {
    const response = await apiRequest<{
      status: string
      message: string
    }>('/api/values/reorder', {
      method: 'PATCH',
      body: JSON.stringify({ valueIds }),
    })

    return response
  },
}

// ==================== Chat API ====================

export interface ESLDecision {
  status: 'APPROVED' | 'VETOED' | 'MODIFIED';
  reason: string;
  violated_values?: string[];
}

export interface LLMModel {
  id: string;
  display_name: string;
  provider: string;
  context_window?: number;
}

export const chatApi = {
  /**
   * Send a chat message
   */
  send: (message: string, context?: Record<string, unknown>, model?: string) =>
    apiRequest<{
      message: string
      response: string | null
      executed: boolean
      esl_decision: ESLDecision
      transparency: string
      timestamp: string
      tool_executed?: boolean;
      tool_name?: string;
      tool_input?: Record<string, unknown>;
      tool_output?: Record<string, unknown>;
    }>('/api/chat/', {
      method: 'POST',
      body: JSON.stringify({ message, context, model }),
    }),

  /**
   * Stream a chat message via Server-Sent Events.
   * Returns a Promise that resolves when the stream ends, and exposes a
   * `cancel()` method to abort early.
   */
  stream: (
    message: string,
    onToken: (token: string) => void,
  ): Promise<void> & { cancel: () => void } => {
    let es: EventSource | null = null
    let settled = false
    let rejectRef: ((err: Error) => void) | null = null

    const promise = new Promise<void>((resolve, reject) => {
      rejectRef = reject
      const url = `${API_URL}/api/chat/stream?message=${encodeURIComponent(message)}`
      es = new EventSource(url, { withCredentials: true })

      es.onmessage = (e) => {
        try {
          const data = JSON.parse(e.data)
          if (data.error) {
            es!.close()
            if (!settled) { settled = true; reject(new Error(data.error)) }
            return
          }
          if (data.done) {
            es!.close()
            if (!settled) { settled = true; resolve() }
            return
          }
          onToken(data.token)
        } catch {
          // ignore parse errors on individual tokens
        }
      }

      es.onerror = () => {
        es!.close()
        if (!settled) { settled = true; reject(new Error('Stream error')) }
      }
    })

    const extended = promise as Promise<void> & { cancel: () => void }
    extended.cancel = () => {
      if (es) {
        es.close()
        es = null
      }
      if (!settled && rejectRef) {
        settled = true
        rejectRef(new Error('Stream cancelled'))
      }
    }

    return extended
  },

  /**
   * Get conversation history
   */
  history: (limit = 50, offset = 0) =>
    apiRequest<{
      user_id: string
      messages: Array<{
        role: string
        content: string
        timestamp: string
      }>
      total_count: number
    }>(`/api/chat/history?limit=${limit}&offset=${offset}`),

  /**
   * Get available LLM models
   */
  getModels: () =>
    apiRequest<LLMModel[]>('/api/chat/models'),
}

// ==================== Goals API ====================

export interface Goal {
  id: string
  user_id: string
  title: string
  description: string | null
  status: 'active' | 'completed' | 'paused' | 'archived'
  priority: number
  progress?: number
  target_date: string | null
  created_at: string
  completed_at: string | null
  metadata?: Record<string, unknown>
}

export const goalsApi = {
  /**
   * Get all goals
   */
  list: async (status?: string) => {
    const query = status ? `?status=${status}` : ''
    const response = await apiRequest<{
      status: string
      count: number
      data: Goal[]
    }>(`/api/goals/${query}`)

    return {
      goals: response.data || [],
      total_count: response.count || 0,
    }
  },

  /**
   * Create a new goal
   */
  create: async (data: {
    title: string
    description?: string
    priority: number
    progress?: number
    target_date?: string
  }) => {
    const response = await apiRequest<{
      status: string
      message: string
      data: Goal
    }>('/api/goals/', {
      method: 'POST',
      body: JSON.stringify(data),
    })

    return response.data
  },

  /**
   * Update a goal
   */
  update: async (id: string, data: Partial<Goal>) => {
    const response = await apiRequest<{
      status: string
      message: string
      data: Goal
    }>(`/api/goals/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    })

    return response.data
  },

  /**
   * Delete a goal
   */
  delete: async (id: string) => {
    const response = await apiRequest<{
      status: string
      message: string
      data: Goal
    }>(`/api/goals/${id}`, {
      method: 'DELETE',
    })

    return { message: response.message }
  },

  /**
   * Reorder goals by updating priorities
   */
  reorder: async (goalIds: string[]) => {
    const response = await apiRequest<{
      status: string
      message: string
    }>('/api/goals/reorder', {
      method: 'PATCH',
      body: JSON.stringify({ goalIds }),
    })

    return response
  },
}

// ==================== Transparency API ====================

export const transparencyApi = {
  /**
   * Get ESL transparency report
   */
  report: (days = 7) =>
    apiRequest<{
      user_id: string
      period_days: number
      total_decisions: number
      approved_count: number
      vetoed_count: number
      modified_count: number
      approval_rate: number
      recent_vetoes: Array<{
        action_type: string
        reason: string
        timestamp: string
      }>
      message?: string
    }>(`/api/transparency/report?days=${days}`),

  /**
   * Get ESL audit logs
   */
  logs: (days = 7, status?: string, limit = 100) => {
    const params = new URLSearchParams({ days: String(days), limit: String(limit) })
    if (status) params.append('decision_status', status)
    return apiRequest<{
      user_id: string
      logs: unknown[]
      total_count: number
      filtered_count: number
    }>(`/api/transparency/logs?${params}`)
  },

  /**
   * Get ESL statistics
   */
  stats: () =>
    apiRequest<{
      user_id: string
      total_decisions: number
      decision_breakdown: Record<string, number>
      most_protected_values: Array<{ value: string; count: number }>
      most_applied_rules: Array<{ rule: string; count: number }>
      average_confidence: number
    }>('/api/transparency/stats'),

  /**
   * Get ESL insights
   */
  insights: () =>
    apiRequest<{
      user_id: string
      period: string
      insights: string[]
    }>('/api/transparency/insights'),
}

// ==================== Feedback API ====================

export const feedbackApi = {
  submit: (data: {
    item_id: string
    item_type: 'chat_response' | 'search_result' | 'calendar_event' | 'proactive_insight' | 'memory_recall'
    feedback_type: 'thumbs_up' | 'thumbs_down' | 'not_relevant' | 'value_conflict' | 'inaccurate'
    additional_notes?: string
  }) =>
    apiRequest<{ status: string; data: { success: boolean; feedback_id: string } }>('/api/feedback/', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
}

// ==================== Relevance API ====================

export const relevanceApi = {
  /**
   * Trigger a relevance scan
   */
  scan: (windowMinutes = 15) =>
    apiRequest<{
      user_id: string
      window_minutes: number
      results: unknown[]
      scanned_at: string
    }>(`/api/relevance/scan?window_minutes=${windowMinutes}`, {
      method: 'POST',
    }),
}

// ==================== Events API ====================

export interface CalendarEvent {
  id: string
  title: string
  start_time: string | null
  end_time: string | null
  description: string | null
  source: string
}

export const eventsApi = {
  upcoming: (hoursAhead = 24) =>
    apiRequest<{ status: string; events: CalendarEvent[] }>(
      `/api/data-sources/events/upcoming?hours_ahead=${hoursAhead}`
    ),
}

// ==================== Data Sources API ====================

export interface DataSource {
  source_type: string
  enabled: boolean
  last_sync: string | null
  token_expires_at: string | null
  status: 'connected' | 'disconnected'
}

export const dataSourcesApi = {
  /**
   * Get all data sources for user
   */
  list: async () => {
    const response = await apiRequest<DataSource[]>('/api/data-sources/connected')

    return {
      sources: response || [],
      total_count: response?.length || 0,
    }
  },

  /**
   * Get OAuth authorization URL
   */
  getAuthUrl: async (sourceType: string) => {
    return apiRequest<{
      authorization_url: string
      state: string
    }>(`/api/data-sources/oauth/${sourceType}/authorize`)
  },

  /**
   * Disconnect a data source
   */
  disconnect: async (sourceType: string) => {
    return apiRequest<{
      success: boolean
      message: string
    }>(`/api/data-sources/${sourceType}`, {
      method: 'DELETE',
    })
  },

  /**
   * Manually trigger sync for a data source
   */
  sync: async (sourceType: string) => {
    return apiRequest<{
      success: boolean
      message: string
      items_synced: number
      source_type: string
    }>(`/api/data-sources/sync/${sourceType}`, {
      method: 'POST',
    })
  },
}

// ==================== Settings API ====================

export interface UserSettings {
  user_id?: string
  email_notifications: boolean
  push_notifications: boolean
  esl_alerts: boolean
  share_analytics: boolean
  pii_protection: boolean
  updated_at?: string
}

export const settingsApi = {
  get: async (): Promise<UserSettings> => {
    const response = await apiRequest<{ status: string; data: UserSettings }>('/api/settings/')
    return response.data
  },

  update: async (payload: Omit<UserSettings, 'user_id' | 'updated_at'>): Promise<UserSettings> => {
    const response = await apiRequest<{ status: string; data: UserSettings }>('/api/settings/', {
      method: 'PUT',
      body: JSON.stringify(payload),
    })
    return response.data
  },
}

// ==================== Notifications API ====================

export interface Notification {
  id: string
  user_id: string
  type: string
  title: string
  message: string
  read: boolean
  metadata?: Record<string, unknown>
  created_at: string
}

export const notificationsApi = {
  list: async (unreadOnly = false): Promise<{ notifications: Notification[]; unread_count: number }> => {
    const url = unreadOnly ? '/api/notifications/?unread_only=true' : '/api/notifications/'
    const response = await apiRequest<{
      status: string
      notifications: Notification[]
      unread_count: number
    }>(url)
    return { notifications: response.notifications || [], unread_count: response.unread_count || 0 }
  },

  markRead: async (id: string): Promise<void> => {
    await apiRequest(`/api/notifications/${id}/read`, { method: 'PATCH' })
  },

  markAllRead: async (): Promise<void> => {
    await apiRequest('/api/notifications/read-all', { method: 'PATCH' })
  },
}

export interface SearchResult {
  id: string
  type: "memory" | "event" | string
  content: string
  score: number
  metadata: Record<string, unknown>
}

export const searchApi = {
  async query(q: string, limit = 10): Promise<SearchResult[]> {
    const params = new URLSearchParams({ q, limit: String(limit) })
    return apiRequest<SearchResult[]>(`/api/search?${params}`)
  },
}

export const api = {
  values: valuesApi,
  chat: chatApi,
  goals: goalsApi,
  transparency: transparencyApi,
  relevance: relevanceApi,
  feedback: feedbackApi,
  events: eventsApi,
  dataSources: dataSourcesApi,
  settings: settingsApi,
  notifications: notificationsApi,
  search: searchApi,
};

export default api;
