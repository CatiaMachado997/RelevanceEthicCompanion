'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/hooks/useAuth';
import { Shield } from 'lucide-react';

export default function LoginPage() {
  const [email, setEmail] = useState('');
  const router = useRouter();
  const { signIn, loading } = useAuth();
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email) return;

    setIsSubmitting(true);
    try {
      await signIn(email);
      router.push('/dashboard');
    } catch (error) {
      console.error('Login failed:', error);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-white p-4">
      <div className="w-full max-w-md rounded-2xl border border-[rgba(0,0,0,0.08)] bg-white shadow-[0_4px_24px_rgba(0,0,0,0.08)] p-8">
        {/* Logo */}
        <div className="flex flex-col items-center gap-4 mb-8">
          <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-[#000000]">
            <Shield className="h-6 w-6 text-white" />
          </div>
          <div className="text-center">
            <h1 className="text-2xl font-bold tracking-tight text-[#0a0a0a]">Welcome back</h1>
            <p className="text-sm text-[#6b6b6b] mt-1">
              Enter your email to sign in to your Ethic Companion
            </p>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-1.5">
            <label className="text-xs font-medium uppercase tracking-wide text-[#9e9e9e]">
              Email
            </label>
            <input
              type="email"
              placeholder="name@example.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              disabled={isSubmitting || loading}
              className="h-10 w-full rounded-xl border border-[rgba(0,0,0,0.12)] bg-white px-3 text-sm text-[#0a0a0a] placeholder:text-[#9e9e9e] focus:border-[#0a0a0a] focus:outline-none focus:ring-1 focus:ring-[#0a0a0a] disabled:opacity-50"
            />
          </div>

          <button
            type="submit"
            disabled={isSubmitting || loading}
            className="mt-2 h-10 w-full rounded-full bg-[#000000] text-white text-sm font-medium transition-opacity hover:opacity-80 disabled:opacity-50"
          >
            {isSubmitting || loading ? 'Signing in...' : 'Sign In'}
          </button>
        </form>
      </div>
    </div>
  );
}
