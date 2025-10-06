'use client'

import { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'

interface ModalProps {
  isOpen: boolean
  onClose: () => void
  title?: string
  message: string
  type?: 'success' | 'error' | 'warning' | 'info'
  actions?: Array<{
    label: string
    onClick: () => void
    variant?: 'primary' | 'secondary' | 'ghost'
  }>
}

export default function Modal({ isOpen, onClose, title, message, type = 'info', actions }: ModalProps) {
  const [mounted, setMounted] = useState(false)

  useEffect(() => {
    setMounted(true)
    return () => setMounted(false)
  }, [])

  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = 'hidden'
    } else {
      document.body.style.overflow = 'unset'
    }
    return () => {
      document.body.style.overflow = 'unset'
    }
  }, [isOpen])

  if (!mounted || !isOpen) return null

  const typeStyles = {
    success: 'text-green-400 border-green-400/20',
    error: 'text-red-400 border-red-400/20',
    warning: 'text-yellow-400 border-yellow-400/20',
    info: 'text-blue-400 border-blue-400/20',
  }

  const icons = {
    success: (
      <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
    ),
    error: (
      <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
    ),
    warning: (
      <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
      </svg>
    ),
    info: (
      <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
    ),
  }

  return createPortal(
    <div 
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      onClick={onClose}
    >
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/80 backdrop-blur-sm" />
      
      {/* Modal */}
      <div 
        className="relative max-w-md w-full bg-surface border border-border rounded-lg p-6 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Close button */}
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-text-muted hover:text-white transition-colors"
        >
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>

        <div className="flex items-start space-x-4">
          <div className={`flex-shrink-0 ${typeStyles[type]}`}>
            {icons[type]}
          </div>
          <div className="flex-1">
            {title && (
              <h3 className="text-lg font-medium text-white mb-1">{title}</h3>
            )}
            <p className="text-text-secondary">{message}</p>
          </div>
        </div>

        {/* Actions */}
        {actions && actions.length > 0 && (
          <div className="mt-6 flex justify-end space-x-3">
            {actions.map((action, index) => (
              <button
                key={index}
                onClick={action.onClick}
                className={
                  action.variant === 'primary'
                    ? 'btn-primary text-sm py-2 px-4'
                    : action.variant === 'ghost'
                    ? 'btn-ghost text-sm py-2 px-4'
                    : 'btn-secondary text-sm py-2 px-4'
                }
              >
                {action.label}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>,
    document.body
  )
}

// Toast notifications for quick feedback
interface ToastProps {
  message: string
  type?: 'success' | 'error' | 'warning' | 'info'
  duration?: number
}

export function Toast({ message, type = 'info', duration = 3000 }: ToastProps) {
  const [isVisible, setIsVisible] = useState(true)

  useEffect(() => {
    const timer = setTimeout(() => {
      setIsVisible(false)
    }, duration)
    return () => clearTimeout(timer)
  }, [duration])

  if (!isVisible) return null

  const typeStyles = {
    success: 'bg-green-900/20 border-green-400/50 text-green-400',
    error: 'bg-red-900/20 border-red-400/50 text-red-400',
    warning: 'bg-yellow-900/20 border-yellow-400/50 text-yellow-400',
    info: 'bg-blue-900/20 border-blue-400/50 text-blue-400',
  }

  return createPortal(
    <div className="fixed top-4 right-4 z-50">
      <div className={`${typeStyles[type]} border rounded-lg px-4 py-3 shadow-lg max-w-sm animate-slide-in-right`}>
        <p className="text-sm">{message}</p>
      </div>
    </div>,
    document.body
  )
}
