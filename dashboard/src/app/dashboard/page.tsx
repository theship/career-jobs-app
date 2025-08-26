'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { createClient } from '@/lib/supabase'
import { apiClient } from '@/lib/api'
import Link from 'next/link'

export default function DashboardPage() {
  const [user, setUser] = useState<any>(null)
  const [resumes, setResumes] = useState<any[]>([])
  const [jobs, setJobs] = useState<any[]>([])
  const [scores, setScores] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [uploadingResume, setUploadingResume] = useState(false)
  const router = useRouter()
  const supabase = createClient()

  useEffect(() => {
    checkAuth()
    fetchData()
  }, [])

  const checkAuth = async () => {
    const { data: { user } } = await supabase.auth.getUser()
    if (!user) {
      router.push('/login')
    } else {
      setUser(user)
    }
  }

  const fetchData = async () => {
    try {
      // Fetch user's resumes
      const resumesData = await apiClient.getResumes()
      setResumes(resumesData)

      // Fetch recent jobs
      const jobsData = await apiClient.getJobs({ limit: 5 })
      setJobs(jobsData)

      // If user has resumes, fetch scores for the first one
      if (resumesData && resumesData.length > 0) {
        const scoresData = await apiClient.getScores(resumesData[0].resume_id)
        setScores(scoresData)
      }
    } catch (error) {
      console.error('Error fetching data:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleResumeUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    setUploadingResume(true)
    try {
      const result = await apiClient.uploadResume(file)
      console.log('Resume uploaded:', result)
      
      // Refresh resumes list
      await fetchData()
      
      // Trigger scoring for the new resume
      if (result.resume_id) {
        await apiClient.runScoring(result.resume_id)
        const scoresData = await apiClient.getScores(result.resume_id)
        setScores(scoresData)
      }
      
      alert('Resume uploaded and analyzed successfully!')
    } catch (error) {
      console.error('Error uploading resume:', error)
      alert('Failed to upload resume. Please try again.')
    } finally {
      setUploadingResume(false)
    }
  }

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
              <Link href="/" className="text-xl font-bold text-gradient-red">
                Career Jobs App
              </Link>
            </div>
            <div className="flex items-center space-x-6">
              <Link href="/jobs" className="nav-link">
                Browse Jobs
              </Link>
              <Link href="/profile" className="nav-link">
                Profile
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
            </div>
          </div>
        </div>
      </nav>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <h1 className="text-3xl font-light text-text-primary mb-8">Dashboard</h1>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Resume Upload Section */}
          <div className="lg:col-span-1">
            <div className="card">
              <h2 className="text-lg font-medium text-text-primary mb-4">Your Resume</h2>
              
              {resumes.length === 0 ? (
                <div className="text-center py-8">
                  <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                  </svg>
                  <p className="mt-2 text-sm text-text-secondary">No resume uploaded yet</p>
                  <label className="mt-4 inline-block cursor-pointer">
                    <span className="btn-primary px-4 py-2 rounded-md text-sm">
                      Upload Resume
                    </span>
                    <input
                      type="file"
                      className="hidden"
                      accept=".pdf,.doc,.docx"
                      onChange={handleResumeUpload}
                      disabled={uploadingResume}
                    />
                  </label>
                </div>
              ) : (
                <div>
                  {resumes.map((resume) => (
                    <div key={resume.resume_id} className="mb-4 p-3 border rounded-md">
                      <p className="font-medium">{resume.file_name || 'Resume'}</p>
                      <p className="text-sm text-text-secondary">
                        Uploaded: {new Date(resume.created_at).toLocaleDateString()}
                      </p>
                      <p className="text-sm text-text-secondary">
                        Skills: {resume.skills?.length || 0} identified
                      </p>
                    </div>
                  ))}
                  <label className="inline-block cursor-pointer mt-2">
                    <span className="text-accent-red hover:text-accent-red-light text-sm">
                      + Upload another resume
                    </span>
                    <input
                      type="file"
                      className="hidden"
                      accept=".pdf,.doc,.docx"
                      onChange={handleResumeUpload}
                      disabled={uploadingResume}
                    />
                  </label>
                </div>
              )}
              
              {uploadingResume && (
                <p className="text-sm text-text-secondary mt-2">Uploading and analyzing...</p>
              )}
            </div>

            {/* Quick Stats */}
            <div className="bg-white rounded-lg shadow p-6 mt-6">
              <h2 className="text-lg font-medium text-text-primary mb-4">Your Stats</h2>
              <div className="space-y-2">
                <div className="flex justify-between">
                  <span className="text-text-secondary">Jobs Matched:</span>
                  <span className="font-medium">{scores.length}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-text-secondary">Applications:</span>
                  <span className="font-medium">0</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-text-secondary">Interviews:</span>
                  <span className="font-medium">0</span>
                </div>
              </div>
            </div>
          </div>

          {/* Job Matches Section */}
          <div className="lg:col-span-2">
            <div className="card">
              <div className="flex justify-between items-center mb-4">
                <h2 className="text-lg font-semibold">Job Matches</h2>
                <Link href="/jobs" className="text-accent-red hover:text-accent-red-light text-sm">
                  View all jobs →
                </Link>
              </div>

              {scores.length > 0 ? (
                <div className="space-y-4">
                  {scores.map((score) => (
                    <div key={score.score_id} className="border rounded-lg p-4 hover:bg-gray-50">
                      <div className="flex justify-between items-start">
                        <div>
                          <h3 className="font-medium text-lg">{score.job_title}</h3>
                          <p className="text-text-secondary">{score.company_name}</p>
                          <p className="text-sm text-text-muted mt-1">{score.location}</p>
                          <div className="flex gap-2 mt-2">
                            <span className="px-2 py-1 bg-blue-100 text-blue-700 text-xs rounded">
                              {score.seniority || 'All levels'}
                            </span>
                            <span className="px-2 py-1 bg-green-100 text-green-700 text-xs rounded">
                              {score.remote_type || 'On-site'}
                            </span>
                          </div>
                        </div>
                        <div className="text-right">
                          <div className="text-2xl font-bold text-blue-600">
                            {Math.round((score.overall_score || 0) * 100)}%
                          </div>
                          <p className="text-xs text-text-muted">Match Score</p>
                          <Link
                            href={`/jobs/${score.job_id}`}
                            className="mt-2 inline-block text-accent-red hover:text-accent-red-light text-sm"
                          >
                            View Details →
                          </Link>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              ) : jobs.length > 0 ? (
                <div className="space-y-4">
                  <p className="text-sm text-text-secondary mb-4">
                    Upload a resume to see personalized job matches
                  </p>
                  {jobs.map((job) => (
                    <div key={job.job_id} className="border rounded-lg p-4 hover:bg-gray-50">
                      <h3 className="font-medium text-lg">{job.title}</h3>
                      <p className="text-text-secondary">{job.company_name}</p>
                      <p className="text-sm text-text-muted mt-1">{job.location}</p>
                      <Link
                        href={`/jobs/${job.job_id}`}
                        className="mt-2 inline-block text-accent-red hover:text-accent-red-light text-sm"
                      >
                        View Details →
                      </Link>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center py-8">
                  <p className="text-text-secondary">No jobs available yet</p>
                  <p className="text-sm text-text-muted mt-2">Check back later for new opportunities</p>
                </div>
              )}
            </div>
          </div>
        </div>
      </main>
    </div>
  )
}