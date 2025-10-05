/**
 * Server-side Supabase clients for secure authentication
 * These clients run on the server and handle cookies securely
 */
import { createServerClient } from '@supabase/ssr'
import { cookies } from 'next/headers'

/**
 * Create a Supabase client for Server Components
 * This client can read cookies but cannot write them
 */
export async function createClient() {
  const cookieStore = await cookies()

  return createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll() {
          return cookieStore.getAll()
        },
        setAll(cookiesToSet) {
          try {
            cookiesToSet.forEach(({ name, value, options }) => {
              cookieStore.set(name, value, options)
            })
          } catch (error) {
            // The `set` method was called from a Server Component.
            // This can be ignored if you have middleware refreshing
            // user sessions.
          }
        },
      },
    }
  )
}

/**
 * Create a Supabase client with service role for admin operations
 * WARNING: This should ONLY be used in secure server-side contexts
 * Never expose the service role key to the client
 */
export async function createServiceClient() {
  const cookieStore = await cookies()

  // Use service role key for elevated permissions
  // This allows bypassing RLS policies for admin operations
  return createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.SUPABASE_SERVICE_ROLE_KEY!,
    {
      cookies: {
        getAll() {
          return cookieStore.getAll()
        },
        setAll(cookiesToSet) {
          try {
            cookiesToSet.forEach(({ name, value, options }) => {
              cookieStore.set(name, value, options)
            })
          } catch (error) {
            // The `set` method was called from a Server Component.
            // This can be ignored if you have middleware refreshing
            // user sessions.
          }
        },
      },
      auth: {
        autoRefreshToken: false,
        persistSession: false,
      },
    }
  )
}

/**
 * Get the current authenticated user from server context
 * This validates the token server-side (secure)
 * @returns User object or null if not authenticated
 */
export async function getUser() {
  const supabase = await createClient()
  
  // getUser() validates the token, unlike getSession()
  // This is the secure way to check authentication server-side
  const {
    data: { user },
    error,
  } = await supabase.auth.getUser()

  if (error || !user) {
    return null
  }

  return user
}

/**
 * Validate user and get auth token for backend API calls
 * This is used by API route handlers to authenticate with FastAPI
 */
export async function getAuthToken() {
  const supabase = await createClient()
  
  const {
    data: { session },
  } = await supabase.auth.getSession()

  return session?.access_token || null
}
