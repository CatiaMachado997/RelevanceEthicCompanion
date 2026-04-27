/**
 * @jest-environment jsdom
 */
import React from "react"
import { render, screen, waitFor } from "@testing-library/react"
import { act } from "react"

// Mock the API module
jest.mock("@/lib/api", () => ({
  autolabApi: {
    insights: jest.fn(),
  },
}))

// Mock next/navigation
jest.mock("next/navigation", () => ({
  usePathname: () => "/dashboard/insights",
  useRouter: () => ({ push: jest.fn() }),
}))

import { autolabApi } from "@/lib/api"
import InsightsPage from "@/app/dashboard/insights/page"

const mockData = {
  daily_insight: "Review your goals today.",
  autolab: {
    best_scores: { esl_tuning: 0.85, prompt_opt: null, context_scoring: 0.72 },
    total_trials: 17,
    total_wins: 5,
  },
  recent_experiments: [
    { track: "esl_tuning", trial: 12, score: 0.85, outcome: "WIN", hypothesis: "test" },
  ],
}

describe("InsightsPage", () => {
  beforeEach(() => {
    jest.clearAllMocks()
  })

  it("renders the page header", async () => {
    ;(autolabApi.insights as jest.Mock).mockResolvedValue(mockData)
    await act(async () => {
      render(<InsightsPage />)
    })
    expect(screen.getByText("Insights")).toBeInTheDocument()
  })

  it("shows daily insight text after loading", async () => {
    ;(autolabApi.insights as jest.Mock).mockResolvedValue(mockData)
    render(<InsightsPage />)
    await waitFor(() =>
      expect(screen.getByText("Review your goals today.")).toBeInTheDocument()
    )
  })

  it("shows error state when API fails", async () => {
    ;(autolabApi.insights as jest.Mock).mockRejectedValue(new Error("Network error"))
    render(<InsightsPage />)
    await waitFor(() =>
      expect(screen.getByText(/Could not load insights/i)).toBeInTheDocument()
    )
  })

  it("shows WIN outcome badge for winning experiments", async () => {
    ;(autolabApi.insights as jest.Mock).mockResolvedValue(mockData)
    render(<InsightsPage />)
    await waitFor(() =>
      expect(screen.getByText("WIN")).toBeInTheDocument()
    )
  })
})
