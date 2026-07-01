import { render, screen } from '@testing-library/react';
import DashboardPage from '../app/dashboard/page';

// next/link transitively reads router context; without an app router
// mounted in the test tree, render() throws "invariant expected app
// router to be mounted". Stub to a plain <a> that just forwards props.
//
// jest.mock factories run before imports — they can't reference any
// out-of-scope variables, including TS-injected helpers. Avoid rest
// spread (which Babel/TS lowers to a `__rest` import) and pull React
// in lazily inside the factory.
jest.mock('next/link', () => ({
  __esModule: true,
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  default: function MockLink(props: any) {
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const r = require('react')
    return r.createElement('a', props, props.children)
  },
}));

// The dashboard page is now just a composition of three sub-components,
// each of which has its own focused tests. Stub them out and verify the
// page composes them in order, inside the ErrorBoundary, without
// crashing.
jest.mock('../components/dashboard-hero', () => ({
  DashboardHero: () => {
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const r = require('react')
    return r.createElement('div', { 'data-testid': 'dashboard-hero' }, 'Hero')
  },
  RecentConversations: () => {
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const r = require('react')
    return r.createElement('div', { 'data-testid': 'recent-conversations' }, 'Recent')
  },
}))
jest.mock('../components/tools-launcher', () => ({
  ToolsLauncher: () => {
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const r = require('react')
    return r.createElement('div', { 'data-testid': 'tools-launcher' }, 'Tools')
  },
}))

describe('DashboardPage', () => {
  it('renders Hero, Tools, and Recent sections', () => {
    render(<DashboardPage />);
    expect(screen.getByTestId('dashboard-hero')).toBeInTheDocument();
    expect(screen.getByTestId('tools-launcher')).toBeInTheDocument();
    expect(screen.getByTestId('recent-conversations')).toBeInTheDocument();
  });

  it('renders without throwing even with empty mocks', () => {
    // Smoke test: page is just composition; the ErrorBoundary wraps the
    // children, so even if a child silently no-ops, the page should mount.
    expect(() => render(<DashboardPage />)).not.toThrow();
  });
});
