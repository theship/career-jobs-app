'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { createClient } from '@/lib/supabase'
import { api } from '@/lib/api-client'
import Link from 'next/link'
import { useNotification } from '@/contexts/NotificationContext'

export default function DashboardPage() {
  const [user, setUser] = useState<any>(null)
  const [resumes, setResumes] = useState<any[]>([])
  const [scores, setScores] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [uploadingResume, setUploadingResume] = useState(false)
  const [uploadSuccess, setUploadSuccess] = useState(false)
  const router = useRouter()
  const supabase = createClient()
  const { showSuccess, showError } = useNotification()

  useEffect(() => {
    checkAuth()
    fetchData()
  // eslint-disable-next-line react-hooks/exhaustive-deps
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
      // Fetch all data in parallel - don't block on any single request
      const [resumesResult] = await Promise.allSettled([
        api.getResumes().catch(err => {
          console.error('Failed to load resumes:', err)
          return []
        }),
        api.getJobs({ limit: 5 }).catch(err => {
          console.error('Failed to load jobs:', err) 
          return []
        })
      ])

      // Process results
      const resumesData = resumesResult.status === 'fulfilled' ? resumesResult.value : []
      
      setResumes(resumesData)
      
      // If user has resumes, fetch existing scores in background (non-blocking)
      if (resumesData && resumesData.length > 0) {
        api.getScores(resumesData[0].resume_id, 10)
          .then(scores => {
            // Dashboard scores loaded successfully
            if (scores && scores.length > 0) {
              setScores(scores)
            }
          })
          .catch(() => {
            // No scores yet, that's fine - don't block UI
          })
      }
    } catch (error) {
      console.error('Dashboard data fetch error:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleResumeUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    setUploadingResume(true)
    setUploadSuccess(false)
    
    try {
      const result = await api.uploadResume(file)
      // Resume uploaded successfully
      
      // Show success immediately
      setUploadSuccess(true)
      showSuccess('Resume uploaded successfully!')
      
      // Refresh resumes list
      await fetchData()
      
      // Don't auto-trigger scoring - let user do it from Matches page
      showSuccess('Resume ready! Go to Matches to generate job matches.', 'Next Step')
      
      // Clear success message after 5 seconds
      setTimeout(() => setUploadSuccess(false), 5000)
      
    } catch (error: any) {
      console.error('Error uploading resume:', error)
      setUploadSuccess(false)
      showError(error.message || 'Failed to upload resume. Please try again.')
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
                <div className="mt-4 p-3 bg-blue-50 border border-blue-200 rounded-md">
                  <p className="text-sm text-blue-700">Processing your resume...</p>
                </div>
              )}
              
              {uploadSuccess && !uploadingResume && (
                <div className="mt-4 p-3 bg-green-50 border border-green-200 rounded-md">
                  <p className="text-sm text-green-700 font-medium">✓ Success: Resume Uploaded</p>
                  <p className="text-xs text-green-600 mt-1">Your resume has been saved and processed.</p>
                </div>
              )}
            </div>

            {/* Quick Stats */}
            <div className="bg-white rounded-lg shadow p-6 mt-6">
              <h2 className="text-lg font-medium text-gray-900 mb-4">Your Stats</h2>
              <div className="space-y-2">
                <div className="flex justify-between">
                  <span className="text-gray-600">Jobs Matched:</span>
                  <span className="font-medium text-gray-900">{scores.length}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">Applications:</span>
                  <span className="font-medium text-gray-900">0</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">Interviews:</span>
                  <span className="font-medium text-gray-900">0</span>
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
                  {scores.map((score, index) => (
                    <div key={score.job_id || `score-${index}`} className="border border-border rounded-lg p-4 hover:bg-surface transition-colors">
                      <div className="flex justify-between items-start">
                        <div>
                          <h3 className="font-medium text-lg">{score.title || score.job_title}</h3>
                          <p className="text-text-secondary">{score.company_name}</p>
                          <p className="text-sm text-text-muted mt-1">{score.location}</p>
                          <div className="flex gap-2 mt-2">
                            <span className="px-2 py-1 bg-blue-900/20 text-blue-400 text-xs rounded border border-blue-400/20">
                              {score.seniority || score.seniority_fit ? `${Math.round((score.seniority_fit || 0) * 100)}% fit` : 'All levels'}
                            </span>
                            <span className="px-2 py-1 bg-green-900/20 text-green-400 text-xs rounded border border-green-400/20">
                              {score.remote_type || 'On-site'}
                            </span>
                          </div>
                        </div>
                        <div className="text-right">
                          <div className="text-2xl font-bold text-accent-red">
                            {Math.round((score.total_score || 0) * 100)}%
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
              ) : resumes.length > 0 ? (
                // User has resume but no matches - show action buttons
                <div className="text-center py-8">
                  <svg className="mx-auto h-12 w-12 text-text-muted mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                  </svg>
                  <p className="text-text-primary text-lg font-medium mb-2">No job matches yet</p>
                  <p className="text-text-secondary mb-6">Generate matches to see personalized job recommendations</p>
                  <div className="flex gap-4 justify-center">
                    <Link 
                      href="/matches" 
                      className="btn-primary px-6 py-2"
                    >
                      Generate Matches
                    </Link>
                    <Link 
                      href="/jobs" 
                      className="btn-secondary px-6 py-2"
                    >
                      Browse All Jobs
                    </Link>
                  </div>
                </div>
              ) : (
                // No resume uploaded yet - prompt to upload
                <div className="text-center py-8">
                  <svg className="mx-auto h-12 w-12 text-text-muted mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                  </svg>
                  <p className="text-text-primary text-lg font-medium mb-2">Upload Your Resume to Get Job Matches</p>
                  <p className="text-text-secondary mb-6">We&apos;ll analyze your skills and experience to find the best matching opportunities</p>
                  <label className="inline-block cursor-pointer">
                    <span className="btn-primary px-6 py-2">
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
                  <div className="mt-4">
                    <Link 
                      href="/jobs" 
                      className="text-accent-red hover:text-accent-red-light text-sm"
                    >
                      or browse all jobs without matching →
                    </Link>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
    </main>
  )
}