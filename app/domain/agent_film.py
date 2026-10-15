"""Domain logic for Agent Film business nodes.

This module contains the actual business logic for:
  - Input normalization (aligns with Go buildStartMessageContent)
  - Product context extraction
  - Creative strategy generation (LLM-assisted)
  - Script generation (LLM-assisted)
  - Storyboard generation (LLM-assisted)
  - Generation preparation
  - Material selection (WP-09)
  - Digital human matching (WP-09)
  - Video rendering (WP-09)
  - Video delivery validation (WP-09)
  - Artifact creation and publishing (WP-09)

WP-08 implements the actual business logic that the graph nodes call.
WP-11 round 2: script/storyboard use LLM structured output with heuristic fallback.
"""
from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, cast

from pydantic import BaseModel, Field

from app.graph.profiles import get_profile
from app.llm.factory import create_llm
from app.persistence.repositories import (
    ArtifactRepository,
    EventRepository,
    OutboxRepository,
)
from app.persistence.unit_of_work import unit_of_work
from app.protocol.language import generate_id
from app.providers.digital_human import DigitalHumanProvider
from app.providers.materials import MaterialProvider
from app.providers.research import ProductResearchProvider
from app.providers.video import VideoRenderProvider

logger = logging.getLogger(__name__)

# Prompt templates for LLM-assisted generation
_STRATEGY_PROMPT = """Generate a marketing creative strategy for the following product.

Product: {product_name}
Description: {product_description}
Selling points: {selling_points}
Target audience: {target_audience}
User request: {user_request}
Mode: {mode}

Return a JSON object with:
  - marketing_angle: one of [promotional, new_launch, brand_story, feature_focused, general]
  - tone: one of [concise, detailed, emotional, urgent]
  - key_messages: list of 3 short selling points
  - target_emotion: one of [fun, warm, premium, urgency, neutral]
"""

_SCRIPT_PROMPT = """Generate a video script for the following product.

Product: {product_name}
Description: {product_description}
Selling points: {selling_points}
Marketing angle: {marketing_angle}
Tone: {tone}
Target emotion: {target_emotion}
Duration: {duration} seconds
Mode: {mode}
Language: {language}

Generate {num_segments} segments. Each segment must have:
  - segment: sequential number starting from 1
  - time: time window like "0-10s"
  - camera_desc: camera movement/angle description
  - script_content: voiceover/narration text
  - screen_text: text shown on screen
  - core_purpose: one of [introduction, highlight, emotional_connect, call_to_action, brand_intro, feature_demo]
  - duration_seconds: how long this segment lasts

Return JSON with:
  - title: catchy video title
  - total_duration: {duration}
  - style: one of [fast_paced, inspiring, emotional, informative, balanced]
  - language: {language}
  - segments: list of segment objects
"""

_STORYBOARD_PROMPT = """Convert the following video script into a detailed storyboard.

Script title: {title}
Style: {style}
Language: {language}

Script segments:
{segments_json}

Convert each segment into a storyboard shot with:
  - shot_number: same as segment number
  - time_window: same as segment time
  - camera_description: detailed camera work (angle, movement, transition)
  - visual_content: what appears on screen (visual description)
  - voiceover: narration text from the segment
  - on_screen_text: text overlays
  - core_purpose: same as segment core_purpose
  - duration_seconds: same as segment duration

Return JSON with:
  - title: storyboard title
  - total_shots: number of shots
  - style: same as script style
  - language: same as script language
  - shots: list of shot objects
"""


# ---------------------------------------------------------------------------
# Structured output models for LLM (WP-11 round 2)
# ---------------------------------------------------------------------------


class ScriptSegmentModel(BaseModel):
    segment: int = Field(description="Sequential segment number starting from 1")
    time: str = Field(description="Time window like '0-10s'")
    camera_desc: str = Field(description="Camera movement and angle description")
    script_content: str = Field(description="Voiceover/narration text")
    screen_text: str = Field(description="Text shown on screen")
    core_purpose: str = Field(
        description="One of: introduction, highlight, emotional_connect, call_to_action, brand_intro, feature_demo"
    )
    duration_seconds: int = Field(description="Duration of this segment in seconds", ge=1)


class ScriptOutput(BaseModel):
    title: str = Field(description="Catchy video title")
    total_duration: int = Field(description="Total video duration in seconds", ge=5, le=120)
    style: str = Field(
        description="One of: fast_paced, inspiring, emotional, informative, balanced"
    )
    language: str = Field(description="Language code like zh-CN or en-US")
    segments: list[ScriptSegmentModel] = Field(
        description="List of script segments", min_length=1, max_length=8
    )


class StoryboardShotModel(BaseModel):
    shot_number: int = Field(description="Sequential shot number", ge=1)
    time_window: str = Field(description="Time window like '0-10s'")
    camera_description: str = Field(description="Detailed camera work description")
    visual_content: str = Field(description="What appears on screen")
    voiceover: str = Field(description="Narration/voiceover text")
    on_screen_text: str = Field(description="Text overlay on screen")
    core_purpose: str = Field(description="Purpose of this shot")
    duration_seconds: int = Field(description="Duration in seconds", ge=1)


class StoryboardOutput(BaseModel):
    title: str = Field(description="Storyboard title")
    total_shots: int = Field(description="Total number of shots", ge=1, le=10)
    style: str = Field(description="Visual style")
    language: str = Field(description="Language code")
    shots: list[StoryboardShotModel] = Field(
        description="List of storyboard shots", min_length=1, max_length=10
    )


if TYPE_CHECKING:
    from app.graph.state import AgentFilmState


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


def _normalize_input_files(files: list[dict[str, Any]]) -> list[dict[str, Any]]:
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
    input_files: list[dict[str, Any]],
    language: str,
) -> str:
    """Build the JSON start message content sent to MAA.

    Mirrors Go's buildStartMessageContent:
      - Splits files into documents and material_assets
      - Includes mode, content, link, files, material_assets, response_language
    """
    # Split files: images/audio/video → material_assets; documents → files
    material_extensions = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".mp4", ".mov", ".avi", ".mp3", ".wav", ".aac"}

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

    Uses LLM with structured output to generate:
      - marketing_angle
      - tone
      - key_messages
      - target_emotion

    Falls back to heuristic approach if LLM fails.

    Returns state update with creative_strategy dict.
    """
    profile = get_profile(state.get("profile_id", "one-click-quick"))
    ctx = state.get("product_context", {})
    user_request = state.get("user_request", "")

    product_name = ctx.get("product_name", "智能商品")
    product_description = ctx.get("product_description", "")
    selling_points = ctx.get("selling_points", [])
    target_audience = ctx.get("target_audience", "")

    # Try LLM first
    try:
        llm = create_llm()
        prompt = _STRATEGY_PROMPT.format(
            product_name=product_name,
            product_description=product_description or "无",
            selling_points=", ".join(selling_points) if selling_points else "无",
            target_audience=target_audience or "通用消费者",
            user_request=user_request or "无特殊要求",
            mode=profile.mode,
        )
        response = await llm.ainvoke(prompt)
        raw_content = response.content if hasattr(response, "content") else str(response)
        content = raw_content if isinstance(raw_content, str) else str(raw_content)

        # Parse LLM response
        strategy = _parse_strategy_response(content, profile.mode)
        strategy["product_name"] = product_name
        strategy["profile_mode"] = profile.mode
        strategy["source"] = "llm"
        logger.info("Creative strategy generated via LLM: angle=%s", strategy.get("marketing_angle"))
        return {"creative_strategy": strategy}

    except Exception as exc:
        logger.warning("LLM strategy generation failed, using heuristic: %s", exc)

    # Fallback to heuristic
    strategy = {
        "marketing_angle": _determine_marketing_angle(user_request, selling_points),
        "tone": _determine_tone(profile.mode),
        "key_messages": selling_points[:3] if selling_points else ["品质优良", "性价比高"],
        "target_emotion": _determine_target_emotion(user_request),
        "product_name": product_name,
        "profile_mode": profile.mode,
        "source": "heuristic",
    }
    logger.info("Creative strategy generated via heuristic: angle=%s", strategy["marketing_angle"])
    return {"creative_strategy": strategy}


def _parse_strategy_response(content: str, mode: str) -> dict[str, Any]:
    """Parse LLM response into strategy dict."""
    import json
    import re

    # Try to extract JSON from response
    json_match = re.search(r'\{.*\}', content, re.DOTALL)
    if json_match:
        try:
            data = json.loads(json_match.group())
            return {
                "marketing_angle": data.get("marketing_angle", _clamp_angle(data.get("marketing_angle", "general"))),
                "tone": data.get("tone", _clamp_tone(data.get("tone", "concise" if mode == "quick" else "detailed"))),
                "key_messages": data.get("key_messages", ["品质优良", "性价比高"])[:3],
                "target_emotion": data.get("target_emotion", "neutral"),
            }
        except (json.JSONDecodeError, AttributeError):
            pass

    # Fallback: return defaults
    return {
        "marketing_angle": "general",
        "tone": "concise" if mode == "quick" else "detailed",
        "key_messages": ["品质优良", "性价比高"],
        "target_emotion": "neutral",
    }


def _clamp_angle(value: str) -> str:
    valid = {"promotional", "new_launch", "brand_story", "feature_focused", "general"}
    return value if value in valid else "general"


def _clamp_tone(value: str) -> str:
    valid = {"concise", "detailed", "emotional", "urgent"}
    return value if value in valid else "balanced"


def _clamp_emotion(value: str) -> str:
    valid = {"fun", "warm", "premium", "urgency", "neutral"}
    return value if value in valid else "neutral"


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

    Uses LLM with structured output to generate a script with:
      - title, total_duration, style, language
      - segments (each with time, camera_desc, script_content, screen_text, core_purpose)

    Falls back to heuristic if LLM fails (WP-11 round 2).

    Returns state update with script dict.
    """
    profile = get_profile(state.get("profile_id", "one-click-quick"))
    ctx = state.get("product_context", {})
    strategy = state.get("creative_strategy", {})
    language = state.get("language", "zh-CN")

    product_name = ctx.get("product_name", "智能商品")
    marketing_angle = strategy.get("marketing_angle", "general")
    key_messages = strategy.get("key_messages", [])
    duration = _parse_duration(profile.default_duration)
    num_segments = 3 if profile.mode == "quick" else 4

    # Try LLM with structured output first (WP-11 round 2)
    try:
        llm = create_llm()
        structured_llm = llm.with_structured_output(ScriptOutput)
        prompt = _SCRIPT_PROMPT.format(
            product_name=product_name,
            product_description=ctx.get("product_description", "") or "无",
            selling_points=", ".join(key_messages) if key_messages else "品质优良",
            marketing_angle=marketing_angle,
            tone=strategy.get("tone", "concise" if profile.mode == "quick" else "detailed"),
            target_emotion=strategy.get("target_emotion", "neutral"),
            duration=duration,
            mode=profile.mode,
            language=language,
            num_segments=num_segments,
        )
        result = cast("ScriptOutput", await structured_llm.ainvoke(prompt))
        segments = [
            {
                "segment": s.segment,
                "time": s.time,
                "camera_desc": s.camera_desc,
                "script_content": s.script_content,
                "screen_text": s.screen_text,
                "core_purpose": s.core_purpose,
                "duration_seconds": s.duration_seconds,
            }
            for s in result.segments
        ]
        script = {
            "title": result.title,
            "total_duration": result.total_duration,
            "style": result.style,
            "language": result.language,
            "segments": segments,
            "profile_mode": profile.mode,
        }
        logger.info(
            "Script generated via LLM: %d segments, duration=%ds",
            len(segments),
            result.total_duration,
        )
        return {"script": script}
    except Exception as exc:
        logger.warning("LLM script generation failed, using heuristic: %s", exc)

    # Fallback to heuristic
    script = {
        "title": f"{product_name} - {_get_script_title(marketing_angle)}",
        "total_duration": duration,
        "style": _get_script_style(marketing_angle),
        "segments": _generate_script_segments(
            product_name=product_name,
            marketing_angle=marketing_angle,
            key_messages=key_messages,
            duration=duration,
            mode=profile.mode,
        ),
        "language": language,
        "profile_mode": profile.mode,
    }
    segments_count = len(script.get("segments", []))
    logger.info("Script generated via heuristic: %d segments", segments_count)
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
                "camera_desc": "特写镜头 - 核心功能展示",
                "script_content": f"{key_messages[1] if len(key_messages) > 1 else '卓越性能，值得信赖'}。",
                "screen_text": key_messages[0] if key_messages else "",
                "core_purpose": "highlight",
                "duration_seconds": duration // 3,
            },
            {
                "segment": 3,
                "time": f"{2 * duration // 3}-{duration}s",
                "camera_desc": "结尾号召 - 行动召唤",
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
            "camera_desc": "开场 - 品牌/商品展示",
            "script_content": f"欢迎了解 {product_name}。{key_messages[0] if key_messages else '我们致力于提供卓越品质'}。",
            "screen_text": product_name,
            "core_purpose": "brand_intro",
            "duration_seconds": duration // 4,
        },
        {
            "segment": 2,
            "time": f"{duration // 4}-{duration // 2}s",
            "camera_desc": "产品功能展示",
            "script_content": f"{key_messages[1] if len(key_messages) > 1 else '每一个细节都经过精心设计'}。",
            "screen_text": key_messages[0] if key_messages else "",
            "core_purpose": "feature_demo",
            "duration_seconds": duration // 4,
        },
        {
            "segment": 3,
            "time": f"{duration // 2}-{3 * duration // 4}s",
            "camera_desc": "用户场景/情感共鸣",
            "script_content": f"{key_messages[2] if len(key_messages) > 2 else '让生活更美好'}。",
            "screen_text": key_messages[1] if len(key_messages) > 1 else "",
            "core_purpose": "emotional_connect",
            "duration_seconds": duration // 4,
        },
        {
            "segment": 4,
            "time": f"{3 * duration // 4}-{duration}s",
            "camera_desc": "结尾号召",
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

    Uses LLM with structured output to convert script segments into a storyboard.

    Falls back to heuristic if LLM fails (WP-11 round 2).

    Returns state update with storyboard dict.
    """
    script = state.get("script", {})
    segments = script.get("segments", [])
    language = script.get("language", state.get("language", "zh-CN"))

    # Try LLM with structured output first (WP-11 round 2)
    if segments:
        try:
            llm = create_llm()
            structured_llm = llm.with_structured_output(StoryboardOutput)
            segments_json = json.dumps(
                [
                    {
                        "segment": s.get("segment", i + 1),
                        "time": s.get("time", ""),
                        "camera_desc": s.get("camera_desc", ""),
                        "script_content": s.get("script_content", ""),
                        "screen_text": s.get("screen_text", ""),
                        "core_purpose": s.get("core_purpose", ""),
                        "duration_seconds": s.get("duration_seconds", 0),
                    }
                    for i, s in enumerate(segments)
                ],
                ensure_ascii=False,
            )
            prompt = _STORYBOARD_PROMPT.format(
                title=script.get("title", "分镜脚本"),
                style=script.get("style", "balanced"),
                language=language,
                segments_json=segments_json,
            )
            result = cast("StoryboardOutput", await structured_llm.ainvoke(prompt))
            storyboard = {
                "title": result.title,
                "total_shots": result.total_shots,
                "style": result.style,
                "language": result.language,
                "shots": [
                    {
                        "shot_number": s.shot_number,
                        "time_window": s.time_window,
                        "camera_description": s.camera_description,
                        "visual_content": s.visual_content,
                        "voiceover": s.voiceover,
                        "on_screen_text": s.on_screen_text,
                        "core_purpose": s.core_purpose,
                        "duration_seconds": s.duration_seconds,
                    }
                    for s in result.shots
                ],
            }
            shots_count = len(storyboard.get("shots", []))
            logger.info("Storyboard generated via LLM: %d shots", shots_count)
            return {"storyboard": storyboard}
        except Exception as exc:
            logger.warning("LLM storyboard generation failed, using heuristic: %s", exc)

    # Fallback to heuristic
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
        "language": language,
    }
    shots_count = len(storyboard.get("shots", []))
    logger.info("Storyboard generated via heuristic: %d shots", shots_count)
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
    render_job: dict[str, Any] = state.get("render_job") or {}
    ctx = state.get("product_context", {}) or {}

    total_points = render_job.get("total_points", 0)
    duration = render_job.get("duration_seconds", 30)
    # has_digital_human = state.get("digital_human") is not None  # Reserved for future cost calculation

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
        "shot_count": state.get("storyboard", {}).get("total_shots", 0),
    }


# ---------------------------------------------------------------------------
# Material Selection (WP-09)
# ---------------------------------------------------------------------------


async def select_materials_for_render(state: AgentFilmState) -> dict[str, Any]:
    """Select materials from search results for rendering."""
    existing_materials = state.get("materials", [])
    if not existing_materials:
        material_provider = MaterialProvider()
        try:
            result = await material_provider.execute(
                query=state.get("product_context", {}).get("product_name", ""),
                style=state.get("script", {}).get("style", "balanced"),
            )
            if result.success:
                existing_materials = result.data.get("materials", [])
        except Exception as exc:
            logger.warning("Material selection failed: %s", exc)

    selected = existing_materials[:3] if existing_materials else []
    return {"materials": selected}


# ---------------------------------------------------------------------------
# Digital Human Matching (WP-09)
# ---------------------------------------------------------------------------


async def match_digital_human(state: AgentFilmState) -> dict[str, Any]:
    """Match a digital human to the product/script."""
    profile = get_profile(state.get("profile_id", "one-click-quick"))
    if profile.mode == "quick":
        return {"digital_human": None}

    provider = DigitalHumanProvider()
    try:
        result = await provider.execute(
            product_category=state.get("product_context", {}).get("product_type", "general"),
            script_style=state.get("script", {}).get("style", "balanced"),
            language=state.get("language", "zh-CN"),
        )
        if result.success:
            return {"digital_human": result.data}
    except Exception as exc:
        logger.warning("Digital human matching failed: %s", exc)

    return {"digital_human": None}


# ---------------------------------------------------------------------------
# Video Rendering (WP-09)
# ---------------------------------------------------------------------------


async def render_video(state: AgentFilmState) -> dict[str, Any]:
    """Trigger video rendering via VideoRenderProvider."""
    profile = get_profile(state.get("profile_id", "one-click-quick"))
    script = state.get("script", {})
    storyboard = state.get("storyboard", {})
    materials = state.get("materials", [])
    digital_human = state.get("digital_human")

    provider = VideoRenderProvider()
    try:
        result = await provider.execute(
            script=script,
            storyboard=storyboard,
            materials=materials,
            digital_human=digital_human,
            aspect_ratio=profile.default_aspect_ratio,
            duration_seconds=script.get("total_duration", 30),
            language=state.get("language", "zh-CN"),
        )
        if result.success:
            render_job = dict(state.get("render_job", {}))
            render_job.update({
                "video_url": result.data.get("video_url"),
                "cover_url": result.data.get("cover_url"),
                "format": result.data.get("format", "mp4"),
                "resolution": result.data.get("resolution", "1920x1080"),
                "status": "completed",
            })
            return {"render_job": render_job}
    except Exception as exc:
        logger.error("Video rendering failed: %s", exc)
        errors = state.get("errors", []) + [{"node": "render_video", "error": str(exc), "fatal": False}]
        return {"errors": errors}

    errors = state.get("errors", []) + [{"node": "render_video", "error": "Rendering failed", "fatal": False}]
    return {"errors": errors}


# ---------------------------------------------------------------------------
# Video Delivery Validation (WP-09)
# ---------------------------------------------------------------------------


def validate_video_delivery(video_url: str) -> dict[str, Any]:
    """Validate a rendered video URL."""
    if not video_url:
        return {"valid": False, "error": "video_url is empty"}

    video_url = video_url.strip()
    if not video_url:
        return {"valid": False, "error": "video_url is empty"}

    if not video_url.lower().startswith(("http://", "https://")):
        return {"valid": False, "error": "video_url must use http or https protocol"}

    # Extract host: handle IPv6 bracket literals vs hostname:port
    host_and_port = video_url.split("/")[2].lower()
    if host_and_port.startswith("[") and host_and_port.endswith("]"):
        host = host_and_port[1:-1]
    else:
        host = host_and_port.split(":")[0]
    if host in ("localhost", "127.0.0.1", "0.0.0.0", "::1"):
        return {"valid": False, "error": "video_url points to internal address"}

    video_extensions = (".mp4", ".mov", ".avi", ".webm", ".m3u8")
    if not any(video_url.lower().endswith(ext) for ext in video_extensions):
        logger.debug("Video URL doesn't have standard extension: %s", video_url)

    return {"valid": True}


# ---------------------------------------------------------------------------
# Artifact Service (WP-09)
# ---------------------------------------------------------------------------


async def create_final_video_artifact(
    state: AgentFilmState,
    video_url: str,
    cover_url: str | None = None,
) -> dict[str, Any]:
    """Create the final video Artifact and emit artifact.created + business.message."""
    artifact_id = generate_id("art")
    now = datetime.now(UTC)
    profile = get_profile(state.get("profile_id", "one-click-quick"))
    script = state.get("script", {})
    storyboard = state.get("storyboard", {})

    validation = validate_video_delivery(video_url)
    if not validation["valid"]:
        return {"success": False, "error": validation["error"]}

    artifact_payload = {
        "final_video": {
            "ready": True,
            "status": "completed",
            "video_url": video_url,
            "cover_url": cover_url or "",
        },
        "specs": {
            "duration_seconds": script.get("total_duration", 30),
            "aspect_ratio": profile.default_aspect_ratio,
            "format": "mp4",
            "resolution": "1920x1080",
        },
        "storyboard_segments": [
            {
                "shot_number": shot.get("shot_number", i + 1),
                "duration_seconds": shot.get("duration_seconds", 0),
                "description": shot.get("camera_description", ""),
                "script_content": shot.get("voiceover", ""),
                "video_url": shot.get("video_url", ""),
                "cover_url": shot.get("cover_url", ""),
                "begin_time": shot.get("begin_time", 0),
                "end_time": shot.get("end_time", 0),
            }
            for i, shot in enumerate(storyboard.get("shots", []))
        ],
        "final_delivery_check": {
            "status": "pass",
            "checked_at": now.isoformat(),
        },
    }

    async with unit_of_work() as uow:
        artifact_repo = ArtifactRepository(uow.session)
        event_repo = EventRepository(uow.session)
        outbox_repo = OutboxRepository(uow.session)

        await artifact_repo.create(
            artifact_id=artifact_id,
            conversation_id=state["conversation_id"],
            run_id=state["run_id"],
            artifact_type="final_video",
            payload=artifact_payload,
            uri=video_url,
        )

        seq = await event_repo.get_next_seq(state["conversation_id"], state["run_id"])

        # artifact.created event
        artifact_event_id = generate_id("event")
        await event_repo.create(
            event_id=artifact_event_id,
            conversation_id=state["conversation_id"],
            run_id=state["run_id"],
            seq=seq,
            event_type="artifact.created",
            payload={
                "artifact_id": artifact_id,
                "uri": video_url,
                "title": script.get("title", "Final Video"),
                "schema_name": "final_video",
                "schema_version": "1.0.0",
                "output_key": "final_video",
                "mime_type": "video/mp4",
                "producer": "post_production_agent",
                "summary": f"Final video: {script.get('title', 'Agent Film')}",
                "preview": {
                    "video_url": video_url,
                    "duration": str(script.get("total_duration", 30)),
                    "aspect_ratio": profile.default_aspect_ratio,
                    "status": "completed",
                },
                "source_type": "agent_generated",
                "trust_level": "high",
                "source_refs": [],
                "built_for": {"constraints": {}, "from": {}},
                "created_at": now.isoformat(),
                "trace": {"agent_name": "post_production_agent"},
                "final_video": {
                    "ready": True,
                    "status": "completed",
                    "video_url": video_url,
                },
            },
        )

        # business.message event (primary delivery path)
        business_event_id = generate_id("event")
        await event_repo.create(
            event_id=business_event_id,
            conversation_id=state["conversation_id"],
            run_id=state["run_id"],
            seq=seq + 1,
            event_type="business.message",
            payload={
                "business_key": "final_video",
                "status": "completed",
                "message": {
                    "business_key": "final_video",
                    "status": "completed",
                    "payload": {
                        "video_url": video_url,
                        "cover_url": cover_url or "",
                        "title": script.get("title", "Final Video"),
                        "duration": script.get("total_duration", 30),
                        "aspect_ratio": profile.default_aspect_ratio,
                        "storyboard_segments": storyboard.get("shots", []),
                    },
                },
            },
        )

        await outbox_repo.enqueue(
            aggregate_type="artifact",
            aggregate_id=artifact_id,
            event_type="artifact.created",
            payload={"artifact_id": artifact_id, "final_video": {"ready": True, "video_url": video_url}},
        )
        await outbox_repo.enqueue(
            aggregate_type="business_message",
            aggregate_id=state["run_id"],
            event_type="business.message",
            payload={"business_key": "final_video", "video_url": video_url},
        )

    logger.info("Final video artifact created: artifact_id=%s video_url=%s", artifact_id, video_url)

    return {
        "success": True,
        "artifact_id": artifact_id,
        "video_url": video_url,
        "cover_url": cover_url,
        "events": ["artifact.created", "business.message"],
    }


async def publish_artifacts(state: AgentFilmState) -> dict[str, Any]:
    """Publish final artifacts."""
    render_job: dict[str, Any] = state.get("render_job") or {}
    video_url = render_job.get("video_url")
    cover_url = render_job.get("cover_url")

    if not video_url:
        logger.warning("No video_url in render_job, cannot publish artifacts")
        return {"artifacts": state.get("artifacts", [])}

    result = await create_final_video_artifact(state=state, video_url=video_url, cover_url=cover_url)

    if result.get("success"):
        artifacts = state.get("artifacts", []) + [{
            "id": result["artifact_id"],
            "type": "final_video",
            "uri": result["video_url"],
            "status": "ready",
            "created_at": datetime.now(UTC).isoformat(),
        }]
        return {"artifacts": artifacts}

    logger.error("Failed to create final video artifact: %s", result.get("error"))
    errors = state.get("errors", []) + [{"node": "publish_artifacts", "error": result.get("error"), "fatal": False}]
    return {"artifacts": state.get("artifacts", []), "errors": errors}
