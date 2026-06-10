from pydantic import BaseModel, Field
from typing import List, Optional
from enum import Enum


class SeverityLevel(str, Enum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"


class ReviewIssue(BaseModel):
    file: str = Field(..., description="Path to the file being reviewed")
    issue: str = Field(..., description="Brief description of the issue")
    severity: SeverityLevel = Field(..., description="Severity level: Low, Medium, or High")
    explanation: str = Field(..., description="Detailed explanation of the issue")
    fix: str = Field(..., description="Code snippet or specific fix instructions")
    recommendation: str = Field(..., description="Best practice recommendation")
    insights: str = Field(..., description="Additional maintainability or performance insights")
    source: Optional[str] = Field(default="ai", description="Source: 'ai' or 'static'")


class AnalysisProgress(BaseModel):
    total_files: int
    processed_files: int
    current_file: str
    status: str
    percentage: float


class AnalysisRequest(BaseModel):
    session_id: str


class AnalysisResponse(BaseModel):
    session_id: str
    status: str
    issues: List[ReviewIssue] = []
    total_files: int = 0
    processed_files: int = 0
    errors: List[str] = []


class ExportRequest(BaseModel):
    session_id: str
    format: str = Field(..., description="Export format: 'excel' or 'markdown'")


class FileInfo(BaseModel):
    path: str
    size: int
    extension: str
    content: Optional[str] = None
    truncated: bool = False
