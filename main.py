import os
import json
import difflib
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Response
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

from backend.database import (
    init_db, get_or_create_default_novel, list_novels, create_novel,
    list_chapters, get_chapter, create_chapter, update_chapter, delete_chapter,
    reorder_chapters, duplicate_chapter, toggle_archive_chapter, split_chapter, merge_chapters,
    list_revisions, get_revision, restore_revision, diff_revisions,
    list_story_bible_entries, get_story_bible_entry, create_story_bible_entry,
    update_story_bible_entry, delete_story_bible_entry, set_canon_status, get_canon_history,
    list_ai_suggestions, update_ai_suggestion_status, global_search,
    get_project_settings, update_project_settings
)
from backend.context_builder import build_chapter_context
from backend.ai_engine import (
    run_continuity_check, run_character_check, run_world_rule_check,
    run_writing_critic, run_pacing_critic, run_pov_check, run_dialogue_check,
    run_writing_assistant, get_ai_client
)
from backend.exporters import (
    export_manuscript_text, export_manuscript_docx, export_full_project_json, import_chapter_file
)

init_db()

app = FastAPI(title="Ascendancy Writer API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

FRONTEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../frontend"))

# --- Pydantic Schemas ---
class NovelCreateRequest(BaseModel):
    title: str
    description: Optional[str] = ""
    target_words: Optional[int] = 80000
    genre: Optional[str] = "Epic Fantasy"

class ChapterCreateRequest(BaseModel):
    title: str
    content: Optional[str] = ""
    pov: Optional[str] = ""
    part_name: Optional[str] = ""
    status: Optional[str] = "Draft"
    notes: Optional[str] = ""

class ChapterUpdateRequest(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    pov: Optional[str] = None
    part_name: Optional[str] = None
    status: Optional[str] = None
    notes: Optional[str] = None
    create_revision: Optional[bool] = False
    revision_summary: Optional[str] = "Manual update"

class ChapterReorderRequest(BaseModel):
    ordered_ids: List[str]

class ChapterSplitRequest(BaseModel):
    split_at_text: str
    new_chapter_title: Optional[str] = ""

class ChapterMergeRequest(BaseModel):
    source_chapter_id: str

class StoryBibleCreateRequest(BaseModel):
    category: str
    name: str
    canon_status: Optional[str] = "DRAFT"
    summary: Optional[str] = ""
    attributes: Optional[Dict[str, Any]] = None
    notes: Optional[str] = ""

class StoryBibleUpdateRequest(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    canon_status: Optional[str] = None
    summary: Optional[str] = None
    attributes: Optional[Dict[str, Any]] = None
    notes: Optional[str] = None
    reason: Optional[str] = "Updated details"

class CanonStatusUpdateRequest(BaseModel):
    entry_id: str
    canon_status: str
    reason: Optional[str] = ""

class AIAssistantRequest(BaseModel):
    action: str # continue_scene, brainstorm, rewrite_selection, improve_sentence, expand_description, reduce_description, improve_dialogue, change_tone, summarize_scene
    selected_text: Optional[str] = ""
    instruction: Optional[str] = ""

class AISuggestionActionRequest(BaseModel):
    action: str # accept, reject, ignore, canon_change
    new_canon_status: Optional[str] = "DRAFT" # If canon_change

class SettingsUpdateRequest(BaseModel):
    theme: Optional[str] = None
    ai_provider: Optional[str] = None
    gemini_api_key: Optional[str] = None
    model_name: Optional[str] = None
    autosave_seconds: Optional[int] = None
    editor_font_family: Optional[str] = None
    editor_font_size: Optional[int] = None
    pinned_context_ids: Optional[List[str]] = None

# --- Novel Routes ---
@app.get("/api/novels/current")
def api_get_current_novel():
    novel = get_or_create_default_novel()
    return novel

@app.get("/api/novels")
def api_list_novels():
    return list_novels()

@app.post("/api/novels")
def api_create_novel(req: NovelCreateRequest):
    return create_novel(req.title, req.description, req.target_words, req.genre)

# --- Chapter Routes ---
@app.get("/api/chapters")
def api_list_chapters(novel_id: Optional[str] = None, include_archived: bool = False):
    nid = novel_id or get_or_create_default_novel()["id"]
    return list_chapters(nid, include_archived=include_archived)

@app.get("/api/chapters/{chapter_id}")
def api_get_chapter(chapter_id: str):
    ch = get_chapter(chapter_id)
    if not ch:
        raise HTTPException(status_code=404, detail="Chapter not found")
    return ch

@app.post("/api/chapters")
def api_create_chapter(req: ChapterCreateRequest, novel_id: Optional[str] = None):
    nid = novel_id or get_or_create_default_novel()["id"]
    return create_chapter(nid, req.title, req.content or "", req.pov or "", req.part_name or "", req.status or "Draft", req.notes or "")

@app.put("/api/chapters/{chapter_id}")
def api_update_chapter(chapter_id: str, req: ChapterUpdateRequest):
    ch = update_chapter(
        chapter_id,
        title=req.title,
        content=req.content,
        pov=req.pov,
        part_name=req.part_name,
        status=req.status,
        notes=req.notes,
        create_revision=req.create_revision,
        revision_summary=req.revision_summary
    )
    if not ch:
        raise HTTPException(status_code=404, detail="Chapter not found")
    return ch

@app.delete("/api/chapters/{chapter_id}")
def api_delete_chapter(chapter_id: str):
    res = delete_chapter(chapter_id)
    if not res:
        raise HTTPException(status_code=404, detail="Chapter not found")
    return {"status": "deleted"}

@app.post("/api/chapters/reorder")
def api_reorder_chapters(req: ChapterReorderRequest, novel_id: Optional[str] = None):
    nid = novel_id or get_or_create_default_novel()["id"]
    reorder_chapters(nid, req.ordered_ids)
    return {"status": "reordered"}

@app.post("/api/chapters/{chapter_id}/duplicate")
def api_duplicate_chapter(chapter_id: str):
    ch = duplicate_chapter(chapter_id)
    if not ch:
        raise HTTPException(status_code=404, detail="Chapter not found")
    return ch

@app.post("/api/chapters/{chapter_id}/archive")
def api_toggle_archive(chapter_id: str, archive: bool = True):
    res = toggle_archive_chapter(chapter_id, archive)
    return {"status": "archived" if archive else "unarchived"}

@app.post("/api/chapters/{chapter_id}/split")
def api_split_chapter(chapter_id: str, req: ChapterSplitRequest):
    new_ch = split_chapter(chapter_id, req.split_at_text, req.new_chapter_title)
    if not new_ch:
        raise HTTPException(status_code=400, detail="Failed to split chapter")
    return new_ch

@app.post("/api/chapters/{chapter_id}/merge")
def api_merge_chapter(chapter_id: str, req: ChapterMergeRequest):
    merged = merge_chapters(req.source_chapter_id, chapter_id)
    if not merged:
        raise HTTPException(status_code=400, detail="Failed to merge chapters")
    return merged

# --- Revisions & History ---
@app.get("/api/chapters/{chapter_id}/revisions")
def api_list_revisions(chapter_id: str):
    return list_revisions(chapter_id)

@app.get("/api/revisions/{revision_id}")
def api_get_revision(revision_id: str):
    rev = get_revision(revision_id)
    if not rev:
        raise HTTPException(status_code=404, detail="Revision not found")
    return rev

@app.post("/api/chapters/{chapter_id}/revisions/{revision_id}/restore")
def api_restore_revision(chapter_id: str, revision_id: str):
    restored = restore_revision(chapter_id, revision_id)
    if not restored:
        raise HTTPException(status_code=404, detail="Failed to restore revision")
    return restored

@app.post("/api/revisions/diff")
def api_diff_revisions(rev_a_id: str, rev_b_id: str):
    rev_a = get_revision(rev_a_id)
    rev_b = get_revision(rev_b_id)
    if not rev_a or not rev_b:
        raise HTTPException(status_code=404, detail="One or both revisions not found")
    diff_data = diff_revisions(rev_a["content"], rev_b["content"])
    return {
        "rev_a": rev_a,
        "rev_b": rev_b,
        "diff": diff_data
    }

# --- Story Bible Routes ---
@app.get("/api/story-bible")
def api_list_story_bible(novel_id: Optional[str] = None, category: Optional[str] = None, status: Optional[str] = None):
    nid = novel_id or get_or_create_default_novel()["id"]
    return list_story_bible_entries(nid, category, status)

@app.get("/api/story-bible/{entry_id}")
def api_get_story_bible_entry(entry_id: str):
    entry = get_story_bible_entry(entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    return entry

@app.post("/api/story-bible")
def api_create_story_bible_entry(req: StoryBibleCreateRequest, novel_id: Optional[str] = None):
    nid = novel_id or get_or_create_default_novel()["id"]
    return create_story_bible_entry(
        novel_id=nid,
        category=req.category,
        name=req.name,
        canon_status=req.canon_status or "DRAFT",
        summary=req.summary or "",
        attributes=req.attributes or {},
        notes=req.notes or ""
    )

@app.put("/api/story-bible/{entry_id}")
def api_update_story_bible_entry(entry_id: str, req: StoryBibleUpdateRequest):
    updated = update_story_bible_entry(
        entry_id=entry_id,
        name=req.name,
        category=req.category,
        canon_status=req.canon_status,
        summary=req.summary,
        attributes=req.attributes,
        notes=req.notes,
        reason=req.reason or "Updated entry"
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Entry not found")
    return updated

@app.delete("/api/story-bible/{entry_id}")
def api_delete_story_bible_entry(entry_id: str):
    res = delete_story_bible_entry(entry_id)
    return {"status": "deleted"}

# --- Canon Control ---
@app.post("/api/canon/status")
def api_set_canon_status(req: CanonStatusUpdateRequest):
    updated = set_canon_status(req.entry_id, req.canon_status, req.reason)
    if not updated:
        raise HTTPException(status_code=404, detail="Entry not found")
    return updated

@app.get("/api/canon/history")
def api_get_canon_history(novel_id: Optional[str] = None):
    nid = novel_id or get_or_create_default_novel()["id"]
    return get_canon_history(nid)

# --- AI Critics & Studio ---
@app.post("/api/ai/critics/{critic_name}/{chapter_id}")
def api_run_critic(critic_name: str, chapter_id: str):
    ch = get_chapter(chapter_id)
    if not ch:
        raise HTTPException(status_code=404, detail="Chapter not found")
    nid = ch["novel_id"]
    
    if critic_name == "continuity":
        suggestions = run_continuity_check(nid, chapter_id)
    elif critic_name == "character":
        suggestions = run_character_check(nid, chapter_id)
    elif critic_name == "world-rule":
        suggestions = run_world_rule_check(nid, chapter_id)
    elif critic_name == "writing":
        suggestions = run_writing_critic(nid, chapter_id)
    elif critic_name == "pacing":
        suggestions = run_pacing_critic(nid, chapter_id)
    elif critic_name == "pov":
        suggestions = run_pov_check(nid, chapter_id)
    elif critic_name == "dialogue":
        suggestions = run_dialogue_check(nid, chapter_id)
    else:
        raise HTTPException(status_code=400, detail=f"Unknown critic: {critic_name}")
        
    return {
        "critic": critic_name,
        "count": len(suggestions),
        "suggestions": suggestions
    }

@app.get("/api/ai/suggestions/{chapter_id}")
def api_list_ai_suggestions(chapter_id: str, status: Optional[str] = None):
    return list_ai_suggestions(chapter_id, status)

@app.post("/api/ai/suggestions/{suggestion_id}/action")
def api_handle_suggestion_action(suggestion_id: str, req: AISuggestionActionRequest):
    # Find suggestion
    conn = get_chapter_by_sug_id(suggestion_id)
    if not conn:
        raise HTTPException(status_code=404, detail="Suggestion not found")
    sug, ch = conn

    if req.action == "accept":
        # Perform surgical modification on chapter text
        orig = sug["original_text"]
        repl = sug["replacement_text"]
        if orig and repl and ch["content"] and orig in ch["content"]:
            new_content = ch["content"].replace(orig, repl, 1)
            update_chapter(
                ch["id"],
                content=new_content,
                create_revision=True,
                revision_summary=f"Accepted AI edit: '{orig}' -> '{repl}'"
            )
        update_ai_suggestion_status(suggestion_id, "accepted")
    elif req.action == "reject":
        update_ai_suggestion_status(suggestion_id, "rejected")
    elif req.action == "ignore":
        update_ai_suggestion_status(suggestion_id, "ignored")
    elif req.action == "canon_change":
        update_ai_suggestion_status(suggestion_id, "canon_changed")
        # Create a new Draft or Confirmed Canon entry
        create_story_bible_entry(
            novel_id=ch["novel_id"],
            category="world",
            name=f"Canon Revision from Ch {ch['chapter_number']}",
            canon_status=req.new_canon_status or "DRAFT",
            summary=sug["problem"],
            notes=f"Created from AI critic suggestion: {sug['suggestion']}"
        )
    return {"status": req.action, "suggestion_id": suggestion_id}

def get_chapter_by_sug_id(suggestion_id: str):
    from backend.database import get_db
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM ai_suggestions WHERE id = ?", (suggestion_id,))
    sug_row = cursor.fetchone()
    if not sug_row:
        conn.close()
        return None
    sug = dict(sug_row)
    cursor.execute("SELECT * FROM chapters WHERE id = ?", (sug["chapter_id"],))
    ch_row = cursor.fetchone()
    conn.close()
    if not ch_row:
        return None
    return sug, dict(ch_row)

@app.post("/api/ai/assistant/{chapter_id}")
def api_run_assistant(chapter_id: str, req: AIAssistantRequest):
    ch = get_chapter(chapter_id)
    if not ch:
        raise HTTPException(status_code=404, detail="Chapter not found")
    return run_writing_assistant(ch["novel_id"], chapter_id, req.action, req.selected_text or "", req.instruction or "")

# --- Context & Chapter Analysis ---
@app.get("/api/chapters/{chapter_id}/context")
def api_get_chapter_context(chapter_id: str):
    ch = get_chapter(chapter_id)
    if not ch:
        raise HTTPException(status_code=404, detail="Chapter not found")
    ctx = build_chapter_context(ch["novel_id"], chapter_id)
    return {
        "chapter_id": chapter_id,
        "pov": ch["pov"],
        "relevant_characters": ctx["relevant_characters"],
        "relevant_locations": ctx["relevant_locations"],
        "relevant_world_rules": ctx["relevant_world_rules"],
        "relevant_powers": ctx["relevant_powers"],
        "relevant_factions": ctx["relevant_factions"],
        "confirmed_canon_count": len(ctx["confirmed_canon"]),
        "draft_count": len(ctx["draft_entries"]),
        "discarded_count": len(ctx["discarded_entries"])
    }

@app.get("/api/chapters/{chapter_id}/analysis")
def api_get_chapter_analysis(chapter_id: str):
    ch = get_chapter(chapter_id)
    if not ch:
        raise HTTPException(status_code=404, detail="Chapter not found")
    ctx = build_chapter_context(ch["novel_id"], chapter_id)
    clean_text = ch["content"] or ""
    
    # Calculate analytical stats
    words = ch["word_count"]
    paras = len([p for p in clean_text.split("<p>") if p.strip()])
    characters_appearing = [c["name"] for c in ctx["relevant_characters"]]
    locations_appearing = [l["name"] for l in ctx["relevant_locations"]]
    rules_applied = [r["name"] for r in ctx["relevant_world_rules"]]
    
    # Check potential new facts introduced (e.g. proper nouns or quotes)
    proper_nouns = set(re.findall(r'\b[A-Z][a-z]{3,}\b', re.sub(r'<[^>]+>', ' ', clean_text)))
    established_names = set([e["name"].split()[0] for e in ctx["confirmed_canon"] + ctx["draft_entries"]])
    candidate_new_facts = list(proper_nouns - established_names)[:6]

    return {
        "chapter_id": chapter_id,
        "title": ch["title"],
        "chapter_number": ch["chapter_number"],
        "status": ch["status"],
        "word_count": words,
        "paragraph_count": paras,
        "pov": ch["pov"] or "Not Set",
        "characters_appearing": characters_appearing,
        "locations_appearing": locations_appearing,
        "rules_applied": rules_applied,
        "potential_new_facts": candidate_new_facts,
        "pacing_assessment": "Moderate momentum with alternating dialogue and sensory description." if words > 300 else "Concise scene with rapid exposition.",
        "pov_assessment": f"Filtered through {ch['pov'] or 'third-person perspective'}."
    }

# --- Search ---
@app.get("/api/search")
def api_global_search(query: str, novel_id: Optional[str] = None):
    nid = novel_id or get_or_create_default_novel()["id"]
    return global_search(nid, query)

# --- Settings ---
@app.get("/api/settings")
def api_get_settings(novel_id: Optional[str] = None):
    nid = novel_id or get_or_create_default_novel()["id"]
    settings = get_project_settings(nid)
    # Mask API key for security
    if settings.get("gemini_api_key"):
        raw_key = settings["gemini_api_key"]
        settings["gemini_api_key_masked"] = raw_key[:4] + "..." + raw_key[-4:] if len(raw_key) > 8 else "****"
    else:
        settings["gemini_api_key_masked"] = ""
    return settings

@app.put("/api/settings")
def api_update_settings(req: SettingsUpdateRequest, novel_id: Optional[str] = None):
    nid = novel_id or get_or_create_default_novel()["id"]
    kwargs = {k: v for k, v in req.dict().items() if v is not None}
    return update_project_settings(nid, **kwargs)

# --- Import / Export ---
@app.get("/api/export/txt")
def api_export_txt(novel_id: Optional[str] = None):
    nid = novel_id or get_or_create_default_novel()["id"]
    text = export_manuscript_text(nid, "txt")
    return Response(
        content=text,
        media_type="text/plain",
        headers={"Content-Disposition": "attachment; filename=manuscript.txt"}
    )

@app.get("/api/export/markdown")
def api_export_markdown(novel_id: Optional[str] = None):
    nid = novel_id or get_or_create_default_novel()["id"]
    text = export_manuscript_text(nid, "markdown")
    return Response(
        content=text,
        media_type="text/markdown",
        headers={"Content-Disposition": "attachment; filename=manuscript.md"}
    )

@app.get("/api/export/docx")
def api_export_docx(novel_id: Optional[str] = None):
    nid = novel_id or get_or_create_default_novel()["id"]
    bio = export_manuscript_docx(nid)
    return StreamingResponse(
        bio,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": "attachment; filename=manuscript.docx"}
    )

@app.get("/api/export/project")
def api_export_project(novel_id: Optional[str] = None):
    nid = novel_id or get_or_create_default_novel()["id"]
    data = export_full_project_json(nid)
    return JSONResponse(
        content=data,
        headers={"Content-Disposition": "attachment; filename=ascendancy_project.json"}
    )

@app.post("/api/import/chapter")
async def api_import_chapter(file: UploadFile = File(...), novel_id: Optional[str] = None):
    nid = novel_id or get_or_create_default_novel()["id"]
    content = await file.read()
    ch = import_chapter_file(nid, file.filename, content)
    return ch

# --- Health Check ---
@app.get("/api/health")
def api_health():
    return {"status": "ok", "app": "Ascendancy Writer", "version": "1.0.0"}

# Static files for web UI
if os.path.exists(FRONTEND_DIR):
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
