"""
Score explanation service for generating human-readable scoring breakdowns
"""

import csv
import io
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from scoring_engine.ranker import JobScore, ScoringWeights


@dataclass
class ScoreInsight:
    """Human-readable insight about a scoring factor"""

    factor: str
    score: float
    weight: float
    contribution: float
    insight: str
    improvement_tip: Optional[str] = None


class ScoreExplainer:
    """Generate detailed explanations for job scoring results"""

    def __init__(self, weights: Optional[ScoringWeights] = None):
        """
        Initialize score explainer

        Args:
            weights: Scoring weights configuration
        """
        self.weights = weights or ScoringWeights()

    def generate_insights(self, job_score: JobScore) -> List[ScoreInsight]:
        """
        Generate human-readable insights for a job score

        Args:
            job_score: JobScore object to explain

        Returns:
            List of ScoreInsight objects
        """
        insights = []

        # Content similarity insight
        cosine_insight = self._generate_cosine_insight(job_score)
        insights.append(cosine_insight)

        # Skills match insight
        skills_insight = self._generate_skills_insight(job_score)
        insights.append(skills_insight)

        # Experience level insight
        seniority_insight = self._generate_seniority_insight(job_score)
        insights.append(seniority_insight)

        # Location insight
        geo_insight = self._generate_geo_insight(job_score)
        insights.append(geo_insight)

        # Recency insight
        recency_insight = self._generate_recency_insight(job_score)
        insights.append(recency_insight)

        return insights

    def _generate_cosine_insight(self, job_score: JobScore) -> ScoreInsight:
        """Generate insight for content similarity"""
        score = job_score.cosine_sim
        contribution = score * self.weights.cosine_similarity

        if score >= 0.85:
            insight = "Excellent match! Your resume content strongly aligns with this job description."
            tip = None
        elif score >= 0.70:
            insight = (
                "Good match. Your background aligns well with the job requirements."
            )
            tip = "Consider tailoring your resume to highlight relevant experiences mentioned in the job description."
        elif score >= 0.50:
            insight = "Fair match. Some alignment between your background and the job."
            tip = "Review the job description and emphasize matching skills and experiences in your application."
        else:
            insight = "Limited content overlap with the job description."
            tip = "This role may require skills or experience not prominently featured in your resume."

        return ScoreInsight(
            factor="Content Similarity",
            score=score,
            weight=self.weights.cosine_similarity,
            contribution=contribution,
            insight=insight,
            improvement_tip=tip,
        )

    def _generate_skills_insight(self, job_score: JobScore) -> ScoreInsight:
        """Generate insight for skills matching"""
        score = job_score.skill_overlap
        contribution = score * self.weights.skills_overlap

        if job_score.skills_details:
            exact_count = len(job_score.skills_details.exact_matches)
            fuzzy_count = len(job_score.skills_details.fuzzy_matches)
            missing_req = len(job_score.skills_details.missing_required)

            if score >= 0.85:
                insight = f"Excellent skills match! {exact_count} exact matches found."
            elif score >= 0.70:
                insight = f"Good skills alignment. {exact_count} exact and {fuzzy_count} similar skills matched."
            elif score >= 0.50:
                insight = (
                    f"Moderate skills match. Missing {missing_req} required skills."
                )
            else:
                insight = (
                    f"Limited skills overlap. Missing {missing_req} required skills."
                )

            if missing_req > 0:
                missing_list = job_score.skills_details.missing_required[:3]
                tip = f"Consider gaining experience with: {', '.join(missing_list)}"
            else:
                tip = None
        else:
            insight = f"Skills overlap score: {score:.0%}"
            tip = "Review the job requirements and highlight matching skills in your application."

        return ScoreInsight(
            factor="Skills Match",
            score=score,
            weight=self.weights.skills_overlap,
            contribution=contribution,
            insight=insight,
            improvement_tip=tip,
        )

    def _generate_seniority_insight(self, job_score: JobScore) -> ScoreInsight:
        """Generate insight for experience level matching"""
        score = job_score.seniority_fit
        contribution = score * self.weights.seniority_fit

        if score >= 0.95:
            insight = "Perfect experience level match!"
            tip = None
        elif score >= 0.80:
            insight = "Good experience level alignment."
            tip = None
        elif score >= 0.50:
            insight = "Acceptable experience level match."
            tip = "Highlight relevant accomplishments that demonstrate your readiness for this level."
        else:
            insight = "Experience level mismatch."
            tip = "This role may be looking for a different experience level. Consider roles that better match your seniority."

        return ScoreInsight(
            factor="Experience Level",
            score=score,
            weight=self.weights.seniority_fit,
            contribution=contribution,
            insight=insight,
            improvement_tip=tip,
        )

    def _generate_geo_insight(self, job_score: JobScore) -> ScoreInsight:
        """Generate insight for geographic factors"""
        if job_score.geo_details:
            score = job_score.geo_details.score
            distance_km = job_score.geo_details.distance_km

            if job_score.geo_details.is_remote:
                insight = "Remote position - location is not a factor."
                tip = None
            elif job_score.geo_details.location_match:
                insight = "Same city/metro area - ideal for commuting."
                tip = None
            elif distance_km <= 80:
                insight = f"Commutable distance ({distance_km:.0f} km)."
                tip = "Consider if daily commute is feasible for you."
            elif distance_km <= 160:
                insight = f"Regional position ({distance_km:.0f} km away)."
                tip = "This role may require relocation or remote work arrangements."
            else:
                insight = f"Different region ({distance_km:.0f} km away)."
                tip = "Relocation would likely be necessary for this position."
        else:
            score = 0.5  # Default neutral score
            insight = "Location compatibility unknown."
            tip = "Verify location requirements with the employer."

        contribution = score * self.weights.geographic_score

        return ScoreInsight(
            factor="Location",
            score=score,
            weight=self.weights.geographic_score,
            contribution=contribution,
            insight=insight,
            improvement_tip=tip,
        )

    def _generate_recency_insight(self, job_score: JobScore) -> ScoreInsight:
        """Generate insight for job posting recency"""
        score = job_score.recency_bonus
        contribution = score * self.weights.recency_bonus

        if score >= 0.90:
            insight = "Very recent posting - apply quickly!"
            tip = "New postings typically get the most attention in the first few days."
        elif score >= 0.70:
            insight = "Recent posting - good timing to apply."
            tip = None
        elif score >= 0.50:
            insight = "Posted within the last few weeks."
            tip = "Still worth applying, but act soon."
        else:
            insight = "Older posting - may have many applicants."
            tip = "Consider checking if the position is still open before applying."

        return ScoreInsight(
            factor="Posting Recency",
            score=score,
            weight=self.weights.recency_bonus,
            contribution=contribution,
            insight=insight,
            improvement_tip=tip,
        )

    def generate_summary(self, job_score: JobScore) -> Dict[str, Any]:
        """
        Generate a comprehensive summary of the scoring

        Args:
            job_score: JobScore object

        Returns:
            Dictionary with complete scoring summary
        """
        insights = self.generate_insights(job_score)

        # Determine overall match level
        total = job_score.total_score
        if total >= 0.85:
            match_level = "Excellent Match"
            recommendation = "Highly recommended - apply immediately!"
        elif total >= 0.70:
            match_level = "Good Match"
            recommendation = "Strong candidate - definitely worth applying."
        elif total >= 0.50:
            match_level = "Fair Match"
            recommendation = (
                "Potential fit - consider applying with a tailored approach."
            )
        elif total >= 0.30:
            match_level = "Possible Match"
            recommendation = (
                "Some alignment - review requirements carefully before applying."
            )
        else:
            match_level = "Poor Match"
            recommendation = "Limited alignment - consider other opportunities."

        # Find strongest and weakest factors
        strongest = max(insights, key=lambda x: x.contribution)
        weakest = min(insights, key=lambda x: x.contribution)

        # Get improvement suggestions
        improvements = [
            i.improvement_tip for i in insights if i.improvement_tip is not None
        ]

        return {
            "job_id": job_score.job_id,
            "job_title": job_score.title,
            "company": job_score.company_name,
            "overall": {
                "score": total,
                "percentile": job_score.percentile,
                "rank": job_score.rank,
                "match_level": match_level,
                "recommendation": recommendation,
            },
            "strengths": {"factor": strongest.factor, "insight": strongest.insight},
            "weaknesses": {"factor": weakest.factor, "insight": weakest.insight},
            "factor_breakdown": [
                {
                    "factor": i.factor,
                    "score": i.score,
                    "weight": i.weight,
                    "contribution": i.contribution,
                    "insight": i.insight,
                }
                for i in insights
            ],
            "improvement_suggestions": improvements,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def export_to_csv(
        self, scores: List[JobScore], include_breakdowns: bool = True
    ) -> str:
        """
        Export scores to CSV format

        Args:
            scores: List of JobScore objects
            include_breakdowns: Whether to include factor breakdowns

        Returns:
            CSV string
        """
        output = io.StringIO()

        # Define columns
        columns = ["rank", "job_id", "title", "company", "total_score", "percentile"]

        if include_breakdowns:
            columns.extend(
                [
                    "cosine_sim",
                    "skill_overlap",
                    "seniority_fit",
                    "geo_score",
                    "recency_bonus",
                ]
            )

        writer = csv.DictWriter(output, fieldnames=columns)
        writer.writeheader()

        for score in scores:
            row = {
                "rank": score.rank,
                "job_id": score.job_id,
                "title": score.title,
                "company": score.company_name,
                "total_score": f"{score.total_score:.3f}",
                "percentile": f"{score.percentile:.1f}" if score.percentile else "",
            }

            if include_breakdowns:
                row.update(
                    {
                        "cosine_sim": f"{score.cosine_sim:.3f}",
                        "skill_overlap": f"{score.skill_overlap:.3f}",
                        "seniority_fit": f"{score.seniority_fit:.3f}",
                        "geo_score": (
                            f"{score.geo_details.score:.3f}"
                            if score.geo_details
                            else "0"
                        ),
                        "recency_bonus": f"{score.recency_bonus:.3f}",
                    }
                )

            writer.writerow(row)

        return output.getvalue()

    def export_to_json(
        self, scores: List[JobScore], include_details: bool = True
    ) -> str:
        """
        Export scores to JSON format

        Args:
            scores: List of JobScore objects
            include_details: Whether to include detailed breakdowns

        Returns:
            JSON string
        """
        export_data = []

        for score in scores:
            data = {
                "rank": score.rank,
                "job_id": score.job_id,
                "title": score.title,
                "company": score.company_name,
                "total_score": score.total_score,
                "percentile": score.percentile,
            }

            if include_details:
                summary = self.generate_summary(score)
                data["match_level"] = summary["overall"]["match_level"]
                data["recommendation"] = summary["overall"]["recommendation"]
                data["factor_scores"] = {
                    "content_similarity": score.cosine_sim,
                    "skills_match": score.skill_overlap,
                    "experience_fit": score.seniority_fit,
                    "location_score": (
                        score.geo_details.score if score.geo_details else 0
                    ),
                    "recency_bonus": score.recency_bonus,
                }

                if score.skills_details:
                    data["skills_breakdown"] = {
                        "matched": score.skills_details.exact_matches,
                        "missing_required": score.skills_details.missing_required[:5],
                    }

            export_data.append(data)

        return json.dumps(export_data, indent=2)

    def generate_match_highlights(
        self, job_score: JobScore, resume_text: str, job_description: str
    ) -> Dict[str, List[str]]:
        """
        Generate highlighted matching sections for UI display

        Args:
            job_score: JobScore object
            resume_text: Resume text
            job_description: Job description text

        Returns:
            Dictionary with highlighted matches
        """
        highlights = {
            "matched_skills": [],
            "relevant_experience": [],
            "key_requirements": [],
        }

        # Highlight matched skills
        if job_score.skills_details:
            for skill in job_score.skills_details.exact_matches[:10]:
                if skill.lower() in resume_text.lower():
                    # Find context around skill mention
                    import re

                    pattern = re.compile(
                        rf"([^.]*\b{re.escape(skill)}\b[^.]*\.)", re.IGNORECASE
                    )
                    matches = pattern.findall(resume_text)
                    if matches:
                        highlights["matched_skills"].append(matches[0])

        # Extract key requirements met
        if job_description:
            # Simple keyword extraction for requirements
            requirement_keywords = ["required", "must have", "essential", "mandatory"]
            sentences = job_description.split(".")

            for sentence in sentences:
                if any(kw in sentence.lower() for kw in requirement_keywords):
                    # Check if any skills match in this requirement
                    if job_score.skills_details:
                        for skill in job_score.skills_details.exact_matches:
                            if skill.lower() in sentence.lower():
                                highlights["key_requirements"].append(sentence.strip())
                                break

        return highlights
