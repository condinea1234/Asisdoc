import json
import os
import re
import textwrap
import time
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
            f"{provider_label}: respuesta invalida del proveedor. "
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
            question = textwrap.dedent(
                f"""
                [{difficulty}] ({topic}) Pregunta {idx}: Uní con flechas cada elemento de la columna A con su par correcto en la columna B.
                Contexto: conceptos clave de {topic}.
                Columna A:
                1) Definición principal de {topic}
                2) Ejemplo representativo de {topic}
                3) Aplicación práctica de {topic}
                Columna B:
                A) Caso aplicado
                B) Concepto base
                C) Ejemplo típico
                """
            ).strip()
            answer = "1-B;2-C;3-A"
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
    force_material_fallback: bool = False,
) -> GenerationResult:
    topic_value = (topic or "").strip() or "Tema general"
    material_value = (material_text or "").strip()
    material_label = material_value if material_value else "No provisto"
    if evaluation_type == "multiple_choice":
        format_instruction = (
            "Cada question_text debe incluir 4 opciones marcadas como A), B), C), D) "
            "en líneas separadas y expected_answer debe ser la letra correcta "
            "(A, B, C o D)."
        )
    elif evaluation_type == "matching":
        format_instruction = (
            "Cada question_text debe incluir: una línea 'Contexto:', luego 'Columna A:' "
            "con al menos 3 ítems numerados (1), 2), 3)) y 'Columna B:' con al menos "
            "3 ítems con letras (A), B), C)). expected_answer debe indicar pares "
            "como '1-B;2-C;3-A'."
        )
    else:
        format_instruction = "Si no aplica, expected_answer puede ser null."
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

    if force_material_fallback:
        material_fallback = _material_fallback_generate_questions(
            topic=topic_value,
            evaluation_type=evaluation_type,
            difficulty=difficulty,
            count=count,
            material_text=material_value,
        )
        if material_fallback:
            return material_fallback, "material_fallback", True
        raise RuntimeError(
            "No se pudo generar con respaldo por material. "
            "Verificá que el material tenga contenido legible."
        )

    provider_errors: list[str] = []
    for provider in _provider_order():
        provider_error: Optional[Exception] = None
        for attempt in range(1, 4):
            try:
                if provider == "gemini":
                    output_text = _generate_text_with_gemini(prompt, max_output_tokens=1400)
                else:
                    output_text = _generate_text_with_openai(prompt, max_output_tokens=1400)
                if not (output_text or "").strip():
                    raise RuntimeError("Respuesta vacia del proveedor.")

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
                    elif evaluation_type == "matching":
                        question_text, expected_answer = _normalize_matching_question(
                            question_text=question_text,
                            expected_answer=expected_answer,
                            topic=topic_value,
                            difficulty=difficulty,
                            idx=len(result) + 1,
                        )
                    result.append((question_text, expected_answer))
                if result:
                    return result, provider, False
                provider_error = RuntimeError("El proveedor no devolvio preguntas válidas.")
            except Exception as exc:
                provider_error = exc
                if attempt < 3:
                    time.sleep(0.5 * attempt)
                    continue
        if provider_error:
            provider_errors.append(_describe_provider_error(provider, provider_error))
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
            question = textwrap.dedent(
                f"""
                [{difficulty}] ({topic}) Pregunta {idx}: Uní con flechas usando el material de estudio.
                Contexto: {fragment}
                Columna A:
                1) Idea principal del fragmento
                2) Dato complementario del fragmento
                3) Aplicación del fragmento
                Columna B:
                A) Desarrollo aplicado
                B) Información central
                C) Información de apoyo
                """
            ).strip()
            answer = "1-B;2-C;3-A"
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


def _normalize_matching_question(
    question_text: str,
    expected_answer: Optional[str],
    topic: str,
    difficulty: str,
    idx: int,
) -> QuestionItem:
    normalized = (question_text or "").strip()
    has_columns = "columna a" in normalized.lower() and "columna b" in normalized.lower()
    if not has_columns:
        normalized = textwrap.dedent(
            f"""
            [{difficulty}] ({topic}) Pregunta {idx}: Uní con flechas cada elemento correspondiente.
            Contexto: clasificación y relaciones de {topic}.
            Columna A:
            1) Concepto principal de {topic}
            2) Ejemplo de {topic}
            3) Aplicación de {topic}
            Columna B:
            A) Aplicación
            B) Concepto base
            C) Ejemplo concreto
            """
        ).strip()
    elif "contexto:" not in normalized.lower():
        normalized = f"Contexto: relaciones de {topic}.\n{normalized}"

    answer = (expected_answer or "").strip()
    if not answer:
        answer = "1-B;2-C;3-A"
    return normalized, answer


def _split_submission_answers(raw_text: str) -> list[str]:
    normalized = (raw_text or "").strip()
    if not normalized:
        return []
    lines = [line.strip() for line in normalized.splitlines() if line.strip()]
    answers: list[str] = []
    numbered_pattern = re.compile(r"^\s*(\d+)[\)\.\:\-]\s*(.+)$")
    for line in lines:
        match = numbered_pattern.match(line)
        if match:
            answers.append(match.group(2).strip())
            continue
        answers.append(line)
    return answers


def _build_question_feedback(
    answers: list[str],
    criteria: str,
    max_score: float,
    question_count: int,
) -> tuple[list[dict], float]:
    keywords = [k.strip() for k in (criteria or "").split(",") if k.strip()]
    total_questions = max(1, question_count, len(answers))
    points_per_question = round(max_score / total_questions, 2)
    items: list[dict] = []
    total_score = 0.0

    for idx in range(1, total_questions + 1):
        answer = answers[idx - 1] if idx - 1 < len(answers) else ""
        normalized_answer = (answer or "").strip()
        lowered = normalized_answer.lower()
        if not lowered:
            items.append(
                {
                    "question": idx,
                    "status": "x",
                    "label": "X",
                    "score": 0.0,
                    "max_score": points_per_question,
                    "comment": f"Respuesta {idx}: X. No responde.",
                }
            )
            continue

        if not keywords:
            ratio = 0.7
            missing: list[str] = []
        else:
            matched = sum(1 for kw in keywords if kw.lower() in lowered)
            ratio = matched / len(keywords)
            missing = [kw for kw in keywords if kw.lower() not in lowered][:2]

        if ratio >= 0.75:
            score = points_per_question
            total_score += score
            items.append(
                {
                    "question": idx,
                    "status": "muy_bien",
                    "label": "Muy bien",
                    "score": round(score, 2),
                    "max_score": points_per_question,
                    "comment": f"Respuesta {idx}: Muy bien.",
                }
            )
            continue

        if ratio >= 0.35:
            score = round(points_per_question * 0.6, 2)
            total_score += score
            if missing:
                improvement = f" Mejorar: agregá {', '.join(missing)}."
            else:
                improvement = " Mejorar: completá con mayor precisión."
            items.append(
                {
                    "question": idx,
                    "status": "mejorar",
                    "label": "Bien, mejorar",
                    "score": score,
                    "max_score": points_per_question,
                    "comment": f"Respuesta {idx}: Bien, mejorar.{improvement}",
                }
            )
            continue

        items.append(
            {
                "question": idx,
                "status": "x",
                "label": "X",
                "score": 0.0,
                "max_score": points_per_question,
                "comment": f"Respuesta {idx}: X. Incorrecta o fuera de criterio.",
            }
        )

    return items, round(min(max_score, total_score), 2)


def _build_teacher_feedback_text(items: list[dict], total_score: float, max_score: float) -> str:
    lines = [
        "Devolucion docente por pregunta:",
        *(
            f"- {item['comment']} ({item['score']}/{item['max_score']})"
            for item in items
        ),
        f"Puntaje total: {round(total_score, 2)}/{max_score}",
    ]
    return "\n".join(lines)


def _mock_grade(
    raw_text: str, criteria: str, max_score: float, question_count: int = 1
) -> tuple[float, str, list[dict]]:
    answers = _split_submission_answers(raw_text)
    items, total_score = _build_question_feedback(
        answers=answers,
        criteria=criteria,
        max_score=max_score,
        question_count=question_count,
    )
    feedback = _build_teacher_feedback_text(items, total_score, max_score)
    return total_score, feedback, items


def grade_submission_with_ai(
    raw_text: str,
    criteria: str,
    max_score: float,
    use_llm: bool = True,
    evaluation_type: Optional[str] = None,
    question_texts: Optional[list[str]] = None,
) -> tuple[float, str, list[dict]]:
    question_count = max(1, len(question_texts or []))
    if not use_llm:
        return _mock_grade(raw_text, criteria, max_score, question_count=question_count)
    prompt = (
        "Corrige la respuesta de un alumno con criterios dados.\n"
        f"Tipo de evaluación: {evaluation_type or 'general'}\n"
        f"Cantidad de preguntas esperadas: {question_count}\n"
        f"Criterios: {criteria}\n"
        f"Respuesta del alumno: {raw_text}\n"
        f"Puntaje maximo: {max_score}\n"
        "Devuelve SOLO JSON con {score, feedback, question_feedback}. "
        "question_feedback debe ser arreglo de {question,label,status,score,max_score,comment}. "
        "Usa lenguaje docente humano: 'Muy bien', 'Bien, mejorar', 'X'."
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
            raw_items = parsed.get("question_feedback")
            if not isinstance(raw_items, list):
                answers = _split_submission_answers(raw_text)
                auto_items, _ = _build_question_feedback(
                    answers=answers,
                    criteria=criteria,
                    max_score=max_score,
                    question_count=question_count,
                )
                return round(score, 2), feedback, auto_items
            normalized_items: list[dict] = []
            for idx, item in enumerate(raw_items[:question_count], start=1):
                if not isinstance(item, dict):
                    continue
                normalized_items.append(
                    {
                        "question": int(item.get("question", idx)),
                        "status": str(item.get("status", "mejorar")),
                        "label": str(item.get("label", "Bien, mejorar")),
                        "score": round(float(item.get("score", 0.0)), 2),
                        "max_score": round(float(item.get("max_score", max_score / question_count)), 2),
                        "comment": str(item.get("comment", f"Respuesta {idx}: Bien, mejorar.")),
                    }
                )
            if not normalized_items:
                answers = _split_submission_answers(raw_text)
                normalized_items, _ = _build_question_feedback(
                    answers=answers,
                    criteria=criteria,
                    max_score=max_score,
                    question_count=question_count,
                )
            return round(score, 2), feedback, normalized_items
        except Exception:
            continue

    return _mock_grade(raw_text, criteria, max_score, question_count=question_count)


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
            "responseMimeType": "application/json",
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
