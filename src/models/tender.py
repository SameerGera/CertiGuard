from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, Field


class Tender(BaseModel):
    tender_id: str
    tender_name: str
    issuing_authority: str = ""
    submission_deadline: Optional[date] = None
    tender_file_path: str = ""
    tender_file_hash: str = ""
    page_count: int = 0
    created_at: datetime = Field(default_factory=datetime.now)