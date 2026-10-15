"""Graph nodes package.

WP-08 and WP-09 will populate this package with real node implementations.
WP-06 provides the infrastructure and stub nodes in builder.py.
"""

from app.graph.nodes.generation import prepare_generation_node as prepare_generation
from app.graph.nodes.generation import (
    request_generation_approval_node as request_generation_approval,
)
from app.graph.nodes.media import (
    collect_materials,
)
from app.graph.nodes.media import (
    match_digital_human_node as match_digital_human,
)
from app.graph.nodes.media import (
    publish_artifacts_node as publish_artifacts,
)
from app.graph.nodes.media import (
    render_video_node as render_video,
)
from app.graph.nodes.media import (
    validate_delivery_node as validate_delivery,
)
from app.graph.nodes.normalize import normalize_input
from app.graph.nodes.product_context import collect_product_context, request_product_context_review
from app.graph.nodes.script import (
    generate_creative_strategy,
    generate_script,
    request_storyboard_review,
)

__all__ = [
    "normalize_input",
    "collect_product_context",
    "request_product_context_review",
    "generate_creative_strategy",
    "generate_script",
    "request_storyboard_review",
    "prepare_generation",
    "request_generation_approval",
    "collect_materials",
    "match_digital_human",
    "render_video",
    "validate_delivery",
    "publish_artifacts",
]
