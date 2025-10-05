"""
Pitch generation service for creating personalized job application pitches
"""

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import openai
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)


class PitchGeneratorService:
    """Generate personalized pitches based on resume, job, and company research"""

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        """
        Initialize pitch generator

        Args:
            api_key: OpenAI API key
            model: OpenAI model to use (defaults to gpt-4o-mini or env var)
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        if not self.api_key:
            logger.warning(
                "OpenAI API key not configured - pitch service will not be available"
            )
            raise ValueError("OpenAI API key required")

        openai.api_key = self.api_key
        self.client = openai.OpenAI(api_key=self.api_key)

        # Load prompt template
        self.prompt_template = self._load_prompt_template()

    def _load_prompt_template(self) -> str:
        """Load pitch generation prompt template"""
        prompt_path = Path("config/prompts/pitch_generation.txt")
        if prompt_path.exists():
            return prompt_path.read_text()
        else:
            # Fallback prompt if file doesn't exist
            return """Create a personalized pitch for this candidate:
            Resume: {resume_content}
            Job: {job_description}
            Company Research: {company_research}

            Generate a compelling pitch that connects their experience to this specific opportunity."""

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
    )
    def _call_openai(self, prompt: str) -> Dict[str, Any]:
        """Call OpenAI API with retry logic"""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert career coach helping candidates craft compelling pitches. Always respond with valid JSON.",
                    },
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.7,  # Balanced creativity
                max_tokens=2500,
            )

            content = response.choices[0].message.content
            return json.loads(content)

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse OpenAI response as JSON: {e}")
            raise
        except Exception as e:
            logger.error(f"OpenAI API call failed: {e}")
            raise

    def _extract_key_skills(self, resume_data: Dict[str, Any]) -> List[str]:
        """Extract key skills from resume data"""
        skills = resume_data.get("skills", [])

        # Also extract skills from experience descriptions if available
        if "experience" in resume_data:
            for exp in resume_data["experience"]:
                if "technologies" in exp:
                    skills.extend(exp["technologies"])

        # Deduplicate
        return list(set(skills))

    def _summarize_experience(self, resume_data: Dict[str, Any]) -> str:
        """Create a summary of relevant experience"""
        summary_parts = []

        # Add years of experience if available
        if "years_experience" in resume_data:
            summary_parts.append(
                f"{resume_data['years_experience']} years of experience"
            )

        # Add current/recent role
        if "experience" in resume_data and resume_data["experience"]:
            recent_role = resume_data["experience"][0]
            summary_parts.append(
                f"Currently {recent_role.get('title', 'working')} at {recent_role.get('company', 'current company')}"
            )

        # Add education if relevant
        if "education" in resume_data and resume_data["education"]:
            education = resume_data["education"][0]
            summary_parts.append(
                f"{education.get('degree', 'Degree')} from {education.get('school', 'University')}"
            )

        return ". ".join(summary_parts) if summary_parts else "Experienced professional"

    def generate_pitch(
        self,
        resume_data: Dict[str, Any],
        job_data: Dict[str, Any],
        company_research: Dict[str, Any],
        skills_match_score: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Generate a personalized pitch for a specific job

        Args:
            resume_data: Candidate's resume information
            job_data: Job posting information
            company_research: Company research data
            skills_match_score: Optional skills matching score

        Returns:
            Generated pitch with multiple components
        """
        logger.info(
            f"Generating pitch for {job_data.get('title', 'position')} at {job_data.get('company_name', 'company')}"
        )

        # Prepare resume content summary
        resume_content = {
            "skills": self._extract_key_skills(resume_data),
            "experience_summary": self._summarize_experience(resume_data),
            "seniority": resume_data.get("seniority", "mid-level"),
            "location": resume_data.get("location", ""),
            "highlights": resume_data.get("highlights", []),
        }

        # Prepare job description summary
        job_description = {
            "title": job_data.get("title", ""),
            "company": job_data.get("company_name", ""),
            "required_skills": job_data.get("required_skills", []),
            "preferred_skills": job_data.get("preferred_skills", []),
            "responsibilities": job_data.get("responsibilities", []),
            "requirements": job_data.get("requirements", []),
            "seniority": job_data.get("seniority", ""),
        }

        # Prepare company research summary (focus on key points)
        company_summary = {
            "company_name": company_research.get(
                "company_name", job_data.get("company_name", "")
            ),
            "industry": company_research.get("industry", ""),
            "top_competitors": company_research.get("competitors", [])[:3],
            "key_strengths": company_research.get("excellence", [])[:3],
            "growth_areas": company_research.get("shortcomings", [])[:2],
            "future_goals": company_research.get("aspirations", [])[:3],
            "culture_values": company_research.get("culture_values", [])[:3],
        }

        # Format the prompt
        prompt = self.prompt_template.format(
            resume_content=json.dumps(resume_content, indent=2),
            job_description=json.dumps(job_description, indent=2),
            company_research=json.dumps(company_summary, indent=2),
            skills_match_score=skills_match_score or "Not calculated",
        )

        # Generate pitch
        pitch = self._call_openai(prompt)

        # Add metadata
        pitch["generated_at"] = datetime.now(timezone.utc).isoformat()
        pitch["job_title"] = job_data.get("title", "")
        pitch["company_name"] = job_data.get("company_name", "")
        pitch["skills_match_score"] = skills_match_score

        # Ensure headline is within character limit
        if "headline" in pitch and len(pitch["headline"]) > 140:
            pitch["headline"] = pitch["headline"][:137] + "..."

        return pitch

    def personalize_template(self, template: str, variables: Dict[str, Any]) -> str:
        """
        Personalize a template with variables

        Args:
            template: Template string with {variable} placeholders
            variables: Dictionary of variable values

        Returns:
            Personalized string
        """
        try:
            return template.format(**variables)
        except KeyError as e:
            logger.warning(f"Missing variable in template: {e}")
            return template

    def generate_email_template(
        self, pitch: Dict[str, Any], recipient_name: Optional[str] = None
    ) -> Dict[str, str]:
        """
        Generate email templates from pitch

        Args:
            pitch: Generated pitch data
            recipient_name: Optional recipient name

        Returns:
            Email subject and body
        """
        greeting = f"Dear {recipient_name}" if recipient_name else "Dear Hiring Manager"

        # Create email subject
        subject = f"Application for {pitch.get('job_title', 'Position')} - {pitch.get('headline', 'Experienced Professional')[:50]}"

        # Create email body
        body_parts = [
            greeting + ",",
            "",
            pitch.get(
                "opening",
                "I am writing to express my interest in this position.",
            ),
            "",
            "Why I'm excited about this opportunity:",
            pitch.get("why_this_company", ""),
            "",
            pitch.get("why_this_role", ""),
            "",
            "Key qualifications:",
        ]

        # Add bullet points
        for bullet in pitch.get("bullet_points", []):
            body_parts.append(f"• {bullet}")

        body_parts.extend(
            [
                "",
                pitch.get(
                    "closing_statement",
                    "I look forward to discussing this opportunity further.",
                ),
                "",
                "Best regards,",
                "[Your Name]",
            ]
        )

        return {"subject": subject, "body": "\n".join(body_parts)}

    def generate_interview_prep(
        self, pitch: Dict[str, Any], company_research: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate interview preparation materials

        Args:
            pitch: Generated pitch data
            company_research: Company research data

        Returns:
            Interview preparation guide
        """
        prep = {
            "elevator_pitch": pitch.get("opening", ""),
            "two_minute_pitch": pitch.get("two_minute_pitch", ""),
            "key_talking_points": pitch.get("bullet_points", []),
            "questions_to_ask": pitch.get("questions_to_ask", []),
            "potential_objections": pitch.get("potential_objections", []),
            "company_insights": {
                "strengths_to_mention": [
                    e["area"] for e in company_research.get("excellence", [])[:3]
                ],
                "challenges_to_address": [
                    s["area"] for s in company_research.get("shortcomings", [])[:2]
                ],
                "goals_to_support": [
                    a["statement"] for a in company_research.get("aspirations", [])[:3]
                ],
            },
            "preparation_checklist": [
                "Research recent company news",
                "Review interviewer LinkedIn profiles",
                "Practice STAR method examples",
                "Prepare portfolio pieces",
                "Plan interview outfit",
                "Test video/audio setup (if remote)",
            ],
        }

        return prep

    def score_pitch_quality(self, pitch: Dict[str, Any]) -> Dict[str, float]:
        """
        Score the quality of a generated pitch

        Args:
            pitch: Generated pitch data

        Returns:
            Quality scores for different aspects
        """
        scores = {}

        # Check completeness
        required_fields = [
            "headline",
            "opening",
            "two_minute_pitch",
            "bullet_points",
            "closing_statement",
        ]
        present = sum(1 for field in required_fields if field in pitch and pitch[field])
        scores["completeness"] = present / len(required_fields)

        # Check headline quality (length)
        headline_len = len(pitch.get("headline", ""))
        scores["headline_quality"] = (
            min(1.0, headline_len / 100) if headline_len > 20 else 0
        )

        # Check pitch length
        pitch_len = len(pitch.get("two_minute_pitch", ""))
        scores["pitch_length"] = 1.0 if 250 <= pitch_len <= 500 else 0.5

        # Check personalization (presence of questions and objection handling)
        scores["personalization"] = (
            1.0
            if pitch.get("questions_to_ask") and pitch.get("potential_objections")
            else 0.5
        )

        # Overall score
        scores["overall"] = sum(scores.values()) / len(scores)

        return scores
