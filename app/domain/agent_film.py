"""Domain logic for Agent Film business nodes.

This module contains the actual business logic for:
  - Input normalization (aligns with Go buildStartMessageContent)
  - Product context extraction
  - Creative strategy generation
  - Script generation and validation
  - Storyboard generation
  - Generation preparation

WP-08 implements the actual business logic that the graph nodes call.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from app.graph.state import AgentFilmState
from app.graph.profiles import get_profile
from app.llm.factory import create_llm
from app.providers.research import ProductResearchProvider
from app.providers.materials import MaterialProvider

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Input Normalization (aligns with Go agent_film_input.go)
# ---------------------------------------------------------------------------


def normalize_start_input(state: AgentFilmState) -> dict[str, Any]:
    """Normalize the initial user input.

    Aligns with Go:
      - normalizeAgentFilmProductLink (add https:// if missing)
      - buildStartMessageContent (split files into documents vs materials)
      - agentFilmPersistedStartInputFromMessages

    Returns state update dict.
    """
    user_request = (state.get("user_request") or "").strip()
    product_link = _normalize_product_link(state.get("product_link"))
    input_files = _normalize_input_files(state.get("input_files") or [])

    # Build the MAA start message content (mirrors Go buildStartMessageContent)
    start_content = _build_start_message_content(
        content=user_request,
        product_link=product_link,
        input_files=input_files,
        language=state.get("language", "zh-CN"),
    )

    return {
        "user_request": user_request,
        "product_link": product_link,
        "input_files": input_files,
        "product_context": {
            "raw_content": start_content,
            "product_link": product_link,
            "input_files": input_files,
        },
    }


def _normalize_product_link(link: str | None) -> str | None:
    """Normalize product link: strip whitespace, add https:// if missing."""
    if not link:
        return None
    link = link.strip()
    if not link:
        return None
    lower = link.lower()
    if lower.startswith("http://") or lower.startswith("https://"):
        return link
    if lower.startswith("//"):
        return f"https:{link}"
    return f"https://{link}"


def _normalize_input_files(files: list[dict]) -> list[dict]:
    """Normalize input files: ensure list of dicts, deduplicate by URL."""
    if not isinstance(files, list):
        return []
    seen = set()
    result = []
    for f in files:
        if not isinstance(f, dict):
            continue
        url = f.get("url", "").strip()
        name = f.get("name", "").strip()
        key = url or name
        if not key or key in seen:
            continue
        seen.add(key)
        result.append({
            "url": url,
            "name": name,
            "type": f.get("type"),
            "size": f.get("size"),
        })
    return result


def _build_start_message_content(
    content: str,
    product_link: str | None,
    input_files: list[dict],
    language: str,
) -> str:
    """Build the JSON start message content sent to MAA.

    Mirrors Go's buildStartMessageContent:
      - Splits files into documents and material_assets
      - Includes mode, content, link, files, material_assets, response_language
    """
    # Split files: images/audio/video → material_assets; documents → files
    material_extensions = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".mp4", ".mov", ".avi", ".mp3", ".wav", ".aac"}
    document_extensions = {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".txt", ".csv"}

    documents = []
    material_assets = []
    for f in input_files:
        url = f.get("url", "")
        ext = "." + url.rsplit(".", 1)[-1].lower() if "." in url else ""
        entry = {
            "url": url,
            "name": f.get("name", ""),
            "type": f.get("type"),
        }
        if ext in material_extensions:
            material_assets.append(entry)
        else:
            documents.append(entry)

    body = {
        "mode": "quick" if content else "deep",
        "content": content,
        "link": product_link or "",
        "files": documents,
        "material_assets": material_assets,
        "response_language": _normalize_language(language),
    }
    return json.dumps(body, ensure_ascii=False)


def _normalize_language(language: str) -> str:
    """Normalize language to canonical form."""
    language = language.strip().lower()
    if not language or language in ("zh", "zh-cn", "zh-hans", "cn"):
        return "zh-CN"
    if language in ("en", "en-us"):
        return "en-US"
    return language


# ---------------------------------------------------------------------------
# Product Context
# ---------------------------------------------------------------------------


async def extract_product_context(state: AgentFilmState) -> dict[str, Any]:
    """Extract product context from link and input files.

    Uses ProductResearchProvider to extract:
      - product_name
      - product_description
      - target_audience
      - selling_points
      - images

    For demo provider, returns deterministic data.
    For real provider, calls external product research APIs.

    Returns state update with product_context dict.
    """
    provider = ProductResearchProvider()
    profile = get_profile(state.get("profile_id", "one-click-quick"))

    product_context = dict(state.get("product_context", {}))

    # If we already have complete product context, skip extraction
    if product_context.get("product_name") and product_context.get("product_description"):
        logger.debug("Product context already complete, skipping extraction")
        return {"product_context": product_context}

    # Try to extract from product link
    product_link = state.get("product_link")
    if product_link:
        try:
            result = await provider.execute(url=product_link)
            if result.success:
                extracted = result.data
                product_context.update({
                    "product_name": extracted.get("product_name", product_context.get("product_name")),
                    "product_description": extracted.get("product_description", product_context.get("product_description")),
                    "target_audience": extracted.get("target_audience", product_context.get("target_audience")),
                    "selling_points": extracted.get("key_selling_points", product_context.get("selling_points")),
                    "images": extracted.get("images", product_context.get("images", [])),
                    "source": "link_extraction",
                })
                logger.info("Product context extracted from link: %s", product_link)
        except Exception as exc:
            logger.warning("Product link extraction failed: %s", exc)
            product_context["extraction_error"] = str(exc)

    # If still missing critical fields and we have input files, try file-based extraction
    if not product_context.get("product_name") and state.get("input_files"):
        # In a real implementation, this would call OCR/analysis on uploaded files
        # For now, we note that files are available for user review
        product_context["has_input_files"] = True
        product_context["input_file_count"] = len(state.get("input_files", []))

    # Quick profile: fill defaults if still empty
    if profile.mode == "quick" and not product_context.get("product_name"):
        product_context.update({
            "product_name": "未命名商品",
            "product_description": state.get("user_request", "智能成片"),
            "target_audience": "通用消费者",
            "selling_points": ["品质优良", "性价比高"],
            "source": "quick_defaults",
        })

    return {"product_context": product_context}


def build_product_context_interaction(state: AgentFilmState) -> dict[str, Any]:
    """Build the interaction payload for product context confirmation.

    Aligns with frontend CardsType.confirm_extracted_product_context:
      - product images
      - product name, description, selling points
      - video settings (aspect_ratio, language, duration)
    """
    profile = get_profile(state.get("profile_id", "one-click-quick"))
    ctx = state.get("product_context", {})

    # Build form fields for the frontend card
    form_data = [
        {
            "key": "product_name",
            "value": ctx.get("product_name", ""),
            "label": "商品名称",
            "required": True,
            "controlType": "input",
        },
        {
            "key": "product_description",
            "value": ctx.get("product_description", ""),
            "label": "商品描述",
            "required": True,
            "controlType": "textarea",
        },
        {
            "key": "selling_points",
            "value": ctx.get("selling_points", []),
            "label": "卖点",
            "required": False,
            "controlType": "text",
        },
        {
            "key": "target_audience",
            "value": ctx.get("target_audience", ""),
            "label": "目标受众",
            "required": False,
            "controlType": "input",
        },
    ]

    # Add video settings
    form_data.extend([
        {
            "key": "aspect_ratio",
            "value": profile.default_aspect_ratio,
            "label": "视频比例",
            "required": False,
            "controlType": "single_choice",
            "options": [
                {"label": "16:9 横屏", "value": "16:9"},
                {"label": "9:16 竖屏", "value": "9:16"},
                {"label": "1:1 方形", "value": "1:1"},
            ],
        },
        {
            "key": "video_length",
            "value": profile.default_duration,
            "label": "视频时长",
            "required": False,
            "controlType": "single_choice",
            "options": [
                {"label": "15秒", "value": "15s"},
                {"label": "30秒", "value": "30s"},
                {"label": "60秒", "value": "60s"},
            ],
        },
    ])

    return {
        "intent": "confirm_extracted_product_context",
        "render_type": "form",
        "form_data": form_data,
        "actions": ["approve", "modify"],
        "status": "pending",
        "source": "orchestrator",
        "product_images": ctx.get("images", []),
    }


# ---------------------------------------------------------------------------
# Creative Strategy
# ---------------------------------------------------------------------------


async def generate_creative_strategy(state: AgentFilmState) -> dict[str, Any]:
    """Generate marketing creative strategy.

    Uses LLM to generate:
      - marketing_angle
      - tone
      - key_messages
      - target_emotion

    In a real implementation, this would call the LLM with a structured
    output schema. For WP-08, we use a heuristic approach.

    Returns state update with creative_strategy dict.
    """
    profile = get_profile(state.get("profile_id", "one-click-quick"))
    ctx = state.get("product_context", {})
    user_request = state.get("user_request", "")

    # Build strategy based on product context and user request
    product_name = ctx.get("product_name", "智能商品")
    selling_points = ctx.get("selling_points", [])

    strategy = {
        "marketing_angle": _determine_marketing_angle(user_request, selling_points),
        "tone": _determine_tone(profile.mode),
        "key_messages": selling_points[:3] if selling_points else ["品质优良", "性价比高"],
        "target_emotion": _determine_target_emotion(user_request),
        "product_name": product_name,
        "profile_mode": profile.mode,
    }

    logger.info("Creative strategy generated: angle=%s", strategy["marketing_angle"])

    return {"creative_strategy": strategy}


def _determine_marketing_angle(user_request: str, selling_points: list[str]) -> str:
    """Determine the marketing angle from user request and selling points."""
    request_lower = user_request.lower()
    if any(kw in request_lower for kw in ["促销", "打折", "优惠", "活动"]):
        return "promotional"
    if any(kw in request_lower for kw in ["新品", "上市", "首发"]):
        return "new_launch"
    if any(kw in request_lower for kw in ["品牌", "故事", "理念"]):
        return "brand_story"
    if selling_points:
        return "feature_focused"
    return "general"


def _determine_tone(mode: str) -> str:
    """Determine the tone based on profile mode."""
    if mode == "quick":
        return "concise"
    return "detailed"


def _determine_target_emotion(user_request: str) -> str:
    """Determine the target emotion."""
    request_lower = user_request.lower()
    if any(kw in request_lower for kw in ["搞笑", "幽默", "趣味"]):
        return "fun"
    if any(kw in request_lower for kw in ["温馨", "温暖", "家庭"]):
        return "warm"
    if any(kw in request_lower for kw in ["高端", "奢华", "品质"]):
        return "premium"
    if any(kw in request_lower for kw in ["紧迫", "限量", "抢购"]):
        return "urgency"
    return "neutral"


# ---------------------------------------------------------------------------
# Script Generation
# ---------------------------------------------------------------------------


async def generate_script(state: AgentFilmState) -> dict[str, Any]:
    """Generate video script.

    Uses LLM to generate a structured script with:
      - title
      - total_duration
      - segments (each with time, camera_desc, script_content, etc.)
      - style

    Returns state update with script dict.
    """
    profile = get_profile(state.get("profile_id", "one-click-quick"))
    ctx = state.get("product_context", {})
    strategy = state.get("creative_strategy", {})

    product_name = ctx.get("product_name", "智能商品")
    marketing_angle = strategy.get("marketing_angle", "general")
    key_messages = strategy.get("key_messages", [])

    # Determine duration from profile or default
    duration = _parse_duration(profile.default_duration)

    # Generate script segments
    segments = _generate_script_segments(
        product_name=product_name,
        marketing_angle=marketing_angle,
        key_messages=key_messages,
        duration=duration,
        mode=profile.mode,
    )

    script = {
        "title": f"{product_name} - {_get_script_title(marketing_angle)}",
        "total_duration": duration,
        "style": _get_script_style(marketing_angle),
        "segments": segments,
        "language": state.get("language", "zh-CN"),
        "profile_mode": profile.mode,
    }

    logger.info("Script generated: %d segments, duration=%ds", len(segments), duration)

    return {"script": script}


def _parse_duration(duration_str: str) -> int:
    """Parse duration string like '30s' to integer seconds."""
    try:
        return int(duration_str.rstrip("sS"))
    except (ValueError, AttributeError):
        return 30


def _get_script_title(angle: str) -> str:
    """Get a script title based on marketing angle."""
    titles = {
        "promotional": "限时优惠",
        "new_launch": "新品首发",
        "brand_story": "品牌故事",
        "feature_focused": "产品亮点",
    }
    return titles.get(angle, "智能成片")


def _get_script_style(angle: str) -> str:
    """Get script style based on marketing angle."""
    styles = {
        "promotional": "fast_paced",
        "new_launch": "inspiring",
        "brand_story": "emotional",
        "feature_focused": "informative",
    }
    return styles.get(angle, "balanced")


def _generate_script_segments(
    product_name: str,
    marketing_angle: str,
    key_messages: list[str],
    duration: int,
    mode: str,
) -> list[dict[str, Any]]:
    """Generate script segments.

    For quick mode: fewer segments, simpler structure.
    For deep mode: more segments, richer content.
    """
    if mode == "quick":
        return [
            {
                "segment": 1,
                "time": f"0-{duration // 3}s",
                "camera_desc": f"商品全景展示 - {product_name}",
                "script_content": f"Introducing {product_name}。{key_messages[0] if key_messages else '品质之选'}。",
                "screen_text": product_name,
                "core_purpose": "introduction",
                "duration_seconds": duration // 3,
            },
            {
                "segment": 2,
                "time": f"{duration // 3}-{2 * duration // 3}s",
                "camera_desc": f"特写镜头 - 核心功能展示",
                "script_content": f"{key_messages[1] if len(key_messages) > 1 else '卓越性能，值得信赖'}。",
                "screen_text": key_messages[0] if key_messages else "",
                "core_purpose": "highlight",
                "duration_seconds": duration // 3,
            },
            {
                "segment": 3,
                "time": f"{2 * duration // 3}-{duration}s",
                "camera_desc": f"结尾号召 - 行动召唤",
                "script_content": f"立即体验 {product_name}，开启品质生活。",
                "screen_text": "立即购买",
                "core_purpose": "call_to_action",
                "duration_seconds": duration // 3,
            },
        ]

    # Deep mode: more detailed segments
    return [
        {
            "segment": 1,
            "time": f"0-{duration // 4}s",
            "camera_desc": f"开场 - 品牌/商品展示",
            "script_content": f"欢迎了解 {product_name}。{key_messages[0] if key_messages else '我们致力于提供卓越品质'}。",
            "screen_text": product_name,
            "core_purpose": "brand_intro",
            "duration_seconds": duration // 4,
        },
        {
            "segment": 2,
            "time": f"{duration // 4}-{duration // 2}s",
            "camera_desc": f"产品功能展示",
            "script_content": f"{key_messages[1] if len(key_messages) > 1 else '每一个细节都经过精心设计'}。",
            "screen_text": key_messages[0] if key_messages else "",
            "core_purpose": "feature_demo",
            "duration_seconds": duration // 4,
        },
        {
            "segment": 3,
            "time": f"{duration // 2}-{3 * duration // 4}s",
            "camera_desc": f"用户场景/情感共鸣",
            "script_content": f"{key_messages[2] if len(key_messages) > 2 else '让生活更美好'}。",
            "screen_text": key_messages[1] if len(key_messages) > 1 else "",
            "core_purpose": "emotional_connect",
            "duration_seconds": duration // 4,
        },
        {
            "segment": 4,
            "time": f"{3 * duration // 4}-{duration}s",
            "camera_desc": f"结尾号召",
            "script_content": f"选择 {product_name}，选择品质。立即行动！",
            "screen_text": "立即购买",
            "core_purpose": "call_to_action",
            "duration_seconds": duration // 4,
        },
    ]


# ---------------------------------------------------------------------------
# Storyboard Generation
# ---------------------------------------------------------------------------


async def generate_storyboard(state: AgentFilmState) -> dict[str, Any]:
    """Generate storyboard from script.

    Converts script segments into a storyboard with:
      - shot_number
      - time_window
      - camera_description
      - visual_content
      - voiceover
      - on_screen_text
      - core_purpose

    Returns state update with storyboard dict.
    """
    script = state.get("script", {})
    segments = script.get("segments", [])

    storyboard = {
        "title": script.get("title", "分镜脚本"),
        "total_shots": len(segments),
        "style": script.get("style", "balanced"),
        "shots": [
            {
                "shot_number": seg.get("segment", i + 1),
                "time_window": seg.get("time", ""),
                "camera_description": seg.get("camera_desc", ""),
                "visual_content": seg.get("camera_desc", ""),
                "voiceover": seg.get("script_content", ""),
                "on_screen_text": seg.get("screen_text", ""),
                "core_purpose": seg.get("core_purpose", ""),
                "duration_seconds": seg.get("duration_seconds", 0),
            }
            for i, seg in enumerate(segments)
        ],
        "language": script.get("language", "zh-CN"),
    }

    logger.info("Storyboard generated: %d shots", len(storyboard["shots"]))

    return {"storyboard": storyboard}


def build_storyboard_interaction(state: AgentFilmState) -> dict[str, Any]:
    """Build the interaction payload for storyboard review.

    Aligns with frontend CardsType.review_storyboard_script:
      - 3-column table: shot/time, camera_desc, core_purpose
      - Actions: approve, modify, deny, regenerate
    """
    storyboard = state.get("storyboard", {})
    shots = storyboard.get("shots", [])

    # Build table rows for the frontend
    rows = [
        {
            "shot": f"#{s.get('shot_number', i + 1)}",
            "time": s.get("time_window", ""),
            "camera_desc": s.get("camera_description", ""),
            "core_purpose": s.get("core_purpose", ""),
            "script_content": s.get("voiceover", ""),
        }
        for i, s in enumerate(shots)
    ]

    return {
        "intent": "review_storyboard_script",
        "render_type": "table_review",
        "title": storyboard.get("title", "分镜脚本审核"),
        "description": "请审核以下分镜脚本，确认或修改",
        "table_data": {
            "columns": ["shot", "time", "camera_desc", "core_purpose"],
            "rows": rows,
        },
        "actions": ["approve", "modify", "deny", "regenerate"],
        "status": "pending",
        "source": "orchestrator",
    }


# ---------------------------------------------------------------------------
# Generation Preparation
# ---------------------------------------------------------------------------


async def prepare_generation(state: AgentFilmState) -> dict[str, Any]:
    """Prepare materials and settings for generation.

    - Selects materials from search results
    - Matches digital human (if configured)
    - Calculates estimated cost

    Returns state update with materials, digital_human, render_job.
    """
    profile = get_profile(state.get("profile_id", "one-click-quick"))
    ctx = state.get("product_context", {})
    script = state.get("script", {})
    storyboard = state.get("storyboard", {})

    # For WP-08, we use demo materials
    # WP-09 will replace with actual material search and selection
    material_provider = MaterialProvider()

    try:
        result = await material_provider.execute(
            query=ctx.get("product_name", ""),
            style=script.get("style", "balanced"),
        )
        materials = result.data.get("materials", []) if result.success else []
    except Exception as exc:
        logger.warning("Material search failed: %s", exc)
        materials = []

    # Calculate estimated cost
    duration = script.get("total_duration", 30)
    billing_seconds = _round_to_billing_increment(duration)
    video_points = billing_seconds * 40  # 40 points per second
    digital_human_points = 500 if state.get("digital_human") else 0
    total_points = video_points + digital_human_points

    render_job = {
        "aspect_ratio": profile.default_aspect_ratio,
        "duration_seconds": duration,
        "billing_seconds": billing_seconds,
        "video_points": video_points,
        "digital_human_points": digital_human_points,
        "total_points": total_points,
        "estimated": True,
        "profile_mode": profile.mode,
    }

    return {
        "materials": materials,
        "render_job": render_job,
    }


def _round_to_billing_increment(seconds: int, increment: int = 5) -> int:
    """Round seconds to billing increment (default 5s)."""
    if seconds <= 0:
        return increment
    return ((seconds + increment - 1) // increment) * increment


def build_generation_approval(state: AgentFilmState) -> dict[str, Any]:
    """Build the approval payload for generation start.

    Aligns with frontend CardsType.confirm_generation_start:
      - cost breakdown (duration, points, digital human)
      - auto-approve countdown (10s default)
      - Actions: approve, cancel
    """
    profile = get_profile(state.get("profile_id", "one-click-quick"))
    render_job = state.get("render_job", {})
    ctx = state.get("product_context", {})
    storyboard = state.get("storyboard", {})

    total_points = render_job.get("total_points", 0)
    duration = render_job.get("duration_seconds", 30)
    has_digital_human = state.get("digital_human") is not None

    return {
        "intent": "confirm_generation_start",
        "render_type": "generation_cost_confirm",
        "title": "确认开始生成视频",
        "description": f"预计消耗 {total_points} 星点，生成 {duration} 秒视频",
        "cost_breakdown": {
            "duration_seconds": duration,
            "billing_seconds": render_job.get("billing_seconds", duration),
            "points_per_second": 40,
            "video_points": render_job.get("video_points", duration * 40),
            "digital_human_points": render_job.get("digital_human_points", 0),
            "total_points": total_points,
            "show": True,
        },
        "auto_approve_countdown_seconds": 10,
        "actions": ["approve", "cancel"],
        "status": "pending",
        "source": "orchestrator",
        "product_name": ctx.get("product_name", ""),
        "shot_count": storyboard.get("total_shots", 0),
    }
