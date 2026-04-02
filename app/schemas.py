from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class TeacherRegister(BaseModel):
    full_name: str = Field(min_length=3)
    email: str = Field(min_length=5)
    password: str = Field(min_length=8)


class TeacherLogin(BaseModel):
    email: str
    password: str


class TeacherRead(BaseModel):
    id: int
    full_name: str
    email: str
    created_at: datetime

    class Config:
        from_attributes = True


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime
    teacher: TeacherRead


class CourseCreate(BaseModel):
    name: str = Field(min_length=2)
    description: Optional[str] = None


class CourseRead(BaseModel):
    id: int
    name: str
    description: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class StudentCreate(BaseModel):
    full_name: str = Field(min_length=2)
    course_id: int


class StudentRead(BaseModel):
    id: int
    full_name: str
    course_id: int
    created_at: datetime

    class Config:
        from_attributes = True


class EvaluationCreate(BaseModel):
    title: str = Field(min_length=3)
    course_id: int
    evaluation_type: str = Field(
        description="Ej: multiple_choice, true_false, matching, open_answer"
    )
    difficulty: str = Field(description="Ej: easy, medium, hard")
    question_count: int = Field(default=10, ge=1, le=100)
    material_text: Optional[str] = None
    use_internal_knowledge: bool = True


class EvaluationQuestionCreate(BaseModel):
    question_text: str = Field(min_length=5)
    expected_answer: Optional[str] = None


class EvaluationQuestionRead(BaseModel):
    id: int
    question_text: str
    expected_answer: Optional[str]

    class Config:
        from_attributes = True


class EvaluationRead(BaseModel):
    id: int
    title: str
    course_id: int
    evaluation_type: str
    difficulty: str
    material_text: Optional[str]
    use_internal_knowledge: bool
    created_at: datetime
    questions: list[EvaluationQuestionRead] = []

    class Config:
        from_attributes = True


class ExamScheduleCreate(BaseModel):
    evaluation_id: int
    scheduled_for: datetime
    notes: Optional[str] = None


class ExamScheduleRead(BaseModel):
    id: int
    evaluation_id: int
    scheduled_for: datetime
    notes: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class SubmissionCreate(BaseModel):
    evaluation_id: int
    student_id: int
    image_reference: Optional[str] = None
    raw_text: Optional[str] = None


class SubmissionPhotoCreate(BaseModel):
    evaluation_id: int
    student_id: int


class SubmissionRead(BaseModel):
    id: int
    evaluation_id: int
    student_id: int
    image_reference: Optional[str]
    raw_text: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class CorrectionCreate(BaseModel):
    criteria: str = Field(
        description="Lista de palabras clave separadas por coma para la corrección."
    )
    max_score: float = Field(gt=0)
    use_llm: bool = True


class CorrectionRead(BaseModel):
    id: int
    submission_id: int
    criteria: str
    score: float
    max_score: float
    feedback: str
    created_at: datetime

    class Config:
        from_attributes = True


class StudentEvaluationRead(BaseModel):
    id: int
    student_id: int
    evaluation_id: int
    score: float
    max_score: float
    feedback: Optional[str]
    updated_at: datetime

    class Config:
        from_attributes = True


class ProgressStats(BaseModel):
    student_id: int
    evaluations_count: int
    average_score: float
    average_percentage: float
    last_score: float
