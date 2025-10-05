/**
 * API client for communicating with our FastAPI backend
 * Handles authentication token attachment and API calls
 */
import { createClient } from './supabase'

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

interface RequestOptions extends RequestInit {
  token?: string
}

class APIClient {
  async getAuthToken(): Promise<string | null> {
    const supabase = createClient()
    const { data: { session } } = await supabase.auth.getSession()
    return session?.access_token || null
  }

  private async request<T>(
    endpoint: string,
    options: RequestOptions = {}
  ): Promise<T> {
    const { token, headers = {}, ...restOptions } = options
    
    // Get auth token if not provided
    const authToken = token || await this.getAuthToken()
    
    const requestHeaders: Record<string, string> = {
      'Content-Type': 'application/json',
      ...(headers as Record<string, string>),
    }
    
    if (authToken) {
      requestHeaders['Authorization'] = `Bearer ${authToken}`
    }
    
    const response = await fetch(`${API_BASE_URL}${endpoint}`, {
      ...restOptions,
      headers: requestHeaders,
    })
    
    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: null }))
      let errorMessage = error.detail || ''
      
      // If no specific error detail, provide user-friendly message based on status
      if (!errorMessage) {
        if (response.status === 401 || response.status === 403) {
          errorMessage = 'Please sign in to access this feature.'
        } else if (response.status === 404) {
          errorMessage = 'The requested information could not be found.'
        } else if (response.status === 405) {
          errorMessage = 'This operation is not currently available.'
        } else if (response.status === 429) {
          errorMessage = 'Too many requests. Please wait a moment and try again.'
        } else if (response.status >= 500) {
          errorMessage = 'Our servers are experiencing issues. Please try again later.'
        } else {
          errorMessage = 'Something went wrong. Please try again.'
        }
      }
      
      throw new Error(errorMessage)
    }
    
    return response.json()
  }

  // Auth endpoints
  async getCurrentUser() {
    return this.request<{ user_id: string; email: string }>('/api/v1/auth/me')
  }

  async verifyToken() {
    return this.request<{ valid: boolean; user_id: string }>('/api/v1/auth/verify')
  }

  // Health check
  async healthCheck() {
    return this.request<{ status: string }>('/health')
  }

  // Resume endpoints (Phase 2)
  async uploadResume(file: File) {
    const formData = new FormData()
    formData.append('file', file)
    
    const token = await this.getAuthToken()
    // Token available for upload
    if (token) {
      // Decode the token header to see the kid
      const parts = token.split('.')
      if (parts.length === 3) {
        const header = JSON.parse(atob(parts[0]))
        // Token header set
      }
    }
    
    const response = await fetch(`${API_BASE_URL}/api/v1/resumes/upload`, {
      method: 'POST',
      headers: token ? { 'Authorization': `Bearer ${token}` } : {},
      body: formData,
    })
    
    // Upload response received
    
    if (!response.ok) {
      let errorMessage = 'Failed to upload resume. '
      if (response.status === 413) {
        errorMessage += 'The file is too large. Please upload a smaller file.'
      } else if (response.status === 401 || response.status === 403) {
        errorMessage += 'Please sign in to upload your resume.'
      } else if (response.status === 405) {
        errorMessage += 'This operation is not currently available. Please try again later.'
      } else if (response.status === 415) {
        errorMessage += 'Invalid file format. Please upload a PDF or Word document.'
      } else if (response.status === 500) {
        errorMessage += 'Our servers are experiencing issues. Please try again later.'
      } else {
        errorMessage += 'Please try again or contact support if the problem persists.'
      }
      throw new Error(errorMessage)
    }
    
    return response.json()
  }

  async getResumes() {
    return this.request<Array<any>>('/api/v1/resumes/')
  }

  async deleteResume(resumeId: string) {
    return this.request<any>(`/api/v1/resumes/${resumeId}`, {
      method: 'DELETE',
    })
  }

  // Job endpoints (Phase 3)
  async getJobs(params?: Record<string, any>) {
    const queryString = params ? `?${new URLSearchParams(params)}` : ''
    return this.request<Array<any>>(`/api/v1/jobs${queryString}`)
  }

  async getJobById(id: string) {
    return this.request<any>(`/api/v1/jobs/${id}`)
  }

  // Scoring endpoints (Phase 4)
  async getScores(resumeId: string, limit: number = 100) {
    // Get stored scores from database
    return this.request<Array<any>>(`/api/v1/scores/?resume_id=${resumeId}&limit=${limit}`)
  }

  async runScoring(resumeId: string, limit: number = 100, minScore: number = 0.0) {
    // Calculate new scores (will store in DB automatically)
    return this.request<any>('/api/v1/scores/run', {
      method: 'POST',
      body: JSON.stringify({ 
        resume_id: resumeId,
        limit: limit,
        min_score: minScore
      }),
    })
  }

  // AI Research endpoints (Phase 5)
  async generateCompanyResearch(companyDomain: string, useCache: boolean = true) {
    return this.request<any>('/api/v1/research/generate', {
      method: 'POST',
      body: JSON.stringify({ company_domain: companyDomain, use_cache: useCache }),
    })
  }

  async getCompanyResearch(companyDomain: string) {
    return this.request<any>(`/api/v1/research/${companyDomain}`)
  }

  // AI Pitch endpoints (Phase 5)
  async generatePitch(resumeId: string, jobId: string, includeResearch: boolean = true) {
    return this.request<any>('/api/v1/pitch/generate', {
      method: 'POST',
      body: JSON.stringify({
        resume_id: resumeId,
        job_id: jobId,
        include_research: includeResearch,
        personalization_level: 'high'
      }),
    })
  }

  async generateEmailTemplate(pitchId: string, recipientName?: string) {
    return this.request<any>('/api/v1/pitch/email-template', {
      method: 'POST',
      body: JSON.stringify({ pitch_id: pitchId, recipient_name: recipientName }),
    })
  }

  async generateInterviewPrep(pitchId: string, interviewType: string = 'general') {
    return this.request<any>('/api/v1/pitch/interview-prep', {
      method: 'POST',
      body: JSON.stringify({ pitch_id: pitchId, interview_type: interviewType }),
    })
  }
}

export const apiClient = new APIClient()
