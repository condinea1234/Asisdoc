# Asisdoc

MVP de asistente docente con IA para:

- crear evaluaciones por tipo y dificultad
- programarlas en una agenda
- exportarlas a Word (`.docx`) con membrete editable
- registrar alumnos, cursos y calificaciones
- corregir entregas con criterios definidos por el docente
- obtener estadísticas básicas de progreso

## Stack inicial

- **Backend:** FastAPI
- **Base de datos:** SQLite + SQLAlchemy
- **Exportación Word:** `python-docx`

## Estructura

```txt
app/
  database.py      # conexión y sesión DB
  models.py        # tablas SQLAlchemy
  schemas.py       # modelos de entrada/salida (Pydantic)
  main.py          # endpoints API
requirements.txt
```

## Ejecución local

1. Crear entorno virtual:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

2. Instalar dependencias:

```bash
pip install -r requirements.txt
```

3. Levantar API:

```bash
uvicorn app.main:app --reload
```

4. Abrir documentación Swagger:

```txt
http://127.0.0.1:8000/docs
```

## Endpoints principales (MVP)

### Salud

- `GET /health`

### Cursos y alumnos

- `POST /courses`
- `GET /courses`
- `POST /students`
- `GET /students?course_id=...`

### Evaluaciones

- `POST /evaluations`  
  Crea evaluación con tipo (`multiple_choice`, `true_false`, `matching`, `open_answer`) y dificultad (`easy`, `medium`, `hard`).
- `GET /evaluations`
- `POST /evaluations/{evaluation_id}/questions`
- `GET /evaluations/{evaluation_id}/export-docx?school_header=...&teacher_name=...`

### Agenda de exámenes

- `POST /schedules`
- `GET /schedules`

### Entregas y corrección automática

- `POST /submissions`
- `POST /submissions/{submission_id}/correct`  
  Permite pasar criterios (palabras clave separadas por coma), puntaje máximo y devuelve puntaje + feedback.

### Historial y progreso

- `GET /students/{student_id}/grades`
- `GET /students/{student_id}/progress`
- `GET /stats/courses/{course_id}`

## Relación con tu idea original

- **Web o Android:** este backend API se puede consumir desde ambas apps.
- **Material opcional para crear evaluación:** `material_text` + `use_internal_knowledge`.
- **Tipos de evaluación + dificultad:** incluidos en creación de evaluación.
- **Impresión con formato Word y membrete:** endpoint de exportación `.docx`.
- **Agenda de evaluaciones:** endpoints de `schedules`.
- **Corrección con criterios del docente:** endpoint de corrección por criterios.
- **Base de datos de alumnos y notas + progreso:** modelos y endpoints de notas/estadísticas.

## Qué falta para la siguiente iteración

- integrar LLM real para generación/corrección avanzada
- OCR real para corregir desde imágenes de exámenes escaneados
- autenticación (docente/admin)
- frontend web (React/Vue) y app Android (Kotlin/Flutter)
- gráficos de evolución (por alumno, curso y materia)
