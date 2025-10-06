'use client'

import { useState } from 'react'
import { DocumentTextIcon, TrashIcon } from '@heroicons/react/24/outline'

interface SkillsVocabUploadProps {
  onUpload: (file: File) => Promise<void>
  onDelete?: () => Promise<void>
  currentVocab?: {
    has_custom_vocab: boolean
    skills_count?: number
    uploaded_at?: string
    sample_skills?: string[]
  }
}

export default function SkillsVocabUpload({ onUpload, onDelete, currentVocab }: SkillsVocabUploadProps) {
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  const [dragActive, setDragActive] = useState(false)

  const handleFile = async (file: File) => {
    setError(null)
    setSuccess(null)

    // Validate file type
    if (!file.name.endsWith('.csv')) {
      setError('Please upload a CSV file')
      return
    }

    // Validate file size (max 1MB)
    if (file.size > 1024 * 1024) {
      setError('File size must be less than 1MB')
      return
    }

    setUploading(true)
    try {
      await onUpload(file)
      setSuccess('Skills vocabulary uploaded successfully!')
    } catch (err: any) {
      setError(err.message || 'Failed to upload vocabulary')
    } finally {
      setUploading(false)
    }
  }

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true)
    } else if (e.type === 'dragleave') {
      setDragActive(false)
    }
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setDragActive(false)

    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFile(e.dataTransfer.files[0])
    }
  }

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    e.preventDefault()
    if (e.target.files && e.target.files[0]) {
      handleFile(e.target.files[0])
    }
  }

  const downloadTemplate = () => {
    const csvContent = `skill,category,aliases,tags
Python,Programming,py|python3,backend|data-science
JavaScript,Programming,js|es6|nodejs,frontend|fullstack
React,Frontend,reactjs,ui|component
PostgreSQL,Database,postgres|psql,sql|rdbms
Docker,DevOps,containers,deployment|infrastructure
Kubernetes,DevOps,k8s|k8,orchestration|containers
AWS,Cloud,amazon-web-services,infrastructure|cloud
Machine Learning,AI/ML,ml|ML,ai|data-science
Git,Tools,github|gitlab,version-control
REST API,Backend,restful|rest,api|web-services`

    const blob = new Blob([csvContent], { type: 'text/csv' })
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'skills_vocab_template.csv'
    document.body.appendChild(a)
    a.click()
    window.URL.revokeObjectURL(url)
    document.body.removeChild(a)
  }

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-start">
        <div>
          <h3 className="text-lg font-medium text-gray-900">Custom Skills Vocabulary</h3>
          <p className="mt-1 text-sm text-gray-600">
            Upload a CSV file to customize skill extraction for your resumes
          </p>
        </div>
        <button
          onClick={downloadTemplate}
          className="text-sm text-blue-600 hover:text-blue-800"
        >
          Download Template
        </button>
      </div>

      {currentVocab?.has_custom_vocab ? (
        <div className="bg-green-50 border border-green-200 rounded-lg p-4">
          <div className="flex justify-between items-start">
            <div>
              <p className="text-sm font-medium text-green-800">
                Custom vocabulary active
              </p>
              <p className="text-sm text-green-700 mt-1">
                {currentVocab.skills_count} skills loaded
              </p>
              {currentVocab.uploaded_at && (
                <p className="text-xs text-green-600 mt-1">
                  Uploaded: {new Date(currentVocab.uploaded_at).toLocaleDateString()}
                </p>
              )}
              {currentVocab.sample_skills && currentVocab.sample_skills.length > 0 && (
                <div className="mt-2">
                  <p className="text-xs text-green-700">Sample skills:</p>
                  <div className="flex flex-wrap gap-1 mt-1">
                    {currentVocab.sample_skills.slice(0, 5).map((skill) => (
                      <span
                        key={skill}
                        className="px-2 py-0.5 text-xs bg-white border border-green-300 rounded"
                      >
                        {skill}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
            {onDelete && (
              <button
                onClick={async () => {
                  if (confirm('Remove custom vocabulary and use default?')) {
                    await onDelete()
                  }
                }}
                className="text-red-600 hover:text-red-800"
              >
                <TrashIcon className="w-5 h-5" />
              </button>
            )}
          </div>
        </div>
      ) : (
        <div
          className={`border-2 border-dashed rounded-lg p-6 text-center ${
            dragActive ? 'border-blue-500 bg-blue-50' : 'border-gray-300'
          }`}
          onDragEnter={handleDrag}
          onDragLeave={handleDrag}
          onDragOver={handleDrag}
          onDrop={handleDrop}
        >
          <DocumentTextIcon className="mx-auto h-12 w-12 text-gray-400" />
          <div className="mt-4">
            <label className="cursor-pointer">
              <span className="text-sm font-medium text-blue-600 hover:text-blue-800">
                Upload CSV file
              </span>
              <input
                type="file"
                className="hidden"
                accept=".csv"
                onChange={handleChange}
                disabled={uploading}
              />
            </label>
            <p className="text-xs text-gray-500 mt-1">or drag and drop</p>
          </div>
          <p className="text-xs text-gray-500 mt-2">
            CSV must include: skill, category, aliases, tags columns
          </p>
        </div>
      )}

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-md p-3">
          <p className="text-sm text-red-800">{error}</p>
        </div>
      )}

      {success && (
        <div className="bg-green-50 border border-green-200 rounded-md p-3">
          <p className="text-sm text-green-800">{success}</p>
        </div>
      )}

      {uploading && (
        <div className="text-center py-2">
          <div className="inline-block animate-spin rounded-full h-6 w-6 border-b-2 border-blue-600"></div>
          <p className="text-sm text-gray-600 mt-1">Uploading...</p>
        </div>
      )}

      <div className="bg-gray-50 rounded-lg p-3">
        <h4 className="text-sm font-medium text-gray-900">CSV Format Requirements:</h4>
        <ul className="mt-2 text-xs text-gray-600 space-y-1">
          <li>• <strong>skill</strong>: The canonical skill name (required)</li>
          <li>• <strong>category</strong>: Category like "Programming", "Database", etc.</li>
          <li>• <strong>aliases</strong>: Alternative names separated by | (e.g., "py|python3")</li>
          <li>• <strong>tags</strong>: Comma-separated tags (e.g., "backend,data-science")</li>
        </ul>
      </div>
    </div>
  )
}
