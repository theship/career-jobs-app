/**
 * Pitch Service
 * Handles AI-powered pitch generation and templates
 */

import { BaseService } from './base.service'
import type { Pitch, PitchRequest } from '@/types/api.types'

export interface EmailTemplateRequest {
  pitch_id: string
  recipient_name?: string
}

export interface InterviewPrepRequest {
  pitch_id: string
  interview_type?: 'general' | 'technical' | 'behavioral'
}

export class PitchService extends BaseService {
  /**
   * Generate a personalized pitch for a job
   */
  async generatePitch(
    resumeId: string,
    jobId: string,
    includeResearch: boolean = true,
    personalizationLevel: 'low' | 'medium' | 'high' = 'high'
  ): Promise<Pitch> {
    const request: PitchRequest = {
      resume_id: resumeId,
      job_id: jobId,
      include_research: includeResearch,
      personalization_level: personalizationLevel,
    }

    return this.request<Pitch>('/pitch/generate', {
      method: 'POST',
      body: request,
    })
  }

  /**
   * Generate email template from a pitch
   */
  async generateEmailTemplate(
    pitchId: string,
    recipientName?: string
  ): Promise<{ subject: string; body: string }> {
    return this.request<{ subject: string; body: string }>('/pitch/email-template', {
      method: 'POST',
      body: {
        pitch_id: pitchId,
        recipient_name: recipientName,
      },
    })
  }

  /**
   * Generate interview preparation materials
   */
  async generateInterviewPrep(
    pitchId: string,
    interviewType: 'general' | 'technical' | 'behavioral' = 'general'
  ): Promise<any> {
    return this.request<any>('/pitch/interview-prep', {
      method: 'POST',
      body: {
        pitch_id: pitchId,
        interview_type: interviewType,
      },
    })
  }

  /**
   * Get pitch quality assessment
   */
  async getPitchQuality(pitchId: string): Promise<{
    quality_scores: any
    improvement_suggestions: string[]
    meets_quality_threshold: boolean
  }> {
    return this.request<any>(`/pitch/quality/${pitchId}`)
  }

  /**
   * Copy pitch to clipboard
   */
  copyPitchToClipboard(pitch: Pitch): void {
    const text = `${pitch.headline}

${pitch.opening}

Key Points:
${pitch.bullet_points.map(point => `• ${point}`).join('\n')}

${pitch.closing_statement}`

    navigator.clipboard.writeText(text)
  }
}

// Export singleton instance
export const pitchService = new PitchService()
