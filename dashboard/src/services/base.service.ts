/**
 * Base Service Class
 * Provides common functionality for all API services
 */

import type { ApiError, RequestOptions } from '@/types/api.types'

interface RequestOptionsWithTimeout extends RequestOptions {
  timeout?: number
}

export abstract class BaseService {
  protected basePath: string = '/api/backend'
  
  // Default timeouts in milliseconds - balanced for production
  private readonly DEFAULT_TIMEOUT_GET = 30000   // 30 seconds for GET (database queries)
  private readonly DEFAULT_TIMEOUT_POST = 60000  // 60 seconds for POST/PUT/DELETE
  private readonly AI_OPERATION_TIMEOUT = 120000 // 2 minutes for AI operations

  /**
   * Get timeout for AI operations
   */
  protected getAITimeout(): number {
    return this.AI_OPERATION_TIMEOUT
  }

  /**
   * Central request method for all API calls
   * Handles authentication automatically through Next.js proxy
   * Includes automatic timeout to prevent hanging requests
   */
  protected async request<T>(
    endpoint: string,
    options: RequestOptionsWithTimeout = {}
  ): Promise<T> {
    const url = `${this.basePath}${endpoint}`
    
    // Determine timeout based on method or use provided timeout
    const timeoutMs = options.timeout || 
      (options.method === 'GET' ? this.DEFAULT_TIMEOUT_GET : this.DEFAULT_TIMEOUT_POST)
    
    // Setup abort controller for timeout
    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), timeoutMs)
    
    try {
      const response = await fetch(url, {
        ...options,
        signal: controller.signal,
        headers: {
          'Content-Type': 'application/json',
          ...options.headers,
        },
        body: options.body ? JSON.stringify(options.body) : undefined,
      })
      
      clearTimeout(timeoutId)

      if (!response.ok) {
        await this.handleError(response)
      }

      return this.handleResponse<T>(response)
    } catch (error: any) {
      clearTimeout(timeoutId)
      
      if (error.name === 'AbortError') {
        throw new Error('Request timeout - please try again')
      }
      throw error
    }
  }

  /**
   * Handle different response types
   */
  private async handleResponse<T>(response: Response): Promise<T> {
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

  /**
   * Handle API errors with user-friendly messages
   */
  private async handleError(response: Response): Promise<never> {
    let errorMessage = 'Request failed'
    let originalError: any = null
    
    try {
      const error: ApiError = await response.json()
      originalError = error
      errorMessage = error.detail || error.error || error.message || errorMessage
    } catch {
      errorMessage = response.statusText || errorMessage
    }

    // User-friendly error messages based on status code
    switch (response.status) {
      case 401:
        errorMessage = 'Please sign in to continue'
        break
      case 403:
        errorMessage = 'You do not have permission to perform this action'
        break
      case 404:
        errorMessage = 'The requested resource was not found'
        break
      case 422:
        // Keep the detailed validation error from backend
        if (originalError?.detail) {
          // Handle FastAPI validation errors
          if (Array.isArray(originalError.detail)) {
            errorMessage = originalError.detail.map((e: any) => e.msg).join(', ')
          } else {
            errorMessage = originalError.detail
          }
        }
        break
      case 500:
      case 502:
      case 503:
        // For server errors in development, show the actual error
        if (process.env.NODE_ENV === 'development' && originalError) {
          errorMessage = originalError.detail || 'Server error. Please try again later'
        } else {
          errorMessage = 'Server error. Please try again later'
        }
        break
    }

    const error = new Error(errorMessage)
    ;(error as any).status = response.status
    ;(error as any).originalError = originalError
    throw error
  }

  /**
   * Handle file upload with FormData
   */
  protected async uploadFile<T>(
    endpoint: string,
    formData: FormData
  ): Promise<T> {
    const response = await fetch(`${this.basePath}${endpoint}`, {
      method: 'POST',
      body: formData,
      // Don't set Content-Type - let browser set it with boundary
    })

    if (!response.ok) {
      await this.handleError(response)
    }

    return this.handleResponse<T>(response)
  }
}
