'use client'

import { useState, useRef } from 'react'
import { api } from '@/lib/api-client'
import { useNotification } from '@/contexts/NotificationContext'

interface SkillPreview {
  skill: string
  category: string
  aliases: string[]
  tags: string[]
}

export default function SkillsVocabularyUpload({ onSuccess }: { onSuccess?: () => void }) {
  const [file, setFile] = useState<File | null>(null)
  const [preview, setPreview] = useState<SkillPreview[]>([])
  const [uploading, setUploading] = useState(false)
  const [validationErrors, setValidationErrors] = useState<string[]>([])
  const [uploadProgress, setUploadProgress] = useState(0)
  const [processingStage, setProcessingStage] = useState('')
  const [isDragging, setIsDragging] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const { showSuccess, showError, showInfo } = useNotification()

  const validateCSV = (content: string): { valid: boolean; errors: string[]; preview: SkillPreview[] } => {
    const errors: string[] = []
    const preview: SkillPreview[] = []
    
    try {
      const lines = content.trim().split('\n')
      if (lines.length < 2) {
        errors.push('CSV file must contain a header and at least one data row')
        return { valid: false, errors, preview }
      }

      // Parse header
      const header = lines[0].toLowerCase()
      const requiredColumns = ['skill', 'category', 'aliases', 'tags']
      const hasAllColumns = requiredColumns.every(col => header.includes(col))
      
      if (!hasAllColumns) {
        errors.push(`CSV must contain columns: ${requiredColumns.join(', ')}`)
        return { valid: false, errors, preview }
      }

      // Parse data rows
      const headerCols = lines[0].split(',').map(col => col.trim())
      const skillIndex = headerCols.findIndex(col => col.toLowerCase() === 'skill')
      const categoryIndex = headerCols.findIndex(col => col.toLowerCase() === 'category')
      const aliasesIndex = headerCols.findIndex(col => col.toLowerCase() === 'aliases')
      const tagsIndex = headerCols.findIndex(col => col.toLowerCase() === 'tags')

      let validRowCount = 0
      for (let i = 1; i < lines.length && i <= 6; i++) { // Preview first 5 data rows
        const row = lines[i].split(',').map(cell => cell.trim())
        
        if (row[skillIndex] && row[skillIndex].length > 0) {
          preview.push({
            skill: row[skillIndex],
            category: row[categoryIndex] || '',
            aliases: row[aliasesIndex] ? row[aliasesIndex].split('|').map(a => a.trim()) : [],
            tags: row[tagsIndex] ? row[tagsIndex].split('|').map(t => t.trim()) : []
          })
          validRowCount++
        }
      }

      // Count total valid rows
      for (let i = 1; i < lines.length; i++) {
        const row = lines[i].split(',')
        if (row[skillIndex] && row[skillIndex].trim().length > 0) {
          validRowCount++
        }
      }

      if (validRowCount === 0) {
        errors.push('No valid skill entries found in CSV')
      } else {
        showInfo(`Found ${validRowCount} valid skills in CSV`)
      }

      return { valid: errors.length === 0, errors, preview }
    } catch {
      errors.push('Failed to parse CSV file. Please check the format.')
      return { valid: false, errors, preview }
    }
  }

  const processFile = async (selectedFile: File) => {
    if (!selectedFile) return

    // Check file type
    if (!selectedFile.name.toLowerCase().endsWith('.csv')) {
      showError('Please upload a CSV file')
      return
    }

    setFile(selectedFile)
    setValidationErrors([])
    setPreview([])
    setProcessingStage('Reading file...')

    // Read and validate file
    const reader = new FileReader()
    reader.onload = (event) => {
      const content = event.target?.result as string
      setProcessingStage('Validating CSV format...')
      
      const { valid, errors, preview: previewData } = validateCSV(content)
      
      if (valid) {
        setPreview(previewData)
        setProcessingStage('')
        showSuccess(`CSV validated! Ready to upload ${previewData.length}+ skills`)
      } else {
        setValidationErrors(errors)
        setFile(null)
        setProcessingStage('')
        showError('CSV validation failed. Please check the errors.')
      }
    }

    reader.onerror = () => {
      setValidationErrors(['Failed to read file'])
      setFile(null)
      setProcessingStage('')
      showError('Failed to read file')
    }

    reader.readAsText(selectedFile)
  }

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0]
    if (selectedFile) {
      await processFile(selectedFile)
    }
  }

  const handleDragOver = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    e.stopPropagation()
  }

  const handleDragEnter = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragging(true)
  }

  const handleDragLeave = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    e.stopPropagation()
    // Only set dragging to false if we're leaving the drop zone entirely
    const rect = e.currentTarget.getBoundingClientRect()
    const x = e.clientX
    const y = e.clientY
    if (x <= rect.left || x >= rect.right || y <= rect.top || y >= rect.bottom) {
      setIsDragging(false)
    }
  }

  const handleDrop = async (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragging(false)

    const droppedFile = e.dataTransfer.files?.[0]
    if (droppedFile) {
      await processFile(droppedFile)
    }
  }

  const handleUpload = async () => {
    if (!file) return

    setUploading(true)
    setUploadProgress(0)
    setProcessingStage('Uploading skills vocabulary...')

    try {
      // Simulate progress updates
      const progressInterval = setInterval(() => {
        setUploadProgress(prev => Math.min(prev + 10, 90))
      }, 200)

      const result = await api.uploadSkillsVocabulary(file)
      
      clearInterval(progressInterval)
      setUploadProgress(100)
      setProcessingStage('Processing complete!')
      
      // Show success with details
      showSuccess(
        `✓ Custom vocabulary loaded successfully!
        ${result.skills_count} skills in ${result.sample_skills?.length || 0} categories.
        Your custom skills will now be used for resume analysis.`
      )

      // Reset state after short delay
      setTimeout(() => {
        setFile(null)
        setPreview([])
        setUploadProgress(0)
        setProcessingStage('')
        if (onSuccess) onSuccess()
      }, 2000)

    } catch (error: any) {
      console.error('Upload error:', error)
      setProcessingStage('')
      setUploadProgress(0)
      showError(error.message || 'Failed to upload skills vocabulary')
    } finally {
      setUploading(false)
    }
  }

  return (
    <div className="space-y-6">
      {/* Upload Section */}
      <div
        className={`border-2 border-dashed rounded-lg p-6 text-center transition-colors ${
          isDragging
            ? 'border-accent-red bg-accent-red/10'
            : 'border-border hover:border-accent-red/50 bg-surface'
        }`}
        onDragOver={handleDragOver}
        onDragEnter={handleDragEnter}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".csv"
          onChange={handleFileSelect}
          className="hidden"
          id="skills-csv-upload"
          disabled={uploading}
        />
        <label
          htmlFor="skills-csv-upload"
          className="cursor-pointer block"
        >
          <svg
            className={`mx-auto h-12 w-12 ${isDragging ? 'text-accent-red' : 'text-text-muted'}`}
            stroke="currentColor"
            fill="none"
            viewBox="0 0 48 48"
          >
            <path
              d="M28 8H12a4 4 0 00-4 4v20m32-12v8m0 0v8a4 4 0 01-4 4H12a4 4 0 01-4-4v-4m32-4l-3.172-3.172a4 4 0 00-5.656 0L28 28M8 32l9.172-9.172a4 4 0 015.656 0L28 28m0 0l4 4m4-24h8m-4-4v8m-12 4h.02"
              strokeWidth={2}
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
          <p className={`mt-2 text-sm ${isDragging ? 'text-accent-red' : 'text-text-secondary'}`}>
            {file ? file.name : (isDragging ? 'Drop your CSV file here' : 'Click to upload or drag and drop CSV file')}
          </p>
          <p className="text-xs text-text-muted mt-1">
            CSV format: skill, category, aliases (pipe-separated), tags (pipe-separated)
          </p>
        </label>
      </div>

      {/* Processing Stage Display */}
      {processingStage && (
        <div className="bg-surface border border-accent-red/20 rounded-lg p-4">
          <div className="flex items-center">
            <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-accent-red mr-3"></div>
            <span className="text-accent-red">{processingStage}</span>
          </div>
        </div>
      )}

      {/* Validation Errors */}
      {validationErrors.length > 0 && (
        <div className="bg-red-900/20 border border-red-400/20 rounded-lg p-4">
          <h3 className="text-red-400 font-medium mb-2">Validation Errors:</h3>
          <ul className="list-disc list-inside text-sm text-red-400/80">
            {validationErrors.map((error, idx) => (
              <li key={idx}>{error}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Preview Table */}
      {preview.length > 0 && (
        <div className="bg-surface rounded-lg border border-border overflow-hidden">
          <div className="bg-background px-6 py-3 border-b border-border">
            <h3 className="text-sm font-medium text-text-primary">
              Preview (showing first {preview.length} skills)
            </h3>
          </div>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-border">
              <thead className="bg-background">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-text-muted uppercase tracking-wider">
                    Skill
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-text-muted uppercase tracking-wider">
                    Category
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-text-muted uppercase tracking-wider">
                    Aliases
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-text-muted uppercase tracking-wider">
                    Tags
                  </th>
                </tr>
              </thead>
              <tbody className="bg-surface divide-y divide-border">
                {preview.map((skill, idx) => (
                  <tr key={idx} className="hover:bg-background/50">
                    <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-text-primary">
                      {skill.skill}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-text-secondary">
                      {skill.category || '-'}
                    </td>
                    <td className="px-6 py-4 text-sm text-text-secondary">
                      {skill.aliases.length > 0 ? (
                        <div className="flex flex-wrap gap-1">
                          {skill.aliases.map((alias, i) => (
                            <span key={i} className="px-2 py-1 text-xs bg-blue-900/20 text-blue-400 rounded border border-blue-400/20">
                              {alias}
                            </span>
                          ))}
                        </div>
                      ) : '-'}
                    </td>
                    <td className="px-6 py-4 text-sm text-text-secondary">
                      {skill.tags.length > 0 ? (
                        <div className="flex flex-wrap gap-1">
                          {skill.tags.map((tag, i) => (
                            <span key={i} className="px-2 py-1 text-xs bg-green-900/20 text-green-400 rounded border border-green-400/20">
                              {tag}
                            </span>
                          ))}
                        </div>
                      ) : '-'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Upload Progress */}
      {uploading && uploadProgress > 0 && (
        <div className="space-y-2">
          <div className="flex justify-between text-sm text-text-secondary">
            <span>Uploading skills vocabulary...</span>
            <span>{uploadProgress}%</span>
          </div>
          <div className="w-full bg-surface rounded-full h-2 border border-border">
            <div
              className="bg-accent-red h-2 rounded-full transition-all duration-300"
              style={{ width: `${uploadProgress}%` }}
            />
          </div>
        </div>
      )}

      {/* Action Buttons */}
      <div className="flex justify-end space-x-3">
        {file && !uploading && (
          <>
            <button
              onClick={() => {
                setFile(null)
                setPreview([])
                setValidationErrors([])
                setProcessingStage('')
              }}
              className="btn-secondary px-4 py-2"
            >
              Cancel
            </button>
            <button
              onClick={handleUpload}
              disabled={preview.length === 0}
              className="btn-primary px-4 py-2 disabled:opacity-50"
            >
              Upload {preview.length}+ Skills
            </button>
          </>
        )}
      </div>

      {/* Help Text */}
      <div className="bg-surface rounded-lg p-4 border border-border">
        <h4 className="text-sm font-medium text-text-primary mb-2">CSV Format Example:</h4>
        <pre className="text-xs text-text-muted bg-background p-2 rounded border border-border">
{`skill,category,aliases,tags
Python,language,py|python3,backend|scripting
React,framework,ReactJS|React.js,frontend|web
PostgreSQL,database,Postgres|PgSQL,sql|relational`}
        </pre>
      </div>
    </div>
  )
}
