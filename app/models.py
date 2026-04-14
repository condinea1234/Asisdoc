from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class Course(Base):
    __tablename__ = "courses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    students: Mapped[list["Student"]] = relationship(back_populates="course")
    evaluations: Mapped[list["Evaluation"]] = relationship(back_populates="course")


class Teacher(Base):
    __tablename__ = "teachers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    full_name: Mapped[str] = mapped_column(String(140), nullable=False)
    email: Mapped[str] = mapped_column(String(180), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    tokens: Mapped[list["AuthToken"]] = relationship(back_populates="teacher")
    materials: Mapped[list["MaterialSource"]] = relationship(back_populates="teacher")


class AuthToken(Base):
    __tablename__ = "auth_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    teacher_id: Mapped[int] = mapped_column(ForeignKey("teachers.id"), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    teacher: Mapped["Teacher"] = relationship(back_populates="tokens")


class Student(Base):
    __tablename__ = "students"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    full_name: Mapped[str] = mapped_column(String(140), nullable=False)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    course: Mapped["Course"] = relationship(back_populates="students")
    submissions: Mapped[list["Submission"]] = relationship(back_populates="student")
    grades: Mapped[list["StudentEvaluation"]] = relationship(back_populates="student")


class MaterialSource(Base):
    __tablename__ = "material_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    teacher_id: Mapped[int] = mapped_column(ForeignKey("teachers.id"), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    extension: Mapped[str] = mapped_column(String(16), nullable=False)
    stored_path: Mapped[str] = mapped_column(String(255), nullable=False)
    extracted_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    teacher: Mapped["Teacher"] = relationship(back_populates="materials")
    evaluations: Mapped[list["Evaluation"]] = relationship(
        back_populates="material_source"
    )


class Evaluation(Base):
    __tablename__ = "evaluations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), nullable=False)
    evaluation_type: Mapped[str] = mapped_column(String(60), nullable=False)
    difficulty: Mapped[str] = mapped_column(String(40), nullable=False)
    material_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    material_source_id: Mapped[int | None] = mapped_column(
        ForeignKey("material_sources.id"), nullable=True
    )
    strict_material_only: Mapped[bool] = mapped_column(default=False, nullable=False)
    use_internal_knowledge: Mapped[bool] = mapped_column(default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    course: Mapped["Course"] = relationship(back_populates="evaluations")
    material_source: Mapped[Optional["MaterialSource"]] = relationship(
        back_populates="evaluations"
    )
    questions: Mapped[list["EvaluationQuestion"]] = relationship(
        back_populates="evaluation", cascade="all, delete-orphan"
    )
    schedules: Mapped[list["ExamSchedule"]] = relationship(back_populates="evaluation")
    submissions: Mapped[list["Submission"]] = relationship(back_populates="evaluation")


class EvaluationQuestion(Base):
    __tablename__ = "evaluation_questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    evaluation_id: Mapped[int] = mapped_column(
        ForeignKey("evaluations.id"), nullable=False
    )
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    expected_answer: Mapped[str | None] = mapped_column(Text, nullable=True)

    evaluation: Mapped["Evaluation"] = relationship(back_populates="questions")


class ExamSchedule(Base):
    __tablename__ = "exam_schedules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    evaluation_id: Mapped[int] = mapped_column(
        ForeignKey("evaluations.id"), nullable=False
    )
    scheduled_for: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    evaluation: Mapped["Evaluation"] = relationship(back_populates="schedules")


class Submission(Base):
    __tablename__ = "submissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    evaluation_id: Mapped[int] = mapped_column(
        ForeignKey("evaluations.id"), nullable=False
    )
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), nullable=False)
    image_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    evaluation: Mapped["Evaluation"] = relationship(back_populates="submissions")
    student: Mapped["Student"] = relationship(back_populates="submissions")
    corrections: Mapped[list["Correction"]] = relationship(back_populates="submission")


class Correction(Base):
    __tablename__ = "corrections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    submission_id: Mapped[int] = mapped_column(
        ForeignKey("submissions.id"), nullable=False
    )
    criteria: Mapped[str] = mapped_column(Text, nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    max_score: Mapped[float] = mapped_column(Float, nullable=False)
    feedback: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    submission: Mapped["Submission"] = relationship(back_populates="corrections")


class StudentEvaluation(Base):
    __tablename__ = "student_evaluations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), nullable=False)
    evaluation_id: Mapped[int] = mapped_column(
        ForeignKey("evaluations.id"), nullable=False
    )
    score: Mapped[float] = mapped_column(Float, nullable=False)
    max_score: Mapped[float] = mapped_column(Float, nullable=False)
    feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    student: Mapped["Student"] = relationship(back_populates="grades")
