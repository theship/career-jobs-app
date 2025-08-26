'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { createClient } from '@/lib/supabase'
import { apiClient } from '@/lib/api'

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

      const jobsData = await apiClient.getJobs(params)
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
                  <Link href="/profile" className="text-gray-700 hover:text-blue-600">
                    Profile
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
        <h1 className="text-3xl font-bold text-gray-900 mb-8">Browse Jobs</h1>

        {/* Search and Filters */}
        <div className="bg-white rounded-lg shadow p-6 mb-8">
          <form onSubmit={handleSearch} className="mb-4">
            <div className="flex gap-4">
              <input
                type="text"
                placeholder="Search jobs by title, company, or keywords..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="flex-1 px-4 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              <button
                type="submit"
                className="bg-blue-600 hover:bg-blue-700 text-white px-6 py-2 rounded-md"
              >
                Search
              </button>
            </div>
          </form>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Seniority Level
              </label>
              <select
                value={filters.seniority}
                onChange={(e) => handleFilterChange('seniority', e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
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
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Work Type
              </label>
              <select
                value={filters.remote_type}
                onChange={(e) => handleFilterChange('remote_type', e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="">All Types</option>
                <option value="Remote">Remote</option>
                <option value="Hybrid">Hybrid</option>
                <option value="Onsite">On-site</option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Location
              </label>
              <input
                type="text"
                placeholder="e.g., San Francisco"
                value={filters.location}
                onChange={(e) => handleFilterChange('location', e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </div>
        </div>

        {/* Job Listings */}
        <div className="bg-white rounded-lg shadow">
          {loading ? (
            <div className="p-8 text-center">
              <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
              <p className="mt-4 text-gray-600">Loading jobs...</p>
            </div>
          ) : jobs.length > 0 ? (
            <div className="divide-y">
              {jobs.map((job) => (
                <div key={job.job_id} className="p-6 hover:bg-gray-50 transition-colors">
                  <div className="flex justify-between items-start">
                    <div className="flex-1">
                      <h3 className="text-xl font-semibold text-gray-900">
                        {job.title}
                      </h3>
                      <p className="text-lg text-gray-700 mt-1">{job.company_name}</p>
                      <p className="text-gray-600 mt-1">{job.location}</p>
                      
                      <div className="flex gap-2 mt-3">
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
                        <p className="text-gray-600 mt-3 line-clamp-2">
                          {job.description}
                        </p>
                      )}
                    </div>

                    <div className="ml-6 text-right">
                      <Link
                        href={`/jobs/${job.job_id}`}
                        className="inline-block bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-md text-sm"
                      >
                        View Details
                      </Link>
                      {job.created_at && (
                        <p className="text-xs text-gray-500 mt-2">
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
              <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
              <p className="mt-4 text-gray-600">No jobs found</p>
              <p className="text-sm text-gray-500 mt-2">Try adjusting your search or filters</p>
            </div>
          )}
        </div>
      </main>
    </div>
  )
}