import { render, screen } from '@testing-library/react';
import DashboardPage from '../app/dashboard/page';
import { transparencyApi, contextApi, insightApi } from '../lib/api';

// Mock all APIs used by the dashboard
jest.mock('../lib/api', () => ({
  transparencyApi: {
    report: jest.fn(),
    logs: jest.fn(),
  },
  contextApi: {
    snapshot: jest.fn(),
  },
  insightApi: {
    daily: jest.fn(),
  },
  // Type re-export — unused at runtime, kept for type imports.
}));

// recharts is heavy and not under test here.
jest.mock('recharts', () => ({
  PieChart: ({ children }: { children?: React.ReactNode }) => {
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const mockReact: typeof import('react') = require('react')
    return mockReact.createElement('div', null, children)
  },
  Pie: () => null,
  Cell: () => null,
  ResponsiveContainer: ({ children }: { children?: React.ReactNode }) => {
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const mockReact: typeof import('react') = require('react')
    return mockReact.createElement('div', null, children)
  },
}))

describe('DashboardPage', () => {
  beforeEach(() => {
    jest.resetAllMocks();

    (transparencyApi.report as jest.Mock).mockResolvedValue({
      total_decisions: 100,
      approval_rate: 0.95,
      vetoed_count: 5,
      modified_count: 10,
    });
    (transparencyApi.logs as jest.Mock).mockResolvedValue({ logs: [] });
    (contextApi.snapshot as jest.Mock).mockResolvedValue({
      calendar_pressure: 'light',
      overdue_count: 0,
      tasks_due_soon: [],
      active_projects: [],
      upcoming_events: [],
    });
    (insightApi.daily as jest.Mock).mockResolvedValue({ insight: null });
  });

  it('renders the Today and ESL activity sections after loading', async () => {
    render(<DashboardPage />);
    expect(await screen.findByText('Today')).toBeInTheDocument();
    expect(await screen.findByText(/ESL activity/i)).toBeInTheDocument();
  });

  it('handles API errors gracefully', async () => {
    (transparencyApi.report as jest.Mock).mockRejectedValue(new Error('API Error'));
    (transparencyApi.logs as jest.Mock).mockRejectedValue(new Error('API Error'));
    (contextApi.snapshot as jest.Mock).mockRejectedValue(new Error('API Error'));
    (insightApi.daily as jest.Mock).mockRejectedValue(new Error('API Error'));
    render(<DashboardPage />);
    // Component renders without crashing even when all APIs fail.
    expect(await screen.findByText('Today')).toBeInTheDocument();
  });
});
