-- Create pitch_history table for secure pitch storage
CREATE TABLE IF NOT EXISTS pitch_history (
    pitch_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    job_id TEXT NOT NULL,
    job_title TEXT NOT NULL,
    company_name TEXT NOT NULL,
    headline TEXT NOT NULL,
    opening TEXT NOT NULL,
    two_minute_pitch TEXT NOT NULL,
    bullet_points JSONB NOT NULL DEFAULT '[]'::JSONB,
    why_this_company TEXT,
    why_this_role TEXT,
    questions_to_ask JSONB DEFAULT '[]'::JSONB,
    potential_objections JSONB DEFAULT '[]'::JSONB,
    closing_statement TEXT,
    skills_match_score NUMERIC,
    quality_scores JSONB,
    generated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Create indexes for performance
CREATE INDEX idx_pitch_history_user_id ON pitch_history(user_id);
CREATE INDEX idx_pitch_history_job_id ON pitch_history(job_id);
CREATE INDEX idx_pitch_history_generated_at ON pitch_history(generated_at DESC);

-- Enable RLS
ALTER TABLE pitch_history ENABLE ROW LEVEL SECURITY;

-- Create RLS policies - users can only see their own pitches
CREATE POLICY "Users can view their own pitches"
    ON pitch_history FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can create their own pitches"
    ON pitch_history FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update their own pitches"
    ON pitch_history FOR UPDATE
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can delete their own pitches"
    ON pitch_history FOR DELETE
    USING (auth.uid() = user_id);

-- Create function to automatically update updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create trigger for updated_at
CREATE TRIGGER update_pitch_history_updated_at BEFORE UPDATE
    ON pitch_history FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Grant permissions to authenticated users
GRANT ALL ON pitch_history TO authenticated;
GRANT USAGE ON SEQUENCE pitch_history_pitch_id_seq TO authenticated;