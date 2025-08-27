/**
 * API Route Proxy to FastAPI Backend
 * Handles authentication server-side and forwards requests securely
 */
import { NextRequest, NextResponse } from 'next/server'
import { getUser, getAuthToken } from '@/lib/supabase-server'

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8000'

// Define which paths require authentication (relative to /api/backend/)
const PUBLIC_PATHS = ['health', '']
const isPublicPath = (path: string) => {
  return PUBLIC_PATHS.some(publicPath => path === publicPath || path.startsWith(`${publicPath}/`))
}

async function handleRequest(
  request: NextRequest,
  method: string,
  params: { path: string[] }
) {
  const path = params.path?.join('/') || ''
  
  // Special handling for health endpoint (not under /api/v1)
  const backendPath = path === 'health' ? '/health' : `/api/v1/${path}`
  const url = `${BACKEND_URL}${backendPath}`

  // Check authentication for protected endpoints
  if (!isPublicPath(path)) {
    const user = await getUser()
    if (!user) {
      return NextResponse.json(
        { error: 'Unauthorized' },
        { status: 401 }
      )
    }
  }

  // Get the auth token to forward to backend
  const token = await getAuthToken()
  
  // Log for debugging
  if (!token) {
    console.warn(`No auth token available for ${backendPath}`)
  }

  // Prepare headers
  const headers: HeadersInit = {
    'Content-Type': 'application/json',
  }

  // Add auth token if available
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }

  // Add service identifier for backend to trust this request
  // The backend can verify this is really our Next.js server
  if (process.env.SERVICE_SECRET) {
    headers['X-Service-Secret'] = process.env.SERVICE_SECRET
  }

  // Prepare request options
  const requestOptions: RequestInit = {
    method,
    headers,
  }

  // Handle body for non-GET requests
  if (method !== 'GET' && method !== 'HEAD') {
    const contentType = request.headers.get('content-type')
    
    if (contentType?.includes('multipart/form-data')) {
      // Handle file uploads
      const formData = await request.formData()
      delete (headers as any)['Content-Type'] // Let fetch set the boundary
      requestOptions.body = formData
    } else {
      // Handle JSON or text body
      try {
        const body = await request.text()
        if (body) {
          requestOptions.body = body
        }
      } catch (error) {
        // No body or invalid body
      }
    }
  }

  try {
    // Forward request to backend
    const response = await fetch(url, requestOptions)
    
    // Get response data
    const contentType = response.headers.get('content-type')
    let data

    if (contentType?.includes('application/json')) {
      data = await response.json()
    } else if (contentType?.includes('text/')) {
      data = await response.text()
    } else {
      // Binary data (e.g., CSV download)
      const buffer = await response.arrayBuffer()
      return new NextResponse(buffer, {
        status: response.status,
        headers: {
          'Content-Type': contentType || 'application/octet-stream',
          'Content-Disposition': response.headers.get('content-disposition') || '',
        },
      })
    }

    // Return JSON response
    return NextResponse.json(data, { status: response.status })
  } catch (error) {
    console.error(`Backend proxy error for ${url}:`, error)
    return NextResponse.json(
      { error: 'Backend service unavailable' },
      { status: 503 }
    )
  }
}

// Export named functions for each HTTP method
export async function GET(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const params = await context.params
  return handleRequest(request, 'GET', params)
}

export async function POST(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const params = await context.params
  return handleRequest(request, 'POST', params)
}

export async function PUT(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const params = await context.params
  return handleRequest(request, 'PUT', params)
}

export async function PATCH(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const params = await context.params
  return handleRequest(request, 'PATCH', params)
}

export async function DELETE(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const params = await context.params
  return handleRequest(request, 'DELETE', params)
}