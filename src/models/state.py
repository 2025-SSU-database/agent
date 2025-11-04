from typing import TypedDict, List, Optional, Annotated
from operator import add
from datetime import datetime
from pydantic import BaseModel, Field

class PlanningDocument(BaseModel):
    """기획 문서 분석 결과"""
    input: str
    project_name: str
    project_goal: str
    key_features: List[str] = Field(default_factory=list)
    stakeholders: List[str] = Field(default_factory=list)
    constraints: List[str] = Field(default_factory=list)
    success_criteria: List[str] = Field(default_factory=list)