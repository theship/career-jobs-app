"""
Security models and validators for input sanitization
"""

from typing import Optional
from pydantic import BaseModel, Field, field_validator
from api.utils.security import sanitize_text


class SecureTextMixin:
    """Mixin for models that need text sanitization"""
    
    @field_validator('*', mode='before')
    @classmethod
    def sanitize_string_fields(cls, v):
        """Sanitize all string fields automatically"""
        if isinstance(v, str):
            return sanitize_text(v)
        return v


class SecureRequest(BaseModel):
    """Base class for secure request models"""
    
    class Config:
        # Strip whitespace from strings
        str_strip_whitespace = True
        # Limit string size
        str_max_length = 10000
        
    @field_validator('*', mode='before')
    @classmethod
    def sanitize_inputs(cls, v):
        """Sanitize all string inputs"""
        if isinstance(v, str):
            return sanitize_text(v, max_length=10000)
        elif isinstance(v, dict):
            # Recursively sanitize dictionary values
            return {k: cls.sanitize_inputs(val) for k, val in v.items()}
        elif isinstance(v, list):
            # Recursively sanitize list items
            return [cls.sanitize_inputs(item) for item in v]
        return v


class SecurePitchRequest(SecureRequest):
    """Secure version of pitch generation request"""
    resume_id: str = Field(..., max_length=100)
    job_id: str = Field(..., max_length=100)
    include_research: bool = Field(default=True)
    custom_instructions: Optional[str] = Field(None, max_length=1000)


class SecureResearchRequest(SecureRequest):
    """Secure version of research request"""
    company_domain: str = Field(..., max_length=255)
    use_cache: bool = Field(default=True)
    research_depth: str = Field(default="standard", pattern="^(basic|standard|detailed)$")