import { render, screen } from '@testing-library/react';
import Home from '../app/page';

// Mock the useRouter hook
jest.mock('next/navigation', () => ({
  useRouter: () => ({
    push: jest.fn(),
  }),
}));

describe('Home page', () => {
  it('renders the loading text', () => {
    render(<Home />);
    const loadingText = screen.getByText(/Loading Ethic Companion.../i);
    expect(loadingText).toBeInTheDocument();
  });
});
