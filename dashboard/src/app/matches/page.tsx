'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import MatchesTable from '@/components/MatchesTable'
import { supabase } from '@/lib/supabase'
import { api } from '@/lib/api'

export default function MatchesPage() {
  const router = useRouter()
  const [user, setUser] = useState<any>(null)
  const [matches, setMatches] = useState<any[]>([])
  const [selectedResume, setSelectedResume] = useState<string>('')
  const [resumes, setResumes] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [runningScoring, setRunningScoring] = useState(false)

  useEffect(() => {
    checkUser()
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

  const fetchResumes = async () => {
    try {
      const data = await api.getResumes()
      setResumes(data)
      if (data.length > 0) {
        setSelectedResume(data[0].resume_id)
      }
    } catch (error) {
      console.error('Failed to fetch resumes:', error)
    }
  }

  const fetchMatches = async () => {
    if (!selectedResume) return
    
    setLoading(true)
    try {
      const response = await fetch(
        `/api/v1/scores?resume_id=${selectedResume}&limit=100`,
        {
          headers: {
            'Authorization': `Bearer ${await api.getAuthToken()}`
          }
        }
      )
      
      if (!response.ok) throw new Error('Failed to fetch scores')
      
      const data = await response.json()
      setMatches(data)
    } catch (error) {
      console.error('Failed to fetch matches:', error)
    } finally {
      setLoading(false)
    }
  }

  const runScoring = async () => {
    if (!selectedResume) return
    
    setRunningScoring(true)
    try {
      const response = await fetch('/api/v1/scores/run', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${await api.getAuthToken()}`
        },
        body: JSON.stringify({
          resume_id: selectedResume,
          limit: 100,
          min_score: 0.3
        })
      })
      
      if (!response.ok) throw new Error('Failed to run scoring')
      
      const result = await response.json()
      setMatches(result.results)
    } catch (error) {
      console.error('Failed to run scoring:', error)
    } finally {
      setRunningScoring(false)
    }
  }

  const downloadCSV = async () => {
    if (!selectedResume) return
    
    try {
      const response = await fetch(
        `/api/v1/scores/export?resume_id=${selectedResume}&format=csv&include_details=true`,
        {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${await api.getAuthToken()}`
          }
        }
      )
      
      if (!response.ok) throw new Error('Failed to export CSV')
      
      const blob = await response.blob()
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
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
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
    </div>
  )
}