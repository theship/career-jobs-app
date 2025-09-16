'use client'

import CompanyManager from '@/components/CompanyManager'

export default function CompaniesPage() {
  return (
    <main className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="mb-8">
        <h1 className="text-3xl font-light text-text-primary">
          Manage Target Companies
        </h1>
        <p className="text-text-secondary mt-2">
          Add companies you want to track for job opportunities. The system will automatically 
          detect their job board system and fetch new positions regularly.
        </p>
      </div>
      
      <CompanyManager />
    </main>
  )
}