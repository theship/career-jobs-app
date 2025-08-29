/**
 * Authentication Service
 * Handles user authentication and session management
 */

import { BaseService } from './base.service'
import type { User } from '@/types/api.types'

export class AuthService extends BaseService {
  /**
   * Get current authenticated user
   */
  async getCurrentUser(): Promise<User> {
    return this.request<User>('/auth/me')
  }

  /**
   * Verify authentication status
   */
  async verifyAuth(): Promise<{ valid: boolean }> {
    return this.request<{ valid: boolean }>('/auth/verify')
  }

  /**
   * Check if user is authenticated
   */
  async isAuthenticated(): Promise<boolean> {
    try {
      const result = await this.verifyAuth()
      return result.valid
    } catch {
      return false
    }
  }
}

// Export singleton instance
export const authService = new AuthService()