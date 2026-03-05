import { render, screen } from '@testing-library/react';
import DashboardPage from '../app/dashboard/page';
import { transparencyApi } from '../lib/api';

// Mock the transparencyApi
jest.mock('../lib/api', () => ({
  transparencyApi: {
    insights: jest.fn(),
    report: jest.fn(),
  },
}));

describe('DashboardPage', () => {
  beforeEach(() => {
    // Reset and mock successful API responses before each test
    (transparencyApi.insights as jest.Mock).mockClear();
    (transparencyApi.report as jest.Mock).mockClear();
    (transparencyApi.insights as jest.Mock).mockResolvedValue({ insights: ['Test Insight'] });
    (transparencyApi.report as jest.Mock).mockResolvedValue({
      total_decisions: 100,
      approval_rate: 0.95,
      vetoed_count: 5,
      modified_count: 10,
    });
  });

  it('shows loading state initially', () => {
    render(<DashboardPage />);
    expect(screen.getByText('Loading your dashboard...')).toBeInTheDocument();
  });

  it('renders dashboard content after loading', async () => {
    render(<DashboardPage />);

    // findBy queries are async and handle waiting for elements to appear
    expect(await screen.findByText('Dashboard')).toBeInTheDocument();
    expect(await screen.findByText('Total Decisions')).toBeInTheDocument();
    expect(await screen.findByText('100')).toBeInTheDocument();
    expect(await screen.findByText('Approval Rate')).toBeInTheDocument();
    expect(await screen.findByText('95%')).toBeInTheDocument();
  });

  it('handles API errors gracefully', async () => {
    // Mock console.error to suppress expected error messages in the test output
    const consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});

    // Override the default successful mock with a failed one for this test
    (transparencyApi.insights as jest.Mock).mockRejectedValue(new Error('API Error'));
    (transparencyApi.report as jest.Mock).mockRejectedValue(new Error('API Error'));

    render(<DashboardPage />);

    // Wait for the content to be loaded
    expect(await screen.findByText('Dashboard')).toBeInTheDocument();
    
    // Check that the stats are not rendered
    expect(screen.queryByText('Total Decisions')).not.toBeInTheDocument();

    // Restore console.error
    consoleErrorSpy.mockRestore();
  });
});
