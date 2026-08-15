"""Deterministic RenderPromptContract -> A1111 request construction."""

from __future__ import annotations

import hashlib
import json
import re

from epos.application.visual.bridge import BuiltRenderRequest, RenderRequestSnapshot
from epos.application.visual.prompt import RenderPromptContract
from epos.infrastructure.rendering.a1111.models import (
    A1111RenderProfile,
    A1111RenderRequest,
)
from epos.infrastructure.rendering.a1111.settings import A1111AdapterSettings

_SAFE_LORA_ALIAS = re.compile(r"^[^<>:\r\n]+$")


class A1111RenderRequestBuilder:
    """Compile backend syntax only after the canonical prompt contract exists."""

    def __init__(
        self,
        *,
        settings: A1111AdapterSettings,
        profile: A1111RenderProfile,
    ) -> None:
        self._settings = settings.model_copy(deep=True)
        self._profile = profile.model_copy(deep=True)

    def build(
        self,
        contract: RenderPromptContract,
        *,
        seed: int,
    ) -> BuiltRenderRequest[A1111RenderRequest]:
        self._validate_dimensions(contract)
        positive = contract.positive_prompt.strip()
        if not positive:
            raise ValueError("A1111 positive prompt must not be empty")

        lora_tokens: list[str] = []
        for lora in contract.loras:
            alias = lora.alias.strip()
            if not alias or _SAFE_LORA_ALIAS.fullmatch(alias) is None:
                raise ValueError(f"unsafe A1111 LoRA alias: {lora.alias!r}")
            weight = self._profile.lora_weight_for(alias)
            lora_tokens.append(f"<lora:{alias}:{weight:g}>")
        if lora_tokens:
            positive = f"{positive}, {', '.join(lora_tokens)}"

        provisional = A1111RenderRequest(
            request_id="pending",
            prompt=positive,
            negative_prompt=contract.negative_prompt,
            seed=seed,
            width=contract.width,
            height=contract.height,
            sampler_name=contract.sampler,
            scheduler=contract.scheduler,
            steps=contract.steps,
            cfg_scale=contract.cfg,
            override_settings={
                "sd_model_checkpoint": self._settings.checkpoint,
            },
            override_settings_restore_afterwards=True,
        )
        payload = provisional.api_payload()
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        request_id = f"a1111-{hashlib.sha256(canonical.encode('utf-8')).hexdigest()[:24]}"
        request = provisional.model_copy(update={"request_id": request_id})
        return BuiltRenderRequest(
            request=request,
            snapshot=RenderRequestSnapshot(
                backend="a1111",
                request_id=request_id,
                payload=payload,
            ),
        )

    def _validate_dimensions(self, contract: RenderPromptContract) -> None:
        for label, dimension in (("width", contract.width), ("height", contract.height)):
            if dimension < self._profile.min_dimension:
                raise ValueError(
                    f"A1111 {label} below minimum {self._profile.min_dimension}: {dimension}"
                )
            if dimension > self._profile.max_dimension:
                raise ValueError(
                    f"A1111 {label} above maximum {self._profile.max_dimension}: {dimension}"
                )
            if dimension % self._profile.dimension_multiple != 0:
                raise ValueError(
                    f"A1111 {label} must be a multiple of "
                    f"{self._profile.dimension_multiple}: {dimension}"
                )
