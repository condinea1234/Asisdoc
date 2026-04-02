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
- **IA (opcional):** OpenAI API o Google Gemini API
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
export GEMINI_API_KEY="tu_api_key_gemini"
export GEMINI_MODEL="gemini-1.5-flash"
export AI_PROVIDER="gemini"   # gemini | openai (default: openai)
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

## Interfaz web en español

El proyecto incluye una interfaz web inicial para docentes, 100% en español, servida por el mismo backend:

- `GET /` abre el panel web
- archivos estáticos bajo `/web/*`
- `GET /demo` abre una vista previa visual con datos simulados (sin login real)

Flujos disponibles en el panel:

- registro e inicio de sesión docente
- creación y listado de cursos
- alta y listado de alumnos
- creación de evaluaciones por tipo/dificultad
- agenda de exámenes
- carga de respuestas en texto + corrección automática
- carga de foto de examen + OCR + corrección
- descarga de evaluación en `.docx`

## Ver la interfaz desde Android (sin PC)

Si estás usando Android y querés ver la evolución visual por fase:

1. Levantá el backend:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8001
```

2. Abrí un túnel temporal:

```bash
npx --yes localtunnel --port 8001
```

3. Tomá la URL pública que te entrega (ej. `https://xxxxx.loca.lt`) y abrila desde tu navegador móvil.

Rutas recomendadas para revisión visual:

- `https://xxxxx.loca.lt/demo` (vista rápida mock, ideal para feedback de diseño)
- `https://xxxxx.loca.lt/` (flujo real con login y datos persistidos)

## Despliegue estable: Firebase + Cloud Run

Para tener URL fija (sin depender de localtunnel), usá esta arquitectura:

- **Backend FastAPI** en **Google Cloud Run**
- **Frontend** (`web/`) en **Firebase Hosting**
- Hosting redirige `"/api/**"` hacia Cloud Run

### 1) Requisitos

Instalar y autenticar:

- `gcloud` CLI
- `firebase-tools` (`npm i -g firebase-tools`)

Login:

```bash
gcloud auth login
gcloud auth application-default login
firebase login
```

### 2) Desplegar backend en Cloud Run

El repositorio ya incluye:

- `Dockerfile`
- `.dockerignore`
- script `scripts/deploy_cloudrun.sh`

Ejemplo:

```bash
export GCP_PROJECT_ID="tu-proyecto"
export GCP_REGION="us-central1"
export CLOUD_RUN_SERVICE="asisdoc-api"

# Opcional IA:
export AI_PROVIDER="gemini"
export GEMINI_API_KEY="tu_api_key_gemini"
export GEMINI_MODEL="gemini-1.5-flash"

./scripts/deploy_cloudrun.sh
```

El script:

- construye imagen con Cloud Build
- despliega servicio Cloud Run
- imprime URL pública del backend

### 3) Configurar Firebase Hosting

Ya están creados:

- `firebase.json`
- `.firebaserc`
- script `scripts/deploy_firebase.sh`

Actualizá en `firebase.json` la URL del backend Cloud Run:

- `hosting.rewrites[0].run.serviceId`
- `hosting.rewrites[0].run.region`

Luego:

```bash
export FIREBASE_PROJECT_ID="tu-proyecto"
./scripts/deploy_firebase.sh
```

### 4) Cómo queda el acceso

- `https://<tu-site>.web.app/` -> panel web
- `https://<tu-site>.web.app/demo` -> vista demo
- `https://<tu-site>.web.app/api/docs` -> Swagger del backend (via rewrite)

> Nota: en producción, el frontend llama a rutas `"/api/..."` automáticamente.

### Script recomendado para probar avances por fase

Podés usar este script para no repetir pasos manuales:

```bash
./scripts/preview_movile.sh
```

Qué hace:

- levanta `uvicorn` en `0.0.0.0:8001`
- espera healthcheck
- abre túnel temporal con `localtunnel`
- muestra en consola:
  - URL demo (`/demo`)
  - URL real (`/`)
- deja corriendo ambos procesos hasta que presiones `Ctrl+C`
- al salir, limpia procesos automáticamente

Opciones:

```bash
./scripts/preview_movile.sh --sin-tunel      # solo local, útil si usás misma red
./scripts/preview_movile.sh --port 8010      # cambiar puerto
```

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

> Si configurás `AI_PROVIDER=gemini` + `GEMINI_API_KEY`, la generación usa Gemini.
> Si configurás `AI_PROVIDER=openai` + `OPENAI_API_KEY`, usa OpenAI.
> Si no hay API key válida, usa fallback local.

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

## Probar Gemini gratis (rápido)

Para pruebas iniciales podés usar la capa gratuita de Google AI Studio:

1. Crear API key en Google AI Studio.
2. Configurar variables:

```bash
export AI_PROVIDER="gemini"
export GEMINI_API_KEY="tu_api_key_gemini"
export GEMINI_MODEL="gemini-1.5-flash"
```

3. Levantar API y usar flujo normal (`/` o endpoints).  
Si la key no está o falla, el sistema usa fallback local automáticamente.

### Historial y progreso (protegidos)

- `GET /students/{student_id}/grades`
- `GET /students/{student_id}/progress`
- `GET /stats/courses/{course_id}`
