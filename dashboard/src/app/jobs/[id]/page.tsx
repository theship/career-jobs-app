'use client'

import { useState, useEffect } from 'react'
import { useParams, useRouter } from 'next/navigation'
import Link from 'next/link'
import { createClient } from '@/lib/supabase'
import { apiClient } from '@/lib/api'

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
      const jobData = await apiClient.getJobById(jobId)
      setJob(jobData)

      // If user is logged in, try to get their score for this job
      if (user) {
        try {
          const resumes = await apiClient.getResumes()
          if (resumes && resumes.length > 0) {
            const scores = await apiClient.getScores(resumes[0].resume_id)
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
      const resumes = await apiClient.getResumes()
      if (!resumes || resumes.length === 0) {
        alert('Please upload a resume first')
        router.push('/dashboard')
        return
      }

      // Call pitch generation API
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1/pitch/generate`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${await (await supabase.auth.getSession()).data.session?.access_token}`
        },
        body: JSON.stringify({
          resume_id: resumes[0].resume_id,
          job_id: jobId,
          include_research: true,
          personalization_level: 'high'
        })
      })

      if (!response.ok) {
        throw new Error('Failed to generate pitch')
      }

      const pitchData = await response.json()
      setPitch(pitchData)
    } catch (error) {
      console.error('Error generating pitch:', error)
      alert('Failed to generate pitch. Please try again.')
    } finally {
      setGeneratingPitch(false)
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
      </div>
    )
  }

  if (!job) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <h2 className="text-2xl font-bold text-gray-900">Job not found</h2>
          <Link href="/jobs" className="mt-4 text-blue-600 hover:text-blue-700">
            ← Back to jobs
          </Link>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Navigation */}
      <nav className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between h-16">
            <div className="flex items-center">
              <Link href="/" className="text-xl font-bold text-gray-900">
                Career Jobs App
              </Link>
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
                  <button
                    onClick={async () => {
                      await supabase.auth.signOut()
                      router.push('/')
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

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <Link href="/jobs" className="text-blue-600 hover:text-blue-700 mb-4 inline-block">
          ← Back to jobs
        </Link>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Job Details */}
          <div className="lg:col-span-2">
            <div className="bg-white rounded-lg shadow p-6">
              <h1 className="text-3xl font-bold text-gray-900">{job.title}</h1>
              <p className="text-xl text-gray-700 mt-2">{job.company_name}</p>
              <p className="text-gray-600 mt-1">{job.location}</p>

              <div className="flex gap-2 mt-4">
                {job.seniority && (
                  <span className="px-3 py-1 bg-blue-100 text-blue-700 text-sm rounded">
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
                  <p className="text-gray-700 whitespace-pre-wrap">{job.description}</p>
                </div>
              )}

              {job.responsibilities && job.responsibilities.length > 0 && (
                <div className="mt-6">
                  <h2 className="text-lg font-semibold mb-2">Responsibilities</h2>
                  <ul className="list-disc list-inside space-y-1">
                    {job.responsibilities.map((resp: string, idx: number) => (
                      <li key={idx} className="text-gray-700">{resp}</li>
                    ))}
                  </ul>
                </div>
              )}

              {job.requirements && job.requirements.length > 0 && (
                <div className="mt-6">
                  <h2 className="text-lg font-semibold mb-2">Requirements</h2>
                  <ul className="list-disc list-inside space-y-1">
                    {job.requirements.map((req: string, idx: number) => (
                      <li key={idx} className="text-gray-700">{req}</li>
                    ))}
                  </ul>
                </div>
              )}

              {job.benefits && job.benefits.length > 0 && (
                <div className="mt-6">
                  <h2 className="text-lg font-semibold mb-2">Benefits</h2>
                  <ul className="list-disc list-inside space-y-1">
                    {job.benefits.map((benefit: string, idx: number) => (
                      <li key={idx} className="text-gray-700">{benefit}</li>
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
              <div className="bg-white rounded-lg shadow p-6 mb-6">
                <h2 className="text-lg font-semibold mb-4">Your Match Score</h2>
                <div className="text-center">
                  <div className="text-4xl font-bold text-blue-600">
                    {Math.round(score.overall_score * 100)}%
                  </div>
                  <p className="text-gray-600 mt-2">Overall Match</p>
                </div>
                <div className="mt-4 space-y-2">
                  <div className="flex justify-between">
                    <span className="text-gray-600">Skills Match:</span>
                    <span className="font-medium">{Math.round(score.skills_score * 100)}%</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-600">Experience Match:</span>
                    <span className="font-medium">{Math.round(score.experience_score * 100)}%</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-600">Location Match:</span>
                    <span className="font-medium">{Math.round(score.location_score * 100)}%</span>
                  </div>
                </div>
              </div>
            )}

            {/* AI Pitch Generator */}
            <div className="bg-white rounded-lg shadow p-6">
              <h2 className="text-lg font-semibold mb-4">AI Application Assistant</h2>
              
              {!pitch ? (
                <div>
                  <p className="text-gray-600 text-sm mb-4">
                    Generate a personalized pitch for this position using AI
                  </p>
                  <button
                    onClick={generatePitch}
                    disabled={generatingPitch || !user}
                    className="w-full bg-blue-600 hover:bg-blue-700 text-white py-2 px-4 rounded-md disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {generatingPitch ? 'Generating...' : user ? 'Generate AI Pitch' : 'Sign in to Generate Pitch'}
                  </button>
                </div>
              ) : (
                <div className="space-y-4">
                  <div>
                    <h3 className="font-medium mb-1">Headline</h3>
                    <p className="text-sm text-gray-700">{pitch.headline}</p>
                  </div>

                  <div>
                    <h3 className="font-medium mb-1">Opening</h3>
                    <p className="text-sm text-gray-700">{pitch.opening}</p>
                  </div>

                  <div>
                    <h3 className="font-medium mb-1">Key Points</h3>
                    <ul className="list-disc list-inside text-sm text-gray-700 space-y-1">
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
                      alert('Pitch copied to clipboard!')
                    }}
                    className="w-full bg-green-600 hover:bg-green-700 text-white py-2 px-4 rounded-md text-sm"
                  >
                    Copy to Clipboard
                  </button>

                  <button
                    onClick={generatePitch}
                    className="w-full bg-gray-200 hover:bg-gray-300 text-gray-700 py-2 px-4 rounded-md text-sm"
                  >
                    Regenerate Pitch
                  </button>
                </div>
              )}
            </div>

            {/* Apply Button */}
            <div className="bg-white rounded-lg shadow p-6 mt-6">
              <a
                href={job.job_url}
                target="_blank"
                rel="noopener noreferrer"
                className="block w-full text-center bg-green-600 hover:bg-green-700 text-white py-3 px-4 rounded-md font-medium"
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