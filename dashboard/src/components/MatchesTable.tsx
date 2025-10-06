'use client'

import { useState, useMemo, useEffect } from 'react'
import { ChevronUpIcon, ChevronDownIcon, ArrowDownTrayIcon, BookmarkIcon } from '@heroicons/react/24/outline'
import { BookmarkIcon as BookmarkSolidIcon } from '@heroicons/react/24/solid'
import { savedJobsService } from '@/services'
import { useNotification } from '@/contexts/NotificationContext'

interface JobMatch {
  job_id: string
  title: string
  company_name: string
  location: string
  total_score: number
  cosine_sim: number
  skill_overlap: number
  seniority_fit: number
  geodist_km: number | null
  recency_bonus: number
  posted_at: string
  match_level: string
}

interface MatchesTableProps {
  matches: JobMatch[]
  loading?: boolean
  onDownloadCSV: () => void
}

type SortKey = keyof JobMatch
type SortDirection = 'asc' | 'desc'

export default function MatchesTable({ matches, loading, onDownloadCSV }: MatchesTableProps) {
  const [sortKey, setSortKey] = useState<SortKey>('total_score')
  const [sortDirection, setSortDirection] = useState<SortDirection>('desc')
  const [filterScore, setFilterScore] = useState<number>(0)
  const [currentPage, setCurrentPage] = useState(1)
  const [savedJobs, setSavedJobs] = useState<Record<string, boolean>>({})
  const [savingJobs, setSavingJobs] = useState<Set<string>>(new Set())
  const itemsPerPage = 20
  const { showSuccess, showError } = useNotification()

  // Load saved jobs status when matches change
  useEffect(() => {
    if (matches.length > 0) {
      checkSavedJobs()
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [matches])

  const checkSavedJobs = async () => {
    try {
      const jobIds = matches.map(m => m.job_id)
      const savedStatus = await savedJobsService.checkMultipleJobs(jobIds)
      setSavedJobs(savedStatus)
    } catch (error) {
      console.error('Failed to check saved jobs:', error)
    }
  }

  const handleToggleSave = async (jobId: string, jobTitle: string) => {
    if (savingJobs.has(jobId)) return // Already processing

    setSavingJobs(prev => new Set(prev).add(jobId))

    try {
      const result = await savedJobsService.toggleSaveJob(jobId)
      setSavedJobs(prev => ({ ...prev, [jobId]: result.saved }))

      if (result.saved) {
        showSuccess(`Saved "${jobTitle}" to your saved jobs`)
      } else {
        showSuccess(`Removed "${jobTitle}" from saved jobs`)
      }
    } catch (error) {
      console.error('Failed to toggle save job:', error)
      showError('Failed to save job. Please try again.')
    } finally {
      setSavingJobs(prev => {
        const newSet = new Set(prev)
        newSet.delete(jobId)
        return newSet
      })
    }
  }

  // Filter matches
  const filteredMatches = useMemo(() => {
    return matches.filter(match => {
      const scoreFilter = match.total_score >= filterScore
      return scoreFilter
    })
  }, [matches, filterScore])

  // Sort matches
  const sortedMatches = useMemo(() => {
    return [...filteredMatches].sort((a, b) => {
      const aVal = a[sortKey]
      const bVal = b[sortKey]
      
      if (aVal === null || aVal === undefined) return 1
      if (bVal === null || bVal === undefined) return -1
      
      const comparison = aVal < bVal ? -1 : aVal > bVal ? 1 : 0
      return sortDirection === 'asc' ? comparison : -comparison
    })
  }, [filteredMatches, sortKey, sortDirection])

  // Paginate
  const paginatedMatches = useMemo(() => {
    const start = (currentPage - 1) * itemsPerPage
    return sortedMatches.slice(start, start + itemsPerPage)
  }, [sortedMatches, currentPage])

  const totalPages = Math.ceil(sortedMatches.length / itemsPerPage)

  const handleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc')
    } else {
      setSortKey(key)
      setSortDirection('desc')
    }
  }

  const getScoreColor = (score: number) => {
    if (score >= 0.7) return 'text-green-600 bg-green-50'
    if (score >= 0.5) return 'text-yellow-600 bg-yellow-50'
    return 'text-red-600 bg-red-50'
  }

  const getMatchLevelBadge = (level: string) => {
    const colors = {
      high: 'bg-green-100 text-green-800',
      medium: 'bg-yellow-100 text-yellow-800',
      low: 'bg-gray-100 text-gray-800'
    }
    return colors[level as keyof typeof colors] || colors.low
  }

  const formatDate = (dateString: string) => {
    if (!dateString) return 'Unknown'
    const date = new Date(dateString)
    // Check for invalid date
    if (isNaN(date.getTime())) return 'Unknown'
    const days = Math.floor((Date.now() - date.getTime()) / (1000 * 60 * 60 * 24))
    if (days === 0) return 'Today'
    if (days === 1) return 'Yesterday'
    if (days < 7) return `${days} days ago`
    return date.toLocaleDateString()
  }

  const SortIcon = ({ column }: { column: SortKey }) => {
    if (sortKey !== column) return null
    return sortDirection === 'asc' ? 
      <ChevronUpIcon className="w-4 h-4 inline ml-1" /> : 
      <ChevronDownIcon className="w-4 h-4 inline ml-1" />
  }

  if (loading) {
    return <div className="text-center py-8">Loading matches...</div>
  }

  return (
    <div className="space-y-4">
      {/* Filters and Actions */}
      <div className="flex flex-wrap gap-4 items-center justify-between bg-white p-4 rounded-lg shadow">
        <div className="flex gap-4 flex-1">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Min Score
            </label>
            <input
              type="range"
              min="0"
              max="1"
              step="0.1"
              value={filterScore}
              onChange={(e) => setFilterScore(Number(e.target.value))}
              className="w-32"
            />
            <span className="ml-2 text-sm">{(filterScore * 100).toFixed(0)}%</span>
          </div>
        </div>
        <button
          onClick={onDownloadCSV}
          className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
        >
          <ArrowDownTrayIcon className="w-5 h-5" />
          Download CSV
        </button>
      </div>

      {/* Results count */}
      <div className="text-sm text-gray-600">
        Showing {paginatedMatches.length} of {sortedMatches.length} matches
      </div>

      {/* Table */}
      <div className="overflow-x-auto bg-white rounded-lg shadow">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th 
                className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100"
                onClick={() => handleSort('total_score')}
              >
                Match Score <SortIcon column="total_score" />
              </th>
              <th 
                className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100"
                onClick={() => handleSort('company_name')}
              >
                Company <SortIcon column="company_name" />
              </th>
              <th 
                className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100"
                onClick={() => handleSort('title')}
              >
                Position <SortIcon column="title" />
              </th>
              <th 
                className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100"
                onClick={() => handleSort('skill_overlap')}
              >
                Skills Match <SortIcon column="skill_overlap" />
              </th>
              <th 
                className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100"
                onClick={() => handleSort('posted_at')}
              >
                Posted <SortIcon column="posted_at" />
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Actions
              </th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {paginatedMatches.map((match, index) => (
              <tr key={`${match.job_id}-${index}`} className="hover:bg-gray-50">
                <td className="px-6 py-4 whitespace-nowrap">
                  <div className="flex items-center gap-2">
                    <span 
                      className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getScoreColor(match.total_score)}`}
                      data-testid="match-score"
                    >
                      {(match.total_score * 100).toFixed(0)}%
                    </span>
                    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs ${getMatchLevelBadge(match.match_level)}`}>
                      {match.match_level}
                    </span>
                  </div>
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900 font-medium">
                  {match.company_name ? match.company_name.charAt(0).toUpperCase() + match.company_name.slice(1) : ''}
                </td>
                <td className="px-6 py-4">
                  <div className="text-sm text-gray-900 line-clamp-2">
                    {match.title}
                  </div>
                </td>
                <td className="px-6 py-4 whitespace-nowrap">
                  <div className="text-sm text-gray-900">
                    {(match.skill_overlap * 100).toFixed(0)}%
                  </div>
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                  {formatDate(match.posted_at)}
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm">
                  <div className="flex items-center gap-2">
                    <a
                      href={`/jobs/${match.job_id}`}
                      className="text-blue-600 hover:text-blue-900"
                    >
                      View
                    </a>
                    <button
                      onClick={() => handleToggleSave(match.job_id, match.title)}
                      disabled={savingJobs.has(match.job_id)}
                      className="p-1 rounded hover:bg-gray-100 transition-colors disabled:opacity-50"
                      title={savedJobs[match.job_id] ? 'Unsave job' : 'Save job'}
                      aria-label={savedJobs[match.job_id] ? `Unsave ${match.title} at ${match.company_name}` : `Save ${match.title} at ${match.company_name}`}
                      aria-pressed={savedJobs[match.job_id] ? 'true' : 'false'}
                    >
                      {savedJobs[match.job_id] ? (
                        <BookmarkSolidIcon className="w-5 h-5 text-blue-600" />
                      ) : (
                        <BookmarkIcon className="w-5 h-5 text-gray-400 hover:text-blue-600" />
                      )}
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex justify-center gap-2">
          <button
            onClick={() => setCurrentPage(Math.max(1, currentPage - 1))}
            disabled={currentPage === 1}
            className="px-3 py-1 border rounded-md disabled:opacity-50"
          >
            Previous
          </button>
          <span className="px-3 py-1">
            Page {currentPage} of {totalPages}
          </span>
          <button
            onClick={() => setCurrentPage(Math.min(totalPages, currentPage + 1))}
            disabled={currentPage === totalPages}
            className="px-3 py-1 border rounded-md disabled:opacity-50"
          >
            Next
          </button>
        </div>
      )}
    </div>
  )
}
