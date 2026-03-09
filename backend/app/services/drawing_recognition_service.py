"""Drawing recognition service — uses AI vision to identify structural components.

Accepts an uploaded drawing image, sends it to the configured AI provider for
analysis, and returns structured component data suitable for BOQ generation.
"""

from __future__ import annotations

import base64
import json
import logging
from dataclasses import dataclass, field
from typing import Any

from app.ai.providers import AIProviderError, get_ai_provider

logger = logging.getLogger(__name__)


@dataclass
class RecognizedComponent:
    id: str
    type: str  # 构件类型: 框架柱, 框架梁, 剪力墙, etc.
    count: int
    spec: str  # 主规格: 600×600, T=250, etc.
    confidence: float  # 0-100
    material: str = ""  # 材料: C30混凝土, HRB400钢筋
    unit: str = ""  # 计量单位
    quantity_estimate: float = 0.0  # 初估工程量


@dataclass
class RecognitionResult:
    components: list[RecognizedComponent] = field(default_factory=list)
    summary: str = ""
    drawing_type: str = ""  # 结构平面图, 建筑平面图, etc.
    error: str | None = None


_RECOGNITION_PROMPT = """\
你是一位专业的建筑工程图纸AI识别助手。请分析上传的工程图纸图片，识别其中的结构构件。

请严格按以下JSON格式输出（不要包含其他文字），每个构件包含:
{
  "drawing_type": "图纸类型(如:结构平面图/建筑平面图/钢筋图等)",
  "summary": "简要描述图纸内容和识别结论",
  "components": [
    {
      "id": "唯一编号如C-1",
      "type": "构件类型(框架柱/框架梁/剪力墙/楼板/基础/连梁等)",
      "count": 数量(整数),
      "spec": "主规格(如600×600, 300×600, T=250等)",
      "confidence": 置信度(0-100的浮点数),
      "material": "材料(如C30混凝土等，不确定则留空)",
      "unit": "计量单位(m³/m²/m/t等)",
      "quantity_estimate": 初估总工程量(浮点数，无法估计则为0)
    }
  ]
}

识别要点:
1. 柱: 矩形实心或打叉的方块
2. 梁: 连接柱之间的线条，标注截面尺寸
3. 墙: 填充图案的厚线条
4. 板: 大面积填充区域
5. 基础: 虚线矩形或梯形
6. 注意轴线编号、尺寸标注和构件标签

如果图片不是工程图纸或无法识别，返回:
{"drawing_type": "unknown", "summary": "无法识别", "components": []}
"""


def recognize_drawing(
    *,
    image_bytes: bytes,
    content_type: str = "image/png",
    project_context: str = "",
) -> RecognitionResult:
    """Recognize structural components from a drawing image.

    Args:
        image_bytes: Raw image file bytes
        content_type: MIME type of the image
        project_context: Optional project context for better recognition

    Returns:
        RecognitionResult with extracted components
    """
    provider = get_ai_provider()
    if not provider.is_enabled() or not provider.is_configured():
        return RecognitionResult(error="ai_not_configured")

    # Encode image to base64 for vision API
    b64_image = base64.b64encode(image_bytes).decode("utf-8")

    user_content: list[dict[str, Any]] = [
        {
            "type": "image_url",
            "image_url": {
                "url": f"data:{content_type};base64,{b64_image}",
            },
        },
        {
            "type": "text",
            "text": "请识别这张工程图纸中的结构构件。" + (
                f"\n项目背景: {project_context}" if project_context else ""
            ),
        },
    ]

    try:
        response_text = provider.generate_text(
            task="drawing_recognition",
            messages=[
                {"role": "system", "content": _RECOGNITION_PROMPT},
                {"role": "user", "content": user_content},
            ],
        )
    except AIProviderError as exc:
        logger.error("Drawing recognition AI call failed: %s", exc)
        return RecognitionResult(error=f"AI调用失败: {exc}")

    # Parse the JSON response
    try:
        # Strip markdown code fences if present
        text = response_text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1]  # remove first line
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()

        data = json.loads(text)
    except (json.JSONDecodeError, IndexError) as exc:
        logger.error("Failed to parse recognition response: %s", exc)
        return RecognitionResult(
            summary=response_text[:500],
            error="AI返回格式异常，无法解析",
        )

    components = []
    for item in data.get("components", []):
        try:
            components.append(RecognizedComponent(
                id=str(item.get("id", "")),
                type=str(item.get("type", "")),
                count=int(item.get("count", 0)),
                spec=str(item.get("spec", "")),
                confidence=float(item.get("confidence", 0)),
                material=str(item.get("material", "")),
                unit=str(item.get("unit", "")),
                quantity_estimate=float(item.get("quantity_estimate", 0)),
            ))
        except (ValueError, TypeError):
            continue

    return RecognitionResult(
        components=components,
        summary=data.get("summary", ""),
        drawing_type=data.get("drawing_type", ""),
    )


def components_to_boq_suggestions(
    components: list[RecognizedComponent],
) -> list[dict[str, Any]]:
    """Convert recognized components into BOQ item suggestions.

    Maps structural component types to GB50500 standard codes where possible.
    """
    _TYPE_TO_CODE = {
        "框架柱": ("010402001", "现浇混凝土柱", "m³"),
        "框架梁": ("010403001", "现浇混凝土梁", "m³"),
        "剪力墙": ("010404001", "现浇混凝土墙", "m³"),
        "楼板": ("010405001", "现浇混凝土板", "m³"),
        "基础": ("010401001", "现浇混凝土基础", "m³"),
        "连梁": ("010403001", "现浇混凝土梁", "m³"),
        "楼梯": ("010406001", "现浇混凝土楼梯", "m³"),
        "钢筋": ("010407001", "钢筋工程", "t"),
        "钢柱": ("010501001", "钢柱", "t"),
    }

    suggestions = []
    for comp in components:
        mapping = _TYPE_TO_CODE.get(comp.type)
        code = mapping[0] if mapping else ""
        standard_name = mapping[1] if mapping else comp.type
        unit = mapping[2] if mapping else comp.unit

        suggestions.append({
            "source_component_id": comp.id,
            "suggested_code": code,
            "suggested_name": f"{standard_name} {comp.spec}",
            "suggested_unit": unit,
            "suggested_quantity": comp.quantity_estimate,
            "characteristics": f"构件类型: {comp.type}, 规格: {comp.spec}",
            "confidence": comp.confidence,
            "material": comp.material,
            "component_count": comp.count,
        })

    return suggestions
