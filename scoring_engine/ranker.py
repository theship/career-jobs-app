"""
Final ranking algorithm combining all scoring factors
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from .geo_scorer import GeoScore, GeoScorer
from .similarity import SimilarityScore, VectorSimilarityCalculator
from .skills_matcher import SkillsMatcher, SkillsScore

logger = logging.getLogger(__name__)


@dataclass
class ScoringWeights:
    """Configurable weights for scoring factors"""

    cosine_similarity: float = 0.5
    skills_overlap: float = 0.2
    seniority_fit: float = 0.1
    geographic_score: float = 0.1
    recency_bonus: float = 0.1

    def validate(self) -> bool:
        """Ensure weights sum to 1.0"""
        total = (
            self.cosine_similarity
            + self.skills_overlap
            + self.seniority_fit
            + self.geographic_score
            + self.recency_bonus
        )
        return abs(total - 1.0) < 0.001

    def normalize(self):
        """Normalize weights to sum to 1.0"""
        total = (
            self.cosine_similarity
            + self.skills_overlap
            + self.seniority_fit
            + self.geographic_score
            + self.recency_bonus
        )
        if total > 0:
            self.cosine_similarity /= total
            self.skills_overlap /= total
            self.seniority_fit /= total
            self.geographic_score /= total
            self.recency_bonus /= total


@dataclass
class JobScore:
    """Complete scoring result for a single job"""

    job_id: str
    title: str
    company_name: str

    # Individual scores
    cosine_sim: float
    skill_overlap: float
    seniority_fit: float
    geodist_km: float
    recency_bonus: float

    # Optional fields
    location: Optional[str] = None
    posted_at: Optional[datetime] = None

    # Detailed breakdowns
    similarity_details: Optional[SimilarityScore] = None
    skills_details: Optional[SkillsScore] = None
    geo_details: Optional[GeoScore] = None

    # Final scores
    total_score: float = 0.0
    rank: Optional[int] = None
    percentile: Optional[float] = None

    # Metadata
    scored_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    weights_used: Optional[ScoringWeights] = None


class JobRanker:
    """Rank jobs based on multiple scoring factors"""

    def __init__(
        self,
        weights: Optional[ScoringWeights] = None,
        similarity_calculator: Optional[VectorSimilarityCalculator] = None,
        skills_matcher: Optional[SkillsMatcher] = None,
        geo_scorer: Optional[GeoScorer] = None,
    ):
        """
        Initialize job ranker with scoring components

        Args:
            weights: Scoring weights configuration
            similarity_calculator: Vector similarity component
            skills_matcher: Skills matching component
            geo_scorer: Geographic scoring component
        """
        self.weights = weights or ScoringWeights()
        if not self.weights.validate():
            self.weights.normalize()

        self.similarity_calculator = (
            similarity_calculator or VectorSimilarityCalculator()
        )
        self.skills_matcher = skills_matcher or SkillsMatcher()
        self.geo_scorer = geo_scorer or GeoScorer()

    def calculate_seniority_fit(
        self, resume_seniority: str, job_seniority: str
    ) -> float:
        """
        Calculate how well seniority levels match

        Args:
            resume_seniority: Resume experience level
            job_seniority: Job required experience level

        Returns:
            Fit score between 0 and 1
        """
        # Define seniority levels and their numeric values
        seniority_levels = {
            "entry": 1,
            "junior": 1,
            "mid": 2,
            "senior": 3,
            "staff": 4,
            "principal": 5,
            "executive": 6,
            "not specified": 2,  # Default to mid-level
        }

        # Normalize strings
        resume_level = seniority_levels.get(resume_seniority.lower(), 2)
        job_level = seniority_levels.get(job_seniority.lower(), 2)

        # Calculate fit
        if resume_level == job_level:
            return 1.0  # Perfect match
        elif abs(resume_level - job_level) == 1:
            return 0.8  # Adjacent levels
        elif resume_level > job_level:
            # Overqualified - small penalty
            return max(0.5, 1.0 - 0.1 * (resume_level - job_level))
        else:
            # Underqualified - larger penalty
            return max(0.2, 1.0 - 0.2 * (job_level - resume_level))

    def calculate_recency_bonus(
        self, posted_date: datetime, max_bonus_days: int = 7
    ) -> float:
        """
        Calculate bonus for recently posted jobs

        Args:
            posted_date: When job was posted
            max_bonus_days: Days within which full bonus applies

        Returns:
            Recency bonus between 0 and 1
        """
        if not posted_date:
            return 0.5  # Neutral score if date unknown

        # Ensure timezone-aware comparison
        if posted_date.tzinfo is None:
            posted_date = posted_date.replace(tzinfo=timezone.utc)

        now = datetime.now(timezone.utc)
        days_ago = (now - posted_date).days

        if days_ago <= 0:
            return 1.0  # Posted today or in future
        elif days_ago <= max_bonus_days:
            # Linear decay over max_bonus_days
            return 1.0 - (days_ago / max_bonus_days) * 0.5
        elif days_ago <= 30:
            # Slower decay for jobs up to 30 days old
            return 0.5 - (days_ago - max_bonus_days) / (30 - max_bonus_days) * 0.3
        else:
            # Minimal bonus for older jobs
            return max(0.1, 0.2 * (0.9 ** (days_ago - 30)))

    def score_single_job(
        self,
        job_data: Dict[str, Any],
        resume_data: Dict[str, Any],
        resume_embedding: np.ndarray,
        job_embedding: np.ndarray,
    ) -> JobScore:
        """
        Score a single job against a resume

        Args:
            job_data: Job information dictionary
            resume_data: Resume information dictionary
            resume_embedding: Resume embedding vector
            job_embedding: Job embedding vector

        Returns:
            JobScore with all scoring details
        """
        # Calculate vector similarity
        similarity_score = self.similarity_calculator.calculate_similarity(
            resume_embedding, job_embedding, return_all_metrics=True
        )

        # Extract skills and calculate overlap
        resume_skills = resume_data.get("skills", [])
        job_required_skills = job_data.get("required_skills", [])
        job_preferred_skills = job_data.get("preferred_skills", [])

        # Check if we have skills data
        has_skills_data = bool(resume_skills) or bool(job_required_skills) or bool(job_preferred_skills)
        
        if has_skills_data:
            skills_score = self.skills_matcher.match_skills(
                resume_skills, job_required_skills, job_preferred_skills
            )
        else:
            # No skills data available, create a neutral score
            skills_score = SkillsScore(
                exact_matches=[],
                fuzzy_matches=[],
                missing_required=[],
                missing_preferred=[],
                overlap_ratio=0.0,
                weighted_score=0.0,  # Will redistribute weight
            )

        # Calculate geographic score
        geo_score = self.geo_scorer.calculate_geo_score(
            resume_data.get("location", ""),
            job_data.get("location", ""),
            job_data.get("remote_type"),
            resume_data.get("willing_to_relocate", False),
        )

        # Calculate seniority fit
        seniority_fit = self.calculate_seniority_fit(
            resume_data.get("seniority", "mid"), job_data.get("seniority", "mid")
        )

        # Calculate recency bonus
        posted_date = job_data.get("posted_at")
        if isinstance(posted_date, str):
            from datetime import datetime

            posted_date = datetime.fromisoformat(posted_date.replace("Z", "+00:00"))
        recency_bonus = self.calculate_recency_bonus(posted_date)

        # Calculate total score with dynamic weight redistribution
        if not has_skills_data:
            # Redistribute skills weight to other factors when no skills data
            # Increase cosine similarity weight since it's our main signal
            adjusted_weights = ScoringWeights(
                cosine_similarity=self.weights.cosine_similarity + self.weights.skills_overlap * 0.7,
                skills_overlap=0.0,  # No skills data
                seniority_fit=self.weights.seniority_fit + self.weights.skills_overlap * 0.1,
                geographic_score=self.weights.geographic_score + self.weights.skills_overlap * 0.1,
                recency_bonus=self.weights.recency_bonus + self.weights.skills_overlap * 0.1,
            )
            total_score = (
                adjusted_weights.cosine_similarity * similarity_score.normalized_score
                + adjusted_weights.seniority_fit * seniority_fit
                + adjusted_weights.geographic_score * geo_score.score
                + adjusted_weights.recency_bonus * recency_bonus
            )
        else:
            # Use normal weights when skills data is available
            total_score = (
                self.weights.cosine_similarity * similarity_score.normalized_score
                + self.weights.skills_overlap * skills_score.weighted_score
                + self.weights.seniority_fit * seniority_fit
                + self.weights.geographic_score * geo_score.score
                + self.weights.recency_bonus * recency_bonus
            )

        return JobScore(
            job_id=job_data.get("job_id", ""),
            title=job_data.get("title", ""),
            company_name=job_data.get("company_name", ""),
            location=job_data.get("location"),
            posted_at=posted_date if isinstance(posted_date, datetime) else None,
            cosine_sim=similarity_score.normalized_score,
            skill_overlap=skills_score.weighted_score,
            seniority_fit=seniority_fit,
            geodist_km=geo_score.distance_km,
            recency_bonus=recency_bonus,
            similarity_details=similarity_score,
            skills_details=skills_score,
            geo_details=geo_score,
            total_score=total_score,
            weights_used=self.weights,
        )

    def rank_jobs(
        self,
        jobs_data: List[Dict[str, Any]],
        resume_data: Dict[str, Any],
        resume_embedding: np.ndarray,
        job_embeddings: np.ndarray,
        top_k: Optional[int] = None,
        min_score_threshold: float = 0.0,
    ) -> List[JobScore]:
        """
        Rank multiple jobs against a resume

        Args:
            jobs_data: List of job information dictionaries
            resume_data: Resume information dictionary
            resume_embedding: Resume embedding vector
            job_embeddings: Matrix of job embeddings
            top_k: Return only top K results
            min_score_threshold: Minimum score to include in results

        Returns:
            Sorted list of JobScore objects
        """
        if len(jobs_data) != len(job_embeddings):
            raise ValueError(
                f"Number of jobs ({len(jobs_data)}) doesn't match "
                f"number of embeddings ({len(job_embeddings)})"
            )

        # Score all jobs
        scores = []
        for i, job_data in enumerate(jobs_data):
            job_score = self.score_single_job(
                job_data, resume_data, resume_embedding, job_embeddings[i]
            )

            if job_score.total_score >= min_score_threshold:
                scores.append(job_score)

        # Sort by total score (descending)
        scores.sort(key=lambda x: x.total_score, reverse=True)

        # Add ranks and percentiles
        for i, score in enumerate(scores):
            score.rank = i + 1
            score.percentile = (len(scores) - i) / len(scores) * 100 if scores else 0

        # Return top K if specified
        if top_k:
            scores = scores[:top_k]

        return scores

    def get_score_explanation(self, job_score: JobScore) -> Dict[str, Any]:
        """
        Generate human-readable explanation of scoring

        Args:
            job_score: JobScore object

        Returns:
            Dictionary with scoring explanation
        """
        explanation = {
            "overall": {
                "score": job_score.total_score,
                "percentile": job_score.percentile,
                "rank": job_score.rank,
            },
            "factors": {
                "content_similarity": {
                    "score": job_score.cosine_sim,
                    "weight": self.weights.cosine_similarity,
                    "contribution": job_score.cosine_sim
                    * self.weights.cosine_similarity,
                    "description": "How well job description matches resume content",
                },
                "skills_match": {
                    "score": job_score.skill_overlap,
                    "weight": self.weights.skills_overlap,
                    "contribution": job_score.skill_overlap
                    * self.weights.skills_overlap,
                    "description": "Overlap between your skills and job requirements",
                },
                "experience_level": {
                    "score": job_score.seniority_fit,
                    "weight": self.weights.seniority_fit,
                    "contribution": job_score.seniority_fit
                    * self.weights.seniority_fit,
                    "description": "How well experience levels align",
                },
                "location": {
                    "score": (
                        job_score.geo_details.score if job_score.geo_details else 0
                    ),
                    "weight": self.weights.geographic_score,
                    "contribution": (
                        job_score.geo_details.score if job_score.geo_details else 0
                    )
                    * self.weights.geographic_score,
                    "description": "Geographic compatibility",
                },
                "recency": {
                    "score": job_score.recency_bonus,
                    "weight": self.weights.recency_bonus,
                    "contribution": job_score.recency_bonus
                    * self.weights.recency_bonus,
                    "description": "Bonus for recently posted jobs",
                },
            },
        }

        # Add skills details if available
        if job_score.skills_details:
            explanation["skills_breakdown"] = {
                "exact_matches": job_score.skills_details.exact_matches,
                "fuzzy_matches": [
                    {"skill": m.skill, "matched_with": m.matched_with}
                    for m in job_score.skills_details.fuzzy_matches
                ],
                "missing_required": job_score.skills_details.missing_required,
                "missing_preferred": job_score.skills_details.missing_preferred,
            }

        # Add location insights if available
        if job_score.geo_details:
            explanation["location_insights"] = self.geo_scorer.get_location_insights(
                job_score.geo_details
            )

        return explanation

    def optimize_weights(
        self,
        training_data: List[Tuple[JobScore, float]],
        learning_rate: float = 0.01,
        iterations: int = 100,
    ) -> ScoringWeights:
        """
        Optimize scoring weights based on training data

        Args:
            training_data: List of (JobScore, target_score) tuples
            learning_rate: Learning rate for optimization
            iterations: Number of optimization iterations

        Returns:
            Optimized ScoringWeights
        """
        # Simple gradient descent optimization
        weights = ScoringWeights()

        for _ in range(iterations):
            gradients = {
                "cosine": 0,
                "skills": 0,
                "seniority": 0,
                "geo": 0,
                "recency": 0,
            }

            for job_score, target in training_data:
                # Calculate error
                predicted = job_score.total_score
                error = predicted - target

                # Update gradients
                gradients["cosine"] += error * job_score.cosine_sim
                gradients["skills"] += error * job_score.skill_overlap
                gradients["seniority"] += error * job_score.seniority_fit
                gradients["geo"] += error * (
                    job_score.geo_details.score if job_score.geo_details else 0
                )
                gradients["recency"] += error * job_score.recency_bonus

            # Update weights
            weights.cosine_similarity -= (
                learning_rate * gradients["cosine"] / len(training_data)
            )
            weights.skills_overlap -= (
                learning_rate * gradients["skills"] / len(training_data)
            )
            weights.seniority_fit -= (
                learning_rate * gradients["seniority"] / len(training_data)
            )
            weights.geographic_score -= (
                learning_rate * gradients["geo"] / len(training_data)
            )
            weights.recency_bonus -= (
                learning_rate * gradients["recency"] / len(training_data)
            )

            # Ensure weights stay positive and normalize
            weights.cosine_similarity = max(0.05, weights.cosine_similarity)
            weights.skills_overlap = max(0.05, weights.skills_overlap)
            weights.seniority_fit = max(0.05, weights.seniority_fit)
            weights.geographic_score = max(0.05, weights.geographic_score)
            weights.recency_bonus = max(0.05, weights.recency_bonus)
            weights.normalize()

        return weights
