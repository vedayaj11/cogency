from __future__ import annotations

from pydantic import BaseModel, Field


class RubricScore(BaseModel):
    """4-dimensional rubric per PRD AC6.2."""

    task_completion: float = Field(ge=0, le=1)
    policy_adherence: float = Field(ge=0, le=1)
    tone: float = Field(ge=0, le=1)
    citation_accuracy: float = Field(ge=0, le=1)

    def aggregate(self) -> float:
        return (
            self.task_completion + self.policy_adherence + self.tone + self.citation_accuracy
        ) / 4


class Rubric(BaseModel):
    name: str
    description: str
    pass_threshold: float = 0.85
