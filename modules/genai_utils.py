import json
import os
import re

from dotenv import load_dotenv

load_dotenv()

MODEL = os.getenv("GEMINI_MODEL", "gemini-flash-latest")


def _mean(values):
    values = [v for v in values if v is not None]
    return round(sum(values) / len(values), 1) if values else None


def build_summary(session_row, intervals):
    """Turns a saved session into plain numbers. No names, no video, no faces."""
    eng = [r["engagement"] for r in intervals if r["engagement"] is not None]
    summary = {
        "duration_seconds": len(intervals) * 5,
        "students_total": session_row["total_students"],
        "students_present": session_row["present_count"],
        "students_absent": session_row["absent_count"],
        "avg_engagement": _mean(eng),
        "lowest_engagement": min(eng) if eng else None,
        "highest_engagement": max(eng) if eng else None,
        "engagement_every_5s": eng,
        "avg_speaking_pct": _mean([r["speaking_pct"] for r in intervals]),
        "avg_inactive_pct": _mean([r["inactive_pct"] for r in intervals]),
        "first_third_avg": None,
        "last_third_avg": None,
    }
    if len(eng) >= 3:
        third = len(eng) // 3
        summary["first_third_avg"] = _mean(eng[:third])
        summary["last_third_avg"] = _mean(eng[-third:])
    return summary


def local_suggestions(s):
    """Rule-based suggestions that work with no internet."""
    avg = s["avg_engagement"]
    if avg is None:
        return ["Not enough data was recorded. Run a longer session (at least 30 seconds) to get suggestions."]

    tips = []
    inactive = s["avg_inactive_pct"] or 0
    speaking = s["avg_speaking_pct"]

    if avg >= 80:
        tips.append("Engagement was high overall. Keep the current pacing and teaching style.")
    elif avg >= 50:
        tips.append("Engagement was moderate. Add a short question or quick poll every few minutes to hold attention.")
    else:
        tips.append("Engagement was low. Switch to an interactive activity such as pair discussion or a quick quiz.")

    first, last = s["first_third_avg"], s["last_third_avg"]
    if first is not None and last is not None and last < first - 15:
        tips.append("Attention dropped towards the end. Plan a short break or a recap activity about two thirds of the way through.")

    if inactive >= 40:
        tips.append("Students sat very still for long stretches. Ask for responses or a bit of movement to wake up the room.")
    elif avg < 60:
        tips.append("Many students were looking away from the front. Check that the board is visible and reduce distractions.")

    if speaking is not None and speaking < 20:
        tips.append("There was little interaction. Invite questions or open a short discussion.")
    elif speaking is not None and speaking > 80:
        tips.append("One voice dominated the session. Consider handing parts of it over to the students.")

    return tips


def ai_suggestions(summary):
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is missing in .env")

    from google import genai
    from google.genai import types

    client = genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(timeout=60000),
    )

    prompt = (
        "You are an assistant for a classroom teacher. Below are numeric engagement "
        "statistics from one class session. Engagement is scored 0 to 100 for each "
        "5-second interval. inactive_pct is the share of time students sat completely "
        "still, and speaking_pct is the share of time someone was speaking.\n\n"
        + json.dumps(summary)
        + "\n\nGive 3 to 5 short, practical teaching suggestions based only on these "
        "numbers. Write one suggestion per line, plain text, no headings, no markdown. "
        "They are suggestions for the teacher to consider, not instructions."
    )

    response = client.models.generate_content(model=MODEL, contents=prompt)
    text = (response.text or "").strip()

    items = []
    for line in text.splitlines():
        line = re.sub(r"^\s*(?:[-*\u2022]|\d+[.)])\s*", "", line).strip()
        if line:
            items.append(line)
    if not items:
        raise RuntimeError("Gemini returned an empty answer")
    return items[:5]


def get_suggestions(summary):
    if summary["avg_engagement"] is None:
        return {"source": "local", "model": None,
                "items": local_suggestions(summary),
                "note": "(No Gemini request was made because the session was too short.)"}
    try:
        return {"source": "gemini", "model": MODEL,
                "items": ai_suggestions(summary), "note": ""}
    except Exception as e:
        message = str(e).replace(os.getenv("GEMINI_API_KEY") or "<none>", "***")
        return {"source": "local", "model": None,
                "items": local_suggestions(summary),
                "note": "(Gemini unavailable: " + message[:120] + ")"}