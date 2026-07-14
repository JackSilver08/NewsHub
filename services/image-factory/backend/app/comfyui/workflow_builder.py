"""Load a ComfyUI API-format workflow template and inject per-item parameters.

The template is expected to be a ComfyUI "API format" JSON (exported via
"Save (API Format)"). We locate well-known node class types and patch their
inputs. Node ids differ per workflow, so we search by `class_type`.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

from app.comfyui.generator import GenerationRequest
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class WorkflowBuilder:
    def __init__(self, workflow_file: str | None = None) -> None:
        name = workflow_file or settings.comfyui_workflow
        self.path: Path = settings.workflows_dir / name
        self._template: dict | None = None

    def _load(self) -> dict:
        if self._template is None:
            if not self.path.exists():
                raise FileNotFoundError(f"Workflow template not found: {self.path}")
            self._template = json.loads(self.path.read_text(encoding="utf-8"))
        return self._template

    def build(self, req: GenerationRequest) -> dict:
        graph = copy.deepcopy(self._load())

        # Distilled model workflows have model-specific sampler settings.  Keep
        # those template values instead of replacing them with the global SD
        # defaults (for example Z-Image uses res_multistep/simple).
        model_files = [
            str((node.get("inputs") or {}).get("unet_name", "")).lower()
            for node in graph.values()
            if isinstance(node, dict) and node.get("class_type") == "UNETLoader"
        ]
        keep_sampler_defaults = any("z_image" in name for name in model_files)

        positive_set = False
        for node in graph.values():
            if not isinstance(node, dict):
                continue
            class_type = node.get("class_type")
            inputs = node.get("inputs", {})

            if class_type == "CLIPTextEncode":
                # The first CLIPTextEncode is treated as positive, others negative.
                # Templates should use _meta.title "Positive"/"Negative" to be explicit.
                title = (node.get("_meta") or {}).get("title", "").lower()
                if "negative" in title:
                    inputs["text"] = req.negative_prompt
                elif "positive" in title or not positive_set:
                    inputs["text"] = req.prompt
                    positive_set = True
                else:
                    inputs["text"] = req.negative_prompt

            elif class_type == "KSampler":
                inputs["seed"] = req.seed
                inputs["steps"] = req.steps
                if not keep_sampler_defaults:
                    inputs["cfg"] = req.cfg
                    inputs["sampler_name"] = req.sampler
                    inputs["scheduler"] = req.scheduler

            elif class_type in ("EmptyLatentImage", "EmptySD3LatentImage"):
                inputs["width"] = req.width
                inputs["height"] = req.height
                inputs["batch_size"] = 1

        return graph
