'use client'

interface ProgressStep {
  name: string
  status: 'pending' | 'in_progress' | 'completed' | 'error'
  detail?: string
}

interface ResumeUploadProgressProps {
  steps: ProgressStep[]
  currentStage?: string
  error?: string
}

export default function ResumeUploadProgress({ steps, currentStage, error }: ResumeUploadProgressProps) {
  return (
    <div className="w-full">
      {/* Progress Steps */}
      <div className="relative">
        <div className="overflow-hidden h-2 text-xs flex rounded bg-gray-200">
          <div
            style={{
              width: `${(steps.filter(s => s.status === 'completed').length / steps.length) * 100}%`
            }}
            className="shadow-none flex flex-col text-center whitespace-nowrap text-white justify-center bg-blue-600 transition-all duration-500"
          />
        </div>
        
        {/* Step indicators */}
        <div className="flex justify-between mt-4">
          {steps.map((step, index) => (
            <div key={index} className="flex flex-col items-center flex-1">
              <div
                className={`
                  w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium
                  ${step.status === 'completed' ? 'bg-green-500 text-white' : 
                    step.status === 'in_progress' ? 'bg-blue-500 text-white animate-pulse' :
                    step.status === 'error' ? 'bg-red-500 text-white' :
                    'bg-gray-300 text-gray-600'}
                `}
              >
                {step.status === 'completed' ? '✓' : 
                 step.status === 'error' ? '✕' : 
                 step.status === 'in_progress' ? (
                  <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                 ) : index + 1}
              </div>
              <p className="text-xs mt-2 text-center text-gray-600">
                {step.name}
              </p>
              {step.detail && (
                <p className="text-xs mt-1 text-center text-gray-500">
                  {step.detail}
                </p>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Current Stage Display */}
      {currentStage && !error && (
        <div className="mt-6 bg-blue-50 border border-blue-200 rounded-lg p-4">
          <div className="flex items-center">
            <div className="flex-shrink-0">
              <svg className="h-5 w-5 text-blue-400 animate-spin" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
              </svg>
            </div>
            <div className="ml-3">
              <p className="text-sm text-blue-700">{currentStage}</p>
            </div>
          </div>
        </div>
      )}

      {/* Error Display */}
      {error && (
        <div className="mt-6 bg-red-50 border border-red-200 rounded-lg p-4">
          <div className="flex">
            <div className="flex-shrink-0">
              <svg className="h-5 w-5 text-red-400" viewBox="0 0 20 20" fill="currentColor">
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
              </svg>
            </div>
            <div className="ml-3">
              <p className="text-sm text-red-700">{error}</p>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
