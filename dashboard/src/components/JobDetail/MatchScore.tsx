/**
 * Match Score Component
 * Displays user's match score for a job
 */

import type { Score } from '@/types/api.types'

interface MatchScoreProps {
  score: Score | null
}

export default function MatchScore({ score }: MatchScoreProps) {
  if (!score) return null

  // Handle different field names and ensure valid numbers
  const getPercent = (value: any): number => {
    const num = typeof value === 'number' ? value : 0
    return Math.round(num * 100)
  }

  const overallPercent = getPercent((score as any).overall_score || (score as any).total_score)
  const skillsPercent = getPercent((score as any).skills_score || (score as any).skill_overlap)
  const experiencePercent = getPercent((score as any).experience_score || (score as any).seniority_fit)
  const locationPercent = getPercent((score as any).location_score || (score as any).geo_score || 0)

  return (
    <div className="card mb-6">
      <h2 className="text-lg font-semibold mb-4">Your Match Score</h2>
      
      <div className="text-center">
        <div className="text-4xl font-bold text-accent-red">
          {overallPercent}%
        </div>
        <p className="text-text-secondary mt-2">Overall Match</p>
      </div>

      <div className="mt-4 space-y-2">
        <ScoreItem label="Skills Match" value={skillsPercent} />
        <ScoreItem label="Experience Match" value={experiencePercent} />
        <ScoreItem label="Location Match" value={locationPercent} />
      </div>
    </div>
  )
}

function ScoreItem({ label, value }: { label: string; value: number }) {
  return (
    <div className="flex justify-between">
      <span className="text-text-secondary">{label}:</span>
      <span className="font-medium">{value}%</span>
    </div>
  )
}
