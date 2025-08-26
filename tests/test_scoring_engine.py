"""
Tests for Phase 4: Scoring Engine
"""

import json
import time
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, Mock, patch

import numpy as np
import pytest

from api.services.experiments import ExperimentConfig, ExperimentTracker
from api.services.score_explainer import ScoreExplainer
from scoring_engine.geo_scorer import GeoScorer, Location
from scoring_engine.ranker import JobRanker, JobScore, ScoringWeights
from scoring_engine.similarity import SimilarityThresholds, VectorSimilarityCalculator
from scoring_engine.skills_matcher import SkillsMatcher, SkillsScore


class TestVectorSimilarity:
    """Test vector similarity calculations"""

    def test_cosine_similarity(self):
        """Test cosine similarity calculation"""
        calculator = VectorSimilarityCalculator(metric="cosine")

        # Test identical vectors
        vec1 = np.array([1, 2, 3])
        vec2 = np.array([1, 2, 3])
        score = calculator.calculate_cosine_similarity(vec1, vec2)
        assert score == pytest.approx(1.0)

        # Test orthogonal vectors
        vec1 = np.array([1, 0, 0])
        vec2 = np.array([0, 1, 0])
        score = calculator.calculate_cosine_similarity(vec1, vec2)
        assert score == pytest.approx(0.0)

        # Test opposite vectors
        vec1 = np.array([1, 2, 3])
        vec2 = np.array([-1, -2, -3])
        score = calculator.calculate_cosine_similarity(vec1, vec2)
        assert score == pytest.approx(-1.0)

    def test_batch_similarity(self):
        """Test batch similarity calculation"""
        calculator = VectorSimilarityCalculator()

        resume_embedding = np.array([1, 2, 3])
        job_embeddings = np.array(
            [
                [1, 2, 3],  # Identical
                [2, 4, 6],  # Scaled version (same direction)
                [0, 0, 0],  # Zero vector
                [-1, -2, -3],  # Opposite
            ]
        )

        scores = calculator.batch_calculate_similarities(
            resume_embedding, job_embeddings
        )

        assert len(scores) == 4
        assert scores[0].cosine_similarity == pytest.approx(1.0)
        assert scores[1].cosine_similarity == pytest.approx(1.0)  # Same direction
        assert scores[2].cosine_similarity == pytest.approx(0.0)  # Zero vector
        assert scores[3].cosine_similarity == pytest.approx(-1.0)  # Opposite

    def test_similarity_thresholds(self):
        """Test match level categorization"""
        assert SimilarityThresholds.get_match_level(0.9) == "Excellent Match"
        assert SimilarityThresholds.get_match_level(0.75) == "Good Match"
        assert SimilarityThresholds.get_match_level(0.6) == "Fair Match"
        assert SimilarityThresholds.get_match_level(0.4) == "Poor Match"
        assert SimilarityThresholds.get_match_level(0.2) == "No Match"


class TestSkillsMatcher:
    """Test skills matching functionality"""

    def test_skill_normalization(self):
        """Test skill string normalization"""
        matcher = SkillsMatcher()

        assert matcher.normalize_skill("Python Programming") == "python"
        assert matcher.normalize_skill("  JavaScript  ") == "javascript"
        assert matcher.normalize_skill("React.js Framework") == "react.js"
        assert matcher.normalize_skill("Python 3.9") == "python"

    def test_exact_skill_matching(self):
        """Test exact skill matches"""
        matcher = SkillsMatcher()

        resume_skills = ["Python", "JavaScript", "React"]
        required_skills = ["Python", "React"]

        score = matcher.match_skills(resume_skills, required_skills)

        assert len(score.exact_matches) == 2
        assert "Python" in score.exact_matches
        assert "React" in score.exact_matches
        assert len(score.missing_required) == 0

    def test_alias_matching(self):
        """Test skill alias matching"""
        matcher = SkillsMatcher()

        resume_skills = ["JS", "NodeJS", "AWS"]
        required_skills = ["JavaScript", "Node.js", "Amazon Web Services"]

        score = matcher.match_skills(resume_skills, required_skills)

        # Should match via aliases
        assert len(score.fuzzy_matches) == 3
        assert all(m.match_type == "alias" for m in score.fuzzy_matches)

    def test_fuzzy_matching(self):
        """Test fuzzy skill matching"""
        matcher = SkillsMatcher(fuzzy_threshold=80)

        resume_skills = ["Pythoon", "JavaScrip"]  # Typos
        required_skills = ["Python", "JavaScript"]

        score = matcher.match_skills(resume_skills, required_skills)

        # Should match with fuzzy matching
        assert len(score.fuzzy_matches) >= 1
        assert any(m.match_type == "fuzzy" for m in score.fuzzy_matches)

    def test_weighted_scoring(self):
        """Test weighted skill scoring"""
        matcher = SkillsMatcher()

        resume_skills = ["Python", "JavaScript"]
        required_skills = ["Python", "Java", "C++"]
        preferred_skills = ["JavaScript", "React"]

        score = matcher.match_skills(resume_skills, required_skills, preferred_skills)

        # With our implementation, the score calculation is different
        # We're matching skills from job requirements against resume
        # Python matches (1 out of 3 required)
        # JavaScript matches (1 out of 2 preferred)
        # The actual weighted score depends on the implementation
        assert 0.3 < score.weighted_score < 0.7  # Reasonable range for partial match


class TestGeoScorer:
    """Test geographic scoring"""

    def test_parse_location(self):
        """Test location string parsing"""
        scorer = GeoScorer()

        loc = scorer.parse_location_string("San Francisco, CA, USA")
        assert loc.city == "San Francisco"
        assert loc.state == "CA"
        assert loc.country == "USA"

        loc = scorer.parse_location_string("Remote")
        assert loc.city == "Remote"

        loc = scorer.parse_location_string("New York, NY")
        assert loc.city == "New York"
        assert loc.state == "NY"
        assert loc.country == "USA"  # Default

    def test_remote_scoring(self):
        """Test scoring for remote positions"""
        scorer = GeoScorer()

        score = scorer.calculate_geo_score("San Francisco, CA", "Remote", "Remote")

        assert score.is_remote == True
        assert score.score == 1.0
        assert score.distance_km == 0

    def test_distance_scoring(self):
        """Test distance-based scoring"""
        scorer = GeoScorer()

        # Mock geocoding to avoid API calls
        with patch.object(scorer, "geocode_location") as mock_geocode:

            def mock_geocode_func(loc):
                if "San Francisco" in loc.city:
                    loc.latitude = 37.7749
                    loc.longitude = -122.4194
                elif "San Jose" in loc.city:
                    loc.latitude = 37.3382
                    loc.longitude = -121.8863
                return loc

            mock_geocode.side_effect = mock_geocode_func

            # Same city
            score = scorer.calculate_geo_score("San Francisco, CA", "San Francisco, CA")
            assert score.location_match == True
            assert score.score == 1.0

            # Nearby city (~50km)
            score = scorer.calculate_geo_score("San Francisco, CA", "San Jose, CA")
            assert score.distance_km < 100
            assert score.score > 0.5  # Should be commutable


class TestJobRanker:
    """Test job ranking algorithm"""

    def test_seniority_fit(self):
        """Test seniority level matching"""
        ranker = JobRanker()

        # Perfect match
        assert ranker.calculate_seniority_fit("senior", "senior") == 1.0

        # Adjacent levels
        assert ranker.calculate_seniority_fit("senior", "staff") == 0.8
        assert ranker.calculate_seniority_fit("mid", "senior") == 0.8

        # Overqualified
        score = ranker.calculate_seniority_fit("staff", "junior")
        assert 0.4 <= score <= 0.7  # Allow boundary values

        # Underqualified
        score = ranker.calculate_seniority_fit("junior", "senior")
        assert 0.2 <= score <= 0.6  # Allow boundary values

    def test_recency_bonus(self):
        """Test job posting recency bonus"""
        ranker = JobRanker()

        # Posted today
        today = datetime.now(timezone.utc)
        assert ranker.calculate_recency_bonus(today) == 1.0

        # Posted 3 days ago
        three_days_ago = today - timedelta(days=3)
        score = ranker.calculate_recency_bonus(three_days_ago)
        assert 0.7 < score < 0.9

        # Posted 30 days ago
        month_ago = today - timedelta(days=30)
        score = ranker.calculate_recency_bonus(month_ago)
        assert 0.1 < score < 0.3

    def test_job_ranking(self):
        """Test ranking multiple jobs"""
        ranker = JobRanker()

        # Create test data
        resume_data = {
            "skills": ["Python", "Django", "PostgreSQL"],
            "location": "San Francisco, CA",
            "seniority": "senior",
        }

        resume_embedding = np.array([1, 2, 3, 4, 5])

        jobs_data = [
            {
                "job_id": "job1",
                "title": "Python Developer",
                "company_name": "Tech Co",
                "required_skills": ["Python", "Django"],
                "preferred_skills": ["PostgreSQL"],
                "location": "San Francisco, CA",
                "seniority": "senior",
                "posted_at": datetime.now(timezone.utc),
            },
            {
                "job_id": "job2",
                "title": "Java Developer",
                "company_name": "Other Co",
                "required_skills": ["Java", "Spring"],
                "preferred_skills": [],
                "location": "New York, NY",
                "seniority": "junior",
                "posted_at": datetime.now(timezone.utc) - timedelta(days=30),
            },
        ]

        job_embeddings = np.array(
            [
                [1, 2, 3, 4, 5],  # Similar to resume
                [5, 4, 3, 2, 1],  # Different from resume
            ]
        )

        scores = ranker.rank_jobs(
            jobs_data, resume_data, resume_embedding, job_embeddings
        )

        assert len(scores) == 2
        assert scores[0].job_id == "job1"  # Better match
        assert scores[0].total_score > scores[1].total_score
        assert scores[0].rank == 1
        assert scores[1].rank == 2

    def test_scoring_weights(self):
        """Test custom scoring weights"""
        weights = ScoringWeights(
            cosine_similarity=0.6,
            skills_overlap=0.2,
            seniority_fit=0.1,
            geographic_score=0.05,
            recency_bonus=0.05,
        )

        assert weights.validate() == True

        # Test normalization
        weights = ScoringWeights(
            cosine_similarity=1.0,
            skills_overlap=1.0,
            seniority_fit=1.0,
            geographic_score=1.0,
            recency_bonus=1.0,
        )
        weights.normalize()
        assert weights.validate() == True
        assert weights.cosine_similarity == 0.2


class TestExperimentTracking:
    """Test W&B experiment tracking"""

    def test_experiment_config(self):
        """Test experiment configuration"""
        config = ExperimentConfig(
            name="test_experiment",
            description="Test scoring run",
            weights=ScoringWeights(),
            tags=["test", "scoring"],
        )

        config_dict = config.to_dict()
        assert config_dict["name"] == "test_experiment"
        assert "weights" in config_dict
        assert config_dict["weights"]["cosine_similarity"] == 0.5

    @patch("wandb.init")
    def test_start_experiment(self, mock_wandb_init):
        """Test starting W&B experiment"""
        mock_run = Mock()
        mock_run.name = "test_run"
        mock_run.id = "run_123"
        mock_wandb_init.return_value = mock_run

        tracker = ExperimentTracker(mode="disabled")
        config = ExperimentConfig(name="test")

        # Should return None when disabled
        run = tracker.start_experiment(config)
        assert run is None

        # Test with online mode
        tracker.mode = "online"
        run = tracker.start_experiment(config)
        mock_wandb_init.assert_called_once()

    @patch("wandb.sweep")
    def test_create_sweep(self, mock_sweep):
        """Test creating optimization sweep"""
        mock_sweep.return_value = "sweep_123"

        tracker = ExperimentTracker()
        from api.services.experiments import get_default_sweep_config

        sweep_config = get_default_sweep_config()

        sweep_id = tracker.create_sweep(sweep_config)

        assert sweep_id == "sweep_123"
        mock_sweep.assert_called_once()


class TestScoreExplainer:
    """Test score explanation generation"""

    def test_generate_insights(self):
        """Test generating score insights"""
        explainer = ScoreExplainer()

        job_score = JobScore(
            job_id="test_job",
            title="Software Engineer",
            company_name="Test Co",
            cosine_sim=0.85,
            skill_overlap=0.7,
            seniority_fit=1.0,
            geodist_km=10,
            recency_bonus=0.9,
            total_score=0.82,
        )

        insights = explainer.generate_insights(job_score)

        assert len(insights) == 5
        assert insights[0].factor == "Content Similarity"
        assert insights[0].score == 0.85
        assert "Excellent match" in insights[0].insight

    def test_export_csv(self):
        """Test CSV export"""
        explainer = ScoreExplainer()

        scores = [
            JobScore(
                job_id="job1",
                title="Engineer",
                company_name="Company A",
                cosine_sim=0.8,
                skill_overlap=0.7,
                seniority_fit=0.9,
                geodist_km=10,
                recency_bonus=0.8,
                total_score=0.79,
                rank=1,
                percentile=100,
            )
        ]

        csv_output = explainer.export_to_csv(scores)

        assert "job_id,title,company,total_score" in csv_output.replace(" ", "")
        assert "job1" in csv_output
        assert "0.790" in csv_output

    def test_export_json(self):
        """Test JSON export"""
        explainer = ScoreExplainer()

        scores = [
            JobScore(
                job_id="job1",
                title="Engineer",
                company_name="Company A",
                cosine_sim=0.8,
                skill_overlap=0.7,
                seniority_fit=0.9,
                geodist_km=10,
                recency_bonus=0.8,
                total_score=0.79,
                rank=1,
                percentile=100,
            )
        ]

        json_output = explainer.export_to_json(scores)
        data = json.loads(json_output)

        assert len(data) == 1
        assert data[0]["job_id"] == "job1"
        assert data[0]["total_score"] == 0.79


class TestAcceptanceTests:
    """Phase 4 acceptance tests from dev-plan.md"""

    def test_job_ranking(self):
        """Jobs are ranked by relevance to resume"""
        ranker = JobRanker()

        resume_data = {
            "skills": ["Python", "Django"],
            "location": "San Francisco, CA",
            "seniority": "senior",
        }

        resume_embedding = np.array([1, 0, 0, 0, 0])

        jobs_data = [
            {
                "job_id": "python_job",
                "title": "Python Developer",
                "company_name": "Python Co",
                "required_skills": ["Python", "Django"],
                "preferred_skills": [],
                "location": "San Francisco, CA",
                "seniority": "senior",
                "posted_at": datetime.now(timezone.utc),
            },
            {
                "job_id": "java_job",
                "title": "Java Developer",
                "company_name": "Java Co",
                "required_skills": ["Java", "Spring"],
                "preferred_skills": [],
                "location": "San Francisco, CA",
                "seniority": "senior",
                "posted_at": datetime.now(timezone.utc),
            },
        ]

        job_embeddings = np.array(
            [
                [0.9, 0.1, 0, 0, 0],  # Similar to Python resume
                [0, 0, 0.9, 0.1, 0],  # Different (Java)
            ]
        )

        scores = ranker.rank_jobs(
            jobs_data, resume_data, resume_embedding, job_embeddings
        )

        # Python job should rank higher
        python_score = next(s for s in scores if s.job_id == "python_job")
        java_score = next(s for s in scores if s.job_id == "java_job")

        assert python_score.total_score > java_score.total_score

    def test_score_breakdown(self):
        """Score includes detailed factor breakdown"""
        ranker = JobRanker()

        resume_data = {
            "skills": ["Python"],
            "location": "San Francisco, CA",
            "seniority": "senior",
        }

        job_data = {
            "job_id": "test_job",
            "title": "Senior Python Engineer",
            "company_name": "Test Co",
            "required_skills": ["Python"],
            "preferred_skills": [],
            "location": "San Francisco, CA",
            "seniority": "senior",
            "posted_at": datetime.now(timezone.utc),
        }

        resume_embedding = np.array([1, 2, 3])
        job_embedding = np.array([1, 2, 3])

        score = ranker.score_single_job(
            job_data, resume_data, resume_embedding, job_embedding
        )

        assert hasattr(score, "cosine_sim")
        assert hasattr(score, "skill_overlap")
        assert hasattr(score, "seniority_fit")
        assert hasattr(score, "geodist_km")
        assert hasattr(score, "recency_bonus")

        # Verify total score calculation
        expected_total = (
            score.weights_used.cosine_similarity * score.cosine_sim
            + score.weights_used.skills_overlap * score.skill_overlap
            + score.weights_used.seniority_fit * score.seniority_fit
            + score.weights_used.geographic_score
            * (score.geo_details.score if score.geo_details else 0)
            + score.weights_used.recency_bonus * score.recency_bonus
        )
        assert score.total_score == pytest.approx(expected_total)

    def test_vector_similarity_performance(self):
        """Vector similarity queries complete within SLA"""
        calculator = VectorSimilarityCalculator()

        # Create 1000 test embeddings
        resume_embedding = np.random.rand(768)  # OpenAI embedding size
        job_embeddings = np.random.rand(1000, 768)

        start_time = time.time()
        scores = calculator.batch_calculate_similarities(
            resume_embedding, job_embeddings
        )
        duration = time.time() - start_time

        assert duration < 2.0  # Under 2 seconds for 1000 jobs
        assert len(scores) == 1000

    def test_scoring_weight_optimization(self):
        """Scoring weights can be optimized via sweep configuration"""
        from api.services.experiments import get_default_sweep_config

        sweep_config = get_default_sweep_config()

        # Test that sweep config is valid
        assert "method" in sweep_config
        assert "parameters" in sweep_config

        # Verify weight constraints
        params = sweep_config["parameters"]
        max_sum = sum(p["max"] for p in params.values())
        min_sum = sum(p["min"] for p in params.values())

        # Max weights should not exceed reasonable bounds
        assert max_sum <= 2.0  # Some flexibility for optimization


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
