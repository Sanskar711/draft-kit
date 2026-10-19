from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator, field_validator


def linkedin_url(value: str) -> str:
    if value:
        import re
        if not re.fullmatch(r"https://www\.linkedin\.com/in/[^/?#\s]+/?", value) or len(value) > 512:
            raise ValueError("Use a LinkedIn profile URL.")
    return value


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Fact(StrictModel):
    id: str = Field(default_factory=lambda: str(uuid4()), max_length=80)
    text: str = Field(min_length=1, max_length=1500)
    confirmed: bool = False
    source: Literal["manual", "resume", "linkedin"] = "manual"
    source_url: str = Field(default="", max_length=512)
    source_filename: str = Field(default="", max_length=200)

    _source_url = field_validator("source_url")(linkedin_url)


class Profile(StrictModel):
    name: str = Field(default="", max_length=120)
    headline: str = Field(default="", max_length=240)
    writing_style: str = Field(default="", max_length=1200)
    facts: list[Fact] = Field(default_factory=list, max_length=60)
    linkedin_profile_url: str = Field(default="", max_length=512)
    linkedin_imported_at: str = Field(default="", max_length=40)
    resume_filename: str = Field(default="", max_length=200)
    resume_imported_at: str = Field(default="", max_length=40)

    _linkedin_url = field_validator("linkedin_profile_url")(linkedin_url)

    @model_validator(mode="after")
    def unique_facts(self):
        if len({fact.id for fact in self.facts}) != len(self.facts):
            raise ValueError("Fact IDs must be unique.")
        if sum(len(fact.text) for fact in self.facts) > 24000:
            raise ValueError("Keep your profile facts under 24,000 characters.")
        return self


class PairRequest(StrictModel):
    code: str = Field(min_length=10, max_length=100)
    extension_id: str = Field(pattern=r"^[a-p]{32}$")


class ResumeRequest(StrictModel):
    filename: str = Field(min_length=1, max_length=200)
    content_base64: str = Field(min_length=1, max_length=6990508)


class GenerateRequest(StrictModel):
    mode: Literal["dm", "post"]
    model: str = Field(min_length=1, max_length=120)
    prompt: str = Field(min_length=1, max_length=8000)
    tone: str = Field(min_length=1, max_length=80)
    length: Literal["short", "medium", "long"] = "short"
    language: str = Field(default="English", min_length=1, max_length=80)
    job_input: str = Field(default="", max_length=16000)
    dm_intent: Literal["referral", "hiring"] = "referral"
    current_draft: str = Field(default="", max_length=24000)
    revision: Literal["", "shorten", "warmer", "direct", "hook", "custom"] = ""
    modification: str = Field(default="", max_length=4000)
    include_profile: bool = True
    fact_ids: list[str] | None = Field(default=None, max_length=60)
    hashtags: bool = False
    emoji: bool = False

    @model_validator(mode="after")
    def valid_revision(self):
        if self.revision and not self.current_draft:
            raise ValueError("A revision needs a current draft.")
        if self.revision == "custom" and not self.modification:
            raise ValueError("Describe the changes to make.")
        if self.modification and self.revision != "custom":
            raise ValueError("Use custom revision for written changes.")
        return self

