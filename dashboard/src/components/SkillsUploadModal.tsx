'use client'

import SkillsVocabularyUpload from './SkillsVocabularyUpload'

interface SkillsUploadModalProps {
  isOpen: boolean
  onClose: () => void
  onSuccess?: () => void
}

export default function SkillsUploadModal({ isOpen, onClose, onSuccess }: SkillsUploadModalProps) {
  if (!isOpen) return null

  const handleSuccess = () => {
    if (onSuccess) {
      onSuccess()
    }
    // Close modal after a short delay to show success message
    setTimeout(() => {
      onClose()
    }, 2000)
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/80 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Modal */}
      <div className="relative max-w-4xl w-full max-h-[90vh] bg-surface border border-border rounded-lg shadow-2xl overflow-hidden">
        {/* Header */}
        <div className="bg-background border-b border-border px-6 py-4 flex items-center justify-between">
          <h2 className="text-xl font-light text-text-primary">Upload Skills Vocabulary</h2>
          <button
            onClick={onClose}
            className="text-text-muted hover:text-text-primary transition-colors"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Content */}
        <div className="p-6 overflow-y-auto max-h-[calc(90vh-80px)]">
          <SkillsVocabularyUpload onSuccess={handleSuccess} />
        </div>
      </div>
    </div>
  )
}
