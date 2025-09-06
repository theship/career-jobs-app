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
    loadCachedMatches()
  }, [])

  useEffect(() => {
    if (selectedResume) {
      // Try to load cached matches for this resume
      const cached = getCachedMatches(selectedResume)
      if (cached && cached.length > 0) {
        setMatches(cached)
        setLoading(false)
      } else {
        fetchMatches()
      }
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

  const getCachedMatches = (resumeId: string): any[] => {
    try {
      const cached = localStorage.getItem(`matches_${resumeId}`)
      if (cached) {
        const parsed = JSON.parse(cached)
        // Check if cache is less than 24 hours old
        if (parsed.timestamp && Date.now() - parsed.timestamp < 24 * 60 * 60 * 1000) {
          return parsed.matches || []
        }
      }
    } catch (error) {
      console.error('Error loading cached matches:', error)
    }
    return []
  }

  const saveCachedMatches = (resumeId: string, matchesData: any[]) => {
    try {
      localStorage.setItem(`matches_${resumeId}`, JSON.stringify({
        matches: matchesData,
        timestamp: Date.now()
      }))
    } catch (error) {
      console.error('Error saving matches to cache:', error)
    }
  }

  const clearCachedMatches = (resumeId: string) => {
    try {
      localStorage.removeItem(`matches_${resumeId}`)
    } catch (error) {
      console.error('Error clearing cached matches:', error)
    }
  }

  const loadCachedMatches = () => {
    // Check if we have a previously selected resume in localStorage
    try {
      const lastResume = localStorage.getItem('last_selected_resume')
      if (lastResume && resumes.find(r => r.resume_id === lastResume)) {
        setSelectedResume(lastResume)
      }
    } catch (error) {
      console.error('Error loading last selected resume:', error)
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
      // Cache the fetched matches
      if (data && data.length > 0) {
        saveCachedMatches(selectedResume, data)
      }
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
    
    // Clear any cached matches for this resume when running new scoring
    clearCachedMatches(selectedResume)
    
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
      
      // Cache the new matches
      if (result.results && result.results.length > 0) {
        saveCachedMatches(selectedResume, result.results)
        showSuccess(`Found ${result.results.length} job matches!`, 'Scoring Complete')
      } else {
        // No matches found
        if (!hasCustomSkills) {
          showInfo(
            'No strong matches found. The system matched your resume using AI embeddings, but uploading a custom skills vocabulary CSV could improve accuracy by identifying specific technical skills.',
            'Matches Generated'
          )
        } else {
          showInfo('No matches found with current criteria. Try adjusting your resume or waiting for more jobs to be added.', 'No Matches')
        }
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
    <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Header */}
      <div className="card mb-6">
        <h1 className="text-3xl font-light text-text-primary mb-2">Generate Matches</h1>
        <p className="text-text-secondary">
          Generate and manage job match scores based on your resume
        </p>
        {!hasCustomSkills && (
          <div className="mt-4 p-3 bg-surface border border-border rounded">
            <p className="text-sm text-text-secondary">
              <strong className="text-accent-red">Tip:</strong> Upload a custom skills vocabulary CSV to improve matching accuracy. 
              The system will still match jobs using AI embeddings, but skills matching helps identify specific technical requirements.
              <button
                onClick={() => setShowSkillsUpload(true)}
                className="ml-2 text-accent-red hover:text-accent-red-light underline hover:no-underline transition-colors"
              >
                Upload Skills
              </button>
            </p>
          </div>
        )}

        {/* Resume Selection and Actions */}
        <div className="flex gap-4 items-end mt-6">
          <div className="flex-1">
            <label className="input-label">
              Select Resume
            </label>
            <select
              value={selectedResume}
              onChange={(e) => {
                setSelectedResume(e.target.value)
                // Save the selected resume to localStorage
                if (e.target.value) {
                  localStorage.setItem('last_selected_resume', e.target.value)
                }
              }}
              className="w-full input-dark"
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
            className="btn-primary disabled:opacity-50"
          >
            {runningScoring ? 'Running...' : 'Generate New Matches'}
          </button>
        </div>
      </div>

      {/* Matches Table */}
      <div className="card">
        {resumes.length === 0 ? (
          <div className="p-8 text-center">
            <p className="text-text-secondary mb-4">
              No resumes uploaded yet. Upload a resume to generate job matches.
            </p>
            <button
              onClick={() => router.push('/profile')}
              className="btn-primary"
            >
              Upload Resume
            </button>
          </div>
        ) : matches.length === 0 && !loading ? (
          <div className="p-8 text-center">
            <p className="text-text-secondary mb-4">
              No matches found yet. Generate matches to see results.
            </p>
            <button
              onClick={runScoring}
              disabled={!selectedResume || runningScoring}
              className="btn-primary disabled:opacity-50"
            >
              {runningScoring ? 'Generating...' : 'Generate Matches'}
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
    </main>
  )
}