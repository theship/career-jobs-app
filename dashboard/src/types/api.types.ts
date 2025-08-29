/**
 * API Type Definitions
 * Shared types for API requests and responses
 */

// User types
export interface User {
  user_id: string
  email: string
  created_at?: string
  updated_at?: string
}

export interface AuthResponse {
  user: User
  session?: any
}

// Resume types
export interface Resume {
  resume_id: string
  filename: string
  content?: string
  skills?: string[]
  skills_count?: number
  years_experience?: number
  seniority?: string
  location?: string
  parsed_data?: {
    experience?: any[]
    education?: any[]
    highlights?: string[]
  }
  embedding?: number[]
  created_at?: string
  updated_at?: string
}

export interface SkillsVocabulary {
  has_custom_vocab: boolean
  vocab_count?: number
  uploaded_at?: string
}

// Job types
export interface Job {
  job_id: string
  title: string
  company_name: string
  company_domain?: string
  location?: string
  remote_type?: string
  employment_type?: string
  seniority?: string
  description?: string
  requirements?: string[]
  responsibilities?: string[]
  benefits?: string[]
  required_skills?: string[]
  preferred_skills?: string[]
  posted_at?: string
  job_url?: string
  salary_range?: {
    min?: number
    max?: number
    currency?: string
  }
}

// Scoring types
export interface Score {
  job_id: string
  job_title: string
  company_name: string
  location?: string
  posted_at?: string
  overall_score: number
  skills_score: number
  experience_score: number
  location_score: number
  cosine_sim?: number
  skill_overlap?: number
  seniority_fit?: number
  geo_score?: number
  recency_bonus?: number
  percentile?: number
  rank?: number
}

export interface ScoringRequest {
  resume_id: string
  limit?: number
  min_score?: number
}

export interface ScoringResponse {
  results: Score[]
  total_jobs?: number
  processing_time?: number
}

// Pitch types
export interface Pitch {
  pitch_id?: string
  job_id: string
  job_title: string
  company_name: string
  headline: string
  opening: string
  two_minute_pitch: string
  bullet_points: string[]
  why_this_company: string
  why_this_role: string
  questions_to_ask: Array<{
    question: string
    purpose: string
  }>
  potential_objections: Array<{
    objection: string
    response: string
  }>
  closing_statement: string
  generated_at: string
  skills_match_score?: number
  quality_scores?: {
    overall: number
    headline_quality: number
    pitch_length: number
    personalization: number
  }
}

export interface PitchRequest {
  resume_id: string
  job_id: string
  include_research?: boolean
  personalization_level?: 'low' | 'medium' | 'high'
}

// Research types
export interface CompanyResearch {
  company_name: string
  company_domain: string
  description?: string
  industry?: string
  size?: string
  culture?: string
  recent_news?: string[]
  technologies?: string[]
  competitors?: string[]
  cached?: boolean
  research_date?: string
}

// Error types
export interface ApiError {
  error?: string
  detail?: string
  message?: string
  status?: number
}

// Request options
export interface RequestOptions extends Omit<RequestInit, 'body'> {
  body?: any
}