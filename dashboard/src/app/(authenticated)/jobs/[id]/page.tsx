/**
 * Job Detail Page
 * Clean separation of concerns with hooks and components
 */

'use client'

import { useState, useEffect } from 'react'
import { useParams, useRouter } from 'next/navigation'
import Link from 'next/link'
import { BookmarkIcon } from '@heroicons/react/24/outline'
import { BookmarkIcon as BookmarkSolidIcon } from '@heroicons/react/24/solid'
import { createClient } from '@/lib/supabase'
import { useJobDetail } from '@/hooks/useJobDetail'
import { usePitchGeneration } from '@/hooks/usePitchGeneration'
import { savedJobsService } from '@/services'
import { useNotification } from '@/contexts/NotificationContext'
import JobInfo from '@/components/JobDetail/JobInfo'
import MatchScore from '@/components/JobDetail/MatchScore'
import PitchGenerator from '@/components/JobDetail/PitchGenerator'

export default function JobDetailPage() {
  const params = useParams()
  const router = useRouter()
  const [user, setUser] = useState<any>(null)
  const [isSaved, setIsSaved] = useState(false)
  const [savingJob, setSavingJob] = useState(false)
  const supabase = createClient()
  const jobId = params.id as string
  const { showSuccess, showError } = useNotification()

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
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    if (user && jobId) {
      checkSavedStatus()
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user, jobId])

  const checkAuth = async () => {
    const { data: { user } } = await supabase.auth.getUser()
    setUser(user)
  }

  const checkSavedStatus = async () => {
    try {
      const response = await savedJobsService.checkIfSaved(jobId)
      setIsSaved(response.is_saved)
    } catch (error) {
      console.error('Failed to check saved status:', error)
    }
  }

  const handleToggleSave = async () => {
    if (savingJob) return

    setSavingJob(true)
    try {
      const result = await savedJobsService.toggleSaveJob(jobId)
      setIsSaved(result.saved)

      if (result.saved) {
        showSuccess(`Saved "${job?.title}" to your saved jobs`)
      } else {
        showSuccess(`Removed "${job?.title}" from saved jobs`)
      }
    } catch (error) {
      console.error('Failed to toggle save job:', error)
      showError('Failed to save job. Please try again.')
    } finally {
      setSavingJob(false)
    }
  }

  const handleSignOut = async () => {
    const { clearAllSensitiveData } = await import('@/lib/clear-sensitive-data')
    clearAllSensitiveData()
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
          {/* Main Content Area */}
          <div className="lg:col-span-2 space-y-8">
            <JobInfo job={job} />
            
            {/* Pitch Generator in main content */}
            <PitchGenerator
              pitch={pitch}
              generating={generating}
              error={pitchError}
              onGenerate={generatePitch}
              onCopyToClipboard={copyToClipboard}
              onRegenerate={regenerate}
              isAuthenticated={!!user}
            />
          </div>

          {/* Sidebar */}
          <div className="lg:col-span-1">
            {score && <MatchScore score={score} />}
            <ApplyButton jobUrl={job.job_url} />
            <SaveJobButton
              isSaved={isSaved}
              savingJob={savingJob}
              onToggleSave={handleToggleSave}
            />
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

  // Ensure the URL has a protocol
  const validUrl = jobUrl.startsWith('http://') || jobUrl.startsWith('https://')
    ? jobUrl
    : `https://${jobUrl}`

  return (
    <div className="card mt-6">
      <a
        href={validUrl}
        target="_blank"
        rel="noopener noreferrer"
        className="block w-full text-center bg-green-600/90 hover:bg-green-600 text-white py-3 px-4 rounded-lg font-medium transition-all"
      >
        Apply on Company Site
      </a>
    </div>
  )
}

function SaveJobButton({
  isSaved,
  savingJob,
  onToggleSave
}: {
  isSaved: boolean;
  savingJob: boolean;
  onToggleSave: () => void
}) {
  return (
    <div className="card mt-4">
      <button
        onClick={onToggleSave}
        disabled={savingJob}
        className={`w-full flex items-center justify-center gap-2 py-3 px-4 rounded-lg font-medium transition-all ${
          isSaved
            ? 'bg-gray-100 hover:bg-gray-200 text-gray-700'
            : 'bg-blue-600/90 hover:bg-blue-600 text-white'
        } disabled:opacity-50`}
      >
        {isSaved ? (
          <>
            <BookmarkSolidIcon className="w-5 h-5" />
            <span>Saved to Jobs</span>
          </>
        ) : (
          <>
            <BookmarkIcon className="w-5 h-5" />
            <span>Save Job</span>
          </>
        )}
      </button>
    </div>
  )
}