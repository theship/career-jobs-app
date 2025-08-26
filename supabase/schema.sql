-- Career Jobs App Database Schema
-- Based on docs/project-structure-overview.md

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Users and Preferences
CREATE TABLE IF NOT EXISTS app_user (
  user_id uuid PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  preferred_geolocation text,
  notes text,
  created_at timestamptz DEFAULT now()
);

-- Job Postings (Current + History)
CREATE TABLE IF NOT EXISTS job_postings (
  job_id text PRIMARY KEY,
  company_name text NOT NULL,
  company_domain text NOT NULL,
  title text NOT NULL,
  location text,
  remote_type text, -- onsite|hybrid|remote
  posted_at timestamptz,
  updated_at timestamptz,
  department text,
  employment_type text,
  seniority text,
  salary_min numeric,
  salary_max numeric,
  currency text,
  job_url text NOT NULL,
  description_text text,
  requirements_text text,
  embedding vector(3072), -- text-embedding-3-large
  first_seen_at timestamptz DEFAULT now(),
  last_seen_at timestamptz DEFAULT now()
);

-- Type-2 history tracking for jobs
CREATE TABLE IF NOT EXISTS job_postings_versions (
  version_id bigserial PRIMARY KEY,
  job_id text NOT NULL,
  valid_from timestamptz NOT NULL DEFAULT now(),
  valid_to timestamptz,
  record jsonb NOT NULL
);

-- Résumés and Versions
CREATE TABLE IF NOT EXISTS resumes (
  resume_id bigserial PRIMARY KEY,
  user_id uuid NOT NULL REFERENCES app_user(user_id),
  filename text NOT NULL,
  storage_path text NOT NULL,
  sha256 bytea NOT NULL,
  text_content text,
  embedding vector(3072),
  created_at timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS resume_versions (
  version_id bigserial PRIMARY KEY,
  resume_id bigint NOT NULL REFERENCES resumes(resume_id),
  created_at timestamptz DEFAULT now(),
  storage_path text NOT NULL,
  sha256 bytea NOT NULL
);

-- Scoring and Research
CREATE TABLE IF NOT EXISTS scores (
  score_id bigserial PRIMARY KEY,
  user_id uuid NOT NULL REFERENCES app_user(user_id),
  resume_id bigint NOT NULL REFERENCES resumes(resume_id),
  job_id text NOT NULL REFERENCES job_postings(job_id),
  cosine_sim numeric NOT NULL,
  skill_overlap numeric NOT NULL,
  seniority_fit numeric NOT NULL,
  geodist_km numeric,
  recency_bonus numeric NOT NULL,
  total_score numeric NOT NULL,
  created_at timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS company_research (
  company_domain text PRIMARY KEY,
  researched_at timestamptz NOT NULL DEFAULT now(),
  research jsonb NOT NULL -- conforms to CompanyResearch schema
);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_job_postings_company ON job_postings(company_name);
CREATE INDEX IF NOT EXISTS idx_job_postings_posted ON job_postings(posted_at DESC);
CREATE INDEX IF NOT EXISTS idx_job_postings_seniority ON job_postings(seniority);
CREATE INDEX IF NOT EXISTS idx_job_postings_remote ON job_postings(remote_type);
CREATE INDEX IF NOT EXISTS idx_resumes_user ON resumes(user_id);
CREATE INDEX IF NOT EXISTS idx_scores_user ON scores(user_id);
CREATE INDEX IF NOT EXISTS idx_scores_job ON scores(job_id);

-- Enable Row Level Security
ALTER TABLE app_user ENABLE ROW LEVEL SECURITY;
ALTER TABLE resumes ENABLE ROW LEVEL SECURITY;
ALTER TABLE resume_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE scores ENABLE ROW LEVEL SECURITY;

-- RLS Policies for app_user
CREATE POLICY "Users can view own profile" ON app_user
  FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can update own profile" ON app_user
  FOR UPDATE USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own profile" ON app_user
  FOR INSERT WITH CHECK (auth.uid() = user_id);

-- RLS Policies for resumes
CREATE POLICY "Users can view own resumes" ON resumes
  FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own resumes" ON resumes
  FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own resumes" ON resumes
  FOR UPDATE USING (auth.uid() = user_id);

CREATE POLICY "Users can delete own resumes" ON resumes
  FOR DELETE USING (auth.uid() = user_id);

-- RLS Policies for resume_versions
CREATE POLICY "Users can view own resume versions" ON resume_versions
  FOR SELECT USING (
    EXISTS (
      SELECT 1 FROM resumes 
      WHERE resumes.resume_id = resume_versions.resume_id 
      AND resumes.user_id = auth.uid()
    )
  );

-- RLS Policies for scores
CREATE POLICY "Users can view own scores" ON scores
  FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own scores" ON scores
  FOR INSERT WITH CHECK (auth.uid() = user_id);

-- Note: job_postings and company_research are public tables (no RLS)