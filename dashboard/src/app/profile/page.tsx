'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { createClient } from '@/lib/supabase'
import { api } from '@/lib/api-client'
import { useNotification } from '@/contexts/NotificationContext'

export default function ProfilePage() {
  const [user, setUser] = useState<any>(null)
  const [profile, setProfile] = useState<any>(null)
  const [resumes, setResumes] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [editing, setEditing] = useState(false)
  const [formData, setFormData] = useState({
    name: '',
    phone: '',
    location: '',
    linkedin: '',
    github: '',
    portfolio: ''
  })
  const router = useRouter()
  const supabase = createClient()
  const { showSuccess, showError, showInfo } = useNotification()

  useEffect(() => {
    checkAuth()
  }, [])

  const checkAuth = async () => {
    const { data: { user } } = await supabase.auth.getUser()
    if (!user) {
      router.push('/login')
      return
    }
    setUser(user)
    fetchProfile()
    fetchResumes()
  }

  const fetchProfile = async () => {
    try {
      const { data: { user } } = await supabase.auth.getUser()
      if (user) {
        setFormData({
          name: user.user_metadata?.name || '',
          phone: user.user_metadata?.phone || '',
          location: user.user_metadata?.location || '',
          linkedin: user.user_metadata?.linkedin || '',
          github: user.user_metadata?.github || '',
          portfolio: user.user_metadata?.portfolio || ''
        })
        setProfile(user.user_metadata)
      }
    } catch (error) {
      console.error('Error fetching profile:', error)
    } finally {
      setLoading(false)
    }
  }

  const fetchResumes = async () => {
    try {
      const resumeData = await api.getResumes()
      setResumes(resumeData || [])
    } catch (error) {
      console.error('Error fetching resumes:', error)
    }
  }

  const handleUpdateProfile = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)

    try {
      const { error } = await supabase.auth.updateUser({
        data: formData
      })

      if (error) {
        showError('Failed to update profile. Please try again.')
      } else {
        showSuccess('Profile updated successfully!')
        setProfile(formData)
        setEditing(false)
      }
    } catch (err) {
      showError('An unexpected error occurred while updating your profile.')
    } finally {
      setLoading(false)
    }
  }

  const handleDeleteResume = async (resumeId: string) => {
    try {
      await api.deleteResume(resumeId)
      showSuccess('Resume deleted successfully')
      fetchResumes()
    } catch (error) {
      showError('Failed to delete resume. Please try again.')
    }
  }

  const handleSignOut = async () => {
    // Clear all sensitive data from localStorage before signing out
    const { clearAllSensitiveData } = await import('@/lib/clear-sensitive-data')
    clearAllSensitiveData()
    
    await supabase.auth.signOut()
    router.push('/')
  }

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="spinner"></div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-background">
      {/* Navigation */}
      <nav className="border-b border-border bg-surface/50 backdrop-blur-lg sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between h-16">
            <div className="flex items-center">
              <Link href="/" className="text-xl font-bold text-gradient-red">
                Career Jobs App
              </Link>
            </div>
            <div className="flex items-center space-x-4">
              <Link href="/dashboard" className="nav-link">
                Dashboard
              </Link>
              <Link href="/jobs" className="nav-link">
                Browse Jobs
              </Link>
              <Link href="/profile" className="nav-link nav-link-active">
                Profile
              </Link>
              <button
                onClick={handleSignOut}
                className="btn-ghost text-sm"
              >
                Sign Out
              </button>
            </div>
          </div>
        </div>
      </nav>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <h1 className="text-3xl font-light text-text-primary mb-8">Your Profile</h1>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Profile Information */}
          <div className="lg:col-span-2">
            <div className="card">
              <div className="flex justify-between items-center mb-6">
                <h2 className="text-xl font-medium text-text-primary">Profile Information</h2>
                {!editing && (
                  <button
                    onClick={() => setEditing(true)}
                    className="btn-secondary text-sm"
                  >
                    Edit Profile
                  </button>
                )}
              </div>

              {editing ? (
                <form onSubmit={handleUpdateProfile} className="space-y-4">
                  <div>
                    <label className="input-label">Name</label>
                    <input
                      type="text"
                      value={formData.name}
                      onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                      className="w-full input-dark"
                      placeholder="Your full name"
                    />
                  </div>

                  <div>
                    <label className="input-label">Email</label>
                    <input
                      type="email"
                      value={user?.email || ''}
                      disabled
                      className="w-full input-dark opacity-50"
                    />
                    <p className="text-xs text-text-muted mt-1">Email cannot be changed</p>
                  </div>

                  <div>
                    <label className="input-label">Phone</label>
                    <input
                      type="tel"
                      value={formData.phone}
                      onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                      className="w-full input-dark"
                      placeholder="+1 (555) 123-4567"
                    />
                  </div>

                  <div>
                    <label className="input-label">Location</label>
                    <input
                      type="text"
                      value={formData.location}
                      onChange={(e) => setFormData({ ...formData, location: e.target.value })}
                      className="w-full input-dark"
                      placeholder="San Francisco, CA"
                    />
                  </div>

                  <div>
                    <label className="input-label">LinkedIn</label>
                    <input
                      type="url"
                      value={formData.linkedin}
                      onChange={(e) => setFormData({ ...formData, linkedin: e.target.value })}
                      className="w-full input-dark"
                      placeholder="https://linkedin.com/in/yourprofile"
                    />
                  </div>

                  <div>
                    <label className="input-label">GitHub</label>
                    <input
                      type="url"
                      value={formData.github}
                      onChange={(e) => setFormData({ ...formData, github: e.target.value })}
                      className="w-full input-dark"
                      placeholder="https://github.com/yourusername"
                    />
                  </div>

                  <div>
                    <label className="input-label">Portfolio</label>
                    <input
                      type="url"
                      value={formData.portfolio}
                      onChange={(e) => setFormData({ ...formData, portfolio: e.target.value })}
                      className="w-full input-dark"
                      placeholder="https://yourportfolio.com"
                    />
                  </div>

                  <div className="flex gap-4">
                    <button
                      type="submit"
                      disabled={loading}
                      className="btn-primary disabled:opacity-50"
                    >
                      Save Changes
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        setEditing(false)
                        fetchProfile()
                      }}
                      className="btn-ghost"
                    >
                      Cancel
                    </button>
                  </div>
                </form>
              ) : (
                <div className="space-y-4">
                  <div>
                    <p className="text-text-muted text-sm">Name</p>
                    <p className="text-text-primary">{profile?.name || 'Not set'}</p>
                  </div>

                  <div>
                    <p className="text-text-muted text-sm">Email</p>
                    <p className="text-text-primary">{user?.email}</p>
                  </div>

                  <div>
                    <p className="text-text-muted text-sm">Phone</p>
                    <p className="text-text-primary">{profile?.phone || 'Not set'}</p>
                  </div>

                  <div>
                    <p className="text-text-muted text-sm">Location</p>
                    <p className="text-text-primary">{profile?.location || 'Not set'}</p>
                  </div>

                  {profile?.linkedin && (
                    <div>
                      <p className="text-text-muted text-sm">LinkedIn</p>
                      <a href={profile.linkedin} target="_blank" rel="noopener noreferrer" className="text-accent-red hover:text-accent-red-light transition-colors">
                        {profile.linkedin}
                      </a>
                    </div>
                  )}

                  {profile?.github && (
                    <div>
                      <p className="text-text-muted text-sm">GitHub</p>
                      <a href={profile.github} target="_blank" rel="noopener noreferrer" className="text-accent-red hover:text-accent-red-light transition-colors">
                        {profile.github}
                      </a>
                    </div>
                  )}

                  {profile?.portfolio && (
                    <div>
                      <p className="text-text-muted text-sm">Portfolio</p>
                      <a href={profile.portfolio} target="_blank" rel="noopener noreferrer" className="text-accent-red hover:text-accent-red-light transition-colors">
                        {profile.portfolio}
                      </a>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>

          {/* Resumes Section */}
          <div className="lg:col-span-1">
            <div className="card">
              <h2 className="text-xl font-medium text-text-primary mb-4">Your Resumes</h2>
              
              {resumes.length > 0 ? (
                <div className="space-y-3">
                  {resumes.map((resume) => (
                    <div key={resume.resume_id} className="p-3 bg-surface rounded-lg border border-border">
                      <div className="flex justify-between items-start">
                        <div className="flex-1">
                          <p className="text-sm font-medium text-text-primary">
                            {resume.filename || 'Resume'}
                          </p>
                          <p className="text-xs text-text-muted mt-1">
                            Uploaded {new Date(resume.created_at).toLocaleDateString()}
                          </p>
                        </div>
                        <button
                          onClick={() => handleDeleteResume(resume.resume_id)}
                          className="text-red-400 hover:text-red-300 text-sm transition-colors"
                        >
                          Delete
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center py-4">
                  <p className="text-text-secondary text-sm mb-3">No resumes uploaded</p>
                  <Link href="/dashboard" className="btn-primary text-sm inline-block">
                    Upload Resume
                  </Link>
                </div>
              )}
            </div>

            {/* Account Actions */}
            <div className="card mt-6">
              <h2 className="text-xl font-medium text-text-primary mb-4">Account</h2>
              <div className="space-y-3">
                <button
                  onClick={() => showInfo('Password reset functionality coming soon!')}
                  className="w-full btn-secondary text-sm"
                >
                  Change Password
                </button>
                <button
                  onClick={() => showInfo('Account deletion is not available in demo mode')}
                  className="w-full text-red-400 hover:text-red-300 py-2 px-4 border border-red-400/50 rounded-lg text-sm transition-colors"
                >
                  Delete Account
                </button>
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  )
}