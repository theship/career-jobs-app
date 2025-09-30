'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { BookmarkSlashIcon, ArrowDownTrayIcon } from '@heroicons/react/24/outline'
import { createClient } from '@/lib/supabase'
import { savedJobsService } from '@/services'
import { useNotification } from '@/contexts/NotificationContext'

interface SavedJob {
  id: string
  job_id: string
  saved_at: string
  notes?: string
  job_postings?: {
    job_id: string
    title: string
    company_name: string
    location: string
    department?: string
    posted_at?: string
    job_url: string
  }
}

export default function SavedJobsPage() {
  const router = useRouter()
  const [user, setUser] = useState<any>(null)
  const [savedJobs, setSavedJobs] = useState<SavedJob[]>([])
  const [loading, setLoading] = useState(true)
  const [removingJobs, setRemovingJobs] = useState<Set<string>>(new Set())
  const supabase = createClient()
  const { showSuccess, showError } = useNotification()

  useEffect(() => {
    checkUser()
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const checkUser = async () => {
    const { data: { user } } = await supabase.auth.getUser()
    if (!user) {
      router.push('/login')
      return
    }
    setUser(user)
    await fetchSavedJobs()
  }

  const fetchSavedJobs = async () => {
    setLoading(true)
    try {
      const jobs = await savedJobsService.getSavedJobs(true)
      setSavedJobs(jobs)
    } catch (error) {
      console.error('Failed to fetch saved jobs:', error)
      showError('Failed to load saved jobs')
    } finally {
      setLoading(false)
    }
  }

  const handleRemoveJob = async (jobId: string, jobTitle: string) => {
    if (removingJobs.has(jobId)) return

    setRemovingJobs(prev => new Set(prev).add(jobId))

    try {
      await savedJobsService.unsaveJob(jobId)
      setSavedJobs(prev => prev.filter(sj => sj.job_id !== jobId))
      showSuccess(`Removed "${jobTitle}" from saved jobs`)
    } catch (error) {
      console.error('Failed to remove saved job:', error)
      showError('Failed to remove job')
    } finally {
      setRemovingJobs(prev => {
        const newSet = new Set(prev)
        newSet.delete(jobId)
        return newSet
      })
    }
  }

  const formatDate = (dateString: string) => {
    if (!dateString) return 'Unknown'
    const date = new Date(dateString)
    if (isNaN(date.getTime())) return 'Unknown'
    const days = Math.floor((Date.now() - date.getTime()) / (1000 * 60 * 60 * 24))
    if (days === 0) return 'Today'
    if (days === 1) return 'Yesterday'
    if (days < 7) return `${days} days ago`
    return date.toLocaleDateString()
  }

  const exportSavedJobs = () => {
    const csvContent = [
      ['Company', 'Position', 'Location', 'Department', 'Posted', 'Saved On', 'Job URL'].join(','),
      ...savedJobs.map(sj => {
        const job = sj.job_postings
        if (!job) return ''
        return [
          `"${job.company_name}"`,
          `"${job.title}"`,
          `"${job.location || ''}"`,
          `"${job.department || ''}"`,
          formatDate(job.posted_at || ''),
          new Date(sj.saved_at).toLocaleDateString(),
          job.job_url
        ].join(',')
      })
    ].join('\n')

    const blob = new Blob([csvContent], { type: 'text/csv' })
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `saved_jobs_${new Date().toISOString().split('T')[0]}.csv`
    document.body.appendChild(a)
    a.click()
    window.URL.revokeObjectURL(url)
    document.body.removeChild(a)
  }

  if (!user) {
    return <div className="p-8">Loading...</div>
  }

  return (
    <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Header */}
      <div className="card mb-6">
        <div className="flex justify-between items-start mb-4">
          <div>
            <h1 className="text-3xl font-light text-text-primary mb-2">Saved Jobs</h1>
            <p className="text-text-secondary">
              Jobs you've bookmarked for later review
            </p>
          </div>
          {savedJobs.length > 0 && (
            <button
              onClick={exportSavedJobs}
              className="flex items-center gap-2 px-4 py-2 btn-ghost"
            >
              <ArrowDownTrayIcon className="w-5 h-5" />
              Export CSV
            </button>
          )}
        </div>
      </div>

      {/* Jobs List */}
      <div className="card">
        {loading ? (
          <div className="p-8 text-center">
            <div className="animate-pulse">Loading saved jobs...</div>
          </div>
        ) : savedJobs.length === 0 ? (
          <div className="p-8 text-center">
            <BookmarkSlashIcon className="w-12 h-12 mx-auto mb-4 text-text-tertiary" />
            <p className="text-text-secondary mb-4">
              You haven't saved any jobs yet
            </p>
            <div className="flex gap-4 justify-center">
              <Link href="/jobs" className="btn-primary">
                Browse Jobs
              </Link>
              <Link href="/matches" className="btn-ghost">
                View Matches
              </Link>
            </div>
          </div>
        ) : (
          <div className="divide-y divide-border">
            {savedJobs.map(savedJob => {
              const job = savedJob.job_postings
              if (!job) return null

              return (
                <div
                  key={savedJob.id}
                  className="p-6 hover:bg-surface/50 transition-colors"
                >
                  <div className="flex justify-between items-start">
                    <div className="flex-1">
                      <Link
                        href={`/jobs/${job.job_id}`}
                        className="text-lg font-medium text-text-primary hover:text-accent-red transition-colors"
                      >
                        {job.title}
                      </Link>
                      <p className="text-text-secondary mt-1">
                        {job.company_name} • {job.location}
                      </p>
                      {job.department && (
                        <p className="text-sm text-text-tertiary mt-1">
                          {job.department}
                        </p>
                      )}
                      <div className="flex gap-4 mt-2 text-sm text-text-tertiary">
                        <span>Posted {formatDate(job.posted_at || '')}</span>
                        <span>•</span>
                        <span>Saved {formatDate(savedJob.saved_at)}</span>
                      </div>
                      {savedJob.notes && (
                        <p className="mt-3 text-sm text-text-secondary italic">
                          Note: {savedJob.notes}
                        </p>
                      )}
                    </div>
                    <div className="flex items-center gap-2 ml-4">
                      <Link
                        href={`/jobs/${job.job_id}`}
                        className="btn-ghost text-sm"
                      >
                        View Details
                      </Link>
                      <button
                        onClick={() => handleRemoveJob(job.job_id, job.title)}
                        disabled={removingJobs.has(job.job_id)}
                        className="btn-ghost text-sm text-red-600 hover:text-red-700 disabled:opacity-50"
                      >
                        Remove
                      </button>
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>
    </main>
  )
}