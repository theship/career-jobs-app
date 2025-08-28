'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import MatchesTable from '@/components/MatchesTable'
import SkillsVocabularyUpload from '@/components/SkillsVocabularyUpload'
import { createClient } from '@/lib/supabase'
import { api } from '@/lib/api-client'
import { useNotification } from '@/contexts/NotificationContext'

export default function MatchesPage() {
  const router = useRouter()
  const [user, setUser] = useState<any>(null)
  const [matches, setMatches] = useState<any[]>([])
  const [selectedResume, setSelectedResume] = useState<string>('')
  const [resumes, setResumes] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [runningScoring, setRunningScoring] = useState(false)
  const [showSkillsUpload, setShowSkillsUpload] = useState(false)
  const [hasCustomSkills, setHasCustomSkills] = useState(false)
  
  const supabase = createClient()
  const { showSuccess, showError, showInfo, showWarning, confirm } = useNotification()

  useEffect(() => {
    checkUser()
    checkCustomSkills()
  }, [])

  useEffect(() => {
    if (selectedResume) {
      fetchMatches()
    }
  }, [selectedResume])

  const checkUser = async () => {
    const { data: { user } } = await supabase.auth.getUser()
    if (!user) {
      router.push('/login')
      return
    }
    setUser(user)
    await fetchResumes()
  }

  const checkCustomSkills = async () => {
    try {
      const vocabInfo = await api.getSkillsVocabulary()
      setHasCustomSkills(vocabInfo.has_custom_vocab || false)
    } catch (error) {
      setHasCustomSkills(false)
      // Don't show error on initial load - it's expected if no skills uploaded yet
      // The user will be prompted when they try to run scoring
    }
  }

  const fetchResumes = async () => {
    try {
      const data = await api.getResumes()
      setResumes(data)
      // Don't auto-select, let user choose
      // if (data.length > 0) {
      //   setSelectedResume(data[0].resume_id)
      // }
    } catch (error) {
      console.error('Failed to fetch resumes:', error)
    }
  }

  const fetchMatches = async () => {
    if (!selectedResume) return
    
    setLoading(true)
    try {
      const data = await api.getScores(selectedResume, 100)
      setMatches(data || [])
    } catch (error: any) {
      console.error('Failed to fetch matches:', error)
      // If error is about no scores, that's ok - just show empty
      if (error.message?.includes('404') || error.message?.includes('Not found')) {
        setMatches([])
      }
    } finally {
      setLoading(false)
    }
  }

  const runScoring = async () => {
    if (!selectedResume) return
    
    setRunningScoring(true)
    try {
      // First check if we have jobs in the system
      const jobs = await api.getJobs({ limit: 1 })
      if (!jobs || jobs.length === 0) {
        showWarning('No jobs available in the system yet. Please wait for job data to be ingested.', 'No Jobs Available')
        setRunningScoring(false)
        return
      }

      const result = await api.runScoring(selectedResume, 100, 0.0)
      setMatches(result.results || [])
      
      // Show appropriate message based on results
      if (result.results && result.results.length > 0) {
        showSuccess(`Found ${result.results.length} job matches!`, 'Scoring Complete')
      } else if (!hasCustomSkills) {
        // No matches and no custom skills - suggest uploading skills vocab
        const uploadSkills = await confirm(
          'No job matches found. This might be because the system needs your custom skills vocabulary to better understand your expertise. Would you like to upload a custom skills CSV now?',
          'Upload Skills Vocabulary?'
        )
        if (uploadSkills) {
          setShowSkillsUpload(true)
        }
      } else {
        showInfo('No matches found with current criteria. Try adjusting your resume or waiting for more jobs to be added.', 'No Matches')
      }
    } catch (error: any) {
      console.error('Failed to run scoring:', error)
      
      // Check if it's a "no jobs" error
      if (error.message?.includes('No jobs to score')) {
        showWarning('No jobs available to match against. Please check back later.', 'No Jobs')
      } else {
        showError(error.message || 'Unknown error occurred while running scoring', 'Scoring Failed')
      }
    } finally {
      setRunningScoring(false)
    }
  }

  const downloadCSV = async () => {
    if (!selectedResume) return
    
    try {
      const blob = await api.exportScores(selectedResume, 'csv')
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `job_matches_${selectedResume}_${new Date().toISOString().split('T')[0]}.csv`
      document.body.appendChild(a)
      a.click()
      window.URL.revokeObjectURL(url)
      document.body.removeChild(a)
    } catch (error) {
      console.error('Failed to download CSV:', error)
    }
  }

  if (!user) {
    return <div className="p-8">Loading...</div>
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-7xl mx-auto px-4 py-8">
        {/* Header */}
        <div className="bg-white rounded-lg shadow p-6 mb-6">
          <div className="flex justify-between items-start mb-4">
            <div>
              <h1 className="text-3xl font-bold text-gray-900">Job Matches</h1>
              <p className="mt-2 text-gray-600">
                View and manage your job match scores based on your resume
              </p>
            </div>
            <button
              onClick={() => router.push('/dashboard')}
              className="text-blue-600 hover:text-blue-800"
            >
              ← Back to Dashboard
            </button>
          </div>

          {/* Resume Selection and Actions */}
          <div className="flex gap-4 items-end">
            <div className="flex-1">
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Select Resume
              </label>
              <select
                value={selectedResume}
                onChange={(e) => setSelectedResume(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white text-gray-900"
              >
                <option value="">Choose a resume...</option>
                {resumes.map((resume) => (
                  <option key={resume.resume_id} value={resume.resume_id}>
                    {resume.filename} - {resume.skills_count || 0} skills
                  </option>
                ))}
              </select>
            </div>
            <button
              onClick={runScoring}
              disabled={!selectedResume || runningScoring}
              className="px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 disabled:opacity-50"
            >
              {runningScoring ? 'Running...' : 'Run New Scoring'}
            </button>
          </div>
        </div>

        {/* Matches Table */}
        <div className="bg-white rounded-lg shadow">
          {resumes.length === 0 ? (
            <div className="p-8 text-center">
              <p className="text-gray-600 mb-4">
                No resumes uploaded yet. Upload a resume to see job matches.
              </p>
              <button
                onClick={() => router.push('/profile')}
                className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
              >
                Upload Resume
              </button>
            </div>
          ) : matches.length === 0 && !loading ? (
            <div className="p-8 text-center">
              <p className="text-gray-600 mb-4">
                No matches found yet. Run scoring to find job matches.
              </p>
              <button
                onClick={runScoring}
                disabled={!selectedResume || runningScoring}
                className="px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 disabled:opacity-50"
              >
                {runningScoring ? 'Running...' : 'Run Scoring'}
              </button>
            </div>
          ) : (
            <MatchesTable 
              matches={matches} 
              loading={loading}
              onDownloadCSV={downloadCSV}
            />
          )}
        </div>
      </div>
      
      {/* Skills Vocabulary Upload Modal */}
      {showSkillsUpload && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-lg max-w-4xl w-full max-h-[90vh] overflow-y-auto p-6">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-2xl font-bold">Upload Skills Vocabulary</h2>
              <button
                onClick={() => setShowSkillsUpload(false)}
                className="text-gray-500 hover:text-gray-700"
              >
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            <SkillsVocabularyUpload 
              onSuccess={() => {
                setShowSkillsUpload(false)
                setHasCustomSkills(true)
                checkCustomSkills() // Refresh the status
                showSuccess('Skills vocabulary uploaded successfully! Try running scoring again.', 'Upload Complete')
              }}
            />
          </div>
        </div>
      )}
    </div>
  )
}