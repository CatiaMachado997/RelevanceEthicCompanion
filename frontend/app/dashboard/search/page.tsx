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
          value.content.toLowerCase().includes(searchQuery.toLowerCase()) ||
          value.context?.toLowerCase().includes(searchQuery.toLowerCase())
        )
        searchResults.push(
          ...matchedValues.map((v) => ({
            id: v.id,
            type: "value" as const,
            title: v.type,
            description: v.content,
            content: v.context,
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
            description: g.description,
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
        return "bg-[#F5F5F5] text-[#171717]"
      case "goal":
        return "bg-[#F5F5F5] text-[#171717]"
      case "chat":
        return "bg-[#F5F5F5] text-[#171717]"
      default:
        return "bg-[#FAFAFA] text-[#525252]"
    }
  }

  return (
    <div className="flex-1 overflow-auto bg-[#FAFAFA] p-4 md:p-6">
      <div className="mx-auto max-w-4xl space-y-4 md:space-y-6">
        {/* Header */}
        <div className="space-y-2">
          <h1 className="text-2xl font-semibold text-[#171717]">Search</h1>
          <p className="text-sm text-[#525252]">
            Search across your values, goals, and chat history
          </p>
        </div>

        {/* Search Input */}
        <div className="relative">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[#A3A3A3]" />
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
            className="h-10 w-full rounded-lg border border-[#E5E5E5] bg-white pl-9 pr-9 text-sm text-[#171717] placeholder:text-[#A3A3A3] focus:border-[#171717] focus:outline-none focus:ring-1 focus:ring-[#171717]"
          />
          {query && (
            <button
              onClick={handleClear}
              className="absolute right-3 top-1/2 -translate-y-1/2 rounded hover:bg-[#F5F5F5]"
            >
              <X className="h-4 w-4 text-[#A3A3A3]" />
            </button>
          )}
        </div>

        {/* Filter Buttons */}
        <div className="flex gap-2">
          {(["all", "values", "goals", "chat"] as FilterType[]).map((filter) => (
            <button
              key={filter}
              onClick={() => {
                setFilterType(filter)
                if (query) performSearch(query)
              }}
              className={`rounded-lg px-3 py-1.5 text-sm font-medium transition-colors ${
                filterType === filter
                  ? "bg-[#171717] text-white"
                  : "bg-white text-[#525252] hover:bg-[#F5F5F5] border border-[#E5E5E5]"
              }`}
            >
              {filter.charAt(0).toUpperCase() + filter.slice(1)}
            </button>
          ))}
        </div>

        {/* Results */}
        {loading ? (
          <div className="flex items-center justify-center py-12">
            <div className="h-6 w-6 animate-spin rounded-full border-2 border-[#E5E5E5] border-t-[#171717]" />
          </div>
        ) : results.length > 0 ? (
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-medium text-[#525252]">
                {results.length} result{results.length !== 1 ? "s" : ""}
              </h2>
            </div>
            <div className="space-y-2">
              {results.map((result) => (
                <div
                  key={`${result.type}-${result.id}`}
                  className="rounded-lg border border-[#E5E5E5] bg-white p-4 transition-shadow hover:shadow-md"
                >
                  <div className="flex items-start gap-3">
                    <div className="mt-0.5 text-[#525252]">
                      {getIcon(result.type)}
                    </div>
                    <div className="flex-1 space-y-1">
                      <div className="flex items-center gap-2">
                        <span
                          className={`inline-flex items-center gap-1 rounded px-2 py-0.5 text-xs font-medium ${getTypeColor(
                            result.type
                          )}`}
                        >
                          {result.type}
                        </span>
                        {result.status && (
                          <span className="text-xs text-[#A3A3A3]">
                            {result.status}
                          </span>
                        )}
                      </div>
                      <h3 className="font-medium text-[#171717]">
                        {result.title}
                      </h3>
                      {result.description && (
                        <p className="text-sm text-[#525252] line-clamp-2">
                          {result.description}
                        </p>
                      )}
                      {result.content && result.type === "chat" && (
                        <p className="text-sm text-[#525252] line-clamp-2">
                          {result.content}
                        </p>
                      )}
                      {result.created_at && (
                        <div className="flex items-center gap-1 text-xs text-[#A3A3A3]">
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
            <Search className="mb-3 h-8 w-8 text-[#E5E5E5]" />
            <p className="text-sm font-medium text-[#525252]">
              No results found
            </p>
            <p className="text-xs text-[#A3A3A3]">
              Try adjusting your search or filters
            </p>
          </div>
        ) : null}

        {/* Recent Searches */}
        {!query && recentSearches.length > 0 && (
          <div className="space-y-3">
            <h2 className="text-sm font-medium text-[#525252]">
              Recent Searches
            </h2>
            <div className="space-y-2">
              {recentSearches.map((search, index) => (
                <button
                  key={index}
                  onClick={() => handleRecentClick(search)}
                  className="flex w-full items-center gap-3 rounded-lg border border-[#E5E5E5] bg-white p-3 text-left transition-shadow hover:shadow-md"
                >
                  <Clock className="h-4 w-4 text-[#A3A3A3]" />
                  <span className="text-sm text-[#171717]">{search}</span>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Empty State */}
        {!query && recentSearches.length === 0 && (
          <div className="flex flex-col items-center justify-center py-16 text-center">
            <div className="mb-4 rounded-full bg-[#F5F5F5] p-4">
              <Search className="h-8 w-8 text-[#A3A3A3]" />
            </div>
            <h3 className="mb-1 text-sm font-medium text-[#171717]">
              Start searching
            </h3>
            <p className="text-xs text-[#525252]">
              Search across all your values, goals, and chat history
            </p>
          </div>
        )}
      </div>
    </div>
  )
}
