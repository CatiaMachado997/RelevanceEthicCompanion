import { render, screen } from '@testing-library/react';
import Home from '../app/page';

// Mock the useRouter hook
jest.mock('next/navigation', () => ({
  useRouter: () => ({
    push: jest.fn(),
  }),
}));

describe('Home page', () => {
  it('renders the landing wordmark, tagline, and sign-in link', () => {
    render(<Home />);
    // Wordmark — currently rendered as a <span> next to the logo.
    // Drop the selector qualifier so the test survives a wrapper
    // change (h1 → span → p) as long as the literal text is present.
    expect(screen.getByText(/^Ethic Companion$/i)).toBeInTheDocument();
    expect(
      screen.getByText(/respects your boundaries/i)
    ).toBeInTheDocument();
    const signIn = screen.getByRole('link', { name: /sign in/i });
    expect(signIn).toHaveAttribute('href', '/login');
  });
});
