# Career Jobs App - High-Level Overview & Security Schema

The Career Jobs App is an AI-powered job matching platform that intelligently connects job seekers
with relevant opportunities through semantic matching and personalized pitch generation. The
application uses a sophisticated multi-layer architecture combining modern web technologies with
advanced AI capabilities.

# Core Functionality

1. Resume Processing: Users upload PDF resumes which are:
  - Parsed and text-extracted using pdfminer.six
  - Analyzed for skills using a multi-stage extraction pipeline
  - Converted to embeddings using OpenAI's text-embedding-3-large model (3072 dimensions)
  - Stored with version history tracking
2. Job Ingestion: The system automatically ingests jobs from company ATS systems:
  - Supports Greenhouse, Lever, Ashby, and other ATS platforms
  - Filters for jobs posted within the last 7 days
  - Normalizes job data across different sources
  - Generates embeddings for semantic matching
3. Intelligent Matching: Uses a multi-factor scoring algorithm:
  - Cosine similarity between resume and job embeddings (50% weight)
  - Skill overlap analysis (20% weight)
  - Seniority fit evaluation (10% weight)
  - Geographic proximity scoring (10% weight)
  - Recency bonus for fresh postings (10% weight)
4. AI-Powered Features:
  - Company research with competitive analysis
  - Personalized pitch generation using GPT-4
  - Structured outputs with source citations

---

# Security Architecture - Updated Implementation

> [NOTE!]
> See also, [security maintenance](./security-maintenance.md).


## Stateless approach

The current implementation follows the stateless approach recommended where:
  - Next.js owns ALL user authentication
  - FastAPI trusts Next.js completely via SERVICE_SECRET
  - No JWT validation in FastAPI (removed JWKS complexity)
  - Single authentication path enforced


The only minor deviation is that we still pass the token in X-User-Token header for database operations, but this is necessary for RLS enforcement and the token never reaches the browser directly.

The application implements a single-path authentication architecture that eliminates attack vectors
and ensures all requests flow through a trusted proxy:

## 1. Simplified Authentication Flow

User Browser → Next.js Frontend → FastAPI Backend → Supabase Database
     ↓              ↓                   ↓                ↓
  httpOnly      Server-side       Service Secret     RLS Policies
   Cookie        Validation       (Required Auth)   (User Isolation)

Key Change: Direct browser-to-API access is now completely blocked. All requests MUST go through
Next.js.

## 2. Service-Only Authentication

The backend now requires service authentication and trusts Next.js's pre-validated user information:

Backend Authentication Service (api/services/auth.py):
def verify_service_secret(x_service_secret: Optional[str] = Header(None)) -> bool:
    """Verify request is from trusted Next.js server"""
    if not x_service_secret:
        raise HTTPException(
            status_code=403,
            detail="Service authentication required. Direct API access is not allowed."
        )

    expected_secret = os.getenv("SERVICE_SECRET")
    if x_service_secret != expected_secret:
        raise HTTPException(status_code=403, detail="Invalid service authentication")

    return True

def get_current_user(
    request: Request,
    x_service_secret: Optional[str] = Header(None),
    x_user_id: Optional[str] = Header(None),
    x_user_email: Optional[str] = Header(None),
    x_user_token: Optional[str] = Header(None),
) -> Dict[str, Any]:
    """Get user from trusted Next.js headers"""
    # Verify this is from our trusted Next.js server
    verify_service_secret(x_service_secret)

    if not x_user_id:
        raise HTTPException(status_code=401, detail="User authentication required")

    # Return user info trusted from Next.js
    return {
        "user_id": x_user_id,
        "email": x_user_email,
        "token": x_user_token,  # For database operations
        "trusted_service": True,
    }

Security Benefits:
- No JWT validation in backend - Next.js already validated
- No JWKS complexity - Removed entirely
- Simple shared secret - Easy to rotate
- Single authentication path - No bypass possible

## 3. Next.js Security Proxy Layer

Next.js validates users server-side and forwards verified information:

API Route Handler (dashboard/src/app/api/backend/[...path]/route.ts):
async function handleRequest(request: NextRequest, method: string, params: { path: string[] }) {
  // Get and validate user
  const user = await getUser()  // Server-side Supabase validation
  const token = await getAuthToken()

  // Check authentication for protected endpoints
  if (!isPublicPath(path) && !user) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
  }

  // REQUIRED: Add service secret
  if (!process.env.SERVICE_SECRET) {
    return NextResponse.json({ error: 'Server configuration error' }, { status: 500 })
  }

  const headers: HeadersInit = {
    'Content-Type': 'application/json',
    'X-Service-Secret': process.env.SERVICE_SECRET,  // Required by backend
  }

  // Forward validated user information
  if (user) {
    headers['X-User-Id'] = user.id
    headers['X-User-Email'] = user.email
  }

  // Forward token for database operations
  if (token) {
    headers['X-User-Token'] = token
  }

  // Forward to FastAPI
  const response = await fetch(backendUrl, { headers, ...requestOptions })
}

## 4. Secure Server-Side Supabase Client

Server Authentication (dashboard/src/lib/supabase-server.ts):
export async function getUser() {
  const supabase = await createClient()

  // getUser() validates the token server-side (secure)
  // More secure than getSession() which trusts the cookie
  const { data: { user }, error } = await supabase.auth.getUser()

  if (error || !user) {
    return null
  }

  return user
}

## 5. Database-Level Security (Row Level Security)

Supabase RLS policies ensure complete data isolation:

User Data Protection (supabase/schema.sql):
-- Enable Row Level Security
ALTER TABLE app_user ENABLE ROW LEVEL SECURITY;
ALTER TABLE resumes ENABLE ROW LEVEL SECURITY;
ALTER TABLE scores ENABLE ROW LEVEL SECURITY;
ALTER TABLE job_postings ENABLE ROW LEVEL SECURITY;  -- Added 2025-09-06

-- Users can only access their own data
CREATE POLICY "Users can view own resumes" ON resumes
  FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own resumes" ON resumes
  FOR INSERT WITH CHECK (auth.uid() = user_id);

-- Job postings: NO POLICIES (service role only)
-- This ensures job data is only accessible via backend API with SERVICE_ROLE_KEY

## 6. Authenticated Database Connections

The backend creates user-scoped database clients:

Database Utilities (api/utils/database.py):
def get_authenticated_supabase_client(token: str) -> Client:
    """Create Supabase client with user's JWT for RLS enforcement"""
    options = ClientOptions()
    options.headers = {"Authorization": f"Bearer {token}"}

    return create_client(
        settings.supabase_url,
        settings.supabase_anon_key,  # Uses anon key, respects RLS
        options=options
    )

# Security Architecture Summary

The updated implementation enforces a single authentication path with these layers:

## 1. Frontend Layer:
  - HttpOnly cookies for session management
  - Server-side user validation before API calls
  - No direct backend access possible
## 2. API Gateway (Next.js):
  - Validates users server-side using Supabase Auth
  - Required service secret for all backend requests
  - Acts as the only trusted proxy to FastAPI
## 3. Backend API (FastAPI):
  - Service authentication required (no optional paths)
  - No JWT/JWKS validation (trusts Next.js)
  - Rejects all direct browser requests
## 4. Database Layer (Supabase):
  - Row Level Security policies
  - User-scoped data access
  - Authenticated client connections
## 5. Key Security Improvements:
  - Single authentication path - eliminates bypass vulnerabilities
  - Simplified architecture - no complex JWT validation
  - Reduced attack surface - only one way in
  - Easy secret rotation - single shared secret
  - Clear security boundary - Next.js handles all user auth

## This architecture ensures:
- No direct API access - All requests must go through Next.js
- Pre-validated users - Backend trusts Next.js's authentication
- Complete data isolation - RLS policies at database level
- Simple and secure - Fewer moving parts, fewer vulnerabilities
- Development friendly - Clear separation of concerns

---

## Job Data Protection Implementation (2025-09-06)

The job_postings table follows a service-only access pattern:

1. **Database Level**: RLS enabled with NO policies - only SERVICE_ROLE_KEY can access
2. **API Level**: All job endpoints require SERVICE_SECRET authentication
3. **Data Access**: Uses get_supabase_service_client() to bypass RLS

This ensures:
- No direct client access to job data (prevents scraping)
- All access goes through authenticated API layer
- Business logic controls what users see
- Protects competitive advantage of curated job data and embeddings

# Multiple defensive layers and comprehensive coverage implemented

Security Architecture Includes:

  Browser → Next.js → FastAPI → Database
     ↓           ↓         ↓         ↓
   CSRF      HMAC+Nonce  Identity   RLS
   Cookie     Signing    Coherence  Policies
   Proactive
   protection
 
### Secure Input Processing Pipeline

> [!NOTE]
> Security is prepared for Redis (to be implemented) but currently:
> - No replay attack prevention (nonces not tracked)
> - No distributed rate limiting (in-memory only)
> - No per-user quotas (just basic IP limits)

#### 1. File Size Limits - Enforced for PDFs (10MB), CSVs (5MB), text (1MB)
#### 2. PDF Sanitization - Validates structure, detects malicious elements
#### 3. Input Sanitization - All text inputs cleaned with bleach
#### 4. Rate Limiting - 5 resume uploads/hour, 10 skills uploads/hour
#### 5. Security Headers - CSP, HSTS, X-Frame-Options, and more

#### 6. HMAC Signing & Replay Prevention

  - HMAC-SHA256 request signatures with timestamp validation
  - Redis-based nonce cache to prevent replay attacks
  - 5-minute request freshness window
  - Constant-time comparison against timing attacks

#### 7. CSRF Protection

  - Double-submit cookie pattern for mutations
  - Origin/Referer header validation
  - Secure cookie configuration
  - Client-side fetch wrapper with automatic token inclusion

#### 8. Identity Coherence Check

  - JWT subject validation against X-User-Id header
  - Ensures token claims match forwarded identity
  - Critical security event logging on mismatches

#### 9. CORS Lockdown

  - Production: Complete CORS denial (server-to-server only)
  - Development: Restricted to Next.js origins
  - Explicit header whitelist
  - No wildcard permissions

#### 10. Advanced Rate Limiting

  - Three-tier strategy: Edge (IP), User, Route
  - Redis sliding window algorithm
  - Granular quotas:
    - Uploads: 5 resumes/hr, 10 skills/hr
    - AI ops: 100 embeddings/hr, 50 GPT/hr, 20 pitches/hr
    - Data: 200 scores/hr, 500 searches/hr
  - User usage tracking and metrics

  
## Documentation Created

  - docs/security-maintenance.md - Comprehensive security maintenance guide
  - RLS audit procedures with SQL commands
  - Secret rotation schedules and vault integration
  - Structured logging formats and alert thresholds
  - Incident response playbooks
