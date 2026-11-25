# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Strategic model routing selecting Flash vs. Pro tiers by task complexity."""

from __future__ import annotations

import os
from enum import StrEnum

from google.adk.models import Gemini
from google.genai import types

# Preserve the scaffolded default model for fast tool/retrieval tiers while
# routing complex planning and coordination to the reasoning tier.
DEFAULT_FAST_MODEL = os.environ.get("FAST_MODEL", "gemini-3.8-flash")
DEFAULT_PLANNING_MODEL = os.environ.get("PLANNING_MODEL", "gemini-3.8-flash")


class TaskTier(StrEnum):
    """Task complexity categories governing Gemini model selection."""

    FAST_RETRIEVAL = "fast_retrieval"
    SUMMARIZATION = "summarization"
    BOOKING_FORMAT = "booking_format"
    PLANNING = "planning"
    COORDINATION = "coordination"


_TIER_TO_MODEL_NAME: dict[TaskTier, str] = {
    TaskTier.FAST_RETRIEVAL: DEFAULT_FAST_MODEL,
    TaskTier.SUMMARIZATION: DEFAULT_FAST_MODEL,
    TaskTier.BOOKING_FORMAT: DEFAULT_FAST_MODEL,
    TaskTier.PLANNING: DEFAULT_PLANNING_MODEL,
    TaskTier.COORDINATION: DEFAULT_PLANNING_MODEL,
}


class ModelRouter:
    """Routes ADK agents and summarizers to cost/latency-appropriate Gemini models."""

    @staticmethod
    def resolve_model_name(tier: TaskTier) -> str:
        """Return the configured model identifier for a given TaskTier."""
        if tier in (TaskTier.PLANNING, TaskTier.COORDINATION):
            return os.environ.get("PLANNING_MODEL", DEFAULT_PLANNING_MODEL)
        return os.environ.get("FAST_MODEL", DEFAULT_FAST_MODEL)

    @classmethod
    def select_model(
        cls,
        tier: TaskTier,
        *,
        retry_attempts: int = 3,
    ) -> Gemini:
        """Construct an ADK Gemini model wrapper with retry policy for a TaskTier."""
        model_name = cls.resolve_model_name(tier)
        return Gemini(
            model=model_name,
            retry_options=types.HttpRetryOptions(attempts=retry_attempts),
        )
