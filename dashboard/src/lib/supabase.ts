/**
 * Supabase client for authentication only
 * All data operations go through our FastAPI backend
 */
import { createBrowserClient } from '@supabase/ssr'

// Client-side Supabase client for auth
export function createClient() {
  return createBrowserClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
  )
}