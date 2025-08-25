"""
Job Normalization Pipeline
Standardizes and enriches job data from various ATS sources
"""

import logging
import re
from typing import Any, Dict, List, Optional, Set

from geopy.geocoders import Nominatim
from rapidfuzz import fuzz

from ingestion.connectors.base import JobListing

logger = logging.getLogger(__name__)


class JobNormalizer:
    """Normalize and enrich job listings from various sources"""
    
    def __init__(self):
        """Initialize the normalizer with lookup tables and geocoder"""
        self.geocoder = Nominatim(user_agent="career-jobs-app")
        
        # Standard job titles mapping
        self.title_mappings = {
            "sr": "Senior",
            "jr": "Junior",
            "sw": "Software",
            "eng": "Engineer",
            "dev": "Developer",
            "mgr": "Manager",
            "dir": "Director",
            "vp": "Vice President",
            "cto": "Chief Technology Officer",
            "ceo": "Chief Executive Officer",
            "ml": "Machine Learning",
            "ai": "Artificial Intelligence",
            "fe": "Frontend",
            "be": "Backend",
            "fs": "Full Stack",
        }
        
        # Experience level normalization
        self.experience_levels = {
            "entry": ["entry", "junior", "associate", "graduate", "intern", "0-2"],
            "mid": ["mid", "intermediate", "2-5", "3-5", "regular"],
            "senior": ["senior", "sr", "lead", "5+", "7+", "experienced"],
            "staff": ["staff", "principal", "architect", "10+"],
            "executive": ["director", "vp", "c-level", "chief", "head of"],
        }
        
        # Employment type normalization
        self.employment_types = {
            "full-time": ["full-time", "full time", "ft", "permanent"],
            "part-time": ["part-time", "part time", "pt"],
            "contract": ["contract", "contractor", "consulting", "freelance"],
            "internship": ["intern", "internship", "co-op"],
            "temporary": ["temp", "temporary", "seasonal"],
        }
        
        # Remote type normalization
        self.remote_types = {
            "remote": ["remote", "distributed", "anywhere", "work from home", "wfh"],
            "hybrid": ["hybrid", "flexible", "remote/office", "partial remote"],
            "on-site": ["on-site", "onsite", "in-office", "office", "in person"],
        }
        
        # Common skills extraction patterns
        self.skill_patterns = self._compile_skill_patterns()
    
    def _compile_skill_patterns(self) -> List[re.Pattern]:
        """Compile regex patterns for skill extraction"""
        skill_names = [
            r"Python", r"JavaScript", r"TypeScript", r"Java\b", r"C\+\+", r"C#",
            r"Ruby", r"Go\b", r"Rust", r"Swift", r"Kotlin", r"Scala",
            r"React(?:\.js)?", r"Angular", r"Vue(?:\.js)?", r"Node(?:\.js)?",
            r"Django", r"Flask", r"FastAPI", r"Spring", r"Express",
            r"PostgreSQL", r"MySQL", r"MongoDB", r"Redis", r"Elasticsearch",
            r"AWS", r"Azure", r"GCP", r"Docker", r"Kubernetes", r"Terraform",
            r"CI/CD", r"Git", r"Linux", r"REST(?:ful)?", r"GraphQL", r"gRPC",
            r"Machine Learning", r"Deep Learning", r"NLP", r"Computer Vision",
            r"TensorFlow", r"PyTorch", r"Scikit-learn", r"Pandas", r"NumPy"
        ]
        
        patterns = []
        for skill in skill_names:
            pattern = re.compile(rf"\b{skill}\b", re.IGNORECASE)
            patterns.append(pattern)
        
        return patterns
    
    def normalize(self, job: JobListing) -> JobListing:
        """
        Apply all normalization steps to a job listing
        
        Args:
            job: Raw job listing from ATS
        
        Returns:
            Normalized job listing
        """
        # Normalize title
        job.title = self.normalize_title(job.title)
        
        # Normalize location and add geocoding
        job.location = self.normalize_location(job.location)
        
        # Normalize experience level
        if job.experience_level:
            job.experience_level = self.normalize_experience_level(job.experience_level)
        elif job.title:
            # Try to infer from title
            job.experience_level = self.infer_experience_level(job.title)
        
        # Normalize employment type
        if job.employment_type:
            job.employment_type = self.normalize_employment_type(job.employment_type)
        
        # Normalize remote type
        if job.remote_type:
            job.remote_type = self.normalize_remote_type(job.remote_type)
        elif job.location:
            # Try to infer from location
            job.remote_type = self.infer_remote_type(job.location)
        
        # Extract skills if not provided
        if not job.skills:
            job.skills = self.extract_skills(job)
        else:
            # Deduplicate and clean existing skills
            job.skills = self.clean_skills(job.skills)
        
        # Clean and structure requirements/responsibilities
        if job.requirements:
            job.requirements = self.clean_text_list(job.requirements)
        
        if job.responsibilities:
            job.responsibilities = self.clean_text_list(job.responsibilities)
        
        # Normalize salary
        job = self.normalize_salary(job)
        
        # Generate search keywords
        job = self.add_search_keywords(job)
        
        return job
    
    def normalize_title(self, title: str) -> str:
        """Normalize job title"""
        if not title:
            return ""
        
        # Apply abbreviation expansions
        words = title.split()
        normalized_words = []
        
        for word in words:
            word_lower = word.lower()
            if word_lower in self.title_mappings:
                normalized_words.append(self.title_mappings[word_lower])
            else:
                normalized_words.append(word)
        
        # Reconstruct and clean
        normalized = " ".join(normalized_words)
        
        # Remove extra spaces and special characters
        normalized = re.sub(r"\s+", " ", normalized)
        normalized = re.sub(r"[^\w\s\-/()]", "", normalized)
        
        return normalized.strip()
    
    def normalize_location(self, location: str) -> str:
        """Normalize location string"""
        if not location:
            return "Remote"
        
        # Clean location string
        location = re.sub(r"\s+", " ", location)
        location = location.strip()
        
        # Handle common patterns
        if location.lower() in ["remote", "anywhere", "distributed"]:
            return "Remote"
        
        # Remove country codes in parentheses
        location = re.sub(r"\([A-Z]{2}\)", "", location)
        
        return location.strip()
    
    def normalize_experience_level(self, level: str) -> str:
        """Normalize experience level to standard categories"""
        if not level:
            return "Not Specified"
        
        level_lower = level.lower()
        
        for normalized, variations in self.experience_levels.items():
            for variation in variations:
                if variation in level_lower:
                    return normalized.title()
        
        return "Mid"  # Default to mid-level
    
    def infer_experience_level(self, title: str) -> str:
        """Infer experience level from job title"""
        title_lower = title.lower()
        
        if any(term in title_lower for term in ["intern", "junior", "jr", "entry"]):
            return "Entry"
        elif any(term in title_lower for term in ["senior", "sr", "lead"]):
            return "Senior"
        elif any(term in title_lower for term in ["staff", "principal", "architect"]):
            return "Staff"
        elif any(term in title_lower for term in ["director", "vp", "chief", "head"]):
            return "Executive"
        
        return "Mid"
    
    def normalize_employment_type(self, emp_type: str) -> str:
        """Normalize employment type"""
        if not emp_type:
            return "Full-time"
        
        emp_lower = emp_type.lower()
        
        for normalized, variations in self.employment_types.items():
            for variation in variations:
                if variation in emp_lower:
                    return normalized.replace("-", " ").title()
        
        return "Full-time"
    
    def normalize_remote_type(self, remote_type: str) -> str:
        """Normalize remote type"""
        if not remote_type:
            return "Not Specified"
        
        remote_lower = remote_type.lower()
        
        for normalized, variations in self.remote_types.items():
            for variation in variations:
                if variation in remote_lower:
                    return normalized.replace("-", " ").title()
        
        return "On-site"
    
    def infer_remote_type(self, location: str) -> str:
        """Infer remote type from location"""
        location_lower = location.lower()
        
        if any(term in location_lower for term in ["remote", "anywhere", "distributed"]):
            return "Remote"
        elif "hybrid" in location_lower:
            return "Hybrid"
        
        return "On-site"
    
    def extract_skills(self, job: JobListing) -> List[str]:
        """Extract skills from job description and requirements"""
        skills: Set[str] = set()
        
        # Combine all text sources
        text_sources = []
        if job.description:
            text_sources.append(job.description)
        if job.requirements:
            text_sources.extend(job.requirements)
        if job.responsibilities:
            text_sources.extend(job.responsibilities)
        
        combined_text = " ".join(text_sources)
        
        # Apply skill patterns
        for pattern in self.skill_patterns:
            matches = pattern.findall(combined_text)
            for match in matches:
                # Normalize the skill name
                skill_name = match.strip()
                if skill_name:
                    skills.add(self._normalize_skill_name(skill_name))
        
        return list(skills)[:30]  # Limit to 30 skills
    
    def _normalize_skill_name(self, skill: str) -> str:
        """Normalize individual skill name"""
        # Standard capitalizations
        special_cases = {
            "javascript": "JavaScript",
            "typescript": "TypeScript",
            "postgresql": "PostgreSQL",
            "mysql": "MySQL",
            "mongodb": "MongoDB",
            "nodejs": "Node.js",
            "node": "Node.js",
            "reactjs": "React",
            "react.js": "React",
            "vuejs": "Vue.js",
            "vue": "Vue.js",
            "angular": "Angular",
            "aws": "AWS",
            "gcp": "GCP",
            "ci/cd": "CI/CD",
            "restful": "REST",
            "rest": "REST",
            "graphql": "GraphQL",
            "grpc": "gRPC",
            "nlp": "NLP",
            "tensorflow": "TensorFlow",
            "pytorch": "PyTorch",
            "scikit-learn": "Scikit-learn",
            "numpy": "NumPy",
            "pandas": "Pandas",
        }
        
        skill_lower = skill.lower()
        if skill_lower in special_cases:
            return special_cases[skill_lower]
        
        return skill.title()
    
    def clean_skills(self, skills: List[str]) -> List[str]:
        """Clean and deduplicate skills list"""
        cleaned = set()
        
        for skill in skills:
            if skill and isinstance(skill, str):
                normalized = self._normalize_skill_name(skill.strip())
                if normalized:
                    cleaned.add(normalized)
        
        return list(cleaned)
    
    def clean_text_list(self, items: List[Any]) -> List[str]:
        """Clean a list of text items"""
        cleaned = []
        
        for item in items:
            if isinstance(item, str):
                # Remove HTML tags
                item = re.sub(r"<[^>]+>", "", item)
                # Remove extra whitespace
                item = re.sub(r"\s+", " ", item)
                item = item.strip()
                
                if item and len(item) > 10:  # Filter out very short items
                    cleaned.append(item)
        
        return cleaned
    
    def normalize_salary(self, job: JobListing) -> JobListing:
        """Normalize salary information"""
        # Ensure currency is set
        if not job.salary_currency:
            job.salary_currency = "USD"
        
        # Validate salary range
        if job.salary_min and job.salary_max:
            if job.salary_min > job.salary_max:
                # Swap if reversed
                job.salary_min, job.salary_max = job.salary_max, job.salary_min
        
        # Remove unrealistic salaries
        if job.salary_max and job.salary_max > 1000000:
            job.salary_max = None
        if job.salary_min and job.salary_min < 10000:
            job.salary_min = None
        
        return job
    
    def add_search_keywords(self, job: JobListing) -> JobListing:
        """Add searchable keywords to job metadata"""
        keywords = set()
        
        # Add from title
        if job.title:
            keywords.update(job.title.lower().split())
        
        # Add from skills
        if job.skills:
            keywords.update([s.lower() for s in job.skills])
        
        # Add from department
        if job.department:
            keywords.update(job.department.lower().split())
        
        # Add experience level
        if job.experience_level:
            keywords.add(job.experience_level.lower())
        
        # Store in raw_data for search indexing
        if not job.raw_data:
            job.raw_data = {}
        job.raw_data["search_keywords"] = list(keywords)
        
        return job