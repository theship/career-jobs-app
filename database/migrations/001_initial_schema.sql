-- Career Jobs App Database Schema
-- Phase 1: Foundation & Authentication
-- For use with Supabase (PostgreSQL + pgvector + RLS)

-- Enable required extensions (run in Supabase SQL editor)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "vector";

-- Create app_user table (extends Supabase auth.users)
CREATE TABLE IF NOT EXISTS public.app_user (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email TEXT UNIQUE NOT NULL,
    full_name TEXT,
    avatar_url TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    last_login TIMESTAMPTZ,
    is_active BOOLEAN DEFAULT true,
    email_verified BOOLEAN DEFAULT false
);

-- Create resumes table
CREATE TABLE IF NOT EXISTS public.resumes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES public.app_user(id) ON DELETE CASCADE,
    filename TEXT NOT NULL,
    file_path TEXT,
    file_size INTEGER,
    mime_type TEXT,
    sha256_hash TEXT,
    text_content TEXT,
    extracted_skills JSONB DEFAULT '[]',
    metadata JSONB DEFAULT '{}',
    embedding vector(3072),  -- OpenAI text-embedding-3-large dimension
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create resume_versions table (for versioning)
CREATE TABLE IF NOT EXISTS public.resume_versions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    resume_id UUID NOT NULL REFERENCES public.resumes(id) ON DELETE CASCADE,
    version_number INTEGER NOT NULL,
    filename TEXT NOT NULL,
    file_path TEXT,
    file_size INTEGER,
    sha256_hash TEXT,
    text_content TEXT,
    extracted_skills JSONB DEFAULT '[]',
    metadata JSONB DEFAULT '{}',
    embedding vector(3072),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(resume_id, version_number)
);

-- Create job_postings table
CREATE TABLE IF NOT EXISTS public.job_postings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    external_id TEXT UNIQUE NOT NULL,  -- ATS system ID
    source_ats TEXT NOT NULL,  -- greenhouse, lever, ashby, etc.
    company_name TEXT NOT NULL,
    company_domain TEXT,
    title TEXT NOT NULL,
    department TEXT,
    location TEXT,
    location_type TEXT,  -- remote, hybrid, onsite
    description TEXT,
    requirements TEXT,
    required_skills JSONB DEFAULT '[]',
    nice_to_have_skills JSONB DEFAULT '[]',
    experience_years_min INTEGER,
    experience_years_max INTEGER,
    salary_min INTEGER,
    salary_max INTEGER,
    salary_currency TEXT DEFAULT 'USD',
    benefits JSONB DEFAULT '[]',
    job_url TEXT,
    apply_url TEXT,
    posted_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ,
    last_seen_at TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB DEFAULT '{}',
    embedding vector(3072),
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create job_postings_versions table (SCD Type 2)
CREATE TABLE IF NOT EXISTS public.job_postings_versions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_posting_id UUID NOT NULL REFERENCES public.job_postings(id) ON DELETE CASCADE,
    version_number INTEGER NOT NULL,
    change_type TEXT,  -- created, updated, deleted
    changed_fields JSONB DEFAULT '[]',
    snapshot JSONB NOT NULL,  -- Full snapshot of the job posting
    valid_from TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    valid_to TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(job_posting_id, version_number)
);

-- Create scores table
CREATE TABLE IF NOT EXISTS public.scores (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES public.app_user(id) ON DELETE CASCADE,
    resume_id UUID NOT NULL REFERENCES public.resumes(id) ON DELETE CASCADE,
    job_posting_id UUID NOT NULL REFERENCES public.job_postings(id) ON DELETE CASCADE,
    cosine_similarity FLOAT,
    skill_match_score FLOAT,
    experience_match_score FLOAT,
    location_match_score FLOAT,
    total_score FLOAT NOT NULL,
    score_breakdown JSONB DEFAULT '{}',
    matched_skills JSONB DEFAULT '[]',
    missing_skills JSONB DEFAULT '[]',
    recommendation_reasons JSONB DEFAULT '[]',
    user_interest_level TEXT,  -- interested, applied, rejected, saved
    user_notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(resume_id, job_posting_id)
);

-- Create company_research table
CREATE TABLE IF NOT EXISTS public.company_research (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_domain TEXT UNIQUE NOT NULL,
    company_name TEXT NOT NULL,
    industry TEXT,
    size_range TEXT,
    headquarters_location TEXT,
    competitors JSONB DEFAULT '[]',
    strengths JSONB DEFAULT '[]',
    weaknesses JSONB DEFAULT '[]',
    opportunities JSONB DEFAULT '[]',
    culture_values JSONB DEFAULT '[]',
    recent_news JSONB DEFAULT '[]',
    glassdoor_rating FLOAT,
    linkedin_url TEXT,
    careers_page_url TEXT,
    research_date TIMESTAMPTZ DEFAULT NOW(),
    research_source TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create indexes for performance
CREATE INDEX idx_resumes_user_id ON public.resumes(user_id);
CREATE INDEX idx_resumes_sha256 ON public.resumes(sha256_hash);
CREATE INDEX idx_resumes_embedding ON public.resumes USING ivfflat (embedding vector_cosine_ops);

CREATE INDEX idx_job_postings_external_id ON public.job_postings(external_id);
CREATE INDEX idx_job_postings_company ON public.job_postings(company_name);
CREATE INDEX idx_job_postings_posted_at ON public.job_postings(posted_at DESC);
CREATE INDEX idx_job_postings_embedding ON public.job_postings USING ivfflat (embedding vector_cosine_ops);

CREATE INDEX idx_scores_user_id ON public.scores(user_id);
CREATE INDEX idx_scores_resume_id ON public.scores(resume_id);
CREATE INDEX idx_scores_job_id ON public.scores(job_posting_id);
CREATE INDEX idx_scores_total ON public.scores(total_score DESC);

-- Create update timestamp trigger function
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply update trigger to tables
CREATE TRIGGER update_app_user_updated_at BEFORE UPDATE ON public.app_user
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_resumes_updated_at BEFORE UPDATE ON public.resumes
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_job_postings_updated_at BEFORE UPDATE ON public.job_postings
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_scores_updated_at BEFORE UPDATE ON public.scores
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_company_research_updated_at BEFORE UPDATE ON public.company_research
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();