"""
Company research service using OpenAI for structured data generation
"""

import hashlib
import json
import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import openai
from jsonschema import validate
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)


class CompanyResearchService:
    """Generate structured company research using LLM"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        cache_dir: str = "data/research",
        cache_ttl_hours: int = 168,  # 1 week
    ):
        """
        Initialize research service

        Args:
            api_key: OpenAI API key
            cache_dir: Directory for caching research
            cache_ttl_hours: Cache time-to-live in hours
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            logger.warning(
                "OpenAI API key not configured - research service will not be available"
            )
            raise ValueError("OpenAI API key required")

        openai.api_key = self.api_key
        self.client = openai.OpenAI(api_key=self.api_key)

        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_ttl = timedelta(hours=cache_ttl_hours)

        # Load prompt template and schema
        self.prompt_template = self._load_prompt_template()
        self.schema = self._load_schema()

    def _load_prompt_template(self) -> str:
        """Load company research prompt template"""
        prompt_path = Path("config/prompts/company_research.txt")
        if prompt_path.exists():
            return prompt_path.read_text()
        else:
            # Fallback prompt if file doesn't exist
            return """Research the company at {company_domain} and provide structured JSON data about:
            - Competitors
            - Areas of excellence
            - Shortcomings
            - Future aspirations
            - Recent news
            - Culture and values"""

    def _load_schema(self) -> Dict[str, Any]:
        """Load JSON schema for validation"""
        schema_path = Path("config/schemas/company_research.json")
        if schema_path.exists():
            return json.loads(schema_path.read_text())
        else:
            # Basic schema if file doesn't exist
            return {
                "type": "object",
                "required": [
                    "company_domain",
                    "competitors",
                    "excellence",
                    "shortcomings",
                    "aspirations",
                ],
            }

    def _get_cache_key(self, company_domain: str) -> str:
        """Generate cache key for company domain"""
        return hashlib.md5(company_domain.lower().encode()).hexdigest()

    def _get_cached_research(
        self, company_domain: str
    ) -> Optional[Dict[str, Any]]:
        """Retrieve cached research if available and not expired"""
        cache_key = self._get_cache_key(company_domain)
        cache_file = self.cache_dir / f"{cache_key}.json"

        if not cache_file.exists():
            return None

        try:
            with open(cache_file, "r") as f:
                cached_data = json.load(f)

            # Check if cache is expired
            cached_time = datetime.fromisoformat(cached_data["cached_at"])
            if datetime.now(timezone.utc) - cached_time > self.cache_ttl:
                logger.info(f"Cache expired for {company_domain}")
                return None

            logger.info(f"Using cached research for {company_domain}")
            return cached_data["research"]

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning(f"Invalid cache file for {company_domain}: {e}")
            return None

    def _save_to_cache(self, company_domain: str, research: Dict[str, Any]):
        """Save research to cache"""
        cache_key = self._get_cache_key(company_domain)
        cache_file = self.cache_dir / f"{cache_key}.json"

        cache_data = {
            "company_domain": company_domain,
            "cached_at": datetime.now(timezone.utc).isoformat(),
            "research": research,
        }

        with open(cache_file, "w") as f:
            json.dump(cache_data, f, indent=2)

        logger.info(f"Cached research for {company_domain}")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
    )
    def _call_openai(self, prompt: str) -> Dict[str, Any]:
        """Call OpenAI API with retry logic"""
        try:
            response = self.client.chat.completions.create(
                model="gpt-4-turbo-preview",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a company research assistant. Always respond with valid JSON.",
                    },
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.3,  # Lower temperature for more factual output
                max_tokens=2000,
            )

            content = response.choices[0].message.content
            return json.loads(content)

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse OpenAI response as JSON: {e}")
            raise
        except Exception as e:
            logger.error(f"OpenAI API call failed: {e}")
            raise

    def research_company(
        self, company_domain: str, use_cache: bool = True
    ) -> Dict[str, Any]:
        """
        Research a company and return structured data

        Args:
            company_domain: Company website domain
            use_cache: Whether to use cached results

        Returns:
            Structured company research data
        """
        # Check cache first
        if use_cache:
            cached = self._get_cached_research(company_domain)
            if cached:
                return cached

        logger.info(f"Generating new research for {company_domain}")

        # Generate prompt
        prompt = self.prompt_template.format(company_domain=company_domain)

        # Call OpenAI
        research = self._call_openai(prompt)

        # Validate against schema
        try:
            validate(instance=research, schema=self.schema)
        except Exception as e:
            logger.warning(f"Schema validation failed: {e}")
            # Continue anyway - the data might still be useful

        # Ensure company_domain is set
        research["company_domain"] = company_domain

        # Add metadata
        research["generated_at"] = datetime.now(timezone.utc).isoformat()
        research["model_used"] = "gpt-4-turbo-preview"

        # Cache the result
        self._save_to_cache(company_domain, research)

        return research

    def get_research_quality_score(
        self, research: Dict[str, Any]
    ) -> Dict[str, float]:
        """
        Calculate quality scores for research output

        Args:
            research: Company research data

        Returns:
            Quality scores for different aspects
        """
        scores = {}

        # Check completeness
        required_fields = [
            "competitors",
            "excellence",
            "shortcomings",
            "aspirations",
        ]
        present_fields = sum(
            1
            for field in required_fields
            if field in research and research[field]
        )
        scores["completeness"] = present_fields / len(required_fields)

        # Check competitor coverage
        competitor_count = len(research.get("competitors", []))
        scores["competitor_coverage"] = min(
            1.0, competitor_count / 3
        )  # Expect at least 3

        # Check for URLs/sources
        aspiration_sources = sum(
            1
            for asp in research.get("aspirations", [])
            if asp.get("source_url", "").startswith("http")
        )
        total_aspirations = max(1, len(research.get("aspirations", [])))
        scores["source_coverage"] = aspiration_sources / total_aspirations

        # Check detail level (based on average description length)
        descriptions = []
        for excellence in research.get("excellence", []):
            descriptions.append(excellence.get("description", ""))
        for shortcoming in research.get("shortcomings", []):
            descriptions.append(shortcoming.get("description", ""))

        avg_length = sum(len(d) for d in descriptions) / max(
            1, len(descriptions)
        )
        scores["detail_level"] = min(
            1.0, avg_length / 100
        )  # Expect ~100 chars

        # Overall score
        scores["overall"] = sum(scores.values()) / len(scores)

        return scores

    def clear_cache(self, company_domain: Optional[str] = None):
        """
        Clear research cache

        Args:
            company_domain: Specific company to clear, or None for all
        """
        if company_domain:
            cache_key = self._get_cache_key(company_domain)
            cache_file = self.cache_dir / f"{cache_key}.json"
            if cache_file.exists():
                cache_file.unlink()
                logger.info(f"Cleared cache for {company_domain}")
        else:
            # Clear all cache files
            for cache_file in self.cache_dir.glob("*.json"):
                cache_file.unlink()
            logger.info("Cleared all research cache")
