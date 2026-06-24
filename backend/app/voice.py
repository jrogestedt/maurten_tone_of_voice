from sqlmodel import Session, select

from .config import get_settings
from .models import Document, VoiceConfig

settings = get_settings()


# The default "Head of Copy" system prompt. Stored in the DB on first run and
# editable from the frontend, so this is only the seed value.
DEFAULT_VOICE_PROMPT = """You are the Maurten Head of Copy. Review, rewrite, and advise on brand copy with authority and precision.

Voice:

Economy of language. Fragmented sentence rhythm. Trust the reader to complete the thought. Subtle confidence — the product works; the copy doesn't need to prove it. Default to less. If a line can be cut, cut it. Speak to athletes as peers. Acknowledge the rituals, routines, and compulsions of endurance sport. Acknowledge the hard edges. Never smooth them.

Beckett rhythm throughout. Abstraction is permitted in campaign and athlete content — not in product and education copy.

Hydrogel Technology is central to all product communication. Ground it in what it actually does.

Red lines — never:

No clichés. No influencer theatrics. No content for the sake of filling a feed. No glorification. No exaggerated claims or soft science. No motivational preaching. No polishing of the hard edges of endurance life. No em dashes. No "this isn't X, it's Y" clause formatting. No emojis. No profanities.
"""


# Mirror of the maps in the original HTML tool. Kept server-side so every
# consumer of the API gets identical behaviour.
FORMAT_LABELS: dict[str, str] = {
    "general": "copy",
    "pdp": "PDP copy",
    "newsletter": "newsletter copy",
    "social": "social copy",
    "ad": "ad copy",
    "press": "press release",
    "retail": "retail guide",
    "editorial": "editorial copy",
}

INTENT_LABELS: dict[str, str] = {
    "product": "Product-led. Product mentions and Hydrogel Technology references are expected and appropriate.",
    "reactive": "Reactive moment caption. Responds to a specific athlete performance or event. No commercial objective. Do NOT flag absence of product mentions. Evaluate purely on voice, rhythm, and whether it captures the moment honestly.",
    "athlete": "Athlete story. Focus is the athlete and their experience. Product mention optional, not required.",
    "education": "Educational content. Clarity and accuracy matter most. Product grounding appropriate where relevant.",
    "brand": "Brand or awareness. No product push expected. Voice and tone are the primary criteria.",
}

REVIEW_CONTRACT = (
    "Return JSON only, no preamble, no markdown fences:\n"
    '{"score":<1-10>,"verdict":"<one blunt sentence>","notes":'
    '[{"flag":"red|amber|green","type":"<Red Line|Voice|Structure|Redundant|Hydrogel|Strong>",'
    '"quote":"<exact phrase max 12 words or empty string>","issue":"<direct editorial note>",'
    '"fix":"<suggestion or empty string>"}]}\n'
    "3-8 notes. Direct. No softening."
)


def fmt_label(key: str) -> str:
    return FORMAT_LABELS.get(key, FORMAT_LABELS["general"])


def intent_label(key: str) -> str:
    return INTENT_LABELS.get(key, INTENT_LABELS["product"])


def get_voice_prompt(session: Session) -> str:
    cfg = session.get(VoiceConfig, 1)
    return cfg.prompt if cfg else DEFAULT_VOICE_PROMPT


def build_system_prompt(session: Session) -> str:
    """Persona + active reference documents, capped at max_context_chars."""
    parts = [get_voice_prompt(session)]

    docs = session.exec(
        select(Document).where(Document.active == True)  # noqa: E712
    ).all()

    if docs:
        budget = settings.max_context_chars
        examples: list[str] = []
        for doc in docs:
            block = f"### {doc.title} ({doc.category})\n{doc.content}"
            if budget - len(block) < 0:
                break
            examples.append(block)
            budget -= len(block)
        if examples:
            parts.append(
                "Below are reference examples of the Maurten voice. Use them to "
                "calibrate tone, rhythm, and register. Do not quote them back.\n\n"
                + "\n\n".join(examples)
            )

    return "\n\n".join(parts)


def build_review_prompt(copy: str, fmt_key: str, intent_key: str) -> str:
    return (
        "MAURTEN VOICE REVIEW\n"
        f"Format: {fmt_label(fmt_key)}\n"
        f"Intent: {intent_label(intent_key)}\n\n"
        "Copy to review:\n\n"
        f"{copy}\n\n"
        "---\n"
        f"{REVIEW_CONTRACT}"
    )


def build_rewrite_prompt(copy: str, fmt_key: str, intent_key: str, issues: list[str]) -> str:
    issues_block = "\n".join(f"- {i}" for i in issues) if issues else "- Apply the Maurten voice throughout."
    return (
        "MAURTEN VOICE REWRITE\n"
        f"Format: {fmt_label(fmt_key)}\n"
        f"Intent: {intent_label(intent_key)}\n\n"
        "Original copy:\n\n"
        f"{copy}\n\n"
        "Issues to fix:\n"
        f"{issues_block}\n\n"
        "---\n"
        "Rewrite the copy so it scores at least 8/10 against the Maurten Voice. "
        "Apply the Maurten voice: economy of language, fragmented sentence rhythm, "
        "subtle confidence, no embellishment, athlete-peer register. Fix all red line "
        "violations and amber notes. Return the rewritten copy only — no explanation, "
        "no preamble, no score."
    )
