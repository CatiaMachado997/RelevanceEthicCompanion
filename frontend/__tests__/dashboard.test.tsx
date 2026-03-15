import { render, screen } from '@testing-library/react';
import DashboardPage from '../app/dashboard/page';
import { transparencyApi, goalsApi, valuesApi } from '../lib/api';

// Mock all APIs used by the dashboard
jest.mock('../lib/api', () => ({
  transparencyApi: {
    report: jest.fn(),
    logs: jest.fn(),
  },
  goalsApi: {
    list: jest.fn(),
  },
  valuesApi: {
    list: jest.fn(),
  },
}));

describe('DashboardPage', () => {
  beforeEach(() => {
    // Reset all mocks (clears call history and return values) before re-setting
    jest.resetAllMocks();

    (transparencyApi.report as jest.Mock).mockResolvedValue({
      total_decisions: 100,
      approval_rate: 0.95,
      vetoed_count: 5,
      modified_count: 10,
    });
    (transparencyApi.logs as jest.Mock).mockResolvedValue({ logs: [] });
    (goalsApi.list as jest.Mock).mockResolvedValue({ goals: [] });
    (valuesApi.list as jest.Mock).mockResolvedValue({ values: [] });
  });

  it('renders stat labels after loading', async () => {
    render(<DashboardPage />);
    // 'Values Set' and 'ESL Decisions Today' are unique stat labels
    expect(await screen.findByText('Values Set')).toBeInTheDocument();
    expect(await screen.findByText('ESL Decisions Today')).toBeInTheDocument();
    // 'Active Goals' appears twice (stat label + section heading); verify at least one exists
    expect(screen.getAllByText('Active Goals').length).toBeGreaterThan(0);
  });

  it('handles API errors gracefully', async () => {
    (transparencyApi.report as jest.Mock).mockRejectedValue(new Error('API Error'));
    (goalsApi.list as jest.Mock).mockRejectedValue(new Error('API Error'));
    (valuesApi.list as jest.Mock).mockRejectedValue(new Error('API Error'));
    (transparencyApi.logs as jest.Mock).mockRejectedValue(new Error('API Error'));
    render(<DashboardPage />);
    // Component renders without crashing even when all APIs fail
    expect(await screen.findByText('Values Set')).toBeInTheDocument();
  });
});
