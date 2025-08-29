/**
 * Pitch Generator Component
 * Handles AI pitch generation and display
 */

import type { Pitch } from '@/types/api.types'

interface PitchGeneratorProps {
  pitch: Pitch | null
  generating: boolean
  onGenerate: () => void
  onCopyToClipboard: () => void
  onRegenerate: () => void
  isAuthenticated: boolean
}

export default function PitchGenerator({
  pitch,
  generating,
  onGenerate,
  onCopyToClipboard,
  onRegenerate,
  isAuthenticated,
}: PitchGeneratorProps) {
  return (
    <div className="card">
      <h2 className="text-lg font-semibold mb-4">AI Application Assistant</h2>
      
      {!pitch ? (
        <div>
          <p className="text-text-secondary text-sm mb-4">
            Generate a personalized pitch for this position using AI
          </p>
          <button
            onClick={onGenerate}
            disabled={generating || !isAuthenticated}
            className="w-full btn-primary disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {generating ? 'Generating...' : isAuthenticated ? 'Generate AI Pitch' : 'Sign in to Generate Pitch'}
          </button>
        </div>
      ) : (
        <div className="space-y-4">
          <PitchSection title="Headline" content={pitch.headline} />
          <PitchSection title="Opening" content={pitch.opening} />
          
          <div>
            <h3 className="font-medium mb-1">Key Points</h3>
            <ul className="list-disc list-inside text-sm text-text-secondary space-y-1">
              {pitch.bullet_points?.map((point: string, idx: number) => (
                <li key={idx}>{point}</li>
              ))}
            </ul>
          </div>

          <button
            onClick={onCopyToClipboard}
            className="w-full bg-green-600/90 hover:bg-green-600 text-white py-2 px-4 rounded-lg text-sm transition-all"
          >
            Copy to Clipboard
          </button>

          <button
            onClick={onRegenerate}
            className="w-full btn-secondary text-sm"
          >
            Regenerate Pitch
          </button>
        </div>
      )}
    </div>
  )
}

function PitchSection({ title, content }: { title: string; content: string }) {
  return (
    <div>
      <h3 className="font-medium mb-1">{title}</h3>
      <p className="text-sm text-text-secondary">{content}</p>
    </div>
  )
}