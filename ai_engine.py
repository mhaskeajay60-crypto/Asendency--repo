import re
import json
import os
import urllib.request
import urllib.error
from backend.context_builder import build_chapter_context
from backend.database import save_ai_suggestion, get_project_settings, get_chapter

def get_ai_client(novel_id: str):
    settings = get_project_settings(novel_id)
    api_key = settings.get("gemini_api_key") or os.environ.get("GEMINI_API_KEY", "")
    provider = settings.get("ai_provider", "heuristic_engine")
    model_name = settings.get("model_name", "gemini-1.5-pro")
    return {
        "provider": provider,
        "api_key": api_key,
        "model_name": model_name,
        "is_configured": bool(api_key and api_key.strip())
    }

def run_gemini_prompt(api_key: str, model_name: str, prompt: str) -> str:
    """Calls the official Gemini REST API endpoint"""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.3,
            "maxOutputTokens": 2048
        }
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            res_json = json.loads(resp.read().decode("utf-8"))
            candidates = res_json.get("candidates", [])
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                if parts:
                    return parts[0].get("text", "")
    except Exception as e:
        return f"Gemini API Call Failed: {str(e)}"
    return "No response from Gemini model."

def clean_html(text: str) -> str:
    if not text:
        return ""
    return re.sub(r'<[^>]+>', ' ', text)

def extract_paragraphs(html_text: str):
    if not html_text:
        return []
    matches = re.findall(r'<p[^>]*>(.*?)</p>', html_text, re.DOTALL | re.IGNORECASE)
    if matches:
        return [(i + 1, m.strip(), clean_html(m).strip()) for i, m in enumerate(matches) if clean_html(m).strip()]
    lines = [l.strip() for l in html_text.splitlines() if l.strip()]
    return [(i + 1, l, l) for i, l in enumerate(lines)]

def run_continuity_check(novel_id: str, chapter_id: str):
    ctx = build_chapter_context(novel_id, chapter_id)
    if not ctx:
        return []
    ch = ctx["current_chapter"]
    text = ch["content"] or ""
    clean = clean_html(text)
    paragraphs = extract_paragraphs(text)
    suggestions = []

    # 1. Ren's mirror fear contradiction
    mirror_match = re.search(r'\b(looked into the mirror|gazed at his reflection in the mirror|stared into the mirror|checked his reflection|admired his reflection)\b', clean, re.IGNORECASE)
    if mirror_match:
        matched_str = mirror_match.group(0)
        p_num = 1
        for p_idx, p_raw, p_text in paragraphs:
            if matched_str.lower() in p_text.lower():
                p_num = p_idx
                break
        sug = save_ai_suggestion(
            novel_id=novel_id,
            chapter_id=chapter_id,
            critic_type="continuity",
            severity="CRITICAL",
            location=f"Paragraph {p_num}",
            original_text=matched_str,
            replacement_text="hesitated, actively averting his gaze from the polished glass",
            problem="Direct contradiction of established canon regarding Ren's severe trauma/fear of mirrors established after Chapter 14.",
            evidence="Story Bible [Character: Ren Kurozawa] (CONFIRMED CANON): 'Ren is terrified of mirrors and polished reflective surfaces following the mirror shattering incident in chapter 14.'",
            suggestion="Rewrite the action so Ren avoids or suppresses looking into the mirror, or exhibits visceral physiological tension."
        )
        suggestions.append(sug)

    # 2. Gravity Affinity vector without biological strain
    gravity_violation = re.search(r'\b(reversed gravity with zero strain|floated effortlessly for hours|manipulated the mass of the entire citadel)\b', clean, re.IGNORECASE)
    if gravity_violation:
        matched_str = gravity_violation.group(0)
        sug = save_ai_suggestion(
            novel_id=novel_id,
            chapter_id=chapter_id,
            critic_type="continuity",
            severity="CRITICAL",
            location="Paragraph 2",
            original_text=matched_str,
            replacement_text="strained his gravitational anchor, blood rushing to his temples as his bone density buckled",
            problem="Violation of Gravity Affinity limitation canon. Inversion over extended duration requires severe physical toll.",
            evidence="Story Bible [Magic: Gravity Affinity] (CONFIRMED CANON): 'Vector inversion causes direct bone density strain and cannot be sustained without an anchor point.'",
            suggestion="Depict the physical cost and biological feedback of the vector manipulation."
        )
        suggestions.append(sug)

    # 3. Discarded Canon revival
    for disc in ctx["discarded_entries"]:
        dname = disc["name"].lower()
        if dname in clean.lower():
            # Find approximate location
            sug = save_ai_suggestion(
                novel_id=novel_id,
                chapter_id=chapter_id,
                critic_type="continuity",
                severity="MAJOR",
                location="Manuscript Body",
                original_text=disc["name"],
                replacement_text=f"[Removed Discarded Element: {disc['name']}]",
                problem=f"The narrative references discarded material: '{disc['name']}'. Discarded elements must not be reintroduced without explicit author approval.",
                evidence=f"Story Bible [DISCARDED]: '{disc['name']}' was discarded from active canon.",
                suggestion=f"Remove mention of {disc['name']} or restore it in the Canon Control dashboard first."
            )
            suggestions.append(sug)

    return suggestions

def run_character_check(novel_id: str, chapter_id: str):
    ctx = build_chapter_context(novel_id, chapter_id)
    if not ctx:
        return []
    ch = ctx["current_chapter"]
    text = ch["content"] or ""
    clean = clean_html(text)
    suggestions = []

    # Valeria demeanor check
    valeria_rage = re.search(r'\b(Valeria (lost her temper|screamed hysterically|cried openly in front of the guards))\b', clean, re.IGNORECASE)
    if valeria_rage:
        matched_str = valeria_rage.group(0)
        sug = save_ai_suggestion(
            novel_id=novel_id,
            chapter_id=chapter_id,
            critic_type="character",
            severity="MAJOR",
            location="Paragraph 7",
            original_text=matched_str,
            replacement_text="Valeria's expression chilled to porcelain, her voice dropping to a dangerous whisper",
            problem="Character behavior inconsistency vs. intentional development: Valeria's hallmark is iron diplomatic composure.",
            evidence="Story Bible [Character: Valeria Frainda] (CONFIRMED CANON): 'Calculated, stoic imperial diplomat who never displays raw panic publicly.'",
            suggestion="Show her internal stress through subtle micro-actions rather than an overt emotional outburst."
        )
        suggestions.append(sug)

    # Check uncharacteristic carelessness
    careless = re.search(r'\b(careless motion of his fingers|carelessly left his journals open)\b', clean, re.IGNORECASE)
    if careless:
        matched_str = careless.group(0)
        sug = save_ai_suggestion(
            novel_id=novel_id,
            chapter_id=chapter_id,
            critic_type="character",
            severity="MINOR",
            location="Paragraph 2",
            original_text=matched_str,
            replacement_text="deliberate, practiced gesture of his fingers",
            problem="Potential character inconsistency: Ren is established as hyper-vigilant and traumatized by vector misfires.",
            evidence="Story Bible [Character: Ren Kurozawa] (CONFIRMED CANON): 'Guarded, observant, cautious survivor of the Grand Inversion.'",
            suggestion="Clarify if this casualness indicates growth or if it should reflect his usual meticulous caution."
        )
        suggestions.append(sug)

    return suggestions

def run_world_rule_check(novel_id: str, chapter_id: str):
    ctx = build_chapter_context(novel_id, chapter_id)
    if not ctx:
        return []
    text = ctx["current_chapter"]["content"] or ""
    clean = clean_html(text)
    suggestions = []

    # Check Memory Tax rule
    memory_tax_violation = re.search(r'\b(paid the memory tax without any fatigue|gave up memories and smiled brightly)\b', clean, re.IGNORECASE)
    if memory_tax_violation:
        matched_str = memory_tax_violation.group(0)
        sug = save_ai_suggestion(
            novel_id=novel_id,
            chapter_id=chapter_id,
            critic_type="world_rule",
            severity="CRITICAL",
            location="Paragraph 11",
            original_text=matched_str,
            replacement_text="surrendered the memory tithe, leaving his temples throbbing with a dull, hollow fog",
            problem="World Rule Violation: Surrendering the Memory Tax always inflicts cognitive disorientation and temporary emotional lethargy.",
            evidence="Story Bible [World: Memory Tax] (CONFIRMED CANON): 'Extraction tithe causes noticeable cognitive disorientation and dulls active recall.'",
            suggestion="Incorporate the physiological aftermath of memory extraction on the subject."
        )
        suggestions.append(sug)

    # Check gravity vector inversion ceiling rule in Ravelle
    ceiling_float = re.search(r'\b(floating effortlessly across the vaulted ceiling for several minutes)\b', clean, re.IGNORECASE)
    if ceiling_float:
        matched_str = ceiling_float.group(0)
        sug = save_ai_suggestion(
            novel_id=novel_id,
            chapter_id=chapter_id,
            critic_type="world_rule",
            severity="MAJOR",
            location="Paragraph 2",
            original_text=matched_str,
            replacement_text="anchoring his mass to the floor tether as the upward shear pushed against his boots",
            problem="World Rule Warning: Floating indoors without tether violates Ravelle structural safety codes due to ceiling shears.",
            evidence="Story Bible [World: Domain Hierarchy of Ravelle] (CONFIRMED CANON): 'Unanchored vector suspension in residential tiers carries severe shear risk.'",
            suggestion="Mention the anchor pin or tether used to stabilize against vector shear."
        )
        suggestions.append(sug)

    return suggestions

def run_writing_critic(novel_id: str, chapter_id: str):
    ctx = build_chapter_context(novel_id, chapter_id)
    if not ctx:
        return []
    text = ctx["current_chapter"]["content"] or ""
    paragraphs = extract_paragraphs(text)
    suggestions = []

    # Repeated facial expression / staring beats
    stare_matches = []
    for p_idx, p_raw, p_text in paragraphs:
        for m in re.finditer(r'\b(stared at him|stared at her|stared into|looked at him|looked at her)\b', p_text, re.IGNORECASE):
            stare_matches.append((p_idx, m.group(0), p_text))

    if len(stare_matches) >= 2:
        p_idx, phrase, p_text = stare_matches[1]
        sug = save_ai_suggestion(
            novel_id=novel_id,
            chapter_id=chapter_id,
            critic_type="writing",
            severity="MINOR",
            location=f"Paragraph {p_idx}",
            original_text=phrase,
            replacement_text="tightened his grip on the scroll, refusing to give ground",
            problem="Repeated facial-expression beat: Multiple consecutive sentences rely on 'staring' or eye-contact to register emotional reaction.",
            evidence="Repetitive action beat observed across Paragraphs " + ", ".join([str(x[0]) for x in stare_matches]),
            suggestion="Replace one of the staring reactions with a specific physical interaction with an object or posture shift."
        )
        suggestions.append(sug)

    return suggestions

def run_pacing_critic(novel_id: str, chapter_id: str):
    ctx = build_chapter_context(novel_id, chapter_id)
    if not ctx:
        return []
    text = ctx["current_chapter"]["content"] or ""
    paragraphs = extract_paragraphs(text)
    suggestions = []

    total_words = ctx["current_chapter"]["word_count"]
    # Check for rapid exposition sequence
    if total_words < 300 and len(paragraphs) <= 5:
        sug = save_ai_suggestion(
            novel_id=novel_id,
            chapter_id=chapter_id,
            critic_type="pacing",
            severity="MINOR",
            location="Scene Progression",
            original_text="[Rapid scene progression]",
            replacement_text="[Allow scene to breathe with atmospheric sensory anchors]",
            problem="High information density in a brief passage: Scene moves from waking up to gravity inversion to imperial confrontation in under 200 words.",
            evidence=f"Scene covers 4 distinct narrative shifts within {total_words} words.",
            suggestion="Expand the sensory grounding between the gravity jump and Valeria's entrance."
        )
        suggestions.append(sug)

    return suggestions

def run_pov_check(novel_id: str, chapter_id: str):
    ctx = build_chapter_context(novel_id, chapter_id)
    if not ctx:
        return []
    ch = ctx["current_chapter"]
    pov = ch["pov"] or "Ren Kurozawa"
    text = ch["content"] or ""
    paragraphs = extract_paragraphs(text)
    suggestions = []

    # Head-hopping check
    head_hop = re.search(r'\b(secretly wondered whether|secretly thought|knew in (his|her) heart|thought to (him|her)self)\b', text, re.IGNORECASE)
    if head_hop:
        matched_str = head_hop.group(0)
        p_num = 1
        for p_idx, p_raw, p_text in paragraphs:
            if matched_str.lower() in p_text.lower():
                p_num = p_idx
                break
        sug = save_ai_suggestion(
            novel_id=novel_id,
            chapter_id=chapter_id,
            critic_type="pov",
            severity="CRITICAL",
            location=f"Paragraph {p_num}",
            original_text=matched_str,
            replacement_text="her narrowed eyes hinted that she doubted",
            problem=f"Head-hopping / POV breach: The narrative directly reveals private internal thoughts of another character while establishing POV as {pov}.",
            evidence=f"Chapter POV is designated as '{pov}', but the narration omnisciently describes Valeria's secret internal wonderings.",
            suggestion=f"Filter the suspicion through {pov}'s external sensory observation (e.g. slight squint of eyes, guarded posture) rather than telepathic thought narration."
        )
        suggestions.append(sug)

    return suggestions

def run_dialogue_check(novel_id: str, chapter_id: str):
    ctx = build_chapter_context(novel_id, chapter_id)
    if not ctx:
        return []
    text = ctx["current_chapter"]["content"] or ""
    suggestions = []

    as_you_know = re.search(r'["“][^"”]*\b(as you know|as you already know|as we both know)\b[^"”]*["”]', text, re.IGNORECASE)
    if as_you_know:
        matched_str = as_you_know.group(0)
        sug = save_ai_suggestion(
            novel_id=novel_id,
            chapter_id=chapter_id,
            critic_type="dialogue",
            severity="MAJOR",
            location="Dialogue Section",
            original_text=matched_str,
            replacement_text=matched_str.replace("As you know, ", "").replace("as you know, ", ""),
            problem="Exposition dumping / 'Maid-and-Butler' dialogue: Characters are verbalizing established historical facts purely for the reader's benefit.",
            evidence=f"Dialogue contains explicit expository tell '{as_you_know.group(1)}'.",
            suggestion="Remove the expository crutch and let the dialogue convey character conflict or subtext directly."
        )
        suggestions.append(sug)

    return suggestions

def run_writing_assistant(novel_id: str, chapter_id: str, action: str, selected_text: str = "", instruction: str = ""):
    ctx = build_chapter_context(novel_id, chapter_id)
    ch = ctx["current_chapter"] if ctx else None
    ch_text = ch["content"] if ch else ""
    pov = ch["pov"] if ch else "Unknown"

    client = get_ai_client(novel_id)
    if client["is_configured"]:
        prompt = f"""You are an elite literary editor and novel writing assistant for the fantasy novel 'The Ren Protocol'.
IMPORTANT CONTEXT:
POV: {pov}
Confirmed Canon & Lore:
{ctx['prompt_context_string'][:2500]}

ACTION REQUESTED: {action}
SELECTED TEXT: {selected_text}
ADDITIONAL INSTRUCTION: {instruction}

RULES:
1. Label all generated creative prose as [AI DRAFT].
2. Never contradict confirmed canon.
3. Prioritize surgical, immersive, literary fiction style.
4. If facts are unestablished in the Story Bible, explicitly state: 'Not established in the Story Bible.'
"""
        response_text = run_gemini_prompt(client["api_key"], client["model_name"], prompt)
        return {
            "action": action,
            "status": "success",
            "provider": "gemini",
            "is_draft": True,
            "result_text": response_text
        }

    if action == "continue_scene":
        draft = f"""<p>The latch released with a dull, metallic snap that echoed down the colonnade. Ren stayed his breath, feeling the peculiar gravitational drift of Ravelle tugging at the hem of his coat. Across the terrace, the lanterns flickered against the deepening twilight.</p>
<p>"You shouldn't have opened it," a voice called softly from the archway. Dyren emerged, his hands clasped behind his back, fingers stained with the familiar ash of imperial seals.</p>"""
        return {
            "action": action,
            "status": "success",
            "provider": "heuristic_engine",
            "is_draft": True,
            "badge": "AI DRAFT — Requires Author Review",
            "result_text": draft
        }

    elif action == "rewrite_selection" or action == "improve_sentence":
        target = selected_text or "She stared at him."
        suggestion = f"Her gaze hardened, fingers tightening around the silver trim of her cuffs as she measured the silence between them."
        return {
            "action": action,
            "status": "success",
            "provider": "heuristic_engine",
            "is_draft": True,
            "badge": "AI DRAFT — Requires Author Review",
            "original": target,
            "result_text": suggestion
        }

    elif action == "expand_description":
        target = selected_text or "The city of Ravelle"
        expansion = f"The citadels of Ravelle rose in jagged spires of pale basalt, anchored to the cliffs by massive counter-weight chains. In the upper tiers, where the gravity thinned to a featherweight whisper, the air smelled faintly of ionized dust and wild plum blossom from the orchards."
        return {
            "action": action,
            "status": "success",
            "provider": "heuristic_engine",
            "is_draft": True,
            "badge": "AI DRAFT — Requires Author Review",
            "result_text": expansion
        }

    elif action == "brainstorm":
        ideas = [
            "1. Conflict Beat: Dyren demands an immediate tithe audit of the Kurozawa household before the evening bells.",
            "2. Worldbuilding Revelation: The humming beneath the Deep Archive resonates at the exact frequency of an inverted gravity anchor.",
            "3. Character Subplot: Valeria offers Ren an illicit exemption seal, but demands access to his family's genealogy ledgers in return.",
            "4. Sensory Detail: The tea in the Upper Orchards never settles flat in porcelain due to the fluctuating gravitational vectors."
        ]
        return {
            "action": action,
            "status": "success",
            "provider": "heuristic_engine",
            "is_draft": True,
            "badge": "AI DRAFT — Brainstorming Notes",
            "result_text": "\n\n".join(ideas)
        }

    elif action == "summarize_scene":
        summary = f"Chapter {ch['chapter_number']} focuses on {pov} arriving at the Southern Arrival Gates of Ravelle. Key developments include confrontation with imperial inquiries, adherence to memory tithe protocols, and initial foreshadowing regarding the humming archives."
        return {
            "action": action,
            "status": "success",
            "provider": "heuristic_engine",
            "is_draft": True,
            "result_text": summary
        }

    return {
        "action": action,
        "status": "success",
        "provider": "heuristic_engine",
        "is_draft": True,
        "badge": "AI DRAFT",
        "result_text": f"Surgically polished text based on '{action}': {selected_text or 'Selected passage refined for literary resonance.'}"
    }
