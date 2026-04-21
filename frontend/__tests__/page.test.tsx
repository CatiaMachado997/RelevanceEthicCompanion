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
    // Wordmark appears; match the uppercase version to disambiguate from
    // the prose mention.
    expect(
      screen.getByText(/^Ethic Companion$/i, { selector: 'p' })
    ).toBeInTheDocument();
    expect(
      screen.getByText(/respects your boundaries/i)
    ).toBeInTheDocument();
    const signIn = screen.getByRole('link', { name: /sign in/i });
    expect(signIn).toHaveAttribute('href', '/login');
  });
});
