'use client'

import { useState, useEffect } from 'react'
import { useParams, useRouter } from 'next/navigation'
import Link from 'next/link'
import { createClient } from '@/lib/supabase'
import { api } from '@/lib/api-client'
import { useNotification } from '@/contexts/NotificationContext'

export default function JobDetailPage() {
  const params = useParams()
  const router = useRouter()
  const [user, setUser] = useState<any>(null)
  const [job, setJob] = useState<any>(null)
  const [score, setScore] = useState<any>(null)
  const [pitch, setPitch] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [generatingPitch, setGeneratingPitch] = useState(false)
  const supabase = createClient()
  const jobId = params.id as string
  const { showSuccess, showError, showInfo } = useNotification()

  useEffect(() => {
    checkAuth()
    fetchJobDetails()
  }, [jobId])

  const checkAuth = async () => {
    const { data: { user } } = await supabase.auth.getUser()
    setUser(user)
  }

  const fetchJobDetails = async () => {
    setLoading(true)
    try {
      // Fetch job details
      const jobData = await api.getJobById(jobId)
      setJob(jobData)

      // If user is logged in, try to get their score for this job
      if (user) {
        try {
          const resumes = await api.getResumes()
          if (resumes && resumes.length > 0) {
            const scores = await api.getScores(resumes[0].resume_id)
            const jobScore = scores.find((s: any) => s.job_id === jobId)
            setScore(jobScore)
          }
        } catch (error) {
          console.error('Error fetching score:', error)
        }
      }
    } catch (error) {
      console.error('Error fetching job details:', error)
    } finally {
      setLoading(false)
    }
  }

  const generatePitch = async () => {
    if (!user) {
      router.push('/login')
      return
    }

    setGeneratingPitch(true)
    try {
      // Get user's resume
      const resumes = await api.getResumes()
      if (!resumes || resumes.length === 0) {
        showInfo('Please upload a resume first to generate a pitch')
        router.push('/dashboard')
        return
      }

      // Use the API client to generate pitch - it handles auth automatically
      const pitchData = await api.generatePitch(
        resumes[0].resume_id,
        jobId,
        true // include_research
      )
      
      setPitch(pitchData)
      showSuccess('Pitch generated successfully!')
    } catch (error: any) {
      console.error('Error generating pitch:', error)
      showError(error.message || 'Failed to generate pitch. Please try again.')
    } finally {
      setGeneratingPitch(false)
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="spinner"></div>
      </div>
    )
  }

  if (!job) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <h2 className="text-2xl font-bold text-text-primary">Job not found</h2>
          <Link href="/jobs" className="mt-4 text-accent-red hover:text-accent-red-light transition-colors">
            ← Back to jobs
          </Link>
        </div>
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
              <Link href="/" className="text-xl font-bold text-gradient-red">
                Career Jobs App
              </Link>
            </div>
            <div className="flex items-center space-x-4">
              {user ? (
                <>
                  <Link href="/dashboard" className="nav-link">
                    Dashboard
                  </Link>
                  <Link href="/jobs" className="nav-link">
                    Browse Jobs
                  </Link>
                  <button
                    onClick={async () => {
                      await supabase.auth.signOut()
                      router.push('/')
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
                  <Link 
                    href="/register" 
                    className="btn-primary text-sm"
                  >
                    Get Started
                  </Link>
                </>
              )}
            </div>
          </div>
        </div>
      </nav>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <Link href="/jobs" className="text-accent-red hover:text-accent-red-light mb-4 inline-block transition-colors">
          ← Back to jobs
        </Link>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Job Details */}
          <div className="lg:col-span-2">
            <div className="card">
              <h1 className="text-3xl font-bold text-text-primary">{job.title}</h1>
              <p className="text-xl text-text-secondary mt-2">{job.company_name}</p>
              <p className="text-text-muted mt-1">{job.location}</p>

              <div className="flex gap-2 mt-4">
                {job.seniority && (
                  <span className="px-3 py-1 bg-blue-900/20 text-blue-400 text-sm rounded border border-blue-400/20">
                    {job.seniority}
                  </span>
                )}
                {job.remote_type && (
                  <span className="px-3 py-1 bg-green-100 text-green-700 text-sm rounded">
                    {job.remote_type}
                  </span>
                )}
                {job.employment_type && (
                  <span className="px-3 py-1 bg-purple-100 text-purple-700 text-sm rounded">
                    {job.employment_type}
                  </span>
                )}
              </div>

              {job.description && (
                <div className="mt-6">
                  <h2 className="text-lg font-semibold mb-2">Description</h2>
                  <p className="text-text-secondary whitespace-pre-wrap">{job.description}</p>
                </div>
              )}

              {job.responsibilities && job.responsibilities.length > 0 && (
                <div className="mt-6">
                  <h2 className="text-lg font-semibold mb-2">Responsibilities</h2>
                  <ul className="list-disc list-inside space-y-1">
                    {job.responsibilities.map((resp: string, idx: number) => (
                      <li key={idx} className="text-text-secondary">{resp}</li>
                    ))}
                  </ul>
                </div>
              )}

              {job.requirements && job.requirements.length > 0 && (
                <div className="mt-6">
                  <h2 className="text-lg font-semibold mb-2">Requirements</h2>
                  <ul className="list-disc list-inside space-y-1">
                    {job.requirements.map((req: string, idx: number) => (
                      <li key={idx} className="text-text-secondary">{req}</li>
                    ))}
                  </ul>
                </div>
              )}

              {job.benefits && job.benefits.length > 0 && (
                <div className="mt-6">
                  <h2 className="text-lg font-semibold mb-2">Benefits</h2>
                  <ul className="list-disc list-inside space-y-1">
                    {job.benefits.map((benefit: string, idx: number) => (
                      <li key={idx} className="text-text-secondary">{benefit}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </div>

          {/* Sidebar */}
          <div className="lg:col-span-1">
            {/* Match Score */}
            {score && (
              <div className="card mb-6">
                <h2 className="text-lg font-semibold mb-4">Your Match Score</h2>
                <div className="text-center">
                  <div className="text-4xl font-bold text-accent-red">
                    {Math.round(score.overall_score * 100)}%
                  </div>
                  <p className="text-text-secondary mt-2">Overall Match</p>
                </div>
                <div className="mt-4 space-y-2">
                  <div className="flex justify-between">
                    <span className="text-text-secondary">Skills Match:</span>
                    <span className="font-medium">{Math.round(score.skills_score * 100)}%</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-text-secondary">Experience Match:</span>
                    <span className="font-medium">{Math.round(score.experience_score * 100)}%</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-text-secondary">Location Match:</span>
                    <span className="font-medium">{Math.round(score.location_score * 100)}%</span>
                  </div>
                </div>
              </div>
            )}

            {/* AI Pitch Generator */}
            <div className="card">
              <h2 className="text-lg font-semibold mb-4">AI Application Assistant</h2>
              
              {!pitch ? (
                <div>
                  <p className="text-text-secondary text-sm mb-4">
                    Generate a personalized pitch for this position using AI
                  </p>
                  <button
                    onClick={generatePitch}
                    disabled={generatingPitch || !user}
                    className="w-full btn-primary disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {generatingPitch ? 'Generating...' : user ? 'Generate AI Pitch' : 'Sign in to Generate Pitch'}
                  </button>
                </div>
              ) : (
                <div className="space-y-4">
                  <div>
                    <h3 className="font-medium mb-1">Headline</h3>
                    <p className="text-sm text-text-secondary">{pitch.headline}</p>
                  </div>

                  <div>
                    <h3 className="font-medium mb-1">Opening</h3>
                    <p className="text-sm text-text-secondary">{pitch.opening}</p>
                  </div>

                  <div>
                    <h3 className="font-medium mb-1">Key Points</h3>
                    <ul className="list-disc list-inside text-sm text-text-secondary space-y-1">
                      {pitch.bullet_points?.map((point: string, idx: number) => (
                        <li key={idx}>{point}</li>
                      ))}
                    </ul>
                  </div>

                  <button
                    onClick={() => {
                      // Copy pitch to clipboard
                      const text = `${pitch.headline}\n\n${pitch.opening}\n\n${pitch.bullet_points?.join('\n• ')}\n\n${pitch.closing_statement}`
                      navigator.clipboard.writeText(text)
                      showSuccess('Pitch copied to clipboard!')
                    }}
                    className="w-full bg-green-600/90 hover:bg-green-600 text-white py-2 px-4 rounded-lg text-sm transition-all"
                  >
                    Copy to Clipboard
                  </button>

                  <button
                    onClick={generatePitch}
                    className="w-full btn-secondary text-sm"
                  >
                    Regenerate Pitch
                  </button>
                </div>
              )}
            </div>

            {/* Apply Button */}
            <div className="card mt-6">
              <a
                href={job.job_url}
                target="_blank"
                rel="noopener noreferrer"
                className="block w-full text-center bg-green-600/90 hover:bg-green-600 text-white py-3 px-4 rounded-lg font-medium transition-all"
              >
                Apply on Company Site
              </a>
            </div>
          </div>
        </div>
      </main>
    </div>
  )
}