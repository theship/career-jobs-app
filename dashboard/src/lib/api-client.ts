/**
 * API Client
 * Uses modular service architecture for better organization
 * All authentication handled server-side through Next.js proxy
 */

import { 
  authService,
  resumeService,
  jobService,
  scoringService,
  pitchService 
} from '@/services'

// Re-export all services
export {
  authService,
  resumeService,
  jobService,
  scoringService,
  pitchService
}

// Create a unified API interface for backward compatibility
export const api = {
  // Auth methods
  getCurrentUser: () => authService.getCurrentUser(),
  verifyAuth: () => authService.verifyAuth(),

  // Resume methods
  uploadResume: (file: File, name?: string) => resumeService.uploadResume(file, name),
  getResumes: () => resumeService.getResumes(),
  deleteResume: (resumeId: string) => resumeService.deleteResume(resumeId),
  uploadSkillsVocabulary: (file: File) => resumeService.uploadSkillsVocabulary(file),
  getSkillsVocabulary: () => resumeService.getSkillsVocabulary(),

  // Job methods
  getJobs: (params?: any) => jobService.getJobs(params),
  getJobById: (id: string) => jobService.getJobById(id),

  // Scoring methods
  getScores: (resumeId: string | number, limit?: number) => scoringService.getScores(String(resumeId), limit),
  runScoring: (resumeId: string | number, limit?: number, minScore?: number) => 
    scoringService.runScoring(String(resumeId), limit, minScore),
  exportScores: (resumeId: string, format?: 'csv' | 'json') => 
    scoringService.exportScores(resumeId, format),
  
  // Direct access to scoring service for SSE methods
  scoringService,

  // Pitch methods
  generatePitch: (resumeId: string, jobId: string, includeResearch?: boolean) =>
    pitchService.generatePitch(resumeId, jobId, includeResearch),
  generateEmailTemplate: (pitchId: string, recipientName?: string) =>
    pitchService.generateEmailTemplate(pitchId, recipientName),
  generateInterviewPrep: (pitchId: string, interviewType?: string) =>
    pitchService.generateInterviewPrep(pitchId, interviewType as any),

  // Health check (doesn't belong to a specific service)
  healthCheck: async () => {
    const response = await fetch('/api/backend/health')
    return response.json()
  }
}

// Export for gradual migration
export default api