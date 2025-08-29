/**
 * Scoring Service
 * Handles job matching scores and exports
 */

import { BaseService } from './base.service'
import type { Score, ScoringRequest, ScoringResponse } from '@/types/api.types'

export class ScoringService extends BaseService {
  /**
   * Get scores for a resume
   */
  async getScores(resumeId: string, limit: number = 100): Promise<Score[]> {
    try {
      return await this.request<Score[]>(`/scores?resume_id=${resumeId}&limit=${limit}`)
    } catch (error: any) {
      // Return empty array for 404 (no scores yet)
      if (error.status === 404 || error.message?.toLowerCase().includes('not found')) {
        return []
      }
      throw error
    }
  }

  /**
   * Run scoring for a resume against all jobs
   */
  async runScoring(
    resumeId: string,
    limit: number = 100,
    minScore: number = 0.0
  ): Promise<ScoringResponse> {
    return this.request<ScoringResponse>('/scores/run', {
      method: 'POST',
      body: {
        resume_id: resumeId,
        limit,
        min_score: minScore,
      },
    })
  }

  /**
   * Export scores to CSV or JSON
   */
  async exportScores(
    resumeId: string,
    format: 'csv' | 'json' = 'csv',
    includeDetails: boolean = true
  ): Promise<Blob> {
    return this.request<Blob>(
      `/scores/export?resume_id=${resumeId}&format=${format}&include_details=${includeDetails}`,
      {
        method: 'POST',
      }
    )
  }

  /**
   * Get a single score for a specific job
   */
  async getScoreForJob(resumeId: string, jobId: string): Promise<Score | null> {
    try {
      const scores = await this.getScores(resumeId)
      return scores.find(s => s.job_id === jobId) || null
    } catch {
      return null
    }
  }

  /**
   * Download scores as CSV
   */
  async downloadScoresAsCSV(resumeId: string): Promise<void> {
    const blob = await this.exportScores(resumeId, 'csv')
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `job_matches_${resumeId}_${new Date().toISOString().split('T')[0]}.csv`
    document.body.appendChild(a)
    a.click()
    window.URL.revokeObjectURL(url)
    document.body.removeChild(a)
  }
}

// Export singleton instance
export const scoringService = new ScoringService()