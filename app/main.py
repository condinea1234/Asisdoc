from datetime import datetime
from io import BytesIO
from typing import Optional

from docx import Document
from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from .database import Base, engine, get_db
from .models import (
    Correction,
    Course,
    Evaluation,
    EvaluationQuestion,
    ExamSchedule,
    Student,
    StudentEvaluation,
    Submission,
)
from .schemas import (
    CorrectionCreate,
    CorrectionRead,
    CourseCreate,
    CourseRead,
    EvaluationCreate,
    EvaluationQuestionCreate,
    EvaluationRead,
    ExamScheduleCreate,
    ExamScheduleRead,
    ProgressStats,
    StudentCreate,
    StudentEvaluationRead,
    StudentRead,
    SubmissionCreate,
    SubmissionRead,
)

app = FastAPI(
    title="Asisdoc API",
    version="0.1.0",
    description="MVP para asistencia docente con creación y corrección de evaluaciones.",
)

Base.metadata.create_all(bind=engine)


@app.get("/health")
def healthcheck():
    return {"status": "ok"}


@app.post("/courses", response_model=CourseRead)
def create_course(payload: CourseCreate, db: Session = Depends(get_db)):
    course = Course(name=payload.name, description=payload.description)
    db.add(course)
    db.commit()
    db.refresh(course)
    return course


@app.get("/courses", response_model=list[CourseRead])
def list_courses(db: Session = Depends(get_db)):
    return db.query(Course).order_by(Course.id.desc()).all()


@app.post("/students", response_model=StudentRead)
def create_student(payload: StudentCreate, db: Session = Depends(get_db)):
    course = db.get(Course, payload.course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Curso no encontrado")

    student = Student(full_name=payload.full_name, course_id=payload.course_id)
    db.add(student)
    db.commit()
    db.refresh(student)
    return student


@app.get("/students", response_model=list[StudentRead])
def list_students(course_id: Optional[int] = None, db: Session = Depends(get_db)):
    query = db.query(Student)
    if course_id:
        query = query.filter(Student.course_id == course_id)
    return query.order_by(Student.id.desc()).all()


def _mock_generate_questions(
    topic: str,
    evaluation_type: str,
    difficulty: str,
    count: int,
) -> list[tuple[str, Optional[str]]]:
    """Generador mock de preguntas. Reemplazable por LLM real."""
    questions = []
    for idx in range(1, count + 1):
        if evaluation_type == "multiple_choice":
            question = (
                f"[{difficulty}] ({topic}) Pregunta {idx}: Selecciona la opción correcta."
            )
            answer = "Opción A"
        elif evaluation_type == "true_false":
            question = f"[{difficulty}] ({topic}) Pregunta {idx}: Verdadero o Falso."
            answer = "Verdadero"
        elif evaluation_type == "matching":
            question = (
                f"[{difficulty}] ({topic}) Pregunta {idx}: Relaciona cada concepto."
            )
            answer = None
        else:
            question = (
                f"[{difficulty}] ({topic}) Pregunta {idx}: Responde según lo estudiado."
            )
            answer = None
        questions.append((question, answer))
    return questions


@app.post("/evaluations", response_model=EvaluationRead)
def create_evaluation(payload: EvaluationCreate, db: Session = Depends(get_db)):
    course = db.get(Course, payload.course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Curso no encontrado")

    evaluation = Evaluation(
        title=payload.title,
        course_id=payload.course_id,
        evaluation_type=payload.evaluation_type,
        difficulty=payload.difficulty,
        material_text=payload.material_text,
        use_internal_knowledge=payload.use_internal_knowledge,
    )
    db.add(evaluation)
    db.flush()

    generated_questions = _mock_generate_questions(
        topic=payload.title,
        evaluation_type=payload.evaluation_type,
        difficulty=payload.difficulty,
        count=payload.question_count,
    )
    for question, answer in generated_questions:
        db.add(
            EvaluationQuestion(
                evaluation_id=evaluation.id, question_text=question, expected_answer=answer
            )
        )

    db.commit()
    db.refresh(evaluation)
    return evaluation


@app.get("/evaluations", response_model=list[EvaluationRead])
def list_evaluations(course_id: Optional[int] = None, db: Session = Depends(get_db)):
    query = db.query(Evaluation)
    if course_id:
        query = query.filter(Evaluation.course_id == course_id)
    return query.order_by(Evaluation.id.desc()).all()


@app.post("/evaluations/{evaluation_id}/questions", response_model=EvaluationRead)
def add_question(
    evaluation_id: int,
    payload: EvaluationQuestionCreate,
    db: Session = Depends(get_db),
):
    evaluation = db.get(Evaluation, evaluation_id)
    if not evaluation:
        raise HTTPException(status_code=404, detail="Evaluación no encontrada")
    db.add(
        EvaluationQuestion(
            evaluation_id=evaluation_id,
            question_text=payload.question_text,
            expected_answer=payload.expected_answer,
        )
    )
    db.commit()
    db.refresh(evaluation)
    return evaluation


@app.post("/schedules", response_model=ExamScheduleRead)
def create_schedule(payload: ExamScheduleCreate, db: Session = Depends(get_db)):
    evaluation = db.get(Evaluation, payload.evaluation_id)
    if not evaluation:
        raise HTTPException(status_code=404, detail="Evaluación no encontrada")
    schedule = ExamSchedule(
        evaluation_id=payload.evaluation_id,
        scheduled_for=payload.scheduled_for,
        notes=payload.notes,
    )
    db.add(schedule)
    db.commit()
    db.refresh(schedule)
    return schedule


@app.get("/schedules", response_model=list[ExamScheduleRead])
def list_schedules(db: Session = Depends(get_db)):
    return db.query(ExamSchedule).order_by(ExamSchedule.scheduled_for.asc()).all()


@app.post("/submissions", response_model=SubmissionRead)
def create_submission(payload: SubmissionCreate, db: Session = Depends(get_db)):
    student = db.get(Student, payload.student_id)
    evaluation = db.get(Evaluation, payload.evaluation_id)
    if not student or not evaluation:
        raise HTTPException(
            status_code=404, detail="Alumno o evaluación no encontrada"
        )

    submission = Submission(
        student_id=payload.student_id,
        evaluation_id=payload.evaluation_id,
        image_reference=payload.image_reference,
        raw_text=payload.raw_text,
    )
    db.add(submission)
    db.commit()
    db.refresh(submission)
    return submission


def _calculate_score(raw_text: str, criteria: str, max_score: float) -> tuple[float, str]:
    """
    Simula corrección por IA basada en texto y criterios.
    Reemplazable por integración real con un modelo LLM/vision.
    """
    normalized = (raw_text or "").strip().lower()
    keywords = [k.strip().lower() for k in criteria.split(",") if k.strip()]
    if not keywords:
        keywords = ["correcto"]

    matches = sum(1 for kw in keywords if kw in normalized)
    ratio = matches / len(keywords)
    score = round(max_score * ratio, 2)
    feedback = (
        f"Criterios evaluados: {', '.join(keywords)}. "
        f"Coincidencias detectadas: {matches}/{len(keywords)}. "
        f"Puntaje asignado: {score}/{max_score}."
    )
    return score, feedback


@app.post("/submissions/{submission_id}/correct", response_model=CorrectionRead)
def correct_submission(
    submission_id: int,
    payload: CorrectionCreate,
    db: Session = Depends(get_db),
):
    submission = db.get(Submission, submission_id)
    if not submission:
        raise HTTPException(status_code=404, detail="Entrega no encontrada")

    score, feedback = _calculate_score(
        raw_text=submission.raw_text or "",
        criteria=payload.criteria,
        max_score=payload.max_score,
    )

    correction = Correction(
        submission_id=submission.id,
        criteria=payload.criteria,
        score=score,
        max_score=payload.max_score,
        feedback=feedback,
    )
    db.add(correction)

    student_eval = db.query(StudentEvaluation).filter(
        StudentEvaluation.student_id == submission.student_id,
        StudentEvaluation.evaluation_id == submission.evaluation_id,
    ).first()

    if student_eval:
        student_eval.score = score
        student_eval.max_score = payload.max_score
        student_eval.feedback = feedback
        student_eval.updated_at = datetime.utcnow()
    else:
        db.add(
            StudentEvaluation(
                student_id=submission.student_id,
                evaluation_id=submission.evaluation_id,
                score=score,
                max_score=payload.max_score,
                feedback=feedback,
            )
        )

    db.commit()
    db.refresh(correction)
    return correction


@app.get("/students/{student_id}/grades", response_model=list[StudentEvaluationRead])
def student_grades(student_id: int, db: Session = Depends(get_db)):
    student = db.get(Student, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Alumno no encontrado")
    return (
        db.query(StudentEvaluation)
        .filter(StudentEvaluation.student_id == student_id)
        .order_by(StudentEvaluation.updated_at.desc())
        .all()
    )


@app.get("/students/{student_id}/progress", response_model=ProgressStats)
def student_progress(student_id: int, db: Session = Depends(get_db)):
    student = db.get(Student, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Alumno no encontrado")

    rows = (
        db.query(StudentEvaluation.score, StudentEvaluation.max_score)
        .filter(StudentEvaluation.student_id == student_id)
        .all()
    )
    if not rows:
        return ProgressStats(
            student_id=student_id,
            evaluations_count=0,
            average_score=0.0,
            average_percentage=0.0,
            last_score=0.0,
        )

    evaluations_count = len(rows)
    avg_score = round(sum(r[0] for r in rows) / evaluations_count, 2)
    avg_percentage = round(
        sum((r[0] / r[1] * 100) if r[1] else 0 for r in rows) / evaluations_count, 2
    )
    last = (
        db.query(StudentEvaluation.score)
        .filter(StudentEvaluation.student_id == student_id)
        .order_by(StudentEvaluation.updated_at.desc())
        .first()
    )
    last_score = last[0] if last else 0.0

    return ProgressStats(
        student_id=student_id,
        evaluations_count=evaluations_count,
        average_score=avg_score,
        average_percentage=avg_percentage,
        last_score=last_score,
    )


@app.get("/evaluations/{evaluation_id}/export-docx")
def export_evaluation_docx(
    evaluation_id: int,
    school_header: str = "Institución Educativa",
    teacher_name: str = "Docente",
    db: Session = Depends(get_db),
):
    evaluation = db.get(Evaluation, evaluation_id)
    if not evaluation:
        raise HTTPException(status_code=404, detail="Evaluación no encontrada")

    document = Document()
    document.add_heading(school_header, level=1)
    document.add_paragraph(f"Docente: {teacher_name}")
    document.add_paragraph(f"Evaluación: {evaluation.title}")
    document.add_paragraph(f"Tipo: {evaluation.evaluation_type}")
    document.add_paragraph(f"Dificultad: {evaluation.difficulty}")
    document.add_paragraph(" ")
    document.add_paragraph("Nombre del alumno: ____________________")
    document.add_paragraph("Curso: ____________________")
    document.add_paragraph("Fecha: ____________________")
    document.add_paragraph(" ")

    questions = (
        db.query(EvaluationQuestion)
        .filter(EvaluationQuestion.evaluation_id == evaluation_id)
        .order_by(EvaluationQuestion.id.asc())
        .all()
    )
    for idx, q in enumerate(questions, start=1):
        document.add_paragraph(f"{idx}. {q.question_text}")

    file_stream = BytesIO()
    document.save(file_stream)
    file_stream.seek(0)

    filename = f"evaluacion_{evaluation_id}.docx"
    return StreamingResponse(
        file_stream,
        media_type=(
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ),
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/stats/courses/{course_id}")
def course_stats(course_id: int, db: Session = Depends(get_db)):
    course = db.get(Course, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Curso no encontrado")

    student_count = db.query(func.count(Student.id)).filter(Student.course_id == course_id).scalar()
    evaluation_count = (
        db.query(func.count(Evaluation.id))
        .filter(Evaluation.course_id == course_id)
        .scalar()
    )
    avg_percentage = (
        db.query(func.avg((StudentEvaluation.score / StudentEvaluation.max_score) * 100))
        .join(Student, Student.id == StudentEvaluation.student_id)
        .filter(Student.course_id == course_id)
        .scalar()
    )

    return {
        "course_id": course_id,
        "students": student_count or 0,
        "evaluations": evaluation_count or 0,
        "average_percentage": round(float(avg_percentage or 0.0), 2),
    }
