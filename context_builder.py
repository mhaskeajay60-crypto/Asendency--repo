import re
from backend.database import (
    get_chapter, list_chapters, list_story_bible_entries, get_project_settings
)

def build_chapter_context(novel_id: str, chapter_id: str):
    """
    Constructs comprehensive layered context for AI analysis:
    1. Current chapter
    2. Relevant previous chapters
    3. Confirmed Canon (authoritative)
    4. Draft Canon (distinctly marked)
    5. Relevant characters
    6. Relevant locations
    7. Relevant world rules
    8. Relevant magic rules
    9. Relevant timeline events
    10. Author notes
    """
    current_chapter = get_chapter(chapter_id)
    if not current_chapter:
        return None
    
    # Retrieve all previous chapters in order
    all_chapters = list_chapters(novel_id, include_archived=False)
    current_idx = current_chapter["order_index"]
    prev_chapters = [c for c in all_chapters if c["order_index"] < current_idx]

    # Retrieve all Story Bible entries
    all_entries = list_story_bible_entries(novel_id)
    
    # Filter by canon status
    confirmed_canon = [e for e in all_entries if e["canon_status"] == "CONFIRMED CANON"]
    draft_entries = [e for e in all_entries if e["canon_status"] == "DRAFT"]
    discarded_entries = [e for e in all_entries if e["canon_status"] == "DISCARDED"]

    # Detect entity mentions in chapter text
    content_text = current_chapter["content"] or ""
    clean_text = re.sub(r'<[^>]+>', ' ', content_text).lower()

    relevant_characters = []
    relevant_locations = []
    relevant_world_rules = []
    relevant_powers = []
    relevant_factions = []
    relevant_timeline = []

    # Check pinned context ids
    settings = get_project_settings(novel_id)
    pinned_ids = set(settings.get("pinned_context_ids", []))

    for entry in confirmed_canon + draft_entries:
        name_lower = entry["name"].lower()
        is_pinned = entry["id"] in pinned_ids
        is_mentioned = name_lower in clean_text or (entry["category"] == "character" and entry["name"] == current_chapter.get("pov"))

        if is_pinned or is_mentioned:
            cat = entry["category"]
            if cat == "character":
                relevant_characters.append(entry)
            elif cat == "location":
                relevant_locations.append(entry)
            elif cat == "world":
                relevant_world_rules.append(entry)
            elif cat == "power":
                relevant_powers.append(entry)
            elif cat == "faction":
                relevant_factions.append(entry)
            elif cat == "timeline":
                relevant_timeline.append(entry)

    # Format structured context text for AI/Critic prompts
    prompt_context = []
    prompt_context.append(f"=== NOVEL CURRENT CHAPTER ===")
    prompt_context.append(f"Title: Chapter {current_chapter['chapter_number']}: {current_chapter['title']}")
    prompt_context.append(f"POV: {current_chapter['pov'] or 'Third-Person Limited (Not explicitly set)'}")
    prompt_context.append(f"Status: {current_chapter['status']}")
    prompt_context.append(f"Author Notes: {current_chapter['notes'] or 'None'}")
    prompt_context.append(f"\n--- CHAPTER TEXT ---\n{current_chapter['content']}\n--- END CHAPTER TEXT ---\n")

    if prev_chapters:
        prompt_context.append("=== PREVIOUS CHAPTERS SUMMARY ===")
        for pc in prev_chapters[-3:]: # Last 3 chapters for immediate continuity
            preview = re.sub(r'<[^>]+>', ' ', pc['content'])[:300] + "..." if pc['content'] else "Empty"
            prompt_context.append(f"Chapter {pc['chapter_number']}: {pc['title']} (POV: {pc['pov']}) - Excerpt: {preview}")

    prompt_context.append("\n=== CONFIRMED CANON (STRICT AUTHORITATIVE FACTS) ===")
    for c in confirmed_canon:
        attrs = ", ".join([f"{k}: {v}" for k, v in c.get("attributes", {}).items() if v])
        prompt_context.append(f"[{c['category'].upper()}] {c['name']} (Canon): {c['summary']}. Details: {attrs}")

    if draft_entries:
        prompt_context.append("\n=== DRAFT STORY BIBLE ENTRIES (PROPOSALS, NOT ESTABLISHED FACTS) ===")
        for d in draft_entries:
            attrs = ", ".join([f"{k}: {v}" for k, v in d.get("attributes", {}).items() if v])
            prompt_context.append(f"[{d['category'].upper()}] {d['name']} (Draft): {d['summary']}. Details: {attrs}")

    if discarded_entries:
        prompt_context.append("\n=== DISCARDED ENTRIES (DO NOT REINTRODUCE) ===")
        for disc in discarded_entries:
            prompt_context.append(f"[{disc['category'].upper()}] {disc['name']} (DISCARDED - FORBIDDEN TO RE-ESTABLISH): {disc['summary']}")

    return {
        "current_chapter": current_chapter,
        "previous_chapters": prev_chapters,
        "relevant_characters": relevant_characters,
        "relevant_locations": relevant_locations,
        "relevant_world_rules": relevant_world_rules,
        "relevant_powers": relevant_powers,
        "relevant_factions": relevant_factions,
        "relevant_timeline": relevant_timeline,
        "confirmed_canon": confirmed_canon,
        "draft_entries": draft_entries,
        "discarded_entries": discarded_entries,
        "prompt_context_string": "\n".join(prompt_context)
    }
