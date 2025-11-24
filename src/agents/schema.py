from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field

class BacklogStatus(str, Enum):
    TODO = "TODO"
    IN_PROGRESS = "IN_PROGRESS"
    IN_REVIEW = "IN_REVIEW"
    DONE = "DONE"
    ARCHIVED = "ARCHIVED"

class Backlog(BaseModel):
    """
    Schema for Backlog entity, matching the Service (Core) Schema.
    """
    title: str = Field(description="Title of the backlog item")
    description: str = Field(description="Detailed description")
    priority: Optional[int] = Field(description="Priority level (e.g., 1-5)")
    start_date: Optional[str] = Field(description="Start date (YYYY-MM-DD)")
    end_date: Optional[str] = Field(description="End date (YYYY-MM-DD)")
    status: BacklogStatus = Field(default=BacklogStatus.TODO, description="Status of the backlog item")

class SprintStatus(str, Enum):
    PLANNED = "PLANNED"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    ABORTED = "ABORTED"

class Sprint(BaseModel):
    """
    Schema for Sprint entity, matching the Service (Core) Schema.
    """
    name: str = Field(description="Name of the sprint")
    sprint_number: int = Field(description="Sprint number")
    goal: Optional[str] = Field(description="Sprint goal")
    start_date: str = Field(description="Start date (YYYY-MM-DD)")
    end_date: str = Field(description="End date (YYYY-MM-DD)")
    status: SprintStatus = Field(default=SprintStatus.PLANNED, description="Status of the sprint")
    backlog_ids: Optional[List[str]] = Field(default=None, description="List of backlog IDs or titles included in the sprint")

