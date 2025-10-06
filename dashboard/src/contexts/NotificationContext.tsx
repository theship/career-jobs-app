'use client'

import React, { createContext, useContext, useState } from 'react'
import Modal from '@/components/ui/Modal'

interface NotificationContextType {
  showSuccess: (message: string, title?: string) => void
  showError: (message: string, title?: string) => void
  showWarning: (message: string, title?: string) => void
  showInfo: (message: string, title?: string) => void
  confirm: (message: string, title?: string) => Promise<boolean>
}

const NotificationContext = createContext<NotificationContextType | undefined>(undefined)

export function NotificationProvider({ children }: { children: React.ReactNode }) {
  const [modal, setModal] = useState<{
    isOpen: boolean
    type: 'success' | 'error' | 'warning' | 'info'
    title?: string
    message: string
    actions?: any[]
  }>({
    isOpen: false,
    type: 'info',
    message: '',
  })

  const showSuccess = (message: string, title?: string) => {
    setModal({
      isOpen: true,
      type: 'success',
      title: title || 'Success',
      message,
      actions: [
        {
          label: 'OK',
          onClick: () => setModal(prev => ({ ...prev, isOpen: false })),
          variant: 'primary',
        },
      ],
    })
  }

  const showError = (message: string, title?: string) => {
    setModal({
      isOpen: true,
      type: 'error',
      title: title || 'Error',
      message,
      actions: [
        {
          label: 'OK',
          onClick: () => setModal(prev => ({ ...prev, isOpen: false })),
          variant: 'primary',
        },
      ],
    })
  }

  const showWarning = (message: string, title?: string) => {
    setModal({
      isOpen: true,
      type: 'warning',
      title: title || 'Warning',
      message,
      actions: [
        {
          label: 'OK',
          onClick: () => setModal(prev => ({ ...prev, isOpen: false })),
          variant: 'primary',
        },
      ],
    })
  }

  const showInfo = (message: string, title?: string) => {
    setModal({
      isOpen: true,
      type: 'info',
      title: title || 'Information',
      message,
      actions: [
        {
          label: 'OK',
          onClick: () => setModal(prev => ({ ...prev, isOpen: false })),
          variant: 'primary',
        },
      ],
    })
  }

  const confirm = (message: string, title?: string): Promise<boolean> => {
    return new Promise((resolve) => {
      setModal({
        isOpen: true,
        type: 'info',
        title: title || 'Confirm',
        message,
        actions: [
          {
            label: 'Cancel',
            onClick: () => {
              setModal(prev => ({ ...prev, isOpen: false }))
              resolve(false)
            },
            variant: 'secondary',
          },
          {
            label: 'Confirm',
            onClick: () => {
              setModal(prev => ({ ...prev, isOpen: false }))
              resolve(true)
            },
            variant: 'primary',
          },
        ],
      })
    })
  }

  return (
    <NotificationContext.Provider value={{ showSuccess, showError, showWarning, showInfo, confirm }}>
      {children}
      <Modal
        isOpen={modal.isOpen}
        onClose={() => setModal(prev => ({ ...prev, isOpen: false }))}
        type={modal.type}
        title={modal.title}
        message={modal.message}
        actions={modal.actions}
      />
    </NotificationContext.Provider>
  )
}

export function useNotification() {
  const context = useContext(NotificationContext)
  if (context === undefined) {
    throw new Error('useNotification must be used within a NotificationProvider')
  }
  return context
}
