# Asisdoc

Backend de asistente docente con IA para:

- crear evaluaciones por tipo y dificultad
- programarlas en agenda
- exportarlas a Word (`.docx`) con membrete editable
- registrar alumnos, cursos y calificaciones
- corregir entregas automáticamente con criterios del docente
- cargar fotos de exámenes y extraer texto por OCR
- obtener estadísticas básicas de progreso

## Stack

- **Backend:** FastAPI
- **Base de datos:** SQLite + SQLAlchemy
- **IA (opcional):** OpenAI API
- **OCR:** Tesseract vía `pytesseract`
- **Exportación Word:** `python-docx`

## Estructura

```txt
app/
  ai_services.py    # integración IA y OCR + fallbacks
  database.py       # conexión y sesión DB
  main.py           # endpoints API
  models.py         # tablas SQLAlchemy
  schemas.py        # contratos de API
  security.py       # hash de passwords y tokens
requirements.txt
```

## Ejecución local

1. Crear entorno virtual:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

2. Instalar dependencias Python:

```bash
pip install -r requirements.txt
```

3. (Opcional) Instalar binario de Tesseract en Linux:

```bash
sudo apt-get update
sudo apt-get install -y tesseract-ocr tesseract-ocr-spa tesseract-ocr-eng
```

4. Variables de entorno (opcionales):

```bash
export OPENAI_API_KEY="tu_api_key"
export OPENAI_MODEL="gpt-4o-mini"
export OCR_LANG="spa"        # spa, eng, etc.
export UPLOAD_DIR="uploads"  # carpeta de imágenes
```

5. Levantar API:

```bash
uvicorn app.main:app --reload
```

6. Documentación Swagger:

```txt
http://127.0.0.1:8000/docs
```

## Autenticación (Fase 2)

1. Registrar docente:

- `POST /auth/register`

2. Login:

- `POST /auth/login`
- devuelve `access_token` tipo Bearer

3. Usar token en endpoints protegidos:

```txt
Authorization: Bearer <token>
```

4. Logout:

- `POST /auth/logout`

## Endpoints principales

### Salud

- `GET /health`

### Cursos y alumnos (protegidos)

- `POST /courses`
- `GET /courses`
- `POST /students`
- `GET /students?course_id=...`

### Evaluaciones (protegidos)

- `POST /evaluations`
- `GET /evaluations`
- `POST /evaluations/{evaluation_id}/questions`
- `GET /evaluations/{evaluation_id}/export-docx?school_header=...&teacher_name=...`

> Si existe `OPENAI_API_KEY`, la generación usa LLM real. Si no, usa fallback local.

### Agenda (protegidos)

- `POST /schedules`
- `GET /schedules`

### Entregas y corrección (protegidos)

- `POST /submissions` (texto directo)
- `POST /submissions/photo` (multipart con imagen + OCR)
- `POST /submissions/{submission_id}/correct`

En corrección:
- `use_llm=true` intenta corrección con LLM
- si falla o falta API key, cae a fallback local por criterios

### Historial y progreso (protegidos)

- `GET /students/{student_id}/grades`
- `GET /students/{student_id}/progress`
- `GET /stats/courses/{course_id}`
