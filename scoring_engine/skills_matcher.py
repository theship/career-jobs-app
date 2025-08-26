"""
Skills matching and comparison for job-resume scoring
"""

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple

from fuzzywuzzy import fuzz

logger = logging.getLogger(__name__)


@dataclass
class SkillMatch:
    """Container for skill matching results"""

    skill: str
    matched_with: Optional[str]
    match_type: str  # 'exact', 'fuzzy', 'alias', 'related'
    confidence: float  # 0-1 confidence score


@dataclass
class SkillsScore:
    """Container for skills comparison results"""

    exact_matches: List[str]
    fuzzy_matches: List[SkillMatch]
    missing_required: List[str]
    missing_preferred: List[str]
    overlap_ratio: float  # Jaccard similarity
    weighted_score: float  # Final normalized score


class SkillsMatcher:
    """Match and score skills between resumes and jobs"""

    def __init__(
        self,
        fuzzy_threshold: int = 85,
        skill_aliases: Optional[Dict[str, List[str]]] = None,
    ):
        """
        Initialize skills matcher

        Args:
            fuzzy_threshold: Minimum fuzzy match score (0-100)
            skill_aliases: Dictionary mapping skills to their aliases
        """
        self.fuzzy_threshold = fuzzy_threshold
        self.skill_aliases = skill_aliases or self._default_aliases()

    def _default_aliases(self) -> Dict[str, List[str]]:
        """Get default skill aliases mapping"""
        return {
            "JavaScript": ["JS", "Javascript", "ECMAScript", "ES6", "ES2015"],
            "TypeScript": ["TS", "Typescript"],
            "Python": ["Python3", "Python 3", "Py"],
            "Machine Learning": ["ML", "Machine-Learning", "MachineLearning"],
            "Artificial Intelligence": ["AI", "A.I.", "Artificial-Intelligence"],
            "Natural Language Processing": ["NLP", "Natural-Language-Processing"],
            "React": ["ReactJS", "React.js"],
            "Angular": ["AngularJS", "Angular.js"],
            "Vue": ["VueJS", "Vue.js"],
            "Node.js": ["NodeJS", "Node"],
            "PostgreSQL": ["Postgres", "PgSQL"],
            "MongoDB": ["Mongo"],
            "Amazon Web Services": ["AWS", "Amazon-Web-Services"],
            "Google Cloud Platform": ["GCP", "Google-Cloud"],
            "Microsoft Azure": ["Azure", "MS Azure"],
            "Docker": ["Docker Container", "Containerization"],
            "Kubernetes": ["K8s", "K8"],
            "CI/CD": ["CI-CD", "Continuous Integration", "Continuous Deployment"],
            "REST API": ["REST", "RESTful", "RESTful API"],
            "GraphQL": ["Graph QL"],
            "SQL": ["Structured Query Language"],
            "NoSQL": ["No-SQL", "Non-relational"],
            "Git": ["GitHub", "GitLab", "Version Control"],
            "Agile": ["Scrum", "Agile Methodology"],
            "Test-Driven Development": ["TDD", "Test Driven Development"],
            "Object-Oriented Programming": ["OOP", "Object Oriented"],
            "Data Science": ["DataScience", "Data-Science"],
            "Deep Learning": ["DL", "Deep-Learning", "DeepLearning"],
            "Computer Vision": ["CV", "Computer-Vision"],
            "DevOps": ["Dev-Ops", "Development Operations"],
        }

    def normalize_skill(self, skill: str) -> str:
        """
        Normalize skill string for comparison

        Args:
            skill: Raw skill string

        Returns:
            Normalized skill string
        """
        # Convert to lowercase and strip whitespace
        normalized = skill.lower().strip()

        # Remove common suffixes/prefixes
        for suffix in [" development", " programming", " language", " framework"]:
            if normalized.endswith(suffix):
                normalized = normalized[: -len(suffix)]

        # Handle version numbers (e.g., "Python 3.9" -> "Python")
        import re

        normalized = re.sub(r"\s+\d+(\.\d+)*$", "", normalized)

        return normalized

    def find_skill_match(
        self, skill: str, target_skills: Set[str]
    ) -> Optional[SkillMatch]:
        """
        Find best match for a skill in target skills

        Args:
            skill: Skill to match
            target_skills: Set of target skills to match against

        Returns:
            SkillMatch if found, None otherwise
        """
        normalized_skill = self.normalize_skill(skill)
        normalized_targets = {self.normalize_skill(t): t for t in target_skills}

        # Check exact match
        if normalized_skill in normalized_targets:
            return SkillMatch(
                skill=skill,
                matched_with=normalized_targets[normalized_skill],
                match_type="exact",
                confidence=1.0,
            )

        # Check aliases
        for canonical, aliases in self.skill_aliases.items():
            canonical_norm = self.normalize_skill(canonical)
            aliases_norm = [self.normalize_skill(a) for a in aliases]

            # If skill matches an alias
            if (
                normalized_skill in aliases_norm
                and canonical_norm in normalized_targets
            ):
                return SkillMatch(
                    skill=skill,
                    matched_with=normalized_targets[canonical_norm],
                    match_type="alias",
                    confidence=0.95,
                )

            # If skill is canonical and target has alias
            if normalized_skill == canonical_norm:
                for alias in aliases_norm:
                    if alias in normalized_targets:
                        return SkillMatch(
                            skill=skill,
                            matched_with=normalized_targets[alias],
                            match_type="alias",
                            confidence=0.95,
                        )

        # Fuzzy matching
        best_match = None
        best_score = 0

        for target_norm, target_orig in normalized_targets.items():
            # Try different fuzzy matching algorithms
            ratio = fuzz.ratio(normalized_skill, target_norm)
            partial_ratio = fuzz.partial_ratio(normalized_skill, target_norm)
            token_sort = fuzz.token_sort_ratio(normalized_skill, target_norm)

            # Take the best score
            score = max(ratio, partial_ratio, token_sort)

            if score > best_score and score >= self.fuzzy_threshold:
                best_score = score
                best_match = target_orig

        if best_match:
            return SkillMatch(
                skill=skill,
                matched_with=best_match,
                match_type="fuzzy",
                confidence=best_score / 100.0,
            )

        return None

    def calculate_skills_overlap(
        self, resume_skills: List[str], job_skills: List[str]
    ) -> float:
        """
        Calculate Jaccard similarity between skill sets

        Args:
            resume_skills: List of resume skills
            job_skills: List of job skills

        Returns:
            Overlap ratio (0-1)
        """
        if not resume_skills and not job_skills:
            return 1.0
        if not resume_skills or not job_skills:
            return 0.0

        resume_set = set(self.normalize_skill(s) for s in resume_skills)
        job_set = set(self.normalize_skill(s) for s in job_skills)

        intersection = len(resume_set & job_set)
        union = len(resume_set | job_set)

        return intersection / union if union > 0 else 0.0

    def match_skills(
        self,
        resume_skills: List[str],
        required_skills: List[str],
        preferred_skills: Optional[List[str]] = None,
    ) -> SkillsScore:
        """
        Match resume skills against job requirements

        Args:
            resume_skills: List of skills from resume
            required_skills: List of required job skills
            preferred_skills: List of preferred job skills (optional)

        Returns:
            SkillsScore with detailed matching results
        """
        if preferred_skills is None:
            preferred_skills = []

        resume_set = set(resume_skills)
        required_set = set(required_skills)
        preferred_set = set(preferred_skills)

        exact_matches = []
        fuzzy_matches = []

        # Match required skills
        matched_required = set()
        for req_skill in required_skills:
            match = self.find_skill_match(req_skill, resume_set)
            if match:
                if match.match_type == "exact":
                    exact_matches.append(req_skill)
                else:
                    fuzzy_matches.append(match)
                matched_required.add(req_skill)

        # Match preferred skills
        matched_preferred = set()
        for pref_skill in preferred_skills:
            if pref_skill not in matched_required:  # Avoid double counting
                match = self.find_skill_match(pref_skill, resume_set)
                if match:
                    if match.match_type == "exact":
                        exact_matches.append(pref_skill)
                    else:
                        fuzzy_matches.append(match)
                    matched_preferred.add(pref_skill)

        # Calculate missing skills
        missing_required = list(required_set - matched_required)
        missing_preferred = list(preferred_set - matched_preferred)

        # Calculate overlap ratio
        all_job_skills = list(required_set | preferred_set)
        overlap_ratio = self.calculate_skills_overlap(resume_skills, all_job_skills)

        # Calculate weighted score
        weighted_score = self._calculate_weighted_score(
            len(matched_required),
            len(required_skills),
            len(matched_preferred),
            len(preferred_skills),
            fuzzy_matches,
        )

        return SkillsScore(
            exact_matches=exact_matches,
            fuzzy_matches=fuzzy_matches,
            missing_required=missing_required,
            missing_preferred=missing_preferred,
            overlap_ratio=overlap_ratio,
            weighted_score=weighted_score,
        )

    def _calculate_weighted_score(
        self,
        matched_required: int,
        total_required: int,
        matched_preferred: int,
        total_preferred: int,
        fuzzy_matches: List[SkillMatch],
    ) -> float:
        """
        Calculate weighted score for skills matching

        Args:
            matched_required: Number of matched required skills
            total_required: Total number of required skills
            matched_preferred: Number of matched preferred skills
            total_preferred: Total number of preferred skills
            fuzzy_matches: List of fuzzy matches with confidence scores

        Returns:
            Weighted score between 0 and 1
        """
        # Required skills have 70% weight
        required_score = 0.0
        if total_required > 0:
            required_score = matched_required / total_required

        # Preferred skills have 30% weight
        preferred_score = 0.0
        if total_preferred > 0:
            preferred_score = matched_preferred / total_preferred

        # Base score
        base_score = 0.7 * required_score + 0.3 * preferred_score

        # Apply fuzzy match penalty
        if fuzzy_matches:
            avg_confidence = sum(m.confidence for m in fuzzy_matches) / len(
                fuzzy_matches
            )
            # Small penalty for fuzzy matches (max 5% reduction)
            fuzzy_penalty = (1 - avg_confidence) * 0.05
            base_score = max(0, base_score - fuzzy_penalty)

        return min(1.0, base_score)

    def extract_skill_categories(self, skills: List[str]) -> Dict[str, List[str]]:
        """
        Categorize skills into groups

        Args:
            skills: List of skills

        Returns:
            Dictionary mapping categories to skills
        """
        categories = {
            "Programming Languages": [],
            "Frameworks & Libraries": [],
            "Databases": [],
            "Cloud & DevOps": [],
            "Data & ML": [],
            "Tools & Methodologies": [],
            "Other": [],
        }

        # Simple keyword-based categorization
        for skill in skills:
            skill_lower = skill.lower()

            if any(
                lang in skill_lower
                for lang in [
                    "python",
                    "java",
                    "javascript",
                    "typescript",
                    "c++",
                    "c#",
                    "ruby",
                    "go",
                    "rust",
                    "swift",
                    "kotlin",
                    "php",
                    "r",
                ]
            ):
                categories["Programming Languages"].append(skill)
            elif any(
                fw in skill_lower
                for fw in [
                    "react",
                    "angular",
                    "vue",
                    "django",
                    "flask",
                    "spring",
                    "express",
                    "rails",
                    ".net",
                    "tensorflow",
                    "pytorch",
                ]
            ):
                categories["Frameworks & Libraries"].append(skill)
            elif any(
                db in skill_lower
                for db in [
                    "sql",
                    "postgresql",
                    "mysql",
                    "mongodb",
                    "redis",
                    "cassandra",
                    "elasticsearch",
                    "dynamodb",
                ]
            ):
                categories["Databases"].append(skill)
            elif any(
                cloud in skill_lower
                for cloud in [
                    "aws",
                    "azure",
                    "gcp",
                    "docker",
                    "kubernetes",
                    "jenkins",
                    "terraform",
                    "ansible",
                    "devops",
                    "ci/cd",
                ]
            ):
                categories["Cloud & DevOps"].append(skill)
            elif any(
                ml in skill_lower
                for ml in [
                    "machine learning",
                    "deep learning",
                    "data science",
                    "artificial intelligence",
                    "nlp",
                    "computer vision",
                ]
            ):
                categories["Data & ML"].append(skill)
            elif any(
                tool in skill_lower
                for tool in [
                    "git",
                    "agile",
                    "scrum",
                    "jira",
                    "linux",
                    "testing",
                    "tdd",
                    "rest",
                    "graphql",
                    "microservices",
                ]
            ):
                categories["Tools & Methodologies"].append(skill)
            else:
                categories["Other"].append(skill)

        # Remove empty categories
        return {k: v for k, v in categories.items() if v}
