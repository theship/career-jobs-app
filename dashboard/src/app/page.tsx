'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { createClient } from '@/lib/supabase'
import Link from 'next/link'

export default function Home() {
  const [user, setUser] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const router = useRouter()
  const supabase = createClient()

  useEffect(() => {
    const checkUser = async () => {
      const { data: { user } } = await supabase.auth.getUser()
      setUser(user)
      setLoading(false)
    }
    checkUser()
  }, [])

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <div className="spinner"></div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-background">
      {/* Navigation */}
      <nav className="border-b border-border bg-surface/50 backdrop-blur-lg sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between h-16">
            <div className="flex items-center">
              <h1 className="text-xl font-bold text-gradient-red">Career Jobs App</h1>
            </div>
            <div className="flex items-center space-x-6">
              {user ? (
                <>
                  <Link href="/dashboard" className="nav-link">
                    Dashboard
                  </Link>
                  <Link href="/jobs" className="nav-link">
                    Browse Jobs
                  </Link>
                  <Link href="/profile" className="nav-link">
                    Profile
                  </Link>
                  <button
                    onClick={async () => {
                      await supabase.auth.signOut()
                      router.refresh()
                    }}
                    className="btn-ghost text-sm"
                  >
                    Sign Out
                  </button>
                </>
              ) : (
                <>
                  <Link href="/login" className="nav-link">
                    Sign In
                  </Link>
                  <Link href="/register" className="btn-primary text-sm">
                    Get Started
                  </Link>
                </>
              )}
            </div>
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="relative section-spacing overflow-hidden">
        {/* Background gradient mesh */}
        <div className="absolute inset-0 bg-gradient-radial-dark opacity-50"></div>
        <div className="absolute inset-0 bg-gradient-red-subtle"></div>
        
        <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <h1 className="text-5xl md:text-6xl lg:text-7xl font-light mb-6">
            <span className="text-gradient">Find Your Perfect</span>
            <br />
            <span className="text-gradient-red font-medium">Job Match</span>
          </h1>
          
          <p className="text-xl text-text-secondary max-w-3xl mx-auto mb-12 leading-relaxed">
            AI-powered job matching, personalized pitches, and smart application tracking 
            designed to accelerate your career journey.
          </p>

          {user ? (
            <div className="space-y-4">
              <Link href="/dashboard" className="btn-primary inline-block text-lg">
                Go to Dashboard
              </Link>
            </div>
          ) : (
            <div className="flex gap-4 justify-center">
              <Link href="/register" className="btn-primary inline-block text-lg">
                Start Free Trial
              </Link>
              <Link href="/login" className="btn-secondary inline-block text-lg">
                Sign In
              </Link>
            </div>
          )}

          {/* Stats */}
          <div className="grid grid-cols-3 gap-8 max-w-2xl mx-auto mt-16">
            <div>
              <div className="text-3xl font-light text-accent-red mb-1">10k+</div>
              <div className="text-text-secondary text-sm">Active Jobs</div>
            </div>
            <div>
              <div className="text-3xl font-light text-accent-red mb-1">95%</div>
              <div className="text-text-secondary text-sm">Match Accuracy</div>
            </div>
            <div>
              <div className="text-3xl font-light text-accent-red mb-1">3x</div>
              <div className="text-text-secondary text-sm">Faster Applications</div>
            </div>
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section className="section-spacing border-t border-border">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-16">
            <h2 className="text-4xl font-light text-text-primary mb-4">
              Everything You Need to <span className="text-gradient-red">Succeed</span>
            </h2>
            <p className="text-text-secondary text-lg max-w-2xl mx-auto">
              Our AI-powered platform provides comprehensive tools for your job search journey
            </p>
          </div>

          <div className="grid md:grid-cols-3 gap-8">
            <div className="card group">
              <div className="text-accent-red mb-4 text-2xl">📄</div>
              <h3 className="text-xl font-medium text-text-primary mb-3 group-hover:text-gradient-red transition-all">
                Smart Resume Parsing
              </h3>
              <p className="text-text-secondary leading-relaxed">
                Upload your resume and let our AI extract and analyze your skills, 
                experience, and achievements for optimal job matching.
              </p>
            </div>

            <div className="card group">
              <div className="text-accent-red mb-4 text-2xl">🎯</div>
              <h3 className="text-xl font-medium text-text-primary mb-3 group-hover:text-gradient-red transition-all">
                AI Job Matching
              </h3>
              <p className="text-text-secondary leading-relaxed">
                Get personalized job recommendations based on your skills, experience, 
                and career goals with our advanced matching algorithm.
              </p>
            </div>

            <div className="card group">
              <div className="text-accent-red mb-4 text-2xl">✨</div>
              <h3 className="text-xl font-medium text-text-primary mb-3 group-hover:text-gradient-red transition-all">
                Personalized Pitches
              </h3>
              <p className="text-text-secondary leading-relaxed">
                Generate compelling, tailored pitches for each application using 
                AI-powered insights and company research.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="section-spacing border-t border-border">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <h2 className="text-4xl font-light text-text-primary mb-4">
            Ready to Transform Your <span className="text-gradient-red">Career</span>?
          </h2>
          <p className="text-text-secondary text-lg mb-8">
            Join thousands of professionals who've accelerated their job search with AI
          </p>
          {!user && (
            <Link href="/register" className="btn-primary inline-block text-lg">
              Get Started for Free
            </Link>
          )}
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-border py-8">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <p className="text-text-muted text-sm">
            © {new Date().getFullYear()} Career Jobs App. All rights reserved.
          </p>
        </div>
      </footer>
    </div>
  )
}