/**
 * usePitchGeneration Hook
 * Manages AI pitch generation state and actions
 */

import { useState, useCallback, useEffect } from 'react'
import { pitchService } from '@/services/pitch.service'
import { resumeService } from '@/services/resume.service'
import type { Pitch } from '@/types/api.types'
import { useNotification } from '@/contexts/NotificationContext'
import { useRouter } from 'next/navigation'

const PITCH_CACHE_PREFIX = 'pitch_cache_'

export function usePitchGeneration(jobId: string) {
  const [pitch, setPitch] = useState<Pitch | null>(null)
  const [generating, setGenerating] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const { showSuccess, showError, showInfo } = useNotification()
  const router = useRouter()

  // Load cached pitch on mount
  useEffect(() => {
    if (!jobId) return
    
    try {
      const cacheKey = `${PITCH_CACHE_PREFIX}${jobId}`
      const cached = localStorage.getItem(cacheKey)
      
      if (cached) {
        const { pitch: cachedPitch } = JSON.parse(cached)
        setPitch(cachedPitch)
      }
    } catch (err) {
      console.error('Error loading cached pitch:', err)
    }
  }, [jobId])

  // Save pitch to cache whenever it changes
  const savePitchToCache = useCallback((pitchData: Pitch) => {
    try {
      const cacheKey = `${PITCH_CACHE_PREFIX}${jobId}`
      localStorage.setItem(cacheKey, JSON.stringify({
        pitch: pitchData,
        timestamp: Date.now()
      }))
    } catch (err) {
      console.error('Error saving pitch to cache:', err)
    }
  }, [jobId])

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
      savePitchToCache(pitchData) // Save to localStorage
      showSuccess('Pitch generated successfully!')
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to generate pitch'
      console.error('Error generating pitch:', err)
      setError(errorMessage)
      showError(errorMessage)
    } finally {
      setGenerating(false)
    }
  }, [jobId, showSuccess, showError, showInfo, router, savePitchToCache])

  const copyToClipboard = useCallback(() => {
    if (!pitch) return

    pitchService.copyPitchToClipboard(pitch)
    showSuccess('Pitch copied to clipboard!')
  }, [pitch, showSuccess])

  const regenerate = useCallback(async () => {
    // Clear current pitch and cache
    setPitch(null)
    try {
      const cacheKey = `${PITCH_CACHE_PREFIX}${jobId}`
      localStorage.removeItem(cacheKey)
    } catch (err) {
      console.error('Error clearing pitch cache:', err)
    }
    await generatePitch()
  }, [generatePitch, jobId])

  return {
    pitch,
    generating,
    error,
    generatePitch,
    copyToClipboard,
    regenerate,
  }
}