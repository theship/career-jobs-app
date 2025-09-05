'use client'

import { useEffect, useState } from 'react'
import { useRouter, usePathname } from 'next/navigation'
import Link from 'next/link'
import { createClient } from '@/lib/supabase'

export default function AuthenticatedLayout({
  children,
}: {
  children: React.ReactNode
}) {
  const [user, setUser] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const router = useRouter()
  const pathname = usePathname()
  const supabase = createClient()

  useEffect(() => {
    checkAuth()
  }, [])

  const checkAuth = async () => {
    const { data: { user } } = await supabase.auth.getUser()
    if (!user) {
      router.push('/login')
    } else {
      setUser(user)
    }
    setLoading(false)
  }

  const handleSignOut = async () => {
    const { clearAllSensitiveData } = await import('@/lib/clear-sensitive-data')
    clearAllSensitiveData()
    await supabase.auth.signOut()
    router.push('/')
  }

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <div className="spinner"></div>
      </div>
    )
  }

  if (!user) {
    return null // Will redirect to login
  }

  const isActive = (path: string) => pathname === path

  return (
    <div className="min-h-screen bg-background">
      {/* Global Navigation */}
      <nav className="border-b border-border bg-surface/50 backdrop-blur-lg sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between h-16">
            <div className="flex items-center">
              <Link href="/dashboard" className="text-xl font-bold text-gradient-red">
                Career Jobs App
              </Link>
            </div>
            <div className="flex items-center space-x-6">
              <Link 
                href="/dashboard" 
                className={`nav-link ${isActive('/dashboard') ? 'text-accent-red' : ''}`}
              >
                Dashboard
              </Link>
              <Link 
                href="/jobs" 
                className={`nav-link ${isActive('/jobs') || pathname.startsWith('/jobs/') ? 'text-accent-red' : ''}`}
              >
                Browse Jobs
              </Link>
              <Link 
                href="/matches" 
                className={`nav-link ${isActive('/matches') ? 'text-accent-red' : ''}`}
              >
                Gen Matches
              </Link>
              <Link 
                href="/profile" 
                className={`nav-link ${isActive('/profile') ? 'text-accent-red' : ''}`}
              >
                Profile
              </Link>
              <button
                onClick={handleSignOut}
                className="btn-ghost text-sm"
              >
                Sign Out
              </button>
            </div>
          </div>
        </div>
      </nav>

      {/* Page Content */}
      {children}
    </div>
  )
}