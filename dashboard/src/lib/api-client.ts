/**
 * Secure API Client
 * All requests go through Next.js API routes (server-side auth)
 * No tokens are exposed to the browser
 */

class SecureAPIClient {
  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    // All API calls now go through our Next.js proxy
    // Authentication is handled server-side automatically
    const response = await fetch(`/api/backend${endpoint}`, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
    })

    if (!response.ok) {
      let errorMessage = 'Request failed'
      
      try {
        const error = await response.json()
        errorMessage = error.detail || error.error || errorMessage
      } catch {
        // If response is not JSON, use status text
        errorMessage = response.statusText || errorMessage
      }

      // User-friendly error messages
      if (response.status === 401) {
        errorMessage = 'Please sign in to continue'
      } else if (response.status === 403) {
        errorMessage = 'You do not have permission to perform this action'
      } else if (response.status === 404) {
        errorMessage = 'The requested resource was not found'
      } else if (response.status >= 500) {
        errorMessage = 'Server error. Please try again later'
      }

      throw new Error(errorMessage)
    }

    // Handle different response types
    const contentType = response.headers.get('content-type')
    if (contentType?.includes('application/json')) {
      return response.json()
    } else if (contentType?.includes('text/')) {
      return response.text() as T
    } else {
      // Binary data (e.g., file downloads)
      return response.blob() as T
    }
  }

  // Auth endpoints (these now just check auth state, no token handling)
  async getCurrentUser() {
    return this.request<{ user_id: string; email: string }>('/auth/me')
  }

  async verifyAuth() {
    return this.request<{ valid: boolean }>('/auth/verify')
  }

  // Resume endpoints
  async uploadResume(file: File, name?: string) {
    const formData = new FormData()
    formData.append('file', file)
    if (name) formData.append('name', name)

    try {
      const response = await fetch('/api/backend/resumes/upload', {
        method: 'POST',
        body: formData,
        // Don't set Content-Type - let browser set it with boundary
      })

      if (!response.ok) {
        let errorMessage = 'Failed to upload resume'
        
        try {
          const errorData = await response.json()
          errorMessage = errorData.detail || errorData.error || errorData.message || errorMessage
        } catch {
          errorMessage = response.statusText || errorMessage
        }
        
        throw new Error(errorMessage)
      }
      
      const data = await response.json()
      return data
    } catch (error: any) {
      // Make sure we always throw an Error with a proper message
      if (error instanceof Error) {
        throw error
      } else if (typeof error === 'string') {
        throw new Error(error)
      } else {
        throw new Error('Failed to upload resume')
      }
    }
  }

  async getResumes() {
    return this.request<Array<any>>('/resumes/')
  }

  async deleteResume(resumeId: string) {
    return this.request<any>(`/resumes/${resumeId}`, {
      method: 'DELETE',
    })
  }

  // Skills vocabulary endpoints
  async uploadSkillsVocabulary(file: File) {
    const formData = new FormData()
    formData.append('file', file)

    try {
      const response = await fetch('/api/backend/resumes/skills-vocab', {
        method: 'POST',
        body: formData,
      })

      if (!response.ok) {
        let errorMessage = 'Failed to upload skills vocabulary'
        
        try {
          const errorData = await response.json()
          errorMessage = errorData.detail || errorData.error || errorData.message || errorMessage
        } catch {
          errorMessage = response.statusText || errorMessage
        }
        
        throw new Error(errorMessage)
      }
      
      return await response.json()
    } catch (error: any) {
      if (error instanceof Error) {
        throw error
      } else if (typeof error === 'string') {
        throw new Error(error)
      } else {
        throw new Error('Failed to upload skills vocabulary')
      }
    }
  }

  async getSkillsVocabulary() {
    return this.request<any>('/resumes/skills-vocab')
  }

  // Job endpoints
  async getJobs(params?: Record<string, any>) {
    const queryString = params ? `?${new URLSearchParams(params)}` : ''
    return this.request<Array<any>>(`/jobs${queryString}`)
  }

  async getJobById(id: string) {
    return this.request<any>(`/jobs/${id}`)
  }

  // Scoring endpoints
  async getScores(resumeId: string, limit: number = 100) {
    try {
      return await this.request<Array<any>>(`/scores?resume_id=${resumeId}&limit=${limit}`)
    } catch (error: any) {
      // If no scores found (404), return empty array instead of throwing
      if (error.message?.includes('not found') || error.message?.includes('404')) {
        return []
      }
      throw error
    }
  }

  async runScoring(resumeId: string, limit: number = 100, minScore: number = 0.5) {
    return this.request<any>('/scores/run', {
      method: 'POST',
      body: JSON.stringify({
        resume_id: resumeId,
        limit,
        min_score: minScore,
      }),
    })
  }

  async exportScores(resumeId: string, format: 'csv' | 'json' = 'csv') {
    const response = await fetch(
      `/api/backend/scores/export?resume_id=${resumeId}&format=${format}&include_details=true`,
      {
        method: 'POST',
      }
    )

    if (!response.ok) {
      throw new Error('Failed to export scores')
    }

    return response.blob()
  }

  // Company research endpoints
  async generateCompanyResearch(companyDomain: string, useCache: boolean = true) {
    return this.request<any>('/research/generate', {
      method: 'POST',
      body: JSON.stringify({ company_domain: companyDomain, use_cache: useCache }),
    })
  }

  async getCompanyResearch(companyDomain: string) {
    return this.request<any>(`/research/${companyDomain}`)
  }

  // Pitch generation endpoints
  async generatePitch(resumeId: string, jobId: string, includeResearch: boolean = true) {
    return this.request<any>('/pitch/generate', {
      method: 'POST',
      body: JSON.stringify({
        resume_id: resumeId,
        job_id: jobId,
        include_research: includeResearch,
        personalization_level: 'high',
      }),
    })
  }

  async generateEmailTemplate(pitchId: string, recipientName?: string) {
    return this.request<any>('/pitch/email-template', {
      method: 'POST',
      body: JSON.stringify({ pitch_id: pitchId, recipient_name: recipientName }),
    })
  }

  async generateInterviewPrep(pitchId: string, interviewType: string = 'general') {
    return this.request<any>('/pitch/interview-prep', {
      method: 'POST',
      body: JSON.stringify({ pitch_id: pitchId, interview_type: interviewType }),
    })
  }

  // Health check
  async healthCheck() {
    // This goes to the public health endpoint
    return fetch('/api/backend/health').then(res => res.json())
  }
}

// Export a singleton instance
export const api = new SecureAPIClient()

// Also export the class for testing
export { SecureAPIClient }