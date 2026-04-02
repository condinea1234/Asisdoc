import os
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Optional

from docx import Document
from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func
from sqlalchemy.orm import Session

from .ai_services import extract_text_from_image, generate_questions, grade_submission_with_ai
from .database import Base, engine, get_db
from .models import (
    AuthToken,
    Correction,
    Course,
    Evaluation,
    EvaluationQuestion,
    ExamSchedule,
    Student,
    StudentEvaluation,
    Submission,
    Teacher,
)
from .security import create_token, hash_password, hash_token, verify_password
from .schemas import (
    AuthResponse,
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
    TeacherLogin,
    TeacherRead,
    TeacherRegister,
)

app = FastAPI(
    title="Asisdoc API",
    version="0.2.0",
    description="Asistente docente con autenticacion, IA y OCR.",
)

Base.metadata.create_all(bind=engine)
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "uploads"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
WEB_DIR = Path(__file__).resolve().parent.parent / "web"
app.mount("/web", StaticFiles(directory=WEB_DIR), name="web")


def get_current_teacher(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> Teacher:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Token de acceso requerido")
    token = authorization.split(" ", 1)[1].strip()
    token_digest = hash_token(token)
    record = (
        db.query(AuthToken)
        .filter(
            AuthToken.token_hash == token_digest,
            AuthToken.revoked_at.is_(None),
        )
        .first()
    )
    if not record:
        raise HTTPException(status_code=401, detail="Token inválido")
    if record.expires_at < datetime.utcnow():
        raise HTTPException(status_code=401, detail="Token expirado")
    teacher = db.get(Teacher, record.teacher_id)
    if not teacher:
        raise HTTPException(status_code=401, detail="Docente no encontrado")
    return teacher


@app.post("/auth/register", response_model=TeacherRead)
def register_teacher(payload: TeacherRegister, db: Session = Depends(get_db)):
    email = payload.email.strip().lower()
    exists = db.query(Teacher).filter(Teacher.email == email).first()
    if exists:
        raise HTTPException(status_code=409, detail="El correo ya está registrado")
    teacher = Teacher(
        full_name=payload.full_name.strip(),
        email=email,
        password_hash=hash_password(payload.password),
    )
    db.add(teacher)
    db.commit()
    db.refresh(teacher)
    return teacher


@app.post("/auth/login", response_model=AuthResponse)
def login_teacher(payload: TeacherLogin, db: Session = Depends(get_db)):
    email = payload.email.strip().lower()
    teacher = db.query(Teacher).filter(Teacher.email == email).first()
    if not teacher or not verify_password(payload.password, teacher.password_hash):
        raise HTTPException(status_code=401, detail="Credenciales inválidas")

    plain_token, token_digest, expires_at = create_token()
    token = AuthToken(
        teacher_id=teacher.id,
        token_hash=token_digest,
        expires_at=expires_at,
    )
    db.add(token)
    db.commit()
    db.refresh(teacher)
    return AuthResponse(access_token=plain_token, expires_at=expires_at, teacher=teacher)


@app.post("/auth/logout")
def logout_teacher(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
    _: Teacher = Depends(get_current_teacher),
):
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Token de acceso requerido")
    token = authorization.split(" ", 1)[1].strip()
    token_digest = hash_token(token)
    record = db.query(AuthToken).filter(AuthToken.token_hash == token_digest).first()
    if record and not record.revoked_at:
        record.revoked_at = datetime.utcnow()
        db.commit()
    return {"ok": True}


@app.get("/health")
def healthcheck():
    return {"status": "ok"}


@app.get("/")
def serve_web():
    index_path = WEB_DIR / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    raise HTTPException(status_code=404, detail="Interfaz web no disponible")


@app.post("/courses", response_model=CourseRead)
def create_course(
    payload: CourseCreate,
    db: Session = Depends(get_db),
    _: Teacher = Depends(get_current_teacher),
):
    exists = db.query(Course).filter(Course.name == payload.name).first()
    if exists:
        raise HTTPException(status_code=409, detail="El curso ya existe")
    course = Course(name=payload.name, description=payload.description)
    db.add(course)
    db.commit()
    db.refresh(course)
    return course


@app.get("/courses", response_model=list[CourseRead])
def list_courses(
    db: Session = Depends(get_db),
    _: Teacher = Depends(get_current_teacher),
):
    return db.query(Course).order_by(Course.id.desc()).all()


@app.post("/students", response_model=StudentRead)
def create_student(
    payload: StudentCreate,
    db: Session = Depends(get_db),
    _: Teacher = Depends(get_current_teacher),
):
    course = db.get(Course, payload.course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Curso no encontrado")

    student = Student(full_name=payload.full_name, course_id=payload.course_id)
    db.add(student)
    db.commit()
    db.refresh(student)
    return student


@app.get("/students", response_model=list[StudentRead])
def list_students(
    course_id: Optional[int] = None,
    db: Session = Depends(get_db),
    _: Teacher = Depends(get_current_teacher),
):
    query = db.query(Student)
    if course_id:
        query = query.filter(Student.course_id == course_id)
    return query.order_by(Student.id.desc()).all()


@app.post("/evaluations", response_model=EvaluationRead)
def create_evaluation(
    payload: EvaluationCreate,
    db: Session = Depends(get_db),
    _: Teacher = Depends(get_current_teacher),
):
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

    generated_questions = generate_questions(
        topic=payload.title,
        evaluation_type=payload.evaluation_type,
        difficulty=payload.difficulty,
        count=payload.question_count,
        material_text=payload.material_text if payload.use_internal_knowledge else None,
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
def list_evaluations(
    course_id: Optional[int] = None,
    db: Session = Depends(get_db),
    _: Teacher = Depends(get_current_teacher),
):
    query = db.query(Evaluation)
    if course_id:
        query = query.filter(Evaluation.course_id == course_id)
    return query.order_by(Evaluation.id.desc()).all()


@app.post("/evaluations/{evaluation_id}/questions", response_model=EvaluationRead)
def add_question(
    evaluation_id: int,
    payload: EvaluationQuestionCreate,
    db: Session = Depends(get_db),
    _: Teacher = Depends(get_current_teacher),
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
def create_schedule(
    payload: ExamScheduleCreate,
    db: Session = Depends(get_db),
    _: Teacher = Depends(get_current_teacher),
):
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
def list_schedules(
    db: Session = Depends(get_db),
    _: Teacher = Depends(get_current_teacher),
):
    return db.query(ExamSchedule).order_by(ExamSchedule.scheduled_for.asc()).all()


@app.post("/submissions", response_model=SubmissionRead)
def create_submission(
    payload: SubmissionCreate,
    db: Session = Depends(get_db),
    _: Teacher = Depends(get_current_teacher),
):
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


@app.post("/submissions/photo", response_model=SubmissionRead)
def create_submission_from_photo(
    evaluation_id: int = Form(...),
    student_id: int = Form(...),
    image_file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _: Teacher = Depends(get_current_teacher),
):
    student = db.get(Student, student_id)
    evaluation = db.get(Evaluation, evaluation_id)
    if not student or not evaluation:
        raise HTTPException(
            status_code=404, detail="Alumno o evaluación no encontrada"
        )

    extension = Path(image_file.filename or "submission.jpg").suffix.lower()
    if extension not in {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff"}:
        raise HTTPException(status_code=400, detail="Formato de imagen no soportado")

    filename = f"sub_{student_id}_{evaluation_id}_{int(datetime.utcnow().timestamp())}{extension}"
    file_path = UPLOAD_DIR / filename
    with file_path.open("wb") as out:
        out.write(image_file.file.read())

    extracted_text = extract_text_from_image(file_path)
    submission = Submission(
        student_id=student_id,
        evaluation_id=evaluation_id,
        image_reference=str(file_path),
        raw_text=extracted_text,
    )
    db.add(submission)
    db.commit()
    db.refresh(submission)
    return submission


@app.post("/submissions/{submission_id}/correct", response_model=CorrectionRead)
def correct_submission(
    submission_id: int,
    payload: CorrectionCreate,
    db: Session = Depends(get_db),
    _: Teacher = Depends(get_current_teacher),
):
    submission = db.get(Submission, submission_id)
    if not submission:
        raise HTTPException(status_code=404, detail="Entrega no encontrada")

    score, feedback = grade_submission_with_ai(
        raw_text=submission.raw_text or "",
        criteria=payload.criteria,
        max_score=payload.max_score,
        use_llm=payload.use_llm,
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
def student_grades(
    student_id: int,
    db: Session = Depends(get_db),
    _: Teacher = Depends(get_current_teacher),
):
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
def student_progress(
    student_id: int,
    db: Session = Depends(get_db),
    _: Teacher = Depends(get_current_teacher),
):
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
    _: Teacher = Depends(get_current_teacher),
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
def course_stats(
    course_id: int,
    db: Session = Depends(get_db),
    _: Teacher = Depends(get_current_teacher),
):
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
