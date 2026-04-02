import json
import os
import re
from pathlib import Path
from typing import Optional

import pytesseract
from openai import OpenAI
from PIL import Image


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
    api_key = os.getenv("OPENAI_API_KEY")
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    if not api_key:
        return _mock_generate_questions(topic, evaluation_type, difficulty, count)

    client = OpenAI(api_key=api_key)
    prompt = (
        "Eres un asistente pedagogico. Genera preguntas de evaluacion en JSON.\n"
        f"Tema: {topic}\n"
        f"Tipo: {evaluation_type}\n"
        f"Dificultad: {difficulty}\n"
        f"Cantidad: {count}\n"
        f"Material opcional: {material_text or 'No provisto'}\n"
        "Responde un arreglo JSON con objetos {question_text, expected_answer}."
    )
    try:
        response = client.responses.create(
            model=model,
            input=prompt,
            max_output_tokens=1400,
        )
        output_text = (response.output_text or "").strip()
        parsed = _extract_json_array(output_text)
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
        pass

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
    api_key = os.getenv("OPENAI_API_KEY")
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    if not use_llm or not api_key:
        return _mock_grade(raw_text, criteria, max_score)

    client = OpenAI(api_key=api_key)
    prompt = (
        "Corrige la respuesta de un alumno con criterios dados.\n"
        f"Criterios: {criteria}\n"
        f"Respuesta del alumno: {raw_text}\n"
        f"Puntaje maximo: {max_score}\n"
        "Devuelve SOLO JSON con {score, feedback}. "
        "score debe estar entre 0 y puntaje maximo."
    )
    try:
        response = client.responses.create(
            model=model,
            input=prompt,
            max_output_tokens=700,
        )
        output_text = (response.output_text or "").strip()
        parsed = _extract_json_object(output_text)
        score = float(parsed.get("score", 0.0))
        score = max(0.0, min(max_score, score))
        feedback = str(parsed.get("feedback", "")).strip()
        if not feedback:
            feedback = "Correccion realizada por IA."
        return round(score, 2), feedback
    except Exception:
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
