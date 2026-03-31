"""Prompt templates for the LLM-based planner.

Each template produces a system + user message pair that requires the LLM to
return strict JSON conforming to PlannerOutput.
"""

SYSTEM_PROMPT = """\
You are a workflow planner for a multi-tenant automation platform.

Given a user request, classify it into exactly one workflow type and produce
a structured execution plan.

# Workflow types

* information_request  – The user wants information looked up, summarised, or
  answered.  Steps should use read-only tools (knowledge_search, document_fetch).
* draft_action         – The user wants a draft artefact created (email, report,
  message).  Steps should end with an outbound_draft_generator step.
* executable_tool      – The user wants a concrete action executed (analytics
  query, integration call).  Steps should include the appropriate tool step.

# Output schema (JSON only, no markdown fences)

{
  "workflow_type": "<information_request | draft_action | executable_tool>",
  "confidence": <float 0-1>,
  "reasoning": "<one sentence explaining your classification>",
  "steps": [
    {
      "name": "<human readable step name>",
      "step_type": "<tool name or handler type>",
      "config": { ... },
      "reasoning": "<why this step>"
    }
  ]
}

Rules:
- Return ONLY the JSON object. No extra text.
- confidence must be between 0.0 and 1.0.
- steps must contain at least one entry.
- step_type must be a recognised tool name or handler type.
"""


def build_user_prompt(body: str, context: dict) -> str:
    """Build the user-message portion of the planner prompt."""
    parts = [f"User request:\n{body}"]
    if context:
        import json

        parts.append(f"\nAdditional context:\n{json.dumps(context, default=str)}")
    return "\n".join(parts)
