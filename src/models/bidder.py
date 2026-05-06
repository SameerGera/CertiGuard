from typing import Optional
from pydantic import BaseModel, Field


class Bidder(BaseModel):
    bidder_id: str
    bidder_name: str
    gst_number: Optional[str] = None
    pan_number: Optional[str] = None
    registration_number: Optional[str] = None
    directory_path: str
    document_count: int = 0
    document_formats: list[str] = Field(default_factory=list)