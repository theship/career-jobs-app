/**
 * CSRF Protection Implementation
 * Double-submit cookie pattern with Origin/Referer validation
 */

import { NextRequest, NextResponse } from 'next/server'
import crypto from 'crypto'

const CSRF_COOKIE_NAME = '__Host-csrf-token'
const CSRF_HEADER_NAME = 'X-CSRF-Token'
const CSRF_TOKEN_LENGTH = 32

/**
 * Generate a cryptographically secure CSRF token
 */
export function generateCSRFToken(): string {
  return crypto.randomBytes(CSRF_TOKEN_LENGTH).toString('hex')
}

/**
 * Set CSRF token cookie with secure flags
 */
export function setCSRFCookie(response: NextResponse, token: string): void {
  response.cookies.set({
    name: CSRF_COOKIE_NAME,
    value: token,
    httpOnly: false, // Must be readable by JavaScript for double-submit
    secure: process.env.NODE_ENV === 'production',
    sameSite: 'strict',
    path: '/',
    maxAge: 60 * 60 * 24, // 24 hours
  })
}

/**
 * Get CSRF token from cookie
 */
export function getCSRFToken(request: NextRequest): string | null {
  return request.cookies.get(CSRF_COOKIE_NAME)?.value || null
}

/**
 * Validate CSRF token for mutation requests
 */
export function validateCSRFToken(
  request: NextRequest,
  options?: {
    skipOriginCheck?: boolean
    allowedOrigins?: string[]
  }
): { valid: boolean; error?: string } {
  // Skip CSRF for safe methods
  if (['GET', 'HEAD', 'OPTIONS'].includes(request.method)) {
    return { valid: true }
  }

  // 1. Check Origin/Referer headers
  if (!options?.skipOriginCheck) {
    const origin = request.headers.get('origin')
    const referer = request.headers.get('referer')
    
    if (!origin && !referer) {
      return { 
        valid: false, 
        error: 'Missing Origin and Referer headers' 
      }
    }

    const requestOrigin = origin || new URL(referer!).origin
    const expectedOrigin = process.env.NEXT_PUBLIC_APP_URL || 'http://localhost:3000'
    const allowedOrigins = options?.allowedOrigins || [expectedOrigin]

    if (!allowedOrigins.includes(requestOrigin)) {
      return { 
        valid: false, 
        error: `Invalid origin: ${requestOrigin}` 
      }
    }
  }

  // 2. Double-submit cookie validation
  const cookieToken = getCSRFToken(request)
  const headerToken = request.headers.get(CSRF_HEADER_NAME)

  if (!cookieToken || !headerToken) {
    return { 
      valid: false, 
      error: 'Missing CSRF token' 
    }
  }

  // Constant-time comparison to prevent timing attacks
  if (!crypto.timingSafeEqual(
    Buffer.from(cookieToken),
    Buffer.from(headerToken)
  )) {
    return { 
      valid: false, 
      error: 'CSRF token mismatch' 
    }
  }

  return { valid: true }
}

/**
 * CSRF middleware for API routes
 */
export async function csrfMiddleware(
  request: NextRequest,
  handler: () => Promise<NextResponse>
): Promise<NextResponse> {
  // Validate CSRF for mutations
  const validation = validateCSRFToken(request)
  
  if (!validation.valid) {
    // Log security event
    console.error('CSRF validation failed:', {
      error: validation.error,
      path: request.url,
      method: request.method,
      ip: request.headers.get('x-forwarded-for') || 'unknown',
    })

    return NextResponse.json(
      { error: 'CSRF validation failed', details: validation.error },
      { status: 403 }
    )
  }

  // Process request
  const response = await handler()

  // Refresh CSRF token if needed
  let token = getCSRFToken(request)
  if (!token) {
    token = generateCSRFToken()
    setCSRFCookie(response, token)
  }

  return response
}

/**
 * Hook for client-side CSRF token management
 */
export function useCSRFToken(): {
  token: string | null
  addToHeaders: (headers: HeadersInit) => HeadersInit
} {
  // Get token from cookie (client-side)
  const getTokenFromCookie = (): string | null => {
    if (typeof document === 'undefined') return null
    
    const match = document.cookie.match(new RegExp(`${CSRF_COOKIE_NAME}=([^;]+)`))
    return match ? match[1] : null
  }

  const token = getTokenFromCookie()

  const addToHeaders = (headers: HeadersInit = {}): HeadersInit => {
    if (!token) return headers

    if (headers instanceof Headers) {
      headers.set(CSRF_HEADER_NAME, token)
      return headers
    }

    if (Array.isArray(headers)) {
      return [...headers, [CSRF_HEADER_NAME, token]]
    }

    return {
      ...headers,
      [CSRF_HEADER_NAME]: token,
    }
  }

  return { token, addToHeaders }
}

/**
 * Fetch wrapper with automatic CSRF token inclusion
 */
export async function secureFetch(
  url: string,
  options: RequestInit = {}
): Promise<Response> {
  // Only add CSRF for mutations to same origin
  const method = options.method?.toUpperCase() || 'GET'
  const needsCSRF = !['GET', 'HEAD', 'OPTIONS'].includes(method)

  if (needsCSRF && typeof document !== 'undefined') {
    const match = document.cookie.match(new RegExp(`${CSRF_COOKIE_NAME}=([^;]+)`))
    const token = match ? match[1] : null

    if (token) {
      const headers = new Headers(options.headers)
      headers.set(CSRF_HEADER_NAME, token)
      options.headers = headers
    }
  }

  return fetch(url, options)
}
