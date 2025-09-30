/**
 * Saved Jobs Service
 * Handles saving and unsaving jobs for users
 */

import { BaseService } from './base.service'

export interface SavedJob {
  id: string
  user_id: string
  job_id: string
  saved_at: string
  notes?: string
  job_postings?: any // Full job details when included
}

export interface SaveJobRequest {
  notes?: string
}

export interface UpdateNotesRequest {
  notes: string
}

export interface CheckSavedResponse {
  is_saved: boolean
  saved_job: SavedJob | null
}

export class SavedJobsService extends BaseService {
  /**
   * Get all saved jobs for the current user
   */
  async getSavedJobs(includeJobDetails: boolean = true): Promise<SavedJob[]> {
    return this.request<SavedJob[]>(
      `/saved-jobs?include_job_details=${includeJobDetails}`
    )
  }

  /**
   * Save a job
   */
  async saveJob(jobId: string, notes?: string): Promise<SavedJob> {
    return this.request<SavedJob>(`/saved-jobs/${jobId}`, {
      method: 'POST',
      body: JSON.stringify({ notes })
    })
  }

  /**
   * Unsave a job
   */
  async unsaveJob(jobId: string): Promise<{ message: string }> {
    return this.request<{ message: string }>(`/saved-jobs/${jobId}`, {
      method: 'DELETE'
    })
  }

  /**
   * Check if a job is saved
   */
  async checkIfSaved(jobId: string): Promise<CheckSavedResponse> {
    return this.request<CheckSavedResponse>(`/saved-jobs/check/${jobId}`)
  }

  /**
   * Update notes for a saved job
   */
  async updateNotes(jobId: string, notes: string): Promise<SavedJob> {
    return this.request<SavedJob>(`/saved-jobs/${jobId}/notes`, {
      method: 'PATCH',
      body: JSON.stringify({ notes })
    })
  }

  /**
   * Get count of saved jobs
   */
  async getSavedJobsCount(): Promise<number> {
    const response = await this.request<{ count: number }>('/saved-jobs/count')
    return response.count
  }

  /**
   * Toggle save status of a job
   * Convenience method that checks status and saves/unsaves accordingly
   */
  async toggleSaveJob(jobId: string): Promise<{ saved: boolean }> {
    const checkResponse = await this.checkIfSaved(jobId)

    if (checkResponse.is_saved) {
      await this.unsaveJob(jobId)
      return { saved: false }
    } else {
      await this.saveJob(jobId)
      return { saved: true }
    }
  }

  /**
   * Check multiple job IDs and return their saved status
   * Useful for displaying save status in lists
   */
  async checkMultipleJobs(jobIds: string[]): Promise<Record<string, boolean>> {
    const savedJobs = await this.getSavedJobs(false)
    const savedJobIds = new Set(savedJobs.map(sj => sj.job_id))

    const result: Record<string, boolean> = {}
    for (const jobId of jobIds) {
      result[jobId] = savedJobIds.has(jobId)
    }

    return result
  }
}

// Export singleton instance
export const savedJobsService = new SavedJobsService()