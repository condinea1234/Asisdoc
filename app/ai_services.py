import json
import os
import re
from pathlib import Path
from typing import Optional
from urllib import error as urlerror
from urllib import parse as urlparse
from urllib import request as urlrequest

import pytesseract
from openai import OpenAI
from PIL import Image
from docx import Document

QuestionItem = tuple[str, Optional[str]]
GenerationResult = tuple[list[QuestionItem], str, bool]


def _describe_provider_error(provider: str, exc: Exception) -> str:
    raw_message = str(exc or "").strip()
    normalized = raw_message.lower()
    provider_label = "Gemini" if provider == "gemini" else "OpenAI"

    if (
        "expecting value" in normalized
        or "jsondecodeerror" in normalized
        or "no contiene un arreglo json" in normalized
        or "respuesta vacia del proveedor" in normalized
        or "sin json" in normalized
    ):
        return (
            f"{provider_label}: respuesta invalida del proveedor (sin JSON util). "
            "Reintentá en unos segundos."
        )
    if "http 429" in normalized or "quota" in normalized:
        return (
            f"{provider_label}: límite de cuota o tasa excedido (429). "
            "Esperá unos minutos o revisá el plan/cuota."
        )
    if "http 403" in normalized or "permission_denied" in normalized:
        return (
            f"{provider_label}: acceso denegado (403). "
            "Verificá permisos de la API y restricciones de la clave."
        )
    if "http 404" in normalized or "not found" in normalized or "model" in normalized:
        return (
            f"{provider_label}: modelo no disponible o inválido. "
            "Revisá la variable de modelo configurada."
        )
    if "timed out" in normalized or "timeout" in normalized:
        return f"{provider_label}: timeout de red al consultar el proveedor."
    if "respuesta vacía del proveedor" in normalized or "respuesta vacia del proveedor" in normalized:
        return f"{provider_label}: respuesta vacía del proveedor. Reintentá en unos segundos."
    if not raw_message:
        return f"{provider_label}: error no especificado en la llamada al proveedor."
    return f"{provider_label}: {raw_message[:220]}"


def _mock_generate_questions(
    topic: str,
    evaluation_type: str,
    difficulty: str,
    count: int,
) -> list[QuestionItem]:
    questions = []
    for idx in range(1, count + 1):
        if evaluation_type == "multiple_choice":
            question = (
                f"[{difficulty}] ({topic}) Pregunta {idx}: Selecciona la opción correcta.\n"
                f"A) {topic}: definición principal.\n"
                f"B) {topic}: ejemplo secundario.\n"
                f"C) {topic}: afirmación incorrecta.\n"
                f"D) {topic}: dato irrelevante."
            )
            answer = "A"
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
                f"[{difficulty}] ({topic}) Pregunta {idx}: Responde segun lo estudiado."
            )
            answer = None
        questions.append((question, answer))
    return questions


def generate_questions(
    topic: str,
    evaluation_type: str,
    difficulty: str,
    count: int,
    material_text: Optional[str] = None,
    restrict_to_material: bool = False,
    allow_fallback: bool = True,
) -> GenerationResult:
    topic_value = (topic or "").strip() or "Tema general"
    material_value = (material_text or "").strip()
    material_label = material_value if material_value else "No provisto"
    format_instruction = (
        "Si el tipo es multiple_choice, cada question_text debe incluir 4 opciones "
        "marcadas como A), B), C), D) en líneas separadas y expected_answer debe ser "
        "la letra correcta (A, B, C o D)."
        if evaluation_type == "multiple_choice"
        else "Si no aplica, expected_answer puede ser null."
    )
    source_instruction = (
        "Debes basarte exclusivamente en el material provisto."
        if restrict_to_material
        else "Puedes usar el material provisto y, si falta contexto, conocimiento pedagógico general."
    )
    prompt = (
        "Eres un asistente pedagogico. Genera preguntas de evaluacion en JSON.\n"
        f"Tema: {topic_value}\n"
        f"Tipo: {evaluation_type}\n"
        f"Dificultad: {difficulty}\n"
        f"Cantidad: {count}\n"
        f"Material opcional: {material_label}\n"
        f"Instruccion de fuente: {source_instruction}\n"
        f"Instruccion de formato: {format_instruction}\n"
        "Responde un arreglo JSON con objetos {question_text, expected_answer}."
    )

    provider_errors: list[str] = []
    for provider in _provider_order():
        try:
            if provider == "gemini":
                output_text = _generate_text_with_gemini(prompt, max_output_tokens=1400)
            else:
                output_text = _generate_text_with_openai(prompt, max_output_tokens=1400)
            if not (output_text or "").strip():
                raise RuntimeError("Respuesta vacia del proveedor (sin JSON).")

            parsed = _extract_json_array((output_text or "").strip())
            result: list[tuple[str, Optional[str]]] = []
            for item in parsed[:count]:
                question_text = (
                    str(item.get("question_text", "")).strip() or "Pregunta genérica"
                )
                expected_answer = (
                    str(item.get("expected_answer", "")).strip()
                    if item.get("expected_answer") is not None
                    else None
                )
                if evaluation_type == "multiple_choice":
                    question_text, expected_answer = _normalize_multiple_choice(
                        question_text=question_text,
                        expected_answer=expected_answer,
                        topic=topic_value,
                        difficulty=difficulty,
                        idx=len(result) + 1,
                    )
                result.append((question_text, expected_answer))
            if result:
                return result, provider, False
        except Exception as exc:
            provider_errors.append(_describe_provider_error(provider, exc))
            continue

    if not allow_fallback:
        details = "; ".join(provider_errors) if provider_errors else "Sin proveedores configurados."
        raise RuntimeError(
            "La IA no esta disponible para generar preguntas en este momento. "
            "Intenta nuevamente o carga material para usar modo de respaldo. "
            f"Detalle técnico: {details}"
        )

    material_fallback = _material_fallback_generate_questions(
        topic=topic_value,
        evaluation_type=evaluation_type,
        difficulty=difficulty,
        count=count,
        material_text=material_value,
    )
    if material_fallback:
        return material_fallback, "material_fallback", True

    return _mock_generate_questions(topic_value, evaluation_type, difficulty, count), "mock", True


def _material_fallback_generate_questions(
    topic: str,
    evaluation_type: str,
    difficulty: str,
    count: int,
    material_text: str,
) -> list[QuestionItem]:
    cleaned_material = " ".join((material_text or "").split())
    if not cleaned_material:
        return []

    sentences = [
        s.strip()
        for s in re.split(r"(?<=[\.\!\?])\s+", cleaned_material)
        if len(s.strip()) >= 25
    ]
    if not sentences:
        sentences = [cleaned_material[:220]]

    questions: list[QuestionItem] = []
    for idx in range(1, count + 1):
        fragment = sentences[(idx - 1) % len(sentences)]
        fragment = fragment[:220].rstrip()

        if evaluation_type == "multiple_choice":
            question = (
                f"[{difficulty}] ({topic}) Pregunta {idx}: Segun el material, selecciona la afirmacion correcta.\n"
                f"A) {fragment}\n"
                "B) El material contradice esta afirmacion.\n"
                "C) El texto no desarrolla este contenido.\n"
                "D) No existe evidencia en el material."
            )
            answer = "A"
        elif evaluation_type == "true_false":
            question = (
                f"[{difficulty}] ({topic}) Pregunta {idx}: "
                f"Segun el material, la siguiente afirmacion es verdadera: \"{fragment}\"."
            )
            answer = "Verdadero"
        elif evaluation_type == "matching":
            question = (
                f"[{difficulty}] ({topic}) Pregunta {idx}: Relaciona conceptos usando este fragmento base: "
                f"\"{fragment}\"."
            )
            answer = None
        else:
            question = (
                f"[{difficulty}] ({topic}) Pregunta {idx}: "
                f"Explica con tus palabras este punto del material: \"{fragment}\"."
            )
            answer = None

        questions.append((question, answer))

    return questions


def _normalize_multiple_choice(
    question_text: str,
    expected_answer: Optional[str],
    topic: str,
    difficulty: str,
    idx: int,
) -> QuestionItem:
    has_options = bool(re.search(r"(^|\n)\s*[A-D][\)\.\-:]", question_text, flags=re.I))
    normalized_question = question_text.strip()
    if not has_options:
        normalized_question = (
            f"[{difficulty}] ({topic}) Pregunta {idx}: {normalized_question}\n"
            f"A) Concepto central de {topic}.\n"
            f"B) Definición parcialmente correcta de {topic}.\n"
            f"C) Idea incorrecta sobre {topic}.\n"
            f"D) Dato no relacionado con {topic}."
        )

    normalized_answer = (expected_answer or "").strip().upper()
    if normalized_answer:
        match = re.search(r"\b([A-D])\b", normalized_answer)
        if match:
            normalized_answer = match.group(1)
    if not normalized_answer:
        normalized_answer = "A"

    return normalized_question, normalized_answer


def _mock_grade(raw_text: str, criteria: str, max_score: float) -> tuple[float, str]:
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


def grade_submission_with_ai(
    raw_text: str,
    criteria: str,
    max_score: float,
    use_llm: bool = True,
) -> tuple[float, str]:
    if not use_llm:
        return _mock_grade(raw_text, criteria, max_score)
    prompt = (
        "Corrige la respuesta de un alumno con criterios dados.\n"
        f"Criterios: {criteria}\n"
        f"Respuesta del alumno: {raw_text}\n"
        f"Puntaje maximo: {max_score}\n"
        "Devuelve SOLO JSON con {score, feedback}. "
        "score debe estar entre 0 y puntaje maximo."
    )
    for provider in _provider_order():
        try:
            if provider == "gemini":
                output_text = _generate_text_with_gemini(prompt, max_output_tokens=700)
            else:
                output_text = _generate_text_with_openai(prompt, max_output_tokens=700)
            parsed = _extract_json_object((output_text or "").strip())
            score = float(parsed.get("score", 0.0))
            score = max(0.0, min(max_score, score))
            feedback = str(parsed.get("feedback", "")).strip()
            if not feedback:
                feedback = "Correccion realizada por IA."
            return round(score, 2), feedback
        except Exception:
            continue

    return _mock_grade(raw_text, criteria, max_score)


def extract_text_from_image(image_path: Path) -> str:
    """
    OCR local con Tesseract.
    Intenta idioma configurado, espanol e ingles para mejorar robustez.
    Si Tesseract no esta disponible en el host, devuelve texto vacio.
    """
    try:
        image = Image.open(image_path)
        preferred_lang = os.getenv("OCR_LANG", "spa")
        lang_candidates: list[str] = []
        for lang in [preferred_lang, "spa", "eng"]:
            if lang and lang not in lang_candidates:
                lang_candidates.append(lang)

        for lang in lang_candidates:
            try:
                text = pytesseract.image_to_string(image, lang=lang)
            except Exception:
                continue
            cleaned = " ".join(text.split())
            if cleaned:
                return cleaned[:8000]

        text = pytesseract.image_to_string(image)
        cleaned = " ".join(text.split())
        return cleaned[:8000]
    except Exception:
        return ""


def extract_text_from_docx(docx_path: Path) -> str:
    try:
        document = Document(docx_path)
        paragraphs = [p.text.strip() for p in document.paragraphs if p.text and p.text.strip()]
        text = " ".join(paragraphs)
        return " ".join(text.split())[:30000]
    except Exception:
        return ""


def extract_text_from_pdf(pdf_path: Path) -> str:
    """
    Extrae texto de PDF sin dependencias extras:
    intenta lectura textual básica y, si no hay contenido útil,
    retorna vacío para fallback posterior.
    """
    try:
        raw = pdf_path.read_bytes()
        # Heurística simple para PDFs con texto embebido.
        decoded = raw.decode("latin-1", errors="ignore")
        candidates = re.findall(r"\(([^)]{2,})\)\s*Tj", decoded)
        if not candidates:
            candidates = re.findall(r"\[(.*?)\]\s*TJ", decoded, flags=re.S)
            flattened = []
            for block in candidates:
                flattened.extend(re.findall(r"\(([^)]{2,})\)", block))
            candidates = flattened
        text = " ".join(candidates)
        text = re.sub(r"\\[nrt]", " ", text)
        text = re.sub(r"\\([()\\])", r"\1", text)
        cleaned = " ".join(text.split())
        return cleaned[:30000]
    except Exception:
        return ""


def _extract_json_array(text: str) -> list:
    normalized = (text or "").strip()
    if not normalized:
        raise ValueError("Respuesta vacia del proveedor (sin JSON).")
    try:
        parsed = json.loads(normalized)
        if isinstance(parsed, list):
            return parsed
        if isinstance(parsed, dict):
            if isinstance(parsed.get("questions"), list):
                return parsed["questions"]
            if isinstance(parsed.get("items"), list):
                return parsed["items"]
        raise ValueError("La respuesta no contiene un arreglo JSON valido.")
    except Exception:
        match = re.search(r"\[[\s\S]*\]", normalized)
        if match:
            return json.loads(match.group(0))
        raise ValueError("La respuesta no contiene un arreglo JSON valido.")


def _extract_json_object(text: str) -> dict:
    try:
        return json.loads(text)
    except Exception:
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            return json.loads(match.group(0))
        raise


def _provider_order() -> list[str]:
    """
    Prioridad de proveedores:
    - AI_PROVIDER=gemini -> solo Gemini
    - AI_PROVIDER=openai -> solo OpenAI
    - AI_PROVIDER=auto (default) -> Gemini y luego OpenAI si hay llaves.
    """
    configured = os.getenv("AI_PROVIDER", "auto").strip().lower()
    has_gemini = bool(os.getenv("GEMINI_API_KEY"))
    has_openai = bool(os.getenv("OPENAI_API_KEY"))

    if configured == "gemini":
        return ["gemini"] if has_gemini else []
    if configured == "openai":
        return ["openai"] if has_openai else []

    order: list[str] = []
    if has_gemini:
        order.append("gemini")
    if has_openai:
        order.append("openai")
    return order


def _generate_text_with_openai(prompt: str, max_output_tokens: int) -> str:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY no configurada")
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    client = OpenAI(api_key=api_key)
    response = client.responses.create(
        model=model,
        input=prompt,
        max_output_tokens=max_output_tokens,
    )
    return (response.output_text or "").strip()


def _generate_text_with_gemini(prompt: str, max_output_tokens: int) -> str:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY no configurada")
    model = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{urlparse.quote(model, safe='')}:"  # model in path
        f"generateContent?key={urlparse.quote(api_key, safe='')}"
    )
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": max_output_tokens,
        },
    }
    data = json.dumps(payload).encode("utf-8")
    req = urlrequest.Request(
        url,
        data=data,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urlrequest.urlopen(req, timeout=45) as response:
            raw = response.read().decode("utf-8")
    except urlerror.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"Gemini HTTP {exc.code}: {detail}") from exc

    parsed = json.loads(raw)
    texts: list[str] = []
    for candidate in parsed.get("candidates", []):
        parts = candidate.get("content", {}).get("parts", [])
        for part in parts:
            text = part.get("text")
            if text:
                texts.append(str(text))
    if not texts:
        raise RuntimeError("Gemini no devolvio texto util")
    return "\n".join(texts).strip()
