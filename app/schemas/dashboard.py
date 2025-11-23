from pydantic import BaseModel
from typing import List, Optional
from app.schemas.task import TaskResponse

class StatItem(BaseModel):
    title: str
    value: int

class HighPriorityTasks(BaseModel):
    personal: List[TaskResponse]
    project: List[TaskResponse]

class TaskPerformance(BaseModel):
    totalTasks: int
    done: int
    stuck: int
    pending: int
    inProgress: int

class DashboardResponse(BaseModel):
    stats: List[StatItem]
    highPriorityTasks: HighPriorityTasks
    dueSoon: List[TaskResponse]
    taskPerformance: TaskPerformance

