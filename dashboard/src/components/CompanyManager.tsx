'use client'

import { useState } from 'react'
import { api } from '@/lib/api-client'

interface Company {
  id: string
  company_name: string
  company_id: string
  ats_system: string
  job_board_url?: string
  active: boolean
  last_checked?: string
  jobs_found: number
}

interface ATSDetection {
  company_name: string
  detected_ats?: string
  company_id: string
  confidence: number
  job_board_url?: string
}

export default function CompanyManager() {
  const [companies, setCompanies] = useState<Company[]>([])
  const [companyName, setCompanyName] = useState('')
  const [selectedATS, setSelectedATS] = useState<string>('')
  const [detecting, setDetecting] = useState(false)
  const [detectionResult, setDetectionResult] = useState<ATSDetection | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Load user's watchlist on mount
  useState(() => {
    loadWatchlist()
  }, [])

  const loadWatchlist = async () => {
    try {
      const data = await api.get('/api/v1/companies/my-watchlist')
      setCompanies(data)
    } catch (err) {
      console.error('Failed to load watchlist:', err)
    }
  }

  const detectATS = async () => {
    if (!companyName.trim()) return

    setDetecting(true)
    setError(null)
    try {
      const result = await api.get(`/api/v1/companies/detect-ats?company_name=${encodeURIComponent(companyName)}`)
      setDetectionResult(result)
      if (result.detected_ats) {
        setSelectedATS(result.detected_ats)
      }
    } catch (err) {
      setError('Failed to detect ATS system')
      console.error(err)
    } finally {
      setDetecting(false)
    }
  }

  const addCompany = async () => {
    if (!companyName.trim()) {
      setError('Please enter a company name')
      return
    }

    setLoading(true)
    setError(null)
    try {
      const data = {
        company_name: companyName,
        ats_system: selectedATS || undefined
      }
      
      const newCompany = await api.post('/api/v1/companies/add', data)
      setCompanies([...companies, newCompany])
      
      // Reset form
      setCompanyName('')
      setSelectedATS('')
      setDetectionResult(null)
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to add company')
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  const removeCompany = async (companyId: string) => {
    try {
      await api.delete(`/api/v1/companies/${companyId}`)
      setCompanies(companies.filter(c => c.id !== companyId))
    } catch (err) {
      console.error('Failed to remove company:', err)
    }
  }

  return (
    <div className="space-y-6">
      {/* Add Company Form */}
      <div className="card">
        <h3 className="text-xl font-semibold text-text-primary mb-4">
          Add Company to Watchlist
        </h3>
        
        <div className="space-y-4">
          <div>
            <label className="input-label">Company Name</label>
            <div className="flex gap-2">
              <input
                type="text"
                value={companyName}
                onChange={(e) => setCompanyName(e.target.value)}
                placeholder="e.g., Spotify, Airbnb, etc."
                className="flex-1 input-dark"
              />
              <button
                onClick={detectATS}
                disabled={detecting || !companyName.trim()}
                className="btn-secondary"
              >
                {detecting ? 'Detecting...' : 'Auto-Detect ATS'}
              </button>
            </div>
          </div>

          {detectionResult && (
            <div className={`p-3 rounded-lg ${
              detectionResult.detected_ats 
                ? 'bg-green-900/20 border border-green-700' 
                : 'bg-yellow-900/20 border border-yellow-700'
            }`}>
              {detectionResult.detected_ats ? (
                <div>
                  <p className="text-green-400">
                    ✓ Detected: {detectionResult.detected_ats.toUpperCase()} 
                    (confidence: {Math.round(detectionResult.confidence * 100)}%)
                  </p>
                  {detectionResult.job_board_url && (
                    <a 
                      href={detectionResult.job_board_url} 
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-primary hover:text-primary-hover text-sm"
                    >
                      View job board →
                    </a>
                  )}
                </div>
              ) : (
                <p className="text-yellow-400">
                  Could not auto-detect ATS. Please select manually:
                </p>
              )}
            </div>
          )}

          <div>
            <label className="input-label">ATS System</label>
            <select
              value={selectedATS}
              onChange={(e) => setSelectedATS(e.target.value)}
              className="w-full input-dark"
            >
              <option value="">Select ATS (or auto-detect)</option>
              <option value="lever">Lever</option>
              <option value="greenhouse">Greenhouse</option>
              <option value="ashby">Ashby</option>
            </select>
          </div>

          {error && (
            <div className="text-red-400 text-sm">{error}</div>
          )}

          <button
            onClick={addCompany}
            disabled={loading || !companyName.trim()}
            className="btn-primary w-full"
          >
            {loading ? 'Adding...' : 'Add to Watchlist'}
          </button>
        </div>
      </div>

      {/* Company Watchlist */}
      <div className="card">
        <h3 className="text-xl font-semibold text-text-primary mb-4">
          Your Company Watchlist ({companies.length})
        </h3>

        {companies.length === 0 ? (
          <p className="text-text-secondary">
            No companies in your watchlist yet. Add companies above to start tracking their job postings.
          </p>
        ) : (
          <div className="space-y-2">
            {companies.map((company) => (
              <div
                key={company.id}
                className="flex items-center justify-between p-3 bg-bg-secondary rounded-lg"
              >
                <div className="flex-1">
                  <div className="flex items-center gap-3">
                    <h4 className="font-medium text-text-primary">
                      {company.company_name}
                    </h4>
                    <span className="text-xs px-2 py-1 bg-bg-tertiary rounded">
                      {company.ats_system.toUpperCase()}
                    </span>
                    {company.jobs_found > 0 && (
                      <span className="text-xs text-green-400">
                        {company.jobs_found} jobs
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-4 mt-1">
                    {company.job_board_url && (
                      <a
                        href={company.job_board_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-xs text-primary hover:text-primary-hover"
                      >
                        View jobs →
                      </a>
                    )}
                    {company.last_checked && (
                      <span className="text-xs text-text-secondary">
                        Last checked: {new Date(company.last_checked).toLocaleDateString()}
                      </span>
                    )}
                  </div>
                </div>
                <button
                  onClick={() => removeCompany(company.id)}
                  className="text-text-secondary hover:text-red-400 transition-colors"
                >
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} 
                      d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                  </svg>
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}