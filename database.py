import sqlite3
import json
import os
import uuid
import difflib
from datetime import datetime

DEFAULT_DB_PATH = "/home/spark/ascendancy_data/ascendancy.db"
DB_PATH = os.environ.get("ASCENDANCY_DB_PATH", DEFAULT_DB_PATH)

def get_db():
    os.makedirs(os.path.dirname(os.path.abspath(DB_PATH)), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    
    # Novels table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS novels (
        id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        description TEXT,
        target_words INTEGER DEFAULT 80000,
        genre TEXT DEFAULT 'Epic Fantasy',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    """)

    # Chapters table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS chapters (
        id TEXT PRIMARY KEY,
        novel_id TEXT NOT NULL,
        title TEXT NOT NULL,
        chapter_number INTEGER NOT NULL,
        part_name TEXT DEFAULT '',
        pov TEXT DEFAULT '',
        status TEXT CHECK(status IN ('Draft', 'In Progress', 'Final')) DEFAULT 'Draft',
        word_count INTEGER DEFAULT 0,
        notes TEXT DEFAULT '',
        content TEXT DEFAULT '',
        order_index INTEGER NOT NULL,
        is_archived INTEGER DEFAULT 0,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY (novel_id) REFERENCES novels (id) ON DELETE CASCADE
    );
    """)

    # Revisions table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS revisions (
        id TEXT PRIMARY KEY,
        chapter_id TEXT NOT NULL,
        novel_id TEXT NOT NULL,
        title TEXT NOT NULL,
        content TEXT NOT NULL,
        word_count INTEGER DEFAULT 0,
        notes TEXT,
        change_summary TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY (chapter_id) REFERENCES chapters (id) ON DELETE CASCADE,
        FOREIGN KEY (novel_id) REFERENCES novels (id) ON DELETE CASCADE
    );
    """)

    # Story Bible Entries
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS story_bible (
        id TEXT PRIMARY KEY,
        novel_id TEXT NOT NULL,
        category TEXT NOT NULL, -- character, location, world, power, faction, timeline, or custom
        name TEXT NOT NULL,
        canon_status TEXT CHECK(canon_status IN ('CONFIRMED CANON', 'DRAFT', 'DISCARDED')) DEFAULT 'DRAFT',
        summary TEXT,
        attributes_json TEXT DEFAULT '{}',
        notes TEXT DEFAULT '',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY (novel_id) REFERENCES novels (id) ON DELETE CASCADE
    );
    """)

    # Canon History Audit Trail
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS canon_history (
        id TEXT PRIMARY KEY,
        novel_id TEXT NOT NULL,
        entry_id TEXT NOT NULL,
        entry_name TEXT NOT NULL,
        category TEXT NOT NULL,
        old_status TEXT,
        new_status TEXT NOT NULL,
        reason TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY (novel_id) REFERENCES novels (id) ON DELETE CASCADE
    );
    """)

    # AI Suggestions and Surgical Edits
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS ai_suggestions (
        id TEXT PRIMARY KEY,
        novel_id TEXT NOT NULL,
        chapter_id TEXT NOT NULL,
        critic_type TEXT NOT NULL, -- continuity, character, world_rule, writing, pacing, pov, dialogue, assistant
        severity TEXT CHECK(severity IN ('CRITICAL', 'MAJOR', 'MINOR', 'STYLE')) DEFAULT 'MINOR',
        location TEXT,
        original_text TEXT,
        replacement_text TEXT,
        problem TEXT NOT NULL,
        evidence TEXT,
        suggestion TEXT NOT NULL,
        status TEXT CHECK(status IN ('pending', 'accepted', 'rejected', 'ignored', 'canon_changed')) DEFAULT 'pending',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY (novel_id) REFERENCES novels (id) ON DELETE CASCADE,
        FOREIGN KEY (chapter_id) REFERENCES chapters (id) ON DELETE CASCADE
    );
    """)

    # Project Settings & AI Configuration
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS project_settings (
        novel_id TEXT PRIMARY KEY,
        theme TEXT DEFAULT 'dark',
        ai_provider TEXT DEFAULT 'heuristic_engine', -- 'gemini' or 'heuristic_engine'
        gemini_api_key TEXT DEFAULT '',
        model_name TEXT DEFAULT 'gemini-1.5-pro',
        autosave_seconds INTEGER DEFAULT 3,
        editor_font_family TEXT DEFAULT 'Serif',
        editor_font_size INTEGER DEFAULT 16,
        pinned_context_ids TEXT DEFAULT '[]',
        FOREIGN KEY (novel_id) REFERENCES novels (id) ON DELETE CASCADE
    );
    """)

    conn.commit()
    conn.close()

def count_words(text: str) -> int:
    if not text:
        return 0
    # Clean tags if any
    import re
    clean = re.sub(r'<[^>]+>', ' ', text)
    words = clean.split()
    return len(words)

# --- Novel CRUD ---
def get_or_create_default_novel():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM novels ORDER BY updated_at DESC LIMIT 1")
    row = cursor.fetchone()
    if row:
        novel = dict(row)
        conn.close()
        return novel
    
    # Create default demo novel
    novel_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    cursor.execute("""
    INSERT INTO novels (id, title, description, target_words, genre, created_at, updated_at)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        novel_id,
        "The Ren Protocol: Echoes of Ravelle",
        "An intricate high-fantasy novel following Ren Kurozawa as he navigates the high-gravity spires of Ravelle, memory-tax collectors of the Flame Empire, and the forbidden silence of the Deep Archives.",
        100000,
        "Epic Fantasy",
        now,
        now
    ))
    cursor.execute("""
    INSERT INTO project_settings (novel_id, theme, ai_provider, autosave_seconds)
    VALUES (?, 'dark', 'heuristic_engine', 3)
    """, (novel_id,))
    conn.commit()
    cursor.execute("SELECT * FROM novels WHERE id = ?", (novel_id,))
    novel = dict(cursor.fetchone())
    conn.close()
    return novel

def list_novels():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM novels ORDER BY updated_at DESC")
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

def create_novel(title: str, description: str = "", target_words: int = 80000, genre: str = "Epic Fantasy"):
    conn = get_db()
    cursor = conn.cursor()
    novel_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    cursor.execute("""
    INSERT INTO novels (id, title, description, target_words, genre, created_at, updated_at)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (novel_id, title, description, target_words, genre, now, now))
    cursor.execute("""
    INSERT INTO project_settings (novel_id, theme, ai_provider, autosave_seconds)
    VALUES (?, 'dark', 'heuristic_engine', 3)
    """, (novel_id,))
    conn.commit()
    cursor.execute("SELECT * FROM novels WHERE id = ?", (novel_id,))
    novel = dict(cursor.fetchone())
    conn.close()
    return novel

# --- Chapters CRUD ---
def list_chapters(novel_id: str, include_archived: bool = False):
    conn = get_db()
    cursor = conn.cursor()
    if include_archived:
        cursor.execute("SELECT * FROM chapters WHERE novel_id = ? ORDER BY order_index ASC", (novel_id,))
    else:
        cursor.execute("SELECT * FROM chapters WHERE novel_id = ? AND is_archived = 0 ORDER BY order_index ASC", (novel_id,))
    chapters = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return chapters

def get_chapter(chapter_id: str):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM chapters WHERE id = ?", (chapter_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def create_chapter(novel_id: str, title: str, content: str = "", pov: str = "", part_name: str = "", status: str = "Draft", notes: str = ""):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*), COALESCE(MAX(order_index), -1) FROM chapters WHERE novel_id = ?", (novel_id,))
    cnt, max_order = cursor.fetchone()
    chapter_number = cnt + 1
    order_index = max_order + 1
    chapter_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    wc = count_words(content)

    cursor.execute("""
    INSERT INTO chapters (id, novel_id, title, chapter_number, part_name, pov, status, word_count, notes, content, order_index, is_archived, created_at, updated_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)
    """, (chapter_id, novel_id, title, chapter_number, part_name, pov, status, wc, notes, content, order_index, now, now))
    
    # Also create initial revision
    cursor.execute("""
    INSERT INTO revisions (id, chapter_id, novel_id, title, content, word_count, notes, change_summary, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, 'Initial creation', ?)
    """, (str(uuid.uuid4()), chapter_id, novel_id, title, content, wc, notes, now))

    # Touch novel updated_at
    cursor.execute("UPDATE novels SET updated_at = ? WHERE id = ?", (now, novel_id))

    conn.commit()
    cursor.execute("SELECT * FROM chapters WHERE id = ?", (chapter_id,))
    ch = dict(cursor.fetchone())
    conn.close()
    return ch

def update_chapter(chapter_id: str, title: str = None, content: str = None, pov: str = None, part_name: str = None, status: str = None, notes: str = None, create_revision: bool = False, revision_summary: str = "Autosave"):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM chapters WHERE id = ?", (chapter_id,))
    ch = cursor.fetchone()
    if not ch:
        conn.close()
        return None
    ch = dict(ch)

    new_title = title if title is not None else ch["title"]
    new_content = content if content is not None else ch["content"]
    new_pov = pov if pov is not None else ch["pov"]
    new_part = part_name if part_name is not None else ch["part_name"]
    new_status = status if status is not None else ch["status"]
    new_notes = notes if notes is not None else ch["notes"]
    new_wc = count_words(new_content)
    now = datetime.utcnow().isoformat()

    cursor.execute("""
    UPDATE chapters 
    SET title = ?, content = ?, pov = ?, part_name = ?, status = ?, notes = ?, word_count = ?, updated_at = ?
    WHERE id = ?
    """, (new_title, new_content, new_pov, new_part, new_status, new_notes, new_wc, now, chapter_id))

    # Save revision if content or title changed meaningfully
    if create_revision or (content is not None and content != ch["content"] and abs(new_wc - ch["word_count"]) > 5):
        rev_id = str(uuid.uuid4())
        cursor.execute("""
        INSERT INTO revisions (id, chapter_id, novel_id, title, content, word_count, notes, change_summary, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (rev_id, chapter_id, ch["novel_id"], new_title, new_content, new_wc, new_notes, revision_summary, now))

    cursor.execute("UPDATE novels SET updated_at = ? WHERE id = ?", (now, ch["novel_id"]))
    conn.commit()
    cursor.execute("SELECT * FROM chapters WHERE id = ?", (chapter_id,))
    updated = dict(cursor.fetchone())
    conn.close()
    return updated

def delete_chapter(chapter_id: str):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT novel_id FROM chapters WHERE id = ?", (chapter_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return False
    novel_id = row["novel_id"]
    cursor.execute("DELETE FROM chapters WHERE id = ?", (chapter_id,))
    # Re-sequence chapter numbers and order indices
    cursor.execute("SELECT id FROM chapters WHERE novel_id = ? AND is_archived = 0 ORDER BY order_index ASC", (novel_id,))
    remaining = cursor.fetchall()
    for idx, r in enumerate(remaining):
        cursor.execute("UPDATE chapters SET chapter_number = ?, order_index = ? WHERE id = ?", (idx + 1, idx, r["id"]))
    conn.commit()
    conn.close()
    return True

def reorder_chapters(novel_id: str, ordered_ids: list):
    conn = get_db()
    cursor = conn.cursor()
    for idx, cid in enumerate(ordered_ids):
        cursor.execute("""
        UPDATE chapters 
        SET order_index = ?, chapter_number = ?, updated_at = ? 
        WHERE id = ? AND novel_id = ?
        """, (idx, idx + 1, datetime.utcnow().isoformat(), cid, novel_id))
    conn.commit()
    conn.close()
    return True

def duplicate_chapter(chapter_id: str):
    ch = get_chapter(chapter_id)
    if not ch:
        return None
    return create_chapter(
        novel_id=ch["novel_id"],
        title=f"{ch['title']} (Copy)",
        content=ch["content"],
        pov=ch["pov"],
        part_name=ch["part_name"],
        status="Draft",
        notes=f"Duplicated from Chapter {ch['chapter_number']}. {ch['notes']}"
    )

def toggle_archive_chapter(chapter_id: str, archive_state: bool):
    conn = get_db()
    cursor = conn.cursor()
    now = datetime.utcnow().isoformat()
    cursor.execute("UPDATE chapters SET is_archived = ?, updated_at = ? WHERE id = ?", (1 if archive_state else 0, now, chapter_id))
    conn.commit()
    conn.close()
    return True

def split_chapter(chapter_id: str, split_at_text: str, new_chapter_title: str):
    ch = get_chapter(chapter_id)
    if not ch:
        return None
    content = ch["content"]
    if split_at_text not in content:
        # Split in half
        idx = len(content) // 2
        part1 = content[:idx].strip()
        part2 = content[idx:].strip()
    else:
        parts = content.split(split_at_text, 1)
        part1 = parts[0].strip()
        part2 = (split_at_text + parts[1]).strip()

    update_chapter(chapter_id, content=part1, create_revision=True, revision_summary="Split chapter (Part 1)")
    new_ch = create_chapter(
        novel_id=ch["novel_id"],
        title=new_chapter_title or f"{ch['title']} (Part 2)",
        content=part2,
        pov=ch["pov"],
        part_name=ch["part_name"],
        status=ch["status"],
        notes=f"Created via split from Chapter {ch['chapter_number']}"
    )
    return new_ch

def merge_chapters(source_chapter_id: str, target_chapter_id: str):
    source = get_chapter(source_chapter_id)
    target = get_chapter(target_chapter_id)
    if not source or not target:
        return None
    merged_content = target["content"].rstrip() + "\n\n<p>***</p>\n\n" + source["content"].lstrip()
    update_chapter(target_chapter_id, content=merged_content, create_revision=True, revision_summary=f"Merged Chapter {source['chapter_number']} into this chapter")
    delete_chapter(source_chapter_id)
    return get_chapter(target_chapter_id)

# --- Revisions CRUD & Diffing ---
def list_revisions(chapter_id: str):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM revisions WHERE chapter_id = ? ORDER BY created_at DESC", (chapter_id,))
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

def get_revision(revision_id: str):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM revisions WHERE id = ?", (revision_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def diff_revisions(rev_a_content: str, rev_b_content: str):
    import re
    # Convert html to lines
    lines_a = [re.sub(r'<[^>]+>', '', line) for line in rev_a_content.splitlines() if line.strip()]
    lines_b = [re.sub(r'<[^>]+>', '', line) for line in rev_b_content.splitlines() if line.strip()]
    differ = difflib.HtmlDiff()
    html_diff = differ.make_table(lines_a, lines_b, context=True, numlines=3)
    unified = list(difflib.unified_diff(lines_a, lines_b, fromfile="Older Version", tofile="Newer Version", lineterm=""))
    return {
        "html_table": html_diff,
        "unified_diff": unified
    }

def restore_revision(chapter_id: str, revision_id: str):
    rev = get_revision(revision_id)
    if not rev:
        return None
    return update_chapter(chapter_id, content=rev["content"], title=rev["title"], create_revision=True, revision_summary=f"Restored from revision {rev['created_at']}")

# --- Story Bible CRUD ---
def list_story_bible_entries(novel_id: str, category: str = None, status: str = None):
    conn = get_db()
    cursor = conn.cursor()
    query = "SELECT * FROM story_bible WHERE novel_id = ?"
    params = [novel_id]
    if category:
        query += " AND category = ?"
        params.append(category)
    if status:
        query += " AND canon_status = ?"
        params.append(status)
    query += " ORDER BY name ASC"
    cursor.execute(query, params)
    rows = [dict(r) for r in cursor.fetchall()]
    for r in rows:
        try:
            r["attributes"] = json.loads(r["attributes_json"] or "{}")
        except:
            r["attributes"] = {}
    conn.close()
    return rows

def get_story_bible_entry(entry_id: str):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM story_bible WHERE id = ?", (entry_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return None
    entry = dict(row)
    try:
        entry["attributes"] = json.loads(entry["attributes_json"] or "{}")
    except:
        entry["attributes"] = {}
    conn.close()
    return entry

def create_story_bible_entry(novel_id: str, category: str, name: str, canon_status: str = "DRAFT", summary: str = "", attributes: dict = None, notes: str = ""):
    conn = get_db()
    cursor = conn.cursor()
    entry_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    attr_json = json.dumps(attributes or {})
    
    cursor.execute("""
    INSERT INTO story_bible (id, novel_id, category, name, canon_status, summary, attributes_json, notes, created_at, updated_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (entry_id, novel_id, category, name, canon_status, summary, attr_json, notes, now, now))
    
    # Audit log
    cursor.execute("""
    INSERT INTO canon_history (id, novel_id, entry_id, entry_name, category, old_status, new_status, reason, created_at)
    VALUES (?, ?, ?, ?, ?, NULL, ?, 'Created initial entry', ?)
    """, (str(uuid.uuid4()), novel_id, entry_id, name, category, canon_status, now))

    conn.commit()
    conn.close()
    return get_story_bible_entry(entry_id)

def update_story_bible_entry(entry_id: str, name: str = None, category: str = None, canon_status: str = None, summary: str = None, attributes: dict = None, notes: str = "", reason: str = "Updated entry"):
    existing = get_story_bible_entry(entry_id)
    if not existing:
        return None
    conn = get_db()
    cursor = conn.cursor()
    now = datetime.utcnow().isoformat()
    
    new_name = name if name is not None else existing["name"]
    new_category = category if category is not None else existing["category"]
    new_status = canon_status if canon_status is not None else existing["canon_status"]
    new_summary = summary if summary is not None else existing["summary"]
    new_notes = notes if notes is not None else existing["notes"]
    new_attrs = json.dumps(attributes if attributes is not None else existing["attributes"])

    # Log canon status transition if changed
    if new_status != existing["canon_status"]:
        cursor.execute("""
        INSERT INTO canon_history (id, novel_id, entry_id, entry_name, category, old_status, new_status, reason, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (str(uuid.uuid4()), existing["novel_id"], entry_id, new_name, new_category, existing["canon_status"], new_status, reason, now))

    cursor.execute("""
    UPDATE story_bible 
    SET name = ?, category = ?, canon_status = ?, summary = ?, attributes_json = ?, notes = ?, updated_at = ?
    WHERE id = ?
    """, (new_name, new_category, new_status, new_summary, new_attrs, new_notes, now, entry_id))
    
    conn.commit()
    conn.close()
    return get_story_bible_entry(entry_id)

def delete_story_bible_entry(entry_id: str):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM story_bible WHERE id = ?", (entry_id,))
    cursor.execute("DELETE FROM canon_history WHERE entry_id = ?", (entry_id,))
    conn.commit()
    conn.close()
    return True

# --- Canon Control ---
def set_canon_status(entry_id: str, new_status: str, reason: str = ""):
    assert new_status in ('CONFIRMED CANON', 'DRAFT', 'DISCARDED'), f"Invalid status: {new_status}"
    return update_story_bible_entry(entry_id, canon_status=new_status, reason=reason or f"Status changed to {new_status}")

def get_canon_history(novel_id: str, limit: int = 100):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT * FROM canon_history 
    WHERE novel_id = ? 
    ORDER BY created_at DESC 
    LIMIT ?
    """, (novel_id, limit))
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

# --- AI Suggestions & Surgical Edits ---
def save_ai_suggestion(novel_id: str, chapter_id: str, critic_type: str, severity: str, location: str, original_text: str, replacement_text: str, problem: str, evidence: str, suggestion: str):
    conn = get_db()
    cursor = conn.cursor()
    sug_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    cursor.execute("""
    INSERT INTO ai_suggestions (id, novel_id, chapter_id, critic_type, severity, location, original_text, replacement_text, problem, evidence, suggestion, status, created_at, updated_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?)
    """, (sug_id, novel_id, chapter_id, critic_type, severity, location, original_text, replacement_text, problem, evidence, suggestion, now, now))
    conn.commit()
    cursor.execute("SELECT * FROM ai_suggestions WHERE id = ?", (sug_id,))
    row = dict(cursor.fetchone())
    conn.close()
    return row

def list_ai_suggestions(chapter_id: str, status: str = None):
    conn = get_db()
    cursor = conn.cursor()
    if status:
        cursor.execute("SELECT * FROM ai_suggestions WHERE chapter_id = ? AND status = ? ORDER BY created_at DESC", (chapter_id, status))
    else:
        cursor.execute("SELECT * FROM ai_suggestions WHERE chapter_id = ? ORDER BY created_at DESC", (chapter_id,))
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

def update_ai_suggestion_status(suggestion_id: str, status: str):
    assert status in ('pending', 'accepted', 'rejected', 'ignored', 'canon_changed')
    conn = get_db()
    cursor = conn.cursor()
    now = datetime.utcnow().isoformat()
    cursor.execute("UPDATE ai_suggestions SET status = ?, updated_at = ? WHERE id = ?", (status, now, suggestion_id))
    conn.commit()
    cursor.execute("SELECT * FROM ai_suggestions WHERE id = ?", (suggestion_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

# --- Global Search ---
def global_search(novel_id: str, query_str: str):
    if not query_str or len(query_str.strip()) < 2:
        return []
    term = f"%{query_str.strip()}%"
    conn = get_db()
    cursor = conn.cursor()
    results = []

    # Search chapters
    cursor.execute("""
    SELECT id, title, chapter_number, content, notes 
    FROM chapters 
    WHERE novel_id = ? AND (title LIKE ? OR content LIKE ? OR notes LIKE ?)
    """, (novel_id, term, term, term))
    for r in cursor.fetchall():
        snippet = ""
        if r["content"]:
            idx = r["content"].lower().find(query_str.lower())
            if idx != -1:
                start = max(0, idx - 40)
                end = min(len(r["content"]), idx + len(query_str) + 40)
                snippet = "..." + r["content"][start:end].replace("\n", " ") + "..."
        results.append({
            "type": "chapter",
            "id": r["id"],
            "title": f"Chapter {r['chapter_number']}: {r['title']}",
            "snippet": snippet or "Match in chapter metadata or notes",
            "category": "Manuscript"
        })

    # Search Story Bible
    cursor.execute("""
    SELECT id, name, category, canon_status, summary, notes, attributes_json 
    FROM story_bible 
    WHERE novel_id = ? AND (name LIKE ? OR summary LIKE ? OR notes LIKE ? OR attributes_json LIKE ?)
    """, (novel_id, term, term, term, term))
    for r in cursor.fetchall():
        results.append({
            "type": "story_bible",
            "id": r["id"],
            "title": r["name"],
            "category": f"Story Bible ({r['category'].title()})",
            "canon_status": r["canon_status"],
            "snippet": r["summary"] or "Story bible record match"
        })

    conn.close()
    return results

# --- Settings ---
def get_project_settings(novel_id: str):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM project_settings WHERE novel_id = ?", (novel_id,))
    row = cursor.fetchone()
    if not row:
        cursor.execute("INSERT INTO project_settings (novel_id) VALUES (?)", (novel_id,))
        conn.commit()
        cursor.execute("SELECT * FROM project_settings WHERE novel_id = ?", (novel_id,))
        row = cursor.fetchone()
    settings = dict(row)
    try:
        settings["pinned_context_ids"] = json.loads(settings["pinned_context_ids"] or "[]")
    except:
        settings["pinned_context_ids"] = []
    conn.close()
    return settings

def update_project_settings(novel_id: str, **kwargs):
    conn = get_db()
    cursor = conn.cursor()
    fields = []
    values = []
    for k, v in kwargs.items():
        if k == "pinned_context_ids" and isinstance(v, list):
            v = json.dumps(v)
        fields.append(f"{k} = ?")
        values.append(v)
    if not fields:
        conn.close()
        return get_project_settings(novel_id)
    values.append(novel_id)
    cursor.execute(f"UPDATE project_settings SET {', '.join(fields)} WHERE novel_id = ?", values)
    conn.commit()
    conn.close()
    return get_project_settings(novel_id)
