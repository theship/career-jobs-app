'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { createClient } from '@/lib/supabase'
import { useNotification } from '@/contexts/NotificationContext'

export default function RegisterPage() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const router = useRouter()
  const supabase = createClient()
  const { showSuccess, showInfo } = useNotification()

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)

    if (password !== confirmPassword) {
      setError('Passwords do not match')
      return
    }

    if (password.length < 6) {
      setError('Password must be at least 6 characters')
      return
    }

    setLoading(true)

    try {
      const { error } = await supabase.auth.signUp({
        email,
        password,
      })

      if (error) {
        setError(error.message)
      } else {
        // Show success message
        showSuccess('Registration successful! Please check your email to verify your account.')
        setTimeout(() => router.push('/login'), 2000)
      }
    } catch {
      setError('An unexpected error occurred')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-background flex items-center justify-center px-4">
      <div className="absolute inset-0 bg-gradient-radial-dark opacity-50"></div>
      <div className="relative max-w-md w-full space-y-8">
        <div className="card">
          <div className="text-center mb-8">
            <Link href="/" className="text-2xl font-bold text-gradient-red inline-block mb-4">
              Career Jobs App
            </Link>
            <h2 className="text-3xl font-light text-text-primary">Create your account</h2>
            <p className="mt-2 text-sm text-text-secondary">
              Already have an account?{' '}
              <Link href="/login" className="text-accent-red hover:text-accent-red-light transition-colors">
                Sign in
              </Link>
            </p>
          </div>

          <form className="space-y-6" onSubmit={handleRegister}>
            {error && (
              <div className="bg-red-900/20 border border-red-500/50 text-red-400 px-4 py-3 rounded-lg text-sm">
                {error}
              </div>
            )}

            <div className="space-y-4">
              <div>
                <label htmlFor="email" className="input-label">
                  Email address
                </label>
                <input
                  id="email"
                  name="email"
                  type="email"
                  autoComplete="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="input-dark w-full"
                  placeholder="you@example.com"
                />
              </div>

              <div>
                <label htmlFor="password" className="input-label">
                  Password
                </label>
                <input
                  id="password"
                  name="password"
                  type="password"
                  autoComplete="new-password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="input-dark w-full"
                  placeholder="••••••••"
                />
                <p className="mt-1 text-xs text-text-muted">
                  Must be at least 6 characters
                </p>
              </div>

              <div>
                <label htmlFor="confirm-password" className="input-label">
                  Confirm Password
                </label>
                <input
                  id="confirm-password"
                  name="confirm-password"
                  type="password"
                  autoComplete="new-password"
                  required
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  className="input-dark w-full"
                  placeholder="••••••••"
                />
              </div>
            </div>

            <div className="flex items-center">
              <input
                id="agree-terms"
                name="agree-terms"
                type="checkbox"
                required
                className="h-4 w-4 bg-background border-border rounded focus:ring-accent-red focus:ring-offset-0"
              />
              <label htmlFor="agree-terms" className="ml-2 block text-sm text-text-secondary">
                I agree to the{' '}
                <a href="#" className="text-accent-red hover:text-accent-red-light transition-colors">
                  Terms and Conditions
                </a>
              </label>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="btn-primary w-full disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? (
                <span className="flex items-center justify-center">
                  <svg className="animate-spin h-5 w-5 mr-2" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  Creating account...
                </span>
              ) : (
                'Sign up'
              )}
            </button>

            <div className="relative">
              <div className="absolute inset-0 flex items-center">
                <div className="w-full border-t border-border"></div>
              </div>
              <div className="relative flex justify-center text-sm">
                <span className="px-4 bg-surface text-text-muted">Or sign up with</span>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <button
                type="button"
                className="btn-secondary text-sm py-2"
                onClick={() => showInfo('Google sign-up coming soon!')}
              >
                Google
              </button>
              <button
                type="button"
                className="btn-secondary text-sm py-2"
                onClick={() => showInfo('GitHub sign-up coming soon!')}
              >
                GitHub
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  )
}
