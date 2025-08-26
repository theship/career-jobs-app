"""
Vector similarity calculation for job-resume matching
"""

import logging
from dataclasses import dataclass
from typing import List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class SimilarityScore:
    """Container for similarity calculation results"""

    cosine_similarity: float
    euclidean_distance: float
    dot_product: float
    normalized_score: float  # 0-1 score for use in ranking


class VectorSimilarityCalculator:
    """Calculate various similarity metrics between resume and job embeddings"""

    def __init__(self, metric: str = "cosine"):
        """
        Initialize similarity calculator

        Args:
            metric: Primary metric to use ('cosine', 'euclidean', 'dot')
        """
        self.metric = metric

    def calculate_cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """
        Calculate cosine similarity between two vectors

        Args:
            vec1: First embedding vector
            vec2: Second embedding vector

        Returns:
            Cosine similarity score between -1 and 1
        """
        # Handle zero vectors
        if np.all(vec1 == 0) or np.all(vec2 == 0):
            return 0.0

        # Normalize vectors
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        # Calculate cosine similarity
        cosine_sim = np.dot(vec1, vec2) / (norm1 * norm2)

        return float(cosine_sim)

    def calculate_euclidean_distance(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """
        Calculate Euclidean distance between two vectors

        Args:
            vec1: First embedding vector
            vec2: Second embedding vector

        Returns:
            Euclidean distance (lower is better)
        """
        return float(np.linalg.norm(vec1 - vec2))

    def calculate_dot_product(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """
        Calculate dot product between two vectors

        Args:
            vec1: First embedding vector
            vec2: Second embedding vector

        Returns:
            Dot product score
        """
        return float(np.dot(vec1, vec2))

    def normalize_score(
        self, score: float, metric: str, max_distance: Optional[float] = None
    ) -> float:
        """
        Normalize score to 0-1 range

        Args:
            score: Raw similarity/distance score
            metric: Metric type ('cosine', 'euclidean', 'dot')
            max_distance: Maximum distance for euclidean normalization

        Returns:
            Normalized score between 0 and 1
        """
        if metric == "cosine":
            # Cosine similarity ranges from -1 to 1, normalize to 0-1
            return (score + 1) / 2
        elif metric == "euclidean":
            # Euclidean distance: closer is better
            # Use exponential decay for smooth normalization
            if max_distance:
                return max(0, 1 - score / max_distance)
            else:
                # Use exponential decay without max distance
                return np.exp(-score / 10)  # Adjust scale factor as needed
        elif metric == "dot":
            # Dot product can be any value, use sigmoid
            return 1 / (1 + np.exp(-score))
        else:
            return score

    def calculate_similarity(
        self,
        resume_embedding: np.ndarray,
        job_embedding: np.ndarray,
        return_all_metrics: bool = False,
    ) -> SimilarityScore:
        """
        Calculate similarity between resume and job embeddings

        Args:
            resume_embedding: Resume embedding vector
            job_embedding: Job embedding vector
            return_all_metrics: Whether to calculate all metrics or just primary

        Returns:
            SimilarityScore with calculated metrics
        """
        # Ensure numpy arrays
        if not isinstance(resume_embedding, np.ndarray):
            resume_embedding = np.array(resume_embedding)
        if not isinstance(job_embedding, np.ndarray):
            job_embedding = np.array(job_embedding)

        # Validate dimensions
        if resume_embedding.shape != job_embedding.shape:
            raise ValueError(
                f"Embedding dimensions mismatch: "
                f"{resume_embedding.shape} vs {job_embedding.shape}"
            )

        # Calculate primary metric
        if self.metric == "cosine":
            cosine_sim = self.calculate_cosine_similarity(
                resume_embedding, job_embedding
            )
            normalized = self.normalize_score(cosine_sim, "cosine")
        else:
            cosine_sim = 0.0
            normalized = 0.0

        # Calculate other metrics if requested
        if return_all_metrics:
            euclidean_dist = self.calculate_euclidean_distance(
                resume_embedding, job_embedding
            )
            dot_prod = self.calculate_dot_product(resume_embedding, job_embedding)
        else:
            euclidean_dist = (
                0.0
                if self.metric != "euclidean"
                else self.calculate_euclidean_distance(resume_embedding, job_embedding)
            )
            dot_prod = (
                0.0
                if self.metric != "dot"
                else self.calculate_dot_product(resume_embedding, job_embedding)
            )

        # Update normalized score for non-cosine metrics
        if self.metric == "euclidean":
            normalized = self.normalize_score(euclidean_dist, "euclidean")
        elif self.metric == "dot":
            normalized = self.normalize_score(dot_prod, "dot")

        return SimilarityScore(
            cosine_similarity=cosine_sim,
            euclidean_distance=euclidean_dist,
            dot_product=dot_prod,
            normalized_score=normalized,
        )

    def batch_calculate_similarities(
        self, resume_embedding: np.ndarray, job_embeddings: np.ndarray
    ) -> List[SimilarityScore]:
        """
        Calculate similarities for multiple jobs efficiently

        Args:
            resume_embedding: Single resume embedding vector
            job_embeddings: Matrix of job embeddings (n_jobs x embedding_dim)

        Returns:
            List of SimilarityScore objects
        """
        if not isinstance(resume_embedding, np.ndarray):
            resume_embedding = np.array(resume_embedding)
        if not isinstance(job_embeddings, np.ndarray):
            job_embeddings = np.array(job_embeddings)

        # Ensure resume is 1D
        if resume_embedding.ndim == 2:
            resume_embedding = resume_embedding.squeeze()

        # Validate dimensions
        if len(job_embeddings.shape) != 2:
            raise ValueError(
                f"Expected 2D job embeddings, got shape {job_embeddings.shape}"
            )
        if resume_embedding.shape[0] != job_embeddings.shape[1]:
            raise ValueError(
                f"Dimension mismatch: resume {resume_embedding.shape} "
                f"vs jobs {job_embeddings.shape}"
            )

        scores = []

        # Batch calculate cosine similarities
        if self.metric == "cosine":
            # Normalize resume vector
            resume_norm = np.linalg.norm(resume_embedding)
            if resume_norm > 0:
                resume_normalized = resume_embedding / resume_norm
            else:
                resume_normalized = resume_embedding

            # Normalize job vectors
            job_norms = np.linalg.norm(job_embeddings, axis=1, keepdims=True)
            job_norms[job_norms == 0] = 1  # Avoid division by zero
            jobs_normalized = job_embeddings / job_norms

            # Batch cosine similarity
            cosine_sims = np.dot(jobs_normalized, resume_normalized)

            for i, cosine_sim in enumerate(cosine_sims):
                scores.append(
                    SimilarityScore(
                        cosine_similarity=float(cosine_sim),
                        euclidean_distance=0.0,
                        dot_product=0.0,
                        normalized_score=self.normalize_score(
                            float(cosine_sim), "cosine"
                        ),
                    )
                )
        else:
            # Fall back to individual calculations for other metrics
            for job_embedding in job_embeddings:
                scores.append(
                    self.calculate_similarity(resume_embedding, job_embedding)
                )

        return scores


class SimilarityThresholds:
    """Define thresholds for similarity scoring"""

    EXCELLENT_MATCH = 0.85  # > 85% similarity
    GOOD_MATCH = 0.70  # 70-85% similarity
    FAIR_MATCH = 0.50  # 50-70% similarity
    POOR_MATCH = 0.30  # 30-50% similarity

    @classmethod
    def get_match_level(cls, score: float) -> str:
        """
        Get match level description for a similarity score

        Args:
            score: Normalized similarity score (0-1)

        Returns:
            Match level description
        """
        if score >= cls.EXCELLENT_MATCH:
            return "Excellent Match"
        elif score >= cls.GOOD_MATCH:
            return "Good Match"
        elif score >= cls.FAIR_MATCH:
            return "Fair Match"
        elif score >= cls.POOR_MATCH:
            return "Poor Match"
        else:
            return "No Match"
