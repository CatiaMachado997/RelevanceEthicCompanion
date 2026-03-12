"use client"

import { useState, useEffect } from "react"
import { Search, X, Shield, Target, MessageSquare, Clock, TrendingUp } from "lucide-react"
import { valuesApi, goalsApi, chatApi } from "@/lib/api"

type SearchResult = {
  id: string
  type: "value" | "goal" | "chat"
  title: string
  description?: string
  content?: string
  created_at?: string
  status?: string
}

type FilterType = "all" | "values" | "goals" | "chat"

export default function SearchPage() {
  const [query, setQuery] = useState("")
  const [results, setResults] = useState<SearchResult[]>([])
  const [loading, setLoading] = useState(false)
  const [recentSearches, setRecentSearches] = useState<string[]>([])
  const [filterType, setFilterType] = useState<FilterType>("all")

  // Load recent searches from localStorage
  useEffect(() => {
    const saved = localStorage.getItem("recentSearches")
    if (saved) {
      setRecentSearches(JSON.parse(saved))
    }
  }, [])

  // Save recent searches to localStorage
  const saveRecentSearch = (searchQuery: string) => {
    if (!searchQuery.trim()) return

    const updated = [
      searchQuery,
      ...recentSearches.filter((s) => s !== searchQuery),
    ].slice(0, 5) // Keep only 5 recent searches

    setRecentSearches(updated)
    localStorage.setItem("recentSearches", JSON.stringify(updated))
  }

  const performSearch = async (searchQuery: string) => {
    if (!searchQuery.trim()) {
      setResults([])
      return
    }

    setLoading(true)
    try {
      const searchResults: SearchResult[] = []

      // Search values
      if (filterType === "all" || filterType === "values") {
        const valuesData = await valuesApi.list()
        const matchedValues = valuesData.values.filter((value) =>
          value.type.toLowerCase().includes(searchQuery.toLowerCase()) ||
          value.value.toLowerCase().includes(searchQuery.toLowerCase())
        )
        searchResults.push(
          ...matchedValues.map((v) => ({
            id: v.id,
            type: "value" as const,
            title: v.type,
            description: v.value,
            content: undefined,
            created_at: v.created_at,
          }))
        )
      }

      // Search goals
      if (filterType === "all" || filterType === "goals") {
        const goalsData = await goalsApi.list()
        const matchedGoals = goalsData.goals.filter((goal) =>
          goal.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
          goal.description?.toLowerCase().includes(searchQuery.toLowerCase())
        )
        searchResults.push(
          ...matchedGoals.map((g) => ({
            id: g.id,
            type: "goal" as const,
            title: g.title,
            description: g.description ?? undefined,
            created_at: g.created_at,
            status: g.status,
          }))
        )
      }

      // Search chat history
      if (filterType === "all" || filterType === "chat") {
        const chatData = await chatApi.history()
        const matchedChats = chatData.messages.filter((msg) =>
          msg.content.toLowerCase().includes(searchQuery.toLowerCase())
        )
        searchResults.push(
          ...matchedChats.slice(0, 10).map((c, idx) => ({
            id: String(idx),
            type: "chat" as const,
            title: c.content.substring(0, 60) + (c.content.length > 60 ? "..." : ""),
            content: c.content,
            created_at: c.timestamp,
          }))
        )
      }

      setResults(searchResults)
    } catch (error) {
      console.error("Search error:", error)
    } finally {
      setLoading(false)
    }
  }

  const handleSearch = async (searchQuery: string) => {
    setQuery(searchQuery)
    saveRecentSearch(searchQuery)
    await performSearch(searchQuery)
  }

  const handleClear = () => {
    setQuery("")
    setResults([])
  }

  const handleRecentClick = (search: string) => {
    setQuery(search)
    performSearch(search)
  }

  const getIcon = (type: string) => {
    switch (type) {
      case "value":
        return <Shield className="h-4 w-4" />
      case "goal":
        return <Target className="h-4 w-4" />
      case "chat":
        return <MessageSquare className="h-4 w-4" />
      default:
        return null
    }
  }

  const getTypeColor = (type: string) => {
    switch (type) {
      case "value":
        return "bg-[#f5f5f5] text-[#0a0a0a]"
      case "goal":
        return "bg-[#f5f5f5] text-[#0a0a0a]"
      case "chat":
        return "bg-[#f5f5f5] text-[#0a0a0a]"
      default:
        return "bg-[#fafafa] text-[#6b6b6b]"
    }
  }

  return (
    <div className="flex-1 overflow-auto bg-white p-4 md:p-6">
      <div className="mx-auto max-w-4xl space-y-4 md:space-y-6">
        {/* Header */}
        <div className="space-y-1">
          <h1 className="text-2xl font-bold tracking-tight text-[#0a0a0a]">Search</h1>
          <p className="text-sm text-[#6b6b6b]">
            Search across your values, goals, and chat history
          </p>
        </div>

        {/* Search Input */}
        <div className="relative">
          <Search className="absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-[#9e9e9e]" />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                handleSearch(query)
              }
            }}
            placeholder="Search..."
            className="h-11 w-full rounded-xl border border-[rgba(0,0,0,0.12)] bg-white pl-10 pr-10 text-sm text-[#0a0a0a] placeholder:text-[#9e9e9e] focus:border-[#0a0a0a] focus:outline-none focus:ring-1 focus:ring-[#0a0a0a]"
          />
          {query && (
            <button
              onClick={handleClear}
              className="absolute right-3 top-1/2 -translate-y-1/2 rounded-full p-0.5 hover:bg-[#f5f5f5]"
            >
              <X className="h-4 w-4 text-[#9e9e9e]" />
            </button>
          )}
        </div>

        {/* Filter Buttons */}
        <div className="flex gap-2 flex-wrap">
          {(["all", "values", "goals", "chat"] as FilterType[]).map((filter) => (
            <button
              key={filter}
              onClick={() => {
                setFilterType(filter)
                if (query) performSearch(query)
              }}
              className={`rounded-full px-4 py-1.5 text-sm font-medium transition-colors ${
                filterType === filter
                  ? "bg-[#000000] text-white"
                  : "border border-[rgba(0,0,0,0.10)] text-[#6b6b6b] bg-white hover:bg-[#f5f5f5]"
              }`}
            >
              {filter.charAt(0).toUpperCase() + filter.slice(1)}
            </button>
          ))}
        </div>

        {/* Results */}
        {loading ? (
          <div className="flex items-center justify-center py-12">
            <div className="h-6 w-6 animate-spin rounded-full border-2 border-[rgba(0,0,0,0.08)] border-t-[#0a0a0a]" />
          </div>
        ) : results.length > 0 ? (
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <p className="text-xs font-medium uppercase tracking-wide text-[#9e9e9e]">
                {results.length} result{results.length !== 1 ? "s" : ""}
              </p>
            </div>
            <div className="space-y-2">
              {results.map((result) => (
                <div
                  key={`${result.type}-${result.id}`}
                  className="rounded-2xl border border-[rgba(0,0,0,0.08)] bg-white p-4 shadow-[0_1px_3px_rgba(0,0,0,0.08)] transition-shadow hover:shadow-[0_4px_12px_rgba(0,0,0,0.10)]"
                >
                  <div className="flex items-start gap-3">
                    <div className="mt-0.5 text-[#6b6b6b]">
                      {getIcon(result.type)}
                    </div>
                    <div className="flex-1 space-y-1">
                      <div className="flex items-center gap-2">
                        <span
                          className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium ${getTypeColor(
                            result.type
                          )}`}
                        >
                          {result.type}
                        </span>
                        {result.status && (
                          <span className="text-xs text-[#9e9e9e]">
                            {result.status}
                          </span>
                        )}
                      </div>
                      <h3 className="font-medium text-[#0a0a0a]">
                        {result.title}
                      </h3>
                      {result.description && (
                        <p className="text-sm text-[#6b6b6b] line-clamp-2">
                          {result.description}
                        </p>
                      )}
                      {result.content && result.type === "chat" && (
                        <p className="text-sm text-[#6b6b6b] line-clamp-2">
                          {result.content}
                        </p>
                      )}
                      {result.created_at && (
                        <div className="flex items-center gap-1 text-xs text-[#9e9e9e]">
                          <Clock className="h-3 w-3" />
                          {new Date(result.created_at).toLocaleDateString()}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        ) : query ? (
          <div className="flex flex-col items-center justify-center py-12 text-center">
            <Search className="mb-3 h-8 w-8 text-[#9e9e9e]" />
            <p className="text-sm font-medium text-[#0a0a0a]">
              No results found
            </p>
            <p className="text-xs text-[#9e9e9e]">
              Try adjusting your search or filters
            </p>
          </div>
        ) : null}

        {/* Recent Searches */}
        {!query && recentSearches.length > 0 && (
          <div className="space-y-3">
            <p className="text-xs font-medium uppercase tracking-wide text-[#9e9e9e]">
              Recent Searches
            </p>
            <div className="space-y-2">
              {recentSearches.map((search, index) => (
                <button
                  key={index}
                  onClick={() => handleRecentClick(search)}
                  className="flex w-full items-center gap-3 rounded-2xl border border-[rgba(0,0,0,0.08)] bg-white p-3 text-left shadow-[0_1px_3px_rgba(0,0,0,0.08)] transition-shadow hover:shadow-[0_4px_12px_rgba(0,0,0,0.10)]"
                >
                  <Clock className="h-4 w-4 text-[#9e9e9e]" />
                  <span className="text-sm text-[#0a0a0a]">{search}</span>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Empty State */}
        {!query && recentSearches.length === 0 && (
          <div className="flex flex-col items-center justify-center py-16 text-center">
            <div className="mb-4 rounded-full bg-[#f5f5f5] p-4">
              <Search className="h-8 w-8 text-[#9e9e9e]" />
            </div>
            <h3 className="mb-1 text-sm font-medium text-[#0a0a0a]">
              Start searching
            </h3>
            <p className="text-xs text-[#6b6b6b]">
              Search across all your values, goals, and chat history
            </p>
          </div>
        )}
      </div>
    </div>
  )
}
