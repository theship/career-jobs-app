/**
 * Job Detail Page
 * Clean separation of concerns with hooks and components
 */

'use client'

import { useState, useEffect } from 'react'
import { useParams, useRouter } from 'next/navigation'
import Link from 'next/link'
import { createClient } from '@/lib/supabase'
import { useJobDetail } from '@/hooks/useJobDetail'
import { usePitchGeneration } from '@/hooks/usePitchGeneration'
import JobInfo from '@/components/JobDetail/JobInfo'
import MatchScore from '@/components/JobDetail/MatchScore'
import PitchGenerator from '@/components/JobDetail/PitchGenerator'

export default function JobDetailPage() {
  const params = useParams()
  const router = useRouter()
  const [user, setUser] = useState<any>(null)
  const supabase = createClient()
  const jobId = params.id as string

  // Use custom hooks for data fetching and actions
  const { job, score, loading, error } = useJobDetail(jobId, user?.id)
  const { 
    pitch, 
    generating,
    error: pitchError,
    generatePitch, 
    copyToClipboard, 
    regenerate 
  } = usePitchGeneration(jobId)

  useEffect(() => {
    checkAuth()
  }, [])

  const checkAuth = async () => {
    const { data: { user } } = await supabase.auth.getUser()
    setUser(user)
  }

  const handleSignOut = async () => {
    await supabase.auth.signOut()
    router.push('/')
  }

  if (loading) {
    return <LoadingState />
  }

  if (error || !job) {
    return <ErrorState message={error || 'Job not found'} />
  }

  return (
    <div className="min-h-screen bg-background">
      <Navigation 
        user={user} 
        onSignOut={handleSignOut}
      />

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <BackButton />

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Job Details - Main Content */}
          <div className="lg:col-span-2">
            <JobInfo job={job} />
          </div>

          {/* Sidebar */}
          <div className="lg:col-span-1">
            {score && <MatchScore score={score} />}
            
            <PitchGenerator
              pitch={pitch}
              generating={generating}
              error={pitchError}
              onGenerate={generatePitch}
              onCopyToClipboard={copyToClipboard}
              onRegenerate={regenerate}
              isAuthenticated={!!user}
            />

            <ApplyButton jobUrl={job.job_url} />
          </div>
        </div>
      </main>
    </div>
  )
}

// Sub-components for better organization
function LoadingState() {
  return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="spinner"></div>
    </div>
  )
}

function ErrorState({ message }: { message: string }) {
  return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="text-center">
        <h2 className="text-2xl font-bold text-text-primary">{message}</h2>
        <Link href="/jobs" className="mt-4 text-accent-red hover:text-accent-red-light transition-colors">
          ← Back to jobs
        </Link>
      </div>
    </div>
  )
}

function Navigation({ user, onSignOut }: { user: any; onSignOut: () => void }) {
  return (
    <nav className="border-b border-border bg-surface/50 backdrop-blur-lg sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between h-16">
          <div className="flex items-center">
            <Link href="/" className="text-xl font-bold text-gradient-red">
              Career Jobs App
            </Link>
          </div>
          <div className="flex items-center space-x-4">
            {user ? (
              <>
                <Link href="/dashboard" className="nav-link">Dashboard</Link>
                <Link href="/jobs" className="nav-link">Browse Jobs</Link>
                <button onClick={onSignOut} className="btn-ghost text-sm">
                  Sign Out
                </button>
              </>
            ) : (
              <>
                <Link href="/login" className="nav-link">Sign In</Link>
                <Link href="/register" className="btn-primary text-sm">
                  Get Started
                </Link>
              </>
            )}
          </div>
        </div>
      </div>
    </nav>
  )
}

function BackButton() {
  return (
    <Link href="/jobs" className="text-accent-red hover:text-accent-red-light mb-4 inline-block transition-colors">
      ← Back to jobs
    </Link>
  )
}

function ApplyButton({ jobUrl }: { jobUrl?: string }) {
  if (!jobUrl) return null

  return (
    <div className="card mt-6">
      <a
        href={jobUrl}
        target="_blank"
        rel="noopener noreferrer"
        className="block w-full text-center bg-green-600/90 hover:bg-green-600 text-white py-3 px-4 rounded-lg font-medium transition-all"
      >
        Apply on Company Site
      </a>
    </div>
  )
}