/**
 * Clear all sensitive data from browser storage on logout
 * This prevents data leakage to other users on the same device
 */

const SENSITIVE_PREFIXES = [
  'pitch_cache_',      // Cached pitch data
  'resume_',           // Any cached resume data
  'job_',              // Cached job data
  'score_',            // Cached scoring data
  'research_',         // Cached research data
  'user_',             // User preferences or data
  'auth_',             // Authentication data
]

/**
 * Clear all sensitive data from localStorage
 * Called on logout to prevent data leakage between users
 */
export function clearSensitiveLocalStorage(): void {
  if (typeof window === 'undefined') return

  try {
    // Get all localStorage keys
    const keys = Object.keys(localStorage)
    
    // Remove items with sensitive prefixes
    keys.forEach(key => {
      // Check if key starts with any sensitive prefix
      const shouldRemove = SENSITIVE_PREFIXES.some(prefix => 
        key.startsWith(prefix)
      )
      
      if (shouldRemove) {
        localStorage.removeItem(key)
        console.log(`Cleared sensitive data: ${key}`)
      }
    })

    // Also clear any Supabase-specific items that might contain user data
    // but preserve necessary auth state for proper logout flow
    const supabaseKeys = keys.filter(key => 
      key.includes('supabase') && 
      !key.includes('auth-token') // Keep auth token for logout process
    )
    
    supabaseKeys.forEach(key => {
      localStorage.removeItem(key)
    })

  } catch (error) {
    console.error('Error clearing sensitive localStorage data:', error)
  }
}

/**
 * Clear all sensitive data from sessionStorage
 */
export function clearSensitiveSessionStorage(): void {
  if (typeof window === 'undefined') return

  try {
    // Get all sessionStorage keys
    const keys = Object.keys(sessionStorage)
    
    // Remove items with sensitive prefixes
    keys.forEach(key => {
      const shouldRemove = SENSITIVE_PREFIXES.some(prefix => 
        key.startsWith(prefix)
      )
      
      if (shouldRemove) {
        sessionStorage.removeItem(key)
      }
    })
  } catch (error) {
    console.error('Error clearing sensitive sessionStorage data:', error)
  }
}

/**
 * Clear all sensitive browser data
 * Should be called on logout
 */
export function clearAllSensitiveData(): void {
  clearSensitiveLocalStorage()
  clearSensitiveSessionStorage()
  
  // Clear any in-memory caches if they exist
  if (typeof window !== 'undefined' && (window as any).__APP_CACHE__) {
    (window as any).__APP_CACHE__ = {}
  }
}