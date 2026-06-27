import os
import json
from pathlib import Path
import anthropic

_client = None

CONTEXT_PATH = Path(__file__).parent / "data" / "user_context.md"


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic()
    return _client


def _parse_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.rsplit("```", 1)[0].strip()
    return json.loads(text)


def load_user_context() -> str:
    try:
        if CONTEXT_PATH.exists():
            return CONTEXT_PATH.read_text(encoding="utf-8").strip()
    except Exception:
        pass
    return ""


def update_user_context(session_summary: dict, goal_info: list[dict]):
    if not os.getenv("ANTHROPIC_API_KEY"):
        return

    existing = load_user_context()
    goal_names = [g["name"] for g in goal_info] if goal_info else []

    parts = []
    if session_summary.get("summary"):
        parts.append(f"Summary: {session_summary['summary']}")
    if session_summary.get("main_ideas"):
        parts.append("Main ideas: " + "; ".join(session_summary["main_ideas"]))

    try:
        client = _get_client()
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2048,
            messages=[{
                "role": "user",
                "content": (
                    "You maintain a persistent user context file for a screen monitoring agent. "
                    "Update it with learnings from this session.\n\n"
                    f"Goals tracked: {goal_names}\n\n"
                    f"Session summary:\n{chr(10).join(parts)}\n\n"
                    f"Existing context:\n{existing or '(none yet)'}\n\n"
                    "Produce an updated context file capturing:\n"
                    "- Who the user is (role, skills, goals inferred from their activity)\n"
                    "- What they are currently working on or researching\n"
                    "- Patterns and preferences observed\n"
                    "- Key facts useful for future summarization\n\n"
                    "Keep it under 500 words. Plain text, no JSON, no headers."
                ),
            }],
        )
        CONTEXT_PATH.parent.mkdir(exist_ok=True)
        CONTEXT_PATH.write_text(response.content[0].text, encoding="utf-8")
        print("[context] User context updated.")
    except Exception as e:
        print(f"[context] Failed to update user context: {e}")


def summarize(raw_text: str, title: str, goal_info: list[dict] | None = None) -> dict:
    if not os.getenv("ANTHROPIC_API_KEY"):
        return {"relevant": True, "summary": "", "links": []}

    goal_context = ""
    if goal_info:
        lines = [f'- "{g["name"]}": keywords {g["keywords"]}' for g in goal_info]
        goal_context = "Tracked goals:\n" + "\n".join(lines) + "\n\n"

    user_context = load_user_context()
    context_section = f"User context:\n{user_context}\n\n" if user_context else ""

    try:
        client = _get_client()
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=8192,
            messages=[{
                "role": "user",
                "content": (
                    f"{context_section}"
                    f"Window(s): {title}\n\n"
                    f"{goal_context}"
                    f"Screen text (OCR):\n{raw_text}\n\n"
                    "First decide: is this content genuinely about the tracked goal topic? "
                    "If keywords only appeared coincidentally (toolbar, unrelated UI, background text), "
                    "set relevant=false.\n\n"
                    "If relevant, produce a structured summary. "
                    "IMPORTANT: only include information directly related to the goal topic. "
                    "Completely ignore any off-topic content in the OCR "
                    "(unrelated chats, personal notes on other subjects, other tasks). "
                    "Respond with JSON only, no markdown:\n"
                    "{\n"
                    '  "relevant": true,\n'
                    '  "title": "short descriptive title for this session (5-8 words, no punctuation)",\n'
                    '  "summary": "3-5 sentences about what the user was doing related to the goal",\n'
                    '  "main_ideas": ["every key concept or fact related to the goal topic"],\n'
                    '  "important_notes": ["critical details or warnings related to the goal"],\n'
                    '  "recommendations": ["actionable suggestions based on the goal-related content"],\n'
                    '  "links": ["every URL or resource reference related to the goal topic"]\n'
                    "}\n\n"
                    'If not relevant, respond with just: {"relevant": false}'
                ),
            }],
        )
        return _parse_json(response.content[0].text)
    except json.JSONDecodeError as e:
        print(f"[summarize] JSON parse error: {e}")
        print(f"[summarize] Raw response: {response.content[0].text[:300]}")
        return {"relevant": True, "summary": "", "links": []}
    except Exception as e:
        print(f"[summarize] Error: {e}")
        return {"relevant": True, "summary": "", "links": []}


def merge_summaries(summaries: list[dict], title: str) -> dict:
    if not os.getenv("ANTHROPIC_API_KEY"):
        return {"summary": "", "links": []}

    user_context = load_user_context()
    context_section = f"User context:\n{user_context}\n\n" if user_context else ""

    parts = []
    for i, s in enumerate(summaries, 1):
        lines = [f"[Part {i}]"]
        if s.get("summary"):
            lines.append(f"Summary: {s['summary']}")
        if s.get("main_ideas"):
            lines.append("Main ideas: " + "; ".join(s["main_ideas"]))
        if s.get("important_notes"):
            lines.append("Notes: " + "; ".join(s["important_notes"]))
        if s.get("recommendations"):
            lines.append("Recommendations: " + "; ".join(s["recommendations"]))
        if s.get("links"):
            lines.append("Links: " + ", ".join(s["links"]))
        parts.append("\n".join(lines))

    try:
        client = _get_client()
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=8192,
            messages=[{
                "role": "user",
                "content": (
                    f"{context_section}"
                    f"Session: {title}\n\n"
                    "Below are summaries from different parts of a work/browsing session. "
                    "Consolidate them into one final comprehensive conclusion. "
                    "Only include information relevant to the session topic — "
                    "exclude anything off-topic that may have slipped through.\n\n"
                    + "\n\n".join(parts) +
                    "\n\nRespond with JSON only, no markdown:\n"
                    "{\n"
                    '  "title": "short descriptive title for this session (5-8 words, no punctuation)",\n'
                    '  "summary": "3-5 sentences describing the overall session",\n'
                    '  "main_ideas": ["all consolidated key concepts and facts"],\n'
                    '  "important_notes": ["all critical details worth remembering"],\n'
                    '  "recommendations": ["all actionable suggestions"],\n'
                    '  "links": ["all relevant URLs found across the session"]\n'
                    "}"
                ),
            }],
        )
        return _parse_json(response.content[0].text)
    except json.JSONDecodeError as e:
        print(f"[summarize] Merge JSON parse error: {e}")
        return {"summary": "", "links": []}
    except Exception as e:
        print(f"[summarize] Merge error: {e}")
        return {"summary": "", "links": []}
