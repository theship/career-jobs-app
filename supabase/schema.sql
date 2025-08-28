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

-- User Skills Vocabulary
CREATE TABLE IF NOT EXISTS user_skills_vocab (
  id bigserial PRIMARY KEY,
  user_id uuid NOT NULL REFERENCES app_user(user_id) ON DELETE CASCADE,
  vocab_data jsonb NOT NULL,
  skills_count integer NOT NULL,
  uploaded_at timestamptz NOT NULL DEFAULT now(),
  last_used_at timestamptz,
  usage_count integer DEFAULT 0,
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now(),
  UNIQUE(user_id)
);

-- Activity Log for tracking user actions
CREATE TABLE IF NOT EXISTS activity_log (
  log_id bigserial PRIMARY KEY,
  user_id uuid NOT NULL REFERENCES app_user(user_id) ON DELETE CASCADE,
  action_type text NOT NULL, -- 'resume_upload', 'skills_upload', 'scoring_run', 'csv_export'
  action_status text NOT NULL, -- 'started', 'in_progress', 'completed', 'failed'
  metadata jsonb, -- Store action-specific data (file names, counts, timings, etc.)
  error_details text,
  started_at timestamptz NOT NULL DEFAULT now(),
  completed_at timestamptz,
  duration_ms integer
);

-- Resume Skills (extracted skills from resumes)
CREATE TABLE IF NOT EXISTS resume_skills (
  id bigserial PRIMARY KEY,
  resume_id bigint NOT NULL REFERENCES resumes(resume_id) ON DELETE CASCADE,
  skill_name text NOT NULL,
  confidence numeric,
  evidence_span jsonb, -- [start, end] character positions
  extraction_method text, -- 'dictionary', 'fuzzy', 'llm'
  created_at timestamptz DEFAULT now()
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
CREATE INDEX IF NOT EXISTS idx_activity_log_user ON activity_log(user_id, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_activity_log_type ON activity_log(action_type, action_status);
CREATE INDEX IF NOT EXISTS idx_resume_skills_resume ON resume_skills(resume_id);
CREATE INDEX IF NOT EXISTS idx_user_skills_vocab_user ON user_skills_vocab(user_id);

-- Enable Row Level Security
ALTER TABLE app_user ENABLE ROW LEVEL SECURITY;
ALTER TABLE resumes ENABLE ROW LEVEL SECURITY;
ALTER TABLE resume_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE scores ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_skills_vocab ENABLE ROW LEVEL SECURITY;
ALTER TABLE activity_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE resume_skills ENABLE ROW LEVEL SECURITY;

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

-- RLS Policies for user_skills_vocab
CREATE POLICY "Users can view own skills vocab" ON user_skills_vocab
  FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own skills vocab" ON user_skills_vocab
  FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own skills vocab" ON user_skills_vocab
  FOR UPDATE USING (auth.uid() = user_id);

CREATE POLICY "Users can delete own skills vocab" ON user_skills_vocab
  FOR DELETE USING (auth.uid() = user_id);

-- RLS Policies for activity_log
CREATE POLICY "Users can view own activity" ON activity_log
  FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own activity" ON activity_log
  FOR INSERT WITH CHECK (auth.uid() = user_id);

-- RLS Policies for resume_skills
CREATE POLICY "Users can view own resume skills" ON resume_skills
  FOR SELECT USING (
    EXISTS (
      SELECT 1 FROM resumes 
      WHERE resumes.resume_id = resume_skills.resume_id 
      AND resumes.user_id = auth.uid()
    )
  );

CREATE POLICY "Users can insert own resume skills" ON resume_skills
  FOR INSERT WITH CHECK (
    EXISTS (
      SELECT 1 FROM resumes 
      WHERE resumes.resume_id = resume_skills.resume_id 
      AND resumes.user_id = auth.uid()
    )
  );

-- Note: job_postings and company_research are public tables (no RLS)