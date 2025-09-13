-- WARNING: This schema is for context only and is not meant to be run.
-- Table order and constraints may not be valid for execution.

CREATE TABLE public.app_user (
  user_id uuid NOT NULL,
  preferred_geolocation text,
  notes text,
  created_at timestamp with time zone DEFAULT now(),
  CONSTRAINT app_user_pkey PRIMARY KEY (user_id),
  CONSTRAINT app_user_user_id_fkey FOREIGN KEY (user_id) REFERENCES auth.users(id)
);
CREATE TABLE public.company_research (
  company_domain text NOT NULL,
  researched_at timestamp with time zone NOT NULL DEFAULT now(),
  research jsonb NOT NULL,
  CONSTRAINT company_research_pkey PRIMARY KEY (company_domain)
);
CREATE TABLE public.ingestion_history (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  company_id uuid,
  started_at timestamp with time zone NOT NULL DEFAULT now(),
  completed_at timestamp with time zone,
  jobs_fetched integer DEFAULT 0,
  jobs_created integer DEFAULT 0,
  jobs_updated integer DEFAULT 0,
  embeddings_generated integer DEFAULT 0,
  duration_ms integer,
  status text,
  error_details text,
  metadata jsonb,
  CONSTRAINT ingestion_history_pkey PRIMARY KEY (id),
  CONSTRAINT ingestion_history_company_id_fkey FOREIGN KEY (company_id) REFERENCES public.target_companies(id)
);
CREATE TABLE public.job_postings (
  job_id text NOT NULL,
  company_name text NOT NULL,
  company_domain text NOT NULL,
  title text NOT NULL,
  location text,
  remote_type text,
  posted_at timestamp with time zone,
  updated_at timestamp with time zone,
  department text,
  employment_type text,
  seniority text,
  salary_min numeric,
  salary_max numeric,
  currency text,
  job_url text NOT NULL,
  description_text text,
  requirements_text text,
  embedding USER-DEFINED,
  first_seen_at timestamp with time zone DEFAULT now(),
  last_seen_at timestamp with time zone DEFAULT now(),
  CONSTRAINT job_postings_pkey PRIMARY KEY (job_id)
);
CREATE TABLE public.job_postings_versions (
  version_id bigint NOT NULL DEFAULT nextval('job_postings_versions_version_id_seq'::regclass),
  job_id text NOT NULL,
  valid_from timestamp with time zone NOT NULL DEFAULT now(),
  valid_to timestamp with time zone,
  record jsonb NOT NULL,
  CONSTRAINT job_postings_versions_pkey PRIMARY KEY (version_id)
);
CREATE TABLE public.pitch_history (
  pitch_id uuid NOT NULL DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL,
  job_id text NOT NULL,
  job_title text NOT NULL,
  company_name text NOT NULL,
  headline text NOT NULL,
  opening text NOT NULL,
  two_minute_pitch text NOT NULL,
  bullet_points jsonb NOT NULL DEFAULT '[]'::jsonb,
  why_this_company text,
  why_this_role text,
  questions_to_ask jsonb DEFAULT '[]'::jsonb,
  potential_objections jsonb DEFAULT '[]'::jsonb,
  closing_statement text,
  skills_match_score numeric,
  quality_scores jsonb,
  generated_at timestamp with time zone NOT NULL DEFAULT now(),
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  updated_at timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT pitch_history_pkey PRIMARY KEY (pitch_id),
  CONSTRAINT pitch_history_user_id_fkey FOREIGN KEY (user_id) REFERENCES auth.users(id)
);
CREATE TABLE public.resume_skills (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  resume_id bigint NOT NULL,
  skill_name text NOT NULL,
  confidence numeric DEFAULT 1.0,
  created_at timestamp with time zone DEFAULT now(),
  CONSTRAINT resume_skills_pkey PRIMARY KEY (id),
  CONSTRAINT resume_skills_resume_id_fkey FOREIGN KEY (resume_id) REFERENCES public.resumes(resume_id)
);
CREATE TABLE public.resume_versions (
  version_id bigint NOT NULL DEFAULT nextval('resume_versions_version_id_seq'::regclass),
  resume_id bigint NOT NULL,
  created_at timestamp with time zone DEFAULT now(),
  storage_path text NOT NULL,
  sha256 bytea NOT NULL,
  CONSTRAINT resume_versions_pkey PRIMARY KEY (version_id),
  CONSTRAINT resume_versions_resume_id_fkey FOREIGN KEY (resume_id) REFERENCES public.resumes(resume_id)
);
CREATE TABLE public.resumes (
  resume_id bigint NOT NULL DEFAULT nextval('resumes_resume_id_seq'::regclass),
  user_id uuid NOT NULL,
  filename text NOT NULL,
  storage_path text NOT NULL,
  sha256 bytea NOT NULL,
  text_content text,
  embedding USER-DEFINED,
  created_at timestamp with time zone DEFAULT now(),
  CONSTRAINT resumes_pkey PRIMARY KEY (resume_id),
  CONSTRAINT resumes_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.app_user(user_id)
);
CREATE TABLE public.scores (
  score_id bigint NOT NULL DEFAULT nextval('scores_score_id_seq'::regclass),
  user_id uuid NOT NULL,
  resume_id bigint NOT NULL,
  job_id text NOT NULL,
  cosine_sim numeric NOT NULL,
  skill_overlap numeric NOT NULL,
  seniority_fit numeric NOT NULL,
  geodist_km numeric,
  recency_bonus numeric NOT NULL,
  total_score numeric NOT NULL,
  created_at timestamp with time zone DEFAULT now(),
  CONSTRAINT scores_pkey PRIMARY KEY (score_id),
  CONSTRAINT scores_job_id_fkey FOREIGN KEY (job_id) REFERENCES public.job_postings(job_id),
  CONSTRAINT scores_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.app_user(user_id),
  CONSTRAINT scores_resume_id_fkey FOREIGN KEY (resume_id) REFERENCES public.resumes(resume_id)
);
CREATE TABLE public.target_companies (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  ats_system text NOT NULL,
  company_id text NOT NULL,
  display_name text NOT NULL,
  industry text,
  company_size text,
  priority integer DEFAULT 2,
  check_frequency_days integer DEFAULT 1,
  active boolean DEFAULT true,
  last_successful_fetch timestamp with time zone,
  last_fetch_attempt timestamp with time zone,
  consecutive_failures integer DEFAULT 0,
  error_details text,
  metadata jsonb,
  created_at timestamp with time zone DEFAULT now(),
  updated_at timestamp with time zone DEFAULT now(),
  CONSTRAINT target_companies_pkey PRIMARY KEY (id)
);
CREATE TABLE public.user_skills_vocab (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL UNIQUE,
  vocab_data jsonb NOT NULL,
  skills_count integer,
  uploaded_at timestamp with time zone DEFAULT now(),
  CONSTRAINT user_skills_vocab_pkey PRIMARY KEY (id),
  CONSTRAINT user_skills_vocab_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.app_user(user_id)
);
