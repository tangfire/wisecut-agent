"""Response language normalization matching the Go Client's wire contract.

Go Client reference: internal/third_party/maa/agent/client.go
  - normalizeAgentFilmResponseLanguage
  - buildAgentFilmResponseLanguageInstruction
"""
from __future__ import annotations

import uuid


def generate_id(prefix: str) -> str:
    """Generate a stable unique ID with a prefix."""
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def normalize_response_language(language: str) -> str:
    """Normalize a language identifier to the canonical form used in metadata.

    Mirrors the Go Client's ``normalizeAgentFilmResponseLanguage``.
    """
    language = language.strip()
    if not language or language.lower() == "<nil>":
        return "zh-CN"

    # Strip quality suffix (e.g., "en-US,en;q=0.9" -> "en-US")
    for sep in (",", ";"):
        if sep in language:
            language = language[:language.index(sep)]

    language = language.strip().lower()
    if not language or language == "<nil>":
        return "zh-CN"

    match language:
        case "zh" | "zh-cn" | "zh-hans" | "zh_hans" | "cn" | "sa":
            return "zh-CN"
        case "en" | "en-us" | "en_us":
            return "en-US"
        case _:
            return language


def build_language_instruction(language: str) -> str:
    """Build the LLM instruction for the response language.

    Mirrors the Go Client's ``buildAgentFilmResponseLanguageInstruction``.
    """
    normalized = normalize_response_language(language)
    match normalized:
        case "en-US":
            return "Please answer the user in English. Keep structured IDs, enum values, URLs, and code-like fields unchanged."
        case "zh-CN":
            return "请使用简体中文回答用户。结构化 ID、枚举值、URL 和代码类字段保持原样。"
        case _:
            return (
                f"Please answer the user in {normalized}. "
                "Keep structured IDs, enum values, URLs, and code-like fields unchanged."
            )
