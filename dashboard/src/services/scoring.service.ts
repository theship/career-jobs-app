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
   * Start async scoring for a resume against all jobs
   * Returns a task_id for SSE streaming
   */
  async startScoring(
    resumeId: string,
    limit: number = 500,
    minScore: number = 0.0,
    batchSize: number = 10
  ): Promise<{ task_id: string; resume_id: string; status: string; message: string }> {
    return this.request<any>('/scores/run', {
      method: 'POST',
      body: {
        resume_id: resumeId,
        limit,
        min_score: minScore,
        batch_size: batchSize,
      },
    })
  }

  /**
   * Stream scoring updates via Server-Sent Events
   * @param taskId The task ID from startScoring
   * @param onUpdate Callback for each update
   * @returns EventSource instance (caller should close when done)
   */
  streamScoringUpdates(
    taskId: string,
    onUpdate: (data: any) => void,
    onError?: (error: any) => void,
    onComplete?: () => void
  ): EventSource {
    const eventSource = new EventSource(`/api/backend/scores/stream/${taskId}`)

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        onUpdate(data)
        
        // Check if complete
        if (data.type === 'complete') {
          eventSource.close()
          onComplete?.()
        }
      } catch (error) {
        console.error('Error parsing SSE data:', error)
      }
    }

    eventSource.onerror = (error) => {
      console.error('SSE error:', error)
      eventSource.close()
      onError?.(error)
    }

    return eventSource
  }

  /**
   * Legacy runScoring method for backward compatibility
   * Now uses async scoring with SSE
   */
  async runScoring(
    resumeId: string,
    limit: number = 500,
    minScore: number = 0.0
  ): Promise<{ results: any[], total_processed: number }> {
    // Start async scoring
    const { task_id } = await this.startScoring(resumeId, limit, minScore)
    
    // Wait for completion and collect results
    return new Promise((resolve, reject) => {
      const results: any[] = []
      let totalProcessed = 0
      
      const eventSource = this.streamScoringUpdates(
        task_id,
        (data) => {
          if (data.type === 'progress') {
            totalProcessed = data.processed
          } else if (data.type === 'complete') {
            totalProcessed = data.total_processed
          }
        },
        (error) => reject(error),
        async () => {
          // Fetch the final scores from database
          const scores = await this.getScores(resumeId, limit)
          resolve({ results: scores, total_processed: totalProcessed })
        }
      )
      
      // Cleanup on error
      setTimeout(() => {
        eventSource.close()
        reject(new Error('Scoring timeout'))
      }, 60000) // 60 second timeout
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