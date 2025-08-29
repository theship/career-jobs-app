/**
 * usePitchGeneration Hook
 * Manages AI pitch generation state and actions
 */

import { useState, useCallback } from 'react'
import { pitchService } from '@/services/pitch.service'
import { resumeService } from '@/services/resume.service'
import type { Pitch } from '@/types/api.types'
import { useNotification } from '@/contexts/NotificationContext'
import { useRouter } from 'next/navigation'

export function usePitchGeneration(jobId: string) {
  const [pitch, setPitch] = useState<Pitch | null>(null)
  const [generating, setGenerating] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const { showSuccess, showError, showInfo } = useNotification()
  const router = useRouter()

  const generatePitch = useCallback(async () => {
    setGenerating(true)
    setError(null)

    try {
      // Get user's resumes
      const resumes = await resumeService.getResumes()
      
      if (!resumes || resumes.length === 0) {
        showInfo('Please upload a resume first to generate a pitch')
        router.push('/dashboard')
        return
      }

      // Generate pitch using the first resume
      // Ensure resume_id is a string (database might return number)
      const resumeId = String(resumes[0].resume_id)
      const pitchData = await pitchService.generatePitch(
        resumeId,
        jobId,
        true // include research
      )

      setPitch(pitchData)
      showSuccess('Pitch generated successfully!')
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to generate pitch'
      console.error('Error generating pitch:', err)
      setError(errorMessage)
      showError(errorMessage)
    } finally {
      setGenerating(false)
    }
  }, [jobId, showSuccess, showError, showInfo, router])

  const copyToClipboard = useCallback(() => {
    if (!pitch) return

    pitchService.copyPitchToClipboard(pitch)
    showSuccess('Pitch copied to clipboard!')
  }, [pitch, showSuccess])

  const regenerate = useCallback(async () => {
    setPitch(null)
    await generatePitch()
  }, [generatePitch])

  return {
    pitch,
    generating,
    error,
    generatePitch,
    copyToClipboard,
    regenerate,
  }
}