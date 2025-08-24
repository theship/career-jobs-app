-- Row Level Security Policies
-- Ensures users can only access their own data

-- Enable RLS on all user-scoped tables
ALTER TABLE public.app_user ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.resumes ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.resume_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.scores ENABLE ROW LEVEL SECURITY;

-- Note: job_postings and company_research are public data, no RLS needed
-- But we'll add read-only policies for consistency

-- App User Policies
CREATE POLICY "Users can view own profile"
    ON public.app_user FOR SELECT
    USING (auth.uid() = id);

CREATE POLICY "Users can update own profile"
    ON public.app_user FOR UPDATE
    USING (auth.uid() = id);

CREATE POLICY "Users can insert own profile"
    ON public.app_user FOR INSERT
    WITH CHECK (auth.uid() = id);

-- Resume Policies
CREATE POLICY "Users can view own resumes"
    ON public.resumes FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own resumes"
    ON public.resumes FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own resumes"
    ON public.resumes FOR UPDATE
    USING (auth.uid() = user_id);

CREATE POLICY "Users can delete own resumes"
    ON public.resumes FOR DELETE
    USING (auth.uid() = user_id);

-- Resume Versions Policies
CREATE POLICY "Users can view own resume versions"
    ON public.resume_versions FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM public.resumes
            WHERE resumes.id = resume_versions.resume_id
            AND resumes.user_id = auth.uid()
        )
    );

CREATE POLICY "Users can insert own resume versions"
    ON public.resume_versions FOR INSERT
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM public.resumes
            WHERE resumes.id = resume_versions.resume_id
            AND resumes.user_id = auth.uid()
        )
    );

-- Scores Policies
CREATE POLICY "Users can view own scores"
    ON public.scores FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own scores"
    ON public.scores FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own scores"
    ON public.scores FOR UPDATE
    USING (auth.uid() = user_id);

CREATE POLICY "Users can delete own scores"
    ON public.scores FOR DELETE
    USING (auth.uid() = user_id);

-- Public read policies for job postings and company research
-- (These tables don't have RLS enabled, but adding for completeness if enabled later)

-- Function to handle user creation after signup
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS trigger AS $$
BEGIN
    INSERT INTO public.app_user (id, email, full_name, metadata)
    VALUES (
        NEW.id,
        NEW.email,
        NEW.raw_user_meta_data->>'full_name',
        COALESCE(NEW.raw_user_meta_data, '{}'::jsonb)
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Trigger to create app_user record when auth.users record is created
CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

-- Grant necessary permissions
GRANT USAGE ON SCHEMA public TO anon, authenticated;
GRANT ALL ON ALL TABLES IN SCHEMA public TO anon, authenticated;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO anon, authenticated;
GRANT ALL ON ALL FUNCTIONS IN SCHEMA public TO anon, authenticated;