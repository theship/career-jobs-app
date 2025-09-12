'use client'

import { useState, useMemo } from 'react'
import { ChevronUpIcon, ChevronDownIcon, ArrowDownTrayIcon } from '@heroicons/react/24/outline'

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
  const [filterLocation, setFilterLocation] = useState<string>('')
  const [currentPage, setCurrentPage] = useState(1)
  const itemsPerPage = 20

  // Filter matches
  const filteredMatches = useMemo(() => {
    return matches.filter(match => {
      const scoreFilter = match.total_score >= filterScore
      const locationFilter = !filterLocation || 
        match.location?.toLowerCase().includes(filterLocation.toLowerCase())
      return scoreFilter && locationFilter
    })
  }, [matches, filterScore, filterLocation])

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
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Location
            </label>
            <input
              type="text"
              placeholder="Filter by location"
              value={filterLocation}
              onChange={(e) => setFilterLocation(e.target.value)}
              className="px-3 py-1 border rounded-md"
            />
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
                onClick={() => handleSort('location')}
              >
                Location <SortIcon column="location" />
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
                <td className="px-6 py-4 whitespace-nowrap font-medium">
                  {match.company_name}
                </td>
                <td className="px-6 py-4">
                  <div className="text-sm text-gray-900 line-clamp-2">
                    {match.title}
                  </div>
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm">
                  {match.location}
                </td>
                <td className="px-6 py-4 whitespace-nowrap">
                  <div className="text-sm">
                    {(match.skill_overlap * 100).toFixed(0)}%
                  </div>
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                  {formatDate(match.posted_at)}
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm">
                  <a 
                    href={`/jobs/${match.job_id}`}
                    className="text-blue-600 hover:text-blue-900 mr-3"
                  >
                    View
                  </a>
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