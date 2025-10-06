/**
 * Job Info Component
 * Displays detailed job information
 */

import type { Job } from '@/types/api.types'

interface JobInfoProps {
  job: Job
}

export default function JobInfo({ job }: JobInfoProps) {
  return (
    <div className="card">
      <h1 className="text-3xl font-bold text-text-primary">{job.title}</h1>
      <p className="text-xl text-text-secondary mt-2">{job.company_name}</p>
      <p className="text-text-muted mt-1">{job.location}</p>

      <div className="flex gap-2 mt-4">
        {job.seniority && (
          <Badge variant="blue">{job.seniority}</Badge>
        )}
        {job.remote_type && (
          <Badge variant="green">{job.remote_type}</Badge>
        )}
        {job.employment_type && (
          <Badge variant="purple">{job.employment_type}</Badge>
        )}
      </div>

      {job.description && (
        <Section title="Description">
          <p className="text-text-secondary whitespace-pre-wrap">{job.description}</p>
        </Section>
      )}

      {job.responsibilities && job.responsibilities.length > 0 && (
        <Section title="Responsibilities">
          <BulletList items={job.responsibilities} />
        </Section>
      )}

      {job.requirements && job.requirements.length > 0 && (
        <Section title="Requirements">
          <BulletList items={job.requirements} />
        </Section>
      )}

      {job.benefits && job.benefits.length > 0 && (
        <Section title="Benefits">
          <BulletList items={job.benefits} />
        </Section>
      )}
    </div>
  )
}

function Badge({ 
  children, 
  variant 
}: { 
  children: React.ReactNode
  variant: 'blue' | 'green' | 'purple' 
}) {
  const variantStyles = {
    blue: 'bg-blue-900/20 text-blue-400 border-blue-400/20',
    green: 'bg-green-100 text-green-700',
    purple: 'bg-purple-100 text-purple-700',
  }

  return (
    <span className={`px-3 py-1 text-sm rounded border ${variantStyles[variant]}`}>
      {children}
    </span>
  )
}

function Section({ 
  title, 
  children 
}: { 
  title: string
  children: React.ReactNode 
}) {
  return (
    <div className="mt-6">
      <h2 className="text-lg font-semibold mb-2">{title}</h2>
      {children}
    </div>
  )
}

function BulletList({ items }: { items: string[] }) {
  return (
    <ul className="list-disc list-inside space-y-1">
      {items.map((item: string, idx: number) => (
        <li key={idx} className="text-text-secondary">{item}</li>
      ))}
    </ul>
  )
}
