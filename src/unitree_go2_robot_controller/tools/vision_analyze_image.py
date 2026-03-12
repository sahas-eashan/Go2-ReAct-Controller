from __future__ import annotations

import base64
import json
from pathlib import Path

from langchain_core.tools import tool
from openai import OpenAI
from pydantic import BaseModel, Field

from unitree_go2_robot_controller.config import AppConfig


class VisionAnalyzeImageInput(BaseModel):
    prompt: str = Field(description="Question or instruction for image analysis.")
    image_path: str = Field(
        default="",
        description="Optional absolute path to an image file. If omitted, use the last captured image path.",
    )


def create_vision_analyze_image_tool(config: AppConfig):
    client = OpenAI(api_key=config.openai_api_key)

    @tool("vision_analyze_image", args_schema=VisionAnalyzeImageInput)
    def vision_analyze_image(prompt: str, image_path: str = "") -> str:
        """Analyze an image using a single multimodal OpenAI call."""
        selected_path = Path(image_path.strip() or config.robot_captured_image_path)
        if not selected_path.is_file():
            return json.dumps(
                {
                    "status": "error",
                    "error_code": "image_not_found",
                    "reason": str(selected_path),
                },
                ensure_ascii=True,
            )

        image_bytes = selected_path.read_bytes()
        mime_type = "image/jpeg"
        if selected_path.suffix.lower() == ".png":
            mime_type = "image/png"

        try:
            response = client.responses.create(
                model=config.openai_vlm_model,
                input=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "input_text", "text": prompt},
                            {
                                "type": "input_image",
                                "image_url": f"data:{mime_type};base64,{base64.b64encode(image_bytes).decode('utf-8')}",
                            },
                        ],
                    }
                ],
                max_output_tokens=300,
            )
            answer = getattr(response, "output_text", "") or ""
        except Exception as exc:
            return json.dumps(
                {
                    "status": "error",
                    "error_code": "image_analysis_failed",
                    "reason": str(exc),
                },
                ensure_ascii=True,
            )

        return json.dumps(
            {
                "status": "ok",
                "image_path": str(selected_path),
                "analysis": answer.strip(),
            },
            ensure_ascii=True,
        )

    return vision_analyze_image
