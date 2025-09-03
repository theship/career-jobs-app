'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { createClient } from '@/lib/supabase'
import { api } from '@/lib/api-client'

export default function JobsPage() {
  const [user, setUser] = useState<any>(null)
  const [jobs, setJobs] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [searchQuery, setSearchQuery] = useState('')
  const [filters, setFilters] = useState({
    seniority: '',
    remote_type: '',
    location: ''
  })
  const router = useRouter()
  const supabase = createClient()

  useEffect(() => {
    checkAuth()
    fetchJobs()
  }, [])

  const checkAuth = async () => {
    const { data: { user } } = await supabase.auth.getUser()
    setUser(user)
  }

  const fetchJobs = async () => {
    setLoading(true)
    try {
      const params: any = { limit: 50 }
      
      if (searchQuery) {
        params.search = searchQuery
      }
      if (filters.seniority) {
        params.seniority = filters.seniority
      }
      if (filters.remote_type) {
        params.remote_type = filters.remote_type
      }
      if (filters.location) {
        params.location = filters.location
      }

      const jobsData = await api.getJobs(params)
      setJobs(jobsData)
    } catch (error) {
      console.error('Error fetching jobs:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
    fetchJobs()
  }

  const handleFilterChange = (key: string, value: string) => {
    setFilters(prev => ({ ...prev, [key]: value }))
  }

  useEffect(() => {
    const debounce = setTimeout(() => {
      fetchJobs()
    }, 500)
    return () => clearTimeout(debounce)
  }, [filters])

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
                  <Link href="/profile" className="nav-link">
                    Profile
                  </Link>
                  <button
                    onClick={async () => {
                      const { clearAllSensitiveData } = await import('@/lib/clear-sensitive-data')
                      clearAllSensitiveData()
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
        <h1 className="text-3xl font-light text-text-primary mb-8">Browse Jobs</h1>

        {/* Search and Filters */}
        <div className="card mb-8">
          <form onSubmit={handleSearch} className="mb-4">
            <div className="flex gap-4">
              <input
                type="text"
                placeholder="Search jobs by title, company, or keywords..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="flex-1 input-dark"
              />
              <button
                type="submit"
                className="btn-primary"
              >
                Search
              </button>
            </div>
          </form>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className="input-label">
                Seniority Level
              </label>
              <select
                value={filters.seniority}
                onChange={(e) => handleFilterChange('seniority', e.target.value)}
                className="w-full input-dark"
              >
                <option value="">All Levels</option>
                <option value="Entry">Entry Level</option>
                <option value="Mid">Mid Level</option>
                <option value="Senior">Senior Level</option>
                <option value="Staff">Staff</option>
                <option value="Lead">Lead</option>
                <option value="Manager">Manager</option>
              </select>
            </div>

            <div>
              <label className="input-label">
                Work Type
              </label>
              <select
                value={filters.remote_type}
                onChange={(e) => handleFilterChange('remote_type', e.target.value)}
                className="w-full input-dark"
              >
                <option value="">All Types</option>
                <option value="Remote">Remote</option>
                <option value="Hybrid">Hybrid</option>
                <option value="Onsite">On-site</option>
              </select>
            </div>

            <div>
              <label className="input-label">
                Location
              </label>
              <input
                type="text"
                placeholder="e.g., San Francisco"
                value={filters.location}
                onChange={(e) => handleFilterChange('location', e.target.value)}
                className="w-full input-dark"
              />
            </div>
          </div>
        </div>

        {/* Job Listings */}
        <div className="card">
          {loading ? (
            <div className="p-8 text-center">
              <div className="spinner mx-auto"></div>
              <p className="mt-4 text-text-secondary">Loading jobs...</p>
            </div>
          ) : jobs.length > 0 ? (
            <div className="divide-y">
              {jobs.map((job) => (
                <div key={job.job_id} className="p-6 hover:bg-surface transition-colors border-b border-border last:border-b-0">
                  <div className="flex justify-between items-start">
                    <div className="flex-1">
                      <h3 className="text-xl font-medium text-text-primary">
                        {job.title}
                      </h3>
                      <p className="text-lg text-text-secondary mt-1">{job.company_name}</p>
                      <p className="text-text-muted mt-1">{job.location}</p>
                      
                      <div className="flex gap-2 mt-3">
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
                        <p className="text-text-secondary mt-3 line-clamp-2">
                          {job.description}
                        </p>
                      )}
                    </div>

                    <div className="ml-6 text-right">
                      <Link
                        href={`/jobs/${job.job_id}`}
                        className="inline-block btn-primary text-sm px-4 py-2"
                      >
                        View Details
                      </Link>
                      {job.created_at && (
                        <p className="text-xs text-text-muted mt-2">
                          Posted {new Date(job.created_at).toLocaleDateString()}
                        </p>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="p-8 text-center">
              <svg className="mx-auto h-12 w-12 text-text-muted" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
              <p className="mt-4 text-text-secondary">No jobs found</p>
              <p className="text-sm text-text-muted mt-2">Try adjusting your search or filters</p>
            </div>
          )}
        </div>
      </main>
    </div>
  )
}