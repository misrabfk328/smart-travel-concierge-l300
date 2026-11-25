# DESIGN_SPEC.md — VoyagerAI: Smart Travel & Budget Concierge

## 1. Overview & Problem Statement

Planning multi-day trips within a strict budget requires coordinating flight and lodging searches, destination travel advisories, deterministic cost math, cross-session traveler preferences, and confirmation-gated booking actions. **VoyagerAI** (`smart-travel-concierge-l300`) is a multi-agent **Smart Travel & Budget Concierge** built on **Google Agent Development Kit (ADK-Python 2.x)** that persists traveler preferences across sessions, runs parallel destination research workflows, optimizes itineraries under a hard budget cap, redacts PII before logging or persistence, and enforces human-in-the-loop (HITL) approval prior to any financial booking.

## 2. Multi-Agent Architecture & Strategic Model Routing

- **Coordinator (`smart_travel_concierge`)**: Top-level `LlmAgent` using the planning-tier Gemini model (`PLANNING_MODEL`, default `gemini-2.5-pro`) to orchestrate sub-agents and workflows.
- **Preference Memory Sub-Agent (`preference_memory_agent`)**: `LlmAgent` (`mode="task"`, `FAST_MODEL`, default `gemini-3.8-flash`) managing persistent traveler preferences with `PreloadMemoryTool`, `retrieve_traveler_preferences`, and `save_traveler_preference`.
- **Parallel Destination Planning Workflow (`destination_planning_pipeline`)**: ADK `Workflow` exposing `TripResearchRequest` as `input_schema` and executing:
  1. Concurrent fan-out to `flight_hotel_researcher` (`FAST_MODEL`) and `advisory_weather_researcher` (`FAST_MODEL`).
  2. `JoinNode` fan-in barrier (`merge_destination_research`) combining both branches.
  3. `itinerary_budget_planner` (`PLANNING_MODEL`) synthesizing an itemized plan validated with `calculate_trip_budget_breakdown`.
- **Booking Execution Sub-Agent (`booking_execution_agent`)**: `LlmAgent` (`mode="task"`, `FAST_MODEL`) executing `confirm_and_book_itinerary` behind ADK's `require_confirmation` HITL gate and `ResumabilityConfig(is_resumable=True)`.

## 3. Tools & Strict Schemas

All tools live in `app/tools/`, use descriptive verb-noun names, comprehensive Google-style docstrings, strict Pydantic v2 JSON schemas (`extra="forbid"`), and structured guided recovery error payloads (`GuidedErrorResponse`):

- `search_verified_flights_and_hotels`
- `check_destination_travel_advisories`
- `calculate_trip_budget_breakdown`
- `retrieve_traveler_preferences`
- `save_traveler_preference`
- `confirm_and_book_itinerary`

## 4. Context, Memory, Guardrails & Observability

- **Context & Memory**: `<CONSTITUTION>` prompts (`app/prompts.py`), ADK `EventsCompactionConfig` + `ContextCacheConfig` + `ContextFilterPlugin`, persistent `DatabaseSessionService` (SQLite local / Cloud SQL prod) + `SqliteMemoryService` / `VertexAiMemoryBankService`, and non-blocking `asyncio.create_task()` background memory consolidation.
- **Guardrails & HITL**: `TravelSafetyAndPolicyPlugin(BasePlugin)` (prompt-injection & policy checks + optional Model Armor API + output budget/PII guardrails), `ReflectAndRetryToolPlugin`, and `FunctionTool(..., require_confirmation=requires_booking_confirmation)`.
- **Observability & Security**: `python-json-logger` structured JSON logs, paired `TOOL_INTENT` / `TOOL_OUTCOME` audit events, OpenTelemetry distributed tracing (`AutoTracingPlugin` + `CloudTraceSpanExporter`), active `PiiRedactor` (regex + optional Google Cloud DLP), and `SecretManagerConfig` (`google-cloud-secret-manager` with env fallback).

## 5. Infrastructure, Testing & Evaluation

- **IaC & CI/CD**: Terraform configs under `deployment/terraform/single-project/`, `Dockerfile`, and `.github/workflows/ci.yml`.
- **Testing & Eval**: Deterministic `pytest` unit + integration suite (`FakeLlm` + `InMemoryRunner`) and golden evaluation datasets under `tests/eval/`.
