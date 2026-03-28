from pydantic import BaseModel, field_validator
from app.youtube import extract_video_id


class SummarizeRequest(BaseModel):
    youtube_url: str
    style: str = "brief"
    language: str = "en"
    provider: str = "gemini"

    @field_validator("youtube_url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        if not extract_video_id(v):
            raise ValueError("Invalid YouTube URL")
        return v

    @field_validator("style")
    @classmethod
    def validate_style(cls, v: str) -> str:
        if v not in ("brief", "structured"):
            raise ValueError("Style must be 'brief' or 'structured'")
        return v

    @field_validator("language")
    @classmethod
    def validate_language(cls, v: str) -> str:
        if v not in ("en", "ko"):
            raise ValueError("Language must be 'en' or 'ko'")
        return v


class TagRequest(BaseModel):
    name: str

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        v = v.strip().lower()
        if not v:
            raise ValueError("Tag name cannot be empty")
        return v
