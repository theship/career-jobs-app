/**
 * Pitch Generator Component
 * Handles AI pitch generation and display
 */

import type { Pitch } from '@/types/api.types'

interface PitchGeneratorProps {
  pitch: Pitch | null
  generating: boolean
  error: string | null
  onGenerate: () => void
  onCopyToClipboard: () => void
  onRegenerate: () => void
  isAuthenticated: boolean
}

export default function PitchGenerator({
  pitch,
  generating,
  error,
  onGenerate,
  onCopyToClipboard,
  onRegenerate,
  isAuthenticated,
}: PitchGeneratorProps) {
  return (
    <div className="card">
      <h2 className="text-lg font-semibold mb-4">AI Application Assistant</h2>
      
      {error ? (
        <div className="text-red-500 text-center">
          <p className="font-semibold">Error generating pitch</p>
          <p className="text-sm mt-2">{error}</p>
          <button
            onClick={onGenerate}
            className="mt-4 btn-secondary text-sm"
          >
            Try Again
          </button>
        </div>
      ) : !pitch ? (
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
          {/* Action buttons at the top */}
          <div className="flex gap-2">
            <button
              onClick={onCopyToClipboard}
              className="flex-1 bg-green-600/90 hover:bg-green-600 text-white py-2 px-4 rounded-lg text-sm transition-all"
            >
              📋 Copy to Clipboard
            </button>
            <button
              onClick={onRegenerate}
              disabled={generating}
              className="flex-1 btn-secondary text-sm disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {generating ? 'Regenerating...' : '🔄 Regenerate Pitch'}
            </button>
          </div>

          <hr className="border-border" />

          <PitchSection title="Headline" content={pitch.headline} />
          <PitchSection title="Opening" content={pitch.opening} />
          
          {pitch.two_minute_pitch && (
            <div>
              <h3 className="font-medium mb-1">Details</h3>
              <div className="text-sm text-text-secondary whitespace-pre-wrap">
                {pitch.two_minute_pitch}
              </div>
            </div>
          )}
          
          <div>
            <h3 className="font-medium mb-1">Key Points</h3>
            <ul className="list-disc list-inside text-sm text-text-secondary space-y-1">
              {pitch.bullet_points?.map((point: string, idx: number) => (
                <li key={idx}>{point}</li>
              ))}
            </ul>
          </div>
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