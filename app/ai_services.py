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


def _mock_generate_questions(
    topic: str,
    evaluation_type: str,
    difficulty: str,
    count: int,
) -> list[tuple[str, Optional[str]]]:
    questions = []
    for idx in range(1, count + 1):
        if evaluation_type == "multiple_choice":
            question = (
                f"[{difficulty}] ({topic}) Pregunta {idx}: Selecciona la opcion correcta."
            )
            answer = "Opcion A"
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
) -> list[tuple[str, Optional[str]]]:
    prompt = (
        "Eres un asistente pedagogico. Genera preguntas de evaluacion en JSON.\n"
        f"Tema: {topic}\n"
        f"Tipo: {evaluation_type}\n"
        f"Dificultad: {difficulty}\n"
        f"Cantidad: {count}\n"
        f"Material opcional: {material_text or 'No provisto'}\n"
        "Responde un arreglo JSON con objetos {question_text, expected_answer}."
    )

    for provider in _provider_order():
        try:
            if provider == "gemini":
                output_text = _generate_text_with_gemini(prompt, max_output_tokens=1400)
            else:
                output_text = _generate_text_with_openai(prompt, max_output_tokens=1400)

            parsed = _extract_json_array((output_text or "").strip())
            result: list[tuple[str, Optional[str]]] = []
            for item in parsed[:count]:
                result.append(
                    (
                        str(item.get("question_text", "")).strip() or "Pregunta generica",
                        (
                            str(item.get("expected_answer", "")).strip()
                            if item.get("expected_answer") is not None
                            else None
                        ),
                    )
                )
            if result:
                return result
        except Exception:
            continue

    return _mock_generate_questions(topic, evaluation_type, difficulty, count)


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
    try:
        return json.loads(text)
    except Exception:
        match = re.search(r"\[[\s\S]*\]", text)
        if match:
            return json.loads(match.group(0))
        raise


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
