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
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100">
      <nav className="bg-white shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between h-16">
            <div className="flex items-center">
              <h1 className="text-xl font-bold text-gray-900">Career Jobs App</h1>
            </div>
            <div className="flex items-center space-x-4">
              {user ? (
                <>
                  <Link href="/dashboard" className="text-gray-700 hover:text-blue-600">
                    Dashboard
                  </Link>
                  <Link href="/jobs" className="text-gray-700 hover:text-blue-600">
                    Browse Jobs
                  </Link>
                  <Link href="/profile" className="text-gray-700 hover:text-blue-600">
                    Profile
                  </Link>
                  <button
                    onClick={async () => {
                      await supabase.auth.signOut()
                      router.refresh()
                    }}
                    className="bg-gray-200 hover:bg-gray-300 px-4 py-2 rounded-md text-sm"
                  >
                    Sign Out
                  </button>
                </>
              ) : (
                <>
                  <Link href="/login" className="text-gray-700 hover:text-blue-600">
                    Sign In
                  </Link>
                  <Link 
                    href="/register" 
                    className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-md text-sm"
                  >
                    Get Started
                  </Link>
                </>
              )}
            </div>
          </div>
        </div>
      </nav>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        <div className="text-center">
          <h1 className="text-5xl font-bold text-gray-900 mb-4">
            Find Your Perfect Job Match
          </h1>
          <p className="text-xl text-gray-600 mb-8">
            AI-powered job matching, personalized pitches, and smart application tracking
          </p>

          {user ? (
            <div className="space-y-4">
              <Link
                href="/dashboard"
                className="inline-block bg-blue-600 hover:bg-blue-700 text-white font-semibold px-8 py-3 rounded-lg text-lg"
              >
                Go to Dashboard
              </Link>
            </div>
          ) : (
            <div className="space-x-4">
              <Link
                href="/register"
                className="inline-block bg-blue-600 hover:bg-blue-700 text-white font-semibold px-8 py-3 rounded-lg text-lg"
              >
                Start Free Trial
              </Link>
              <Link
                href="/login"
                className="inline-block bg-white hover:bg-gray-100 text-blue-600 font-semibold px-8 py-3 rounded-lg text-lg border border-blue-600"
              >
                Sign In
              </Link>
            </div>
          )}
        </div>

        <div className="mt-16 grid md:grid-cols-3 gap-8">
          <div className="bg-white p-6 rounded-lg shadow-md">
            <h3 className="text-xl font-semibold mb-2">📄 Smart Resume Parsing</h3>
            <p className="text-gray-600">
              Upload your resume and let our AI extract and analyze your skills, experience, and achievements.
            </p>
          </div>
          <div className="bg-white p-6 rounded-lg shadow-md">
            <h3 className="text-xl font-semibold mb-2">🎯 AI Job Matching</h3>
            <p className="text-gray-600">
              Get personalized job recommendations based on your skills, experience, and career goals.
            </p>
          </div>
          <div className="bg-white p-6 rounded-lg shadow-md">
            <h3 className="text-xl font-semibold mb-2">✨ Personalized Pitches</h3>
            <p className="text-gray-600">
              Generate compelling, tailored pitches for each application using AI-powered insights.
            </p>
          </div>
        </div>
      </main>
    </div>
  )
}