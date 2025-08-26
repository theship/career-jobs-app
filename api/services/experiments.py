"""
Weights & Biases experiment tracking service
"""

import logging
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import wandb

from scoring_engine.ranker import JobScore, ScoringWeights

logger = logging.getLogger(__name__)


@dataclass
class ExperimentConfig:
    """Configuration for a scoring experiment"""

    name: str
    description: Optional[str] = None
    weights: Optional[ScoringWeights] = None
    tags: List[str] = None
    notes: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for W&B config"""
        config = {
            "name": self.name,
            "description": self.description,
            "tags": self.tags or [],
            "notes": self.notes,
        }

        if self.weights:
            config["weights"] = {
                "cosine_similarity": self.weights.cosine_similarity,
                "skills_overlap": self.weights.skills_overlap,
                "seniority_fit": self.weights.seniority_fit,
                "geographic_score": self.weights.geographic_score,
                "recency_bonus": self.weights.recency_bonus,
            }

        return config


class ExperimentTracker:
    """Manage W&B experiment tracking for scoring runs"""

    def __init__(
        self,
        project_name: str = "job-ranker",
        entity: Optional[str] = None,
        mode: Optional[str] = None,
    ):
        """
        Initialize experiment tracker

        Args:
            project_name: W&B project name
            entity: W&B entity (team/user)
            mode: W&B mode ('online', 'offline', 'disabled')
        """
        self.project_name = project_name
        self.entity = entity
        self.mode = mode or os.getenv("WANDB_MODE", "online")
        self.current_run = None

        # Initialize W&B if API key is available
        if os.getenv("WANDB_API_KEY"):
            try:
                wandb.login(key=os.getenv("WANDB_API_KEY"))
            except Exception as e:
                logger.warning(f"Failed to login to W&B: {e}")

    def start_experiment(
        self, config: ExperimentConfig, resume_id: Optional[str] = None
    ) -> Optional[wandb.Run]:
        """
        Start a new W&B experiment run

        Args:
            config: Experiment configuration
            resume_id: Optional resume ID for tracking

        Returns:
            W&B run object or None if disabled
        """
        if self.mode == "disabled":
            logger.info("W&B tracking disabled")
            return None

        try:
            self.current_run = wandb.init(
                project=self.project_name,
                entity=self.entity,
                name=config.name,
                config=config.to_dict(),
                tags=config.tags or [],
                notes=config.notes,
                mode=self.mode,
            )

            # Log additional metadata
            if resume_id:
                self.current_run.config["resume_id"] = resume_id

            self.current_run.config["timestamp"] = datetime.now(
                timezone.utc
            ).isoformat()

            logger.info(f"Started W&B run: {self.current_run.name}")
            return self.current_run

        except Exception as e:
            logger.error(f"Failed to start W&B run: {e}")
            return None

    def log_scoring_run(
        self, scores: List[JobScore], resume_id: str, processing_time_ms: float
    ):
        """
        Log results from a scoring run

        Args:
            scores: List of job scores
            resume_id: Resume ID
            processing_time_ms: Time taken to score in milliseconds
        """
        if not self.current_run:
            return

        try:
            # Log summary statistics
            if scores:
                score_values = [s.total_score for s in scores]
                self.current_run.log(
                    {
                        "scoring/num_jobs": len(scores),
                        "scoring/mean_score": sum(score_values)
                        / len(score_values),
                        "scoring/max_score": max(score_values),
                        "scoring/min_score": min(score_values),
                        "scoring/processing_time_ms": processing_time_ms,
                        "scoring/resume_id": resume_id,
                    }
                )

                # Log score distribution
                import numpy as np

                histogram = np.histogram(score_values, bins=10, range=(0, 1))
                self.current_run.log(
                    {
                        "scoring/score_distribution": wandb.Histogram(
                            np_histogram=histogram
                        )
                    }
                )

                # Log top matches
                top_10 = scores[:10]
                for i, score in enumerate(top_10):
                    self.current_run.log(
                        {
                            f"top_matches/{i+1}_score": score.total_score,
                            f"top_matches/{i+1}_title": score.title,
                            f"top_matches/{i+1}_company": score.company_name,
                        }
                    )

                # Log factor contributions for top match
                if scores[0]:
                    top_score = scores[0]
                    self.current_run.log(
                        {
                            "factors/cosine_sim": top_score.cosine_sim,
                            "factors/skill_overlap": top_score.skill_overlap,
                            "factors/seniority_fit": top_score.seniority_fit,
                            "factors/geo_score": (
                                top_score.geo_details.score
                                if top_score.geo_details
                                else 0
                            ),
                            "factors/recency_bonus": top_score.recency_bonus,
                        }
                    )

        except Exception as e:
            logger.error(f"Failed to log scoring run: {e}")

    def log_weight_optimization(
        self,
        sweep_config: Dict[str, Any],
        best_weights: ScoringWeights,
        best_metric: float,
    ):
        """
        Log results from weight optimization sweep

        Args:
            sweep_config: W&B sweep configuration
            best_weights: Best weights found
            best_metric: Best metric value achieved
        """
        if not self.current_run:
            return

        try:
            self.current_run.log(
                {
                    "optimization/best_metric": best_metric,
                    "optimization/best_cosine_weight": best_weights.cosine_similarity,
                    "optimization/best_skills_weight": best_weights.skills_overlap,
                    "optimization/best_seniority_weight": best_weights.seniority_fit,
                    "optimization/best_geo_weight": best_weights.geographic_score,
                    "optimization/best_recency_weight": best_weights.recency_bonus,
                    "optimization/sweep_config": sweep_config,
                }
            )

            # Save best weights as artifact
            self.save_weights_artifact(
                best_weights, f"optimized_weights_{best_metric:.3f}"
            )

        except Exception as e:
            logger.error(f"Failed to log weight optimization: {e}")

    def save_weights_artifact(
        self, weights: ScoringWeights, artifact_name: str
    ):
        """
        Save scoring weights as W&B artifact

        Args:
            weights: Scoring weights to save
            artifact_name: Name for the artifact
        """
        if not self.current_run:
            return

        try:
            artifact = wandb.Artifact(
                artifact_name,
                type="model_weights",
                description="Scoring weights configuration",
                metadata={
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "validated": weights.validate(),
                },
            )

            # Save weights as JSON
            import json
            import tempfile

            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".json", delete=False
            ) as f:
                json.dump(asdict(weights), f)
                weights_file = f.name

            artifact.add_file(weights_file)
            self.current_run.log_artifact(artifact)

            # Clean up temp file
            os.unlink(weights_file)

            logger.info(f"Saved weights artifact: {artifact_name}")

        except Exception as e:
            logger.error(f"Failed to save weights artifact: {e}")

    def load_weights_artifact(
        self, artifact_name: str, version: str = "latest"
    ) -> Optional[ScoringWeights]:
        """
        Load scoring weights from W&B artifact

        Args:
            artifact_name: Name of the artifact
            version: Version to load (default: latest)

        Returns:
            ScoringWeights object or None if not found
        """
        try:
            api = wandb.Api()
            artifact = api.artifact(
                f"{self.entity}/{self.project_name}/{artifact_name}:{version}"
            )

            # Download artifact
            artifact_dir = artifact.download()

            # Load weights from JSON
            import json

            weights_file = os.path.join(artifact_dir, f"{artifact_name}.json")

            with open(weights_file, "r") as f:
                weights_dict = json.load(f)

            return ScoringWeights(**weights_dict)

        except Exception as e:
            logger.error(f"Failed to load weights artifact: {e}")
            return None

    def create_sweep(self, sweep_config: Dict[str, Any]) -> Optional[str]:
        """
        Create a W&B sweep for hyperparameter optimization

        Args:
            sweep_config: Sweep configuration dictionary

        Returns:
            Sweep ID or None if failed
        """
        try:
            sweep_id = wandb.sweep(
                sweep_config, project=self.project_name, entity=self.entity
            )

            logger.info(f"Created W&B sweep: {sweep_id}")
            return sweep_id

        except Exception as e:
            logger.error(f"Failed to create sweep: {e}")
            return None

    def run_sweep_agent(
        self, sweep_id: str, function: callable, count: Optional[int] = None
    ):
        """
        Run a sweep agent for hyperparameter optimization

        Args:
            sweep_id: W&B sweep ID
            function: Function to optimize
            count: Number of runs (None for continuous)
        """
        try:
            wandb.agent(
                sweep_id,
                function=function,
                count=count,
                project=self.project_name,
                entity=self.entity,
            )
        except Exception as e:
            logger.error(f"Failed to run sweep agent: {e}")

    def finish_experiment(self):
        """Finish the current W&B run"""
        if self.current_run:
            try:
                self.current_run.finish()
                logger.info(f"Finished W&B run: {self.current_run.name}")
            except Exception as e:
                logger.error(f"Failed to finish W&B run: {e}")
            finally:
                self.current_run = None

    def log_evaluation_dataset(
        self,
        dataset_name: str,
        resumes: List[Dict[str, Any]],
        jobs: List[Dict[str, Any]],
        ground_truth: Optional[List[Dict[str, Any]]] = None,
    ):
        """
        Log an evaluation dataset as W&B artifact

        Args:
            dataset_name: Name for the dataset
            resumes: List of resume data
            jobs: List of job data
            ground_truth: Optional ground truth matches
        """
        if not self.current_run:
            return

        try:
            artifact = wandb.Artifact(
                dataset_name,
                type="evaluation_dataset",
                description="Dataset for scoring evaluation",
                metadata={
                    "num_resumes": len(resumes),
                    "num_jobs": len(jobs),
                    "has_ground_truth": ground_truth is not None,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                },
            )

            # Create tables
            import tempfile

            import pandas as pd

            with tempfile.TemporaryDirectory() as tmpdir:
                # Save resumes
                resumes_df = pd.DataFrame(resumes)
                resumes_path = os.path.join(tmpdir, "resumes.csv")
                resumes_df.to_csv(resumes_path, index=False)
                artifact.add_file(resumes_path)

                # Save jobs
                jobs_df = pd.DataFrame(jobs)
                jobs_path = os.path.join(tmpdir, "jobs.csv")
                jobs_df.to_csv(jobs_path, index=False)
                artifact.add_file(jobs_path)

                # Save ground truth if provided
                if ground_truth:
                    gt_df = pd.DataFrame(ground_truth)
                    gt_path = os.path.join(tmpdir, "ground_truth.csv")
                    gt_df.to_csv(gt_path, index=False)
                    artifact.add_file(gt_path)

            self.current_run.log_artifact(artifact)
            logger.info(f"Logged evaluation dataset: {dataset_name}")

        except Exception as e:
            logger.error(f"Failed to log evaluation dataset: {e}")


def get_default_sweep_config() -> Dict[str, Any]:
    """
    Get default W&B sweep configuration for weight optimization

    Returns:
        Sweep configuration dictionary
    """
    return {
        "name": "scoring_weights_optimization",
        "method": "bayes",  # Bayesian optimization
        "metric": {
            "name": "validation_ndcg",  # Normalized Discounted Cumulative Gain
            "goal": "maximize",
        },
        "parameters": {
            "cosine_weight": {"min": 0.3, "max": 0.7},
            "skills_weight": {"min": 0.1, "max": 0.4},
            "seniority_weight": {"min": 0.05, "max": 0.2},
            "geo_weight": {"min": 0.05, "max": 0.2},
            "recency_weight": {"min": 0.05, "max": 0.15},
        },
        "early_terminate": {"type": "hyperband", "min_iter": 3},
    }
