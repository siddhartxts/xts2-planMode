from datetime import datetime
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field, field_validator


class WatchlistItemBase(BaseModel):
    ticker: str = Field(
        description="Stock ticker symbol; normalized to upper-case.",
        examples=["AAPL"],
    )
    company_name: str | None = Field(
        default=None,
        description="Optional human-readable company name.",
        examples=["Apple Inc."],
    )
    notes: str | None = Field(
        default=None,
        description="Optional free-text notes about the position.",
        examples=["core holding"],
    )

    @field_validator("ticker")
    @classmethod
    def clean_ticker(cls, value: str) -> str:
        ticker = value.strip().upper()
        if not ticker:
            raise ValueError("ticker is required")
        return ticker

    @field_validator("company_name", "notes", mode="before")
    @classmethod
    def clean_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None

        text = value.strip()
        return text or None


class WatchlistItemCreate(WatchlistItemBase):
    pass


class WatchlistItemRead(WatchlistItemBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FinanceNoteBase(BaseModel):
    ticker: str = Field(
        description="Ticker the note is about; normalized to upper-case.",
        examples=["AAPL"],
    )
    title: str = Field(description="Short note title.", examples=["Q3 earnings beat"])
    content: str = Field(
        description="Note body.",
        examples=["Revenue up on iPhone + Services."],
    )
    tags: list[str] = Field(
        default_factory=list,
        description="Tags; accepts a list or a comma-separated string.",
        examples=[["earnings", "bullish"]],
    )
    source_url: str | None = Field(
        default=None,
        description="Optional source link; must start with http:// or https://.",
        examples=["https://example.com/report"],
    )

    @field_validator("ticker")
    @classmethod
    def clean_ticker(cls, value: str) -> str:
        ticker = value.strip().upper()
        if not ticker:
            raise ValueError("ticker is required")
        return ticker

    @field_validator("title", "content")
    @classmethod
    def clean_required_text(cls, value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError("field is required")
        return text

    @field_validator("tags", mode="before")
    @classmethod
    def clean_tags(cls, value: list[str] | str | None) -> list[str]:
        if value is None:
            return []

        if isinstance(value, str):
            value = value.split(",")

        return [tag.strip() for tag in value if tag and tag.strip()]

    @field_validator("source_url", mode="before")
    @classmethod
    def clean_source_url(cls, value: str | None) -> str | None:
        if value is None:
            return None

        source_url = value.strip()
        if not source_url:
            return None

        if not source_url.startswith(("http://", "https://")):
            raise ValueError("source_url must start with http:// or https://")

        return source_url


class FinanceNoteCreate(FinanceNoteBase):
    pass


class FinanceNoteIngest(FinanceNoteBase):
    # Optional stable id from the calling source/agent. When present, ingestion
    # is idempotent: a note with the same external_id is skipped.
    external_id: str | None = None

    @field_validator("external_id", mode="before")
    @classmethod
    def clean_external_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None


class FinanceNoteRead(FinanceNoteBase):
    id: int
    external_id: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class IngestResult(BaseModel):
    """Summary returned by the bulk ingest endpoint."""

    created: int
    skipped: int
    items: list[FinanceNoteRead]


T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    """A paginated list response: one page of ``items`` plus the metadata a
    client needs to fetch the rest (``total`` matching rows, and the
    ``limit``/``offset`` used for this page)."""

    items: list[T]
    total: int = Field(description="Total rows matching the query, ignoring paging.")
    limit: int = Field(description="Maximum rows returned in this page.")
    offset: int = Field(description="Rows skipped before this page.")
