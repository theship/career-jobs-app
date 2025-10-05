/**
 * Job Service
 * Handles job listing and detail retrieval
 */

import { BaseService } from './base.service'
import type { Job } from '@/types/api.types'

export interface JobQueryParams {
  limit?: number
  offset?: number
  location?: string
  remote_type?: string
  seniority?: string
  company?: string
}

export class JobService extends BaseService {
  /**
   * Get list of jobs with optional filters
   */
  async getJobs(params?: JobQueryParams): Promise<Job[]> {
    const queryString = params 
      ? `?${new URLSearchParams(params as any).toString()}`
      : ''
    
    return this.request<Job[]>(`/jobs${queryString}`)
  }

  /**
   * Get a specific job by ID
   */
  async getJobById(jobId: string): Promise<Job> {
    return this.request<Job>(`/jobs/${jobId}`)
  }

  /**
   * Search jobs by keyword
   */
  async searchJobs(query: string, limit: number = 20): Promise<Job[]> {
    return this.request<Job[]>(`/jobs/search?q=${encodeURIComponent(query)}&limit=${limit}`)
  }

  /**
   * Get job count
   */
  async getJobCount(): Promise<number> {
    const response = await this.request<{ count: number }>('/jobs/count')
    return response.count
  }

  /**
   * Check if jobs are available
   */
  async hasJobs(): Promise<boolean> {
    try {
      const jobs = await this.getJobs({ limit: 1 })
      return jobs && jobs.length > 0
    } catch {
      return false
    }
  }
}

// Export singleton instance
export const jobService = new JobService()
