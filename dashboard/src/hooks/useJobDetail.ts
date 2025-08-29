/**
 * useJobDetail Hook
 * Manages job detail data fetching and state
 */

import { useState, useEffect } from 'react'
import { jobService } from '@/services/job.service'
import { scoringService } from '@/services/scoring.service'
import { resumeService } from '@/services/resume.service'
import type { Job, Score, Resume } from '@/types/api.types'

export function useJobDetail(jobId: string, userId?: string) {
  const [job, setJob] = useState<Job | null>(null)
  const [score, setScore] = useState<Score | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!jobId) return

    const fetchJobDetails = async () => {
      setLoading(true)
      setError(null)

      try {
        // Fetch job details
        const jobData = await jobService.getJobById(jobId)
        setJob(jobData)

        // If user is logged in, try to get their score for this job
        if (userId) {
          try {
            // Get user's resumes
            const resumes = await resumeService.getResumes()
            
            if (resumes && resumes.length > 0) {
              // Get score for the first resume
              const jobScore = await scoringService.getScoreForJob(
                resumes[0].resume_id,
                jobId
              )
              setScore(jobScore)
            }
          } catch (scoreError) {
            // It's okay if we can't get the score
            console.error('Error fetching score:', scoreError)
          }
        }
      } catch (err) {
        console.error('Error fetching job details:', err)
        setError(err instanceof Error ? err.message : 'Failed to load job details')
      } finally {
        setLoading(false)
      }
    }

    fetchJobDetails()
  }, [jobId, userId])

  return {
    job,
    score,
    loading,
    error,
    refetch: () => {
      if (jobId) {
        setJob(null)
        setScore(null)
        // Re-trigger the effect by updating a dependency
        // In this case, we'll use the effect's own logic
      }
    }
  }
}