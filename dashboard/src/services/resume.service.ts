/**
 * Resume Service
 * Handles resume upload, management, and skills vocabulary
 */

import { BaseService } from './base.service'
import type { Resume, SkillsVocabulary } from '@/types/api.types'

export class ResumeService extends BaseService {
  /**
   * Upload a new resume
   */
  async uploadResume(file: File, name?: string): Promise<Resume> {
    const formData = new FormData()
    formData.append('file', file)
    if (name) formData.append('name', name)

    return this.uploadFile<Resume>('/resumes/upload', formData)
  }

  /**
   * Get all user's resumes
   */
  async getResumes(): Promise<Resume[]> {
    return this.request<Resume[]>('/resumes/')
  }

  /**
   * Get a specific resume by ID
   */
  async getResumeById(resumeId: string): Promise<Resume> {
    return this.request<Resume>(`/resumes/${resumeId}`)
  }

  /**
   * Delete a resume
   */
  async deleteResume(resumeId: string): Promise<void> {
    await this.request<void>(`/resumes/${resumeId}`, {
      method: 'DELETE',
    })
  }

  /**
   * Upload custom skills vocabulary CSV
   */
  async uploadSkillsVocabulary(file: File): Promise<SkillsVocabulary> {
    const formData = new FormData()
    formData.append('file', file)

    return this.uploadFile<SkillsVocabulary>('/resumes/skills-vocab', formData)
  }

  /**
   * Get current skills vocabulary info
   */
  async getSkillsVocabulary(): Promise<SkillsVocabulary> {
    return this.request<SkillsVocabulary>('/resumes/skills-vocab')
  }

  /**
   * Check if user has uploaded custom skills
   */
  async hasCustomSkills(): Promise<boolean> {
    try {
      const vocab = await this.getSkillsVocabulary()
      return vocab.has_custom_vocab || false
    } catch {
      return false
    }
  }
}

// Export singleton instance
export const resumeService = new ResumeService()