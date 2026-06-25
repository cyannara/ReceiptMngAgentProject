import os
import base64
from typing import Any

import requests
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI


def _extract_text_from_upstage_response(payload: Any) -> str:
    if isinstance(payload, str):
        return payload.strip()

    if isinstance(payload, dict):
        for key in (
            "text",
            "ocr_text",
            "content",
            "result",
            "output_text",
            "markdown",
            "raw_text",
            "extracted_text",
        ):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
            if isinstance(value, (dict, list)):
                nested_text = _extract_text_from_upstage_response(value)
                if nested_text:
                    return nested_text

        for key in ("pages", "blocks", "elements", "children", "data"):
            value = payload.get(key)
            if isinstance(value, (dict, list)):
                nested_text = _extract_text_from_upstage_response(value)
                if nested_text:
                    return nested_text

        for value in payload.values():
            if isinstance(value, (dict, list)):
                nested_text = _extract_text_from_upstage_response(value)
                if nested_text:
                    return nested_text

    elif isinstance(payload, list):
        for item in payload:
            nested_text = _extract_text_from_upstage_response(item)
            if nested_text:
                return nested_text

    return ""


def ocr_with_gpt(image_path: str) -> str:
    with open(image_path, "rb") as f:
        base64_image = base64.b64encode(f.read()).decode("utf-8")

    llm = ChatOpenAI(model=os.getenv("OCR_MODEL", "gpt-4o"), temperature=0.0)
    vision_prompt = [
        {
            "type": "text",
            "text": "영수증 이미지에서 가맹점, 일자, 주소, 연락처 및 상세 품목 테이블(수량/금액)을 줄바꿈을 준수하여 텍스트로 복원하세요.",
        },
        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64_image}"}},
    ]
    response = llm.invoke([HumanMessage(content=vision_prompt)])
    return response.content


def ocr_with_upstage(image_path: str) -> str:
    api_key = os.getenv("UPSTAGE_API_KEY", "").strip()
    api_url = os.getenv("UPSTAGE_DOCUMENT_PARSER_URL", "").strip()
    if not api_key or not api_url:
        raise RuntimeError("UPSTAGE_API_KEY와 UPSTAGE_DOCUMENT_PARSER_URL 환경변수가 필요합니다.")

    with open(image_path, "rb") as f:
        image_bytes = f.read()

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
    }
    files = {"document": ("receipt.png", image_bytes, "image/png")}

    response = requests.post(api_url, headers=headers, files=files, timeout=60)
    response.raise_for_status()

    try:
        payload = response.json()
    except ValueError:
        payload = {"raw": response.text}

    extracted_text = _extract_text_from_upstage_response(payload)
    if not extracted_text:
        raise RuntimeError(
            f"Upstage 응답에서 텍스트를 추출하지 못했습니다. 응답 예시: {response.text[:1000]}"
        )
    return extracted_text


def run_ocr(image_path: str, provider: str | None = None) -> str:
    provider = (provider or os.getenv("OCR_PROVIDER", "gpt")).strip().lower()
    if provider == "upstage":
        return ocr_with_upstage(image_path)
    return ocr_with_gpt(image_path)
