import os
import json
import uuid
from datetime import datetime
from backend.database import (
    init_db, get_db, count_words
)

def seed_demo_data():
    init_db()
    conn = get_db()
    cursor = conn.cursor()

    # Clear existing demo data
    cursor.execute("DELETE FROM ai_suggestions")
    cursor.execute("DELETE FROM canon_history")
    cursor.execute("DELETE FROM story_bible")
    cursor.execute("DELETE FROM revisions")
    cursor.execute("DELETE FROM chapters")
    cursor.execute("DELETE FROM project_settings")
    cursor.execute("DELETE FROM novels")

    novel_id = "demo-novel-ren-protocol"
    now = datetime.utcnow().isoformat()

    cursor.execute("""
    INSERT INTO novels (id, title, description, target_words, genre, created_at, updated_at)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        novel_id,
        "The Ren Protocol: Echoes of Ravelle",
        "An intricate high-fantasy novel following Ren Kurozawa through the high-gravity spires of Ravelle, the memory-taxing inquisitors of the Flame Empire, and the forbidden hum of the Deep Archives.",
        90000,
        "Epic Fantasy",
        now,
        now
    ))

    cursor.execute("""
    INSERT INTO project_settings (novel_id, theme, ai_provider, autosave_seconds, editor_font_family, editor_font_size)
    VALUES (?, 'dark', 'heuristic_engine', 3, 'Lora', 17)
    """, (novel_id,))

    # Seed Chapters
    ch1_content = """<p>The iron elevator groaned as it climbed the sheer granite face of Ravelle. Below them, the mist lay thick and silver over the lowlands, but above, the floating citadels gleamed in the twilight like broken porcelain suspended in midair.</p>
<p>Ren Kurozawa leaned against the brass railing, his coat snapping in the freezing updraft. The gravity here was heavier, thicker—each breath felt like drawing mountain silt into his lungs. Behind him, Valeria Frainda adjusted the fur collar of her imperial cloak, her expression impassive.</p>
<p>"The inquisitors are already waiting at the Southern Arrival Gates," Valeria said, her voice cutting through the wind. "Dyren has not forgotten the discrepancy in your family's memory ledgers."</p>
<p>"Dyren collects what the Flame Empire demands," Ren replied quietly. "Ten percent of the season's recollection. Nothing more, nothing less."</p>
<p>When the gates hissed open, the air turned hot with the stench of coal smoke and melted wax. Dyren stood beneath the imperial banner, holding the bronze memory crucible. Ren stepped forward, knelt on the basalt slab, and surrendered the memory tithe, leaving his temples throbbing with a dull, hollow fog.</p>"""

    ch2_content = """<p>The dawn over the Upper Orchards broke pale and fractured. Ren stood beside the stone basin in the guest quarters. Without thinking, he looked into the mirror, examining the faint lines around his tired eyes and checking the color of his irises in the cold glass.</p>
<p>Outside the tall arched window, the plum trees swayed against their tether chains. He felt the sudden pull of the upper spires. With a careless motion of his fingers, he reversed gravity with zero strain, floating effortlessly across the vaulted ceiling for several minutes while adjusting his travel pack.</p>
<p>A knock sounded at the heavy oak door. Valeria stood on the threshold, holding an imperial courier scroll. Ren stared at her as she crossed the rug. She stared at him, her gaze calculating and unblinking.</p>
<p>"As you know, Ren, the Flame Empire established the Memory Tax twelve generations ago," Valeria stated plainly. She held out the scroll, but secretly wondered whether Ren had already forged his brother's signature on the ledger.</p>
<p>Ren tucked the scroll into his tunic. Near the window table, nestled among his research notes, lay the Obsidian Amulet, its dark surface humming with ancient discarded sorcery.</p>"""

    ch3_content = """<p>Midnight settled across the seventh tier like spilled ink. Ryu waited in the shadow of the colonnade, his collar pulled high against the damp wind blowing from the lower abysses.</p>
<p>"The archives are sealed," Ren whispered, stepping into the alcove.</p>
<p>"They are never truly sealed," Ryu murmured. He pointed down the winding staircase where the bronze archway of the archive resonated with its low, nocturnal vibration. "Listen. The bronze hums whenever the memory tides shift beneath the bedrock."</p>
<p>Ren listened. The sound was faint—less a note and more a thrumming pressure against his teeth and ribs. Step by step, they descended into the quiet heart of the mountain.</p>"""

    chapters_data = [
        ("ch-1", "The Southern Arrival Gates", ch1_content, "Ren Kurozawa", "Part I: The Ascent", "Final", 0),
        ("ch-2", "Echoes in the Upper Orchards", ch2_content, "Ren Kurozawa", "Part I: The Ascent", "In Progress", 1),
        ("ch-3", "The Resonant Bronze Archive", ch3_content, "Ren Kurozawa", "Part I: The Ascent", "Draft", 2),
    ]

    for cid, title, content, pov, part, status, order_idx in chapters_data:
        wc = count_words(content)
        cursor.execute("""
        INSERT INTO chapters (id, novel_id, title, chapter_number, part_name, pov, status, word_count, notes, content, order_index, is_archived, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)
        """, (cid, novel_id, title, order_idx + 1, part, pov, status, wc, f"Chapter notes for {title}", content, order_idx, now, now))
        
        cursor.execute("""
        INSERT INTO revisions (id, chapter_id, novel_id, title, content, word_count, notes, change_summary, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'Draft revision', ?)
        """, (str(uuid.uuid4()), cid, novel_id, title, content, wc, "Initial seed revision", now))

    # Seed Story Bible Entries
    # CHARACTERS
    sb_entries = [
        # Characters
        ("sb-char-1", "character", "Ren Kurozawa", "CONFIRMED CANON",
         "Protagonist. Gravity Affinity user carrying trauma from the Chapter 14 mirror shattering incident.",
         {
             "age": "24",
             "appearance": "Dark hair, pale complexion, wears charcoal wool travel coats and high collar.",
             "personality": "Guarded, observant, fiercely protective of his brother Ryu.",
             "abilities": "Gravity Affinity (Tier 3 vector shifting and personal mass manipulation).",
             "relationships": "Brother to Ryu Kurozawa; tenuous political alliance with Valeria Frainda; pursued by Dyren.",
             "background": "Survivor of the Grand Inversion aftershocks; former cadet of the High Vanguard.",
             "goals": "Protect the remaining memories of his family and unlock the Deep Archives.",
             "fears": "Mirrors, reflective surfaces, and losing his foundational childhood memories.",
             "secrets": "Possesses the lost harmonic key to the Deep Archives.",
             "current_status": "Infiltrating the upper tiers of Ravelle."
         }, "Crucial rule: Ren is terrified of mirrors. Never have him casually look into a mirror."),
        
        ("sb-char-2", "character", "Ryu Kurozawa", "CONFIRMED CANON",
         "Ren's younger brother. Archivist and quiet scholar who secretly knows the mechanism of the humming doors.",
         {
             "age": "19",
             "appearance": "Slender build, silver spectacles, ink-stained fingers.",
             "personality": "Quiet, intellectual, speaks softly but notices micro-details.",
             "abilities": "Minor resonant acoustics sensitivity.",
             "relationships": "Devoted younger brother to Ren.",
             "goals": "Document the suppressed history before the Flame Empire wipes it.",
             "secrets": "Understands how the Deep Archive doors resonate and what controls them."
         }, "Knows archive secrets; does not panic under pressure."),

        ("sb-char-3", "character", "Valeria Frainda", "CONFIRMED CANON",
         "Imperial diplomatic liaison from the Flame Citadel. Stoic, calculating, and ruthlessly composed.",
         {
             "age": "28",
             "appearance": "Tall, immaculate crimson and ermine coat, braided raven hair.",
             "personality": "Stoic, aristocratic, diplomatic, calculated.",
             "relationships": "Imperial envoy overseeing Ravelle; handler of Ren's transit pass.",
             "goals": "Secure imperial dominance over Ravelle's gravity anchors without open warfare."
         }, "Valeria never screams or displays overt public hysteria. Her anger is cold porcelain."),

        ("sb-char-4", "character", "Dyren", "CONFIRMED CANON",
         "Flame Empire Senior Inquisitor in charge of Memory Tax tithes.",
         {
             "age": "42",
             "appearance": "Iron-grey goatee, burn scars across knuckles, carries bronze crucible.",
             "personality": "Dogmatic, punctilious, bureaucratic yet menacing.",
             "abilities": "Flame Inscription extraction.",
             "goals": "Extract overdue memories from the Kurozawa household."
         }, "Enforces imperial memory collection without personal malice."),

        ("sb-char-5", "character", "Kaela the Shadow-Weaver", "DRAFT",
         "Proposed ally living in the lower terraces of Ravelle. Smuggles untaxed memories in glass phials.",
         {
             "age": "26",
             "personality": "Cynical, mercenary, loyal to whoever pays in clean silver.",
             "status": "Candidate character proposed for Act II."
         }, "Draft status — pending author decision on whether to introduce her in Chapter 5."),

        # Locations
        ("sb-loc-1", "location", "Ravelle", "CONFIRMED CANON",
         "High-gravity mountain domain composed of suspended basalt citadels anchored by iron chains.",
         {
             "type": "Mountain Citadel Domain",
             "geography": "Vertical cliffs rising 3,000 meters above the lowlands.",
             "rules": "Gravity is 1.4x standard in lower tiers; vector inversion occurs above Tier 7."
         }, "High altitude and heavy gravity define all physical actions here."),

        ("sb-loc-2", "location", "Upper Orchards", "CONFIRMED CANON",
         "Cultivated terraces on Tier 5 anchored by counterweight chains. Known for bitter wild plums.",
         {
             "type": "Agricultural Terrace",
             "important_features": "Heavy iron chains anchoring the soil against gravitational shear."
         }, "Tea and liquids do not settle flat here due to vector turbulence."),

        ("sb-loc-3", "location", "Deep Archives", "CONFIRMED CANON",
         "Subterranean repository carved into the bedrock. Sealed by massive resonant bronze doors that hum at night.",
         {
             "type": "Historical Sanctuary",
             "rules": "No artificial illumination allowed; threshold doors hum audibly between dusk and dawn."
         }, "Audible nocturnal vibration is a strict world rule."),

        # World Rules
        ("sb-world-1", "world", "Memory Tax", "CONFIRMED CANON",
         "The Flame Empire's mandatory tithe requiring citizens to surrender 10% of emotional memories upon domain transit.",
         {
             "domain_hierarchy": "Enforced across all nine vassal territories of the Empire.",
             "consequences": "Causes immediate cognitive disorientation, dull temples, and emotional lethargy."
         }, "Violating this rule (e.g. paying tax without fatigue) is an objective canon error."),

        ("sb-world-2", "world", "Domain Hierarchy of Ravelle", "CONFIRMED CANON",
         "Nine vertical tiers govern status and atmospheric gravity. Higher tiers require specialized mass harnesses.",
         {
             "technology": "Resonant brass harnesses and anchor pins."
         }, "Tier 8 and above cannot be traversed without harness safety."),

        # Power System
        ("sb-pow-1", "power", "Gravity Affinity", "CONFIRMED CANON",
         "The magical ability to manipulate personal mass and localized gravitational vectors.",
         {
             "rules": "Requires physical anchor point or continuous concentration.",
             "limitations": "Direct bone density strain and cerebral fatigue. Cannot be sustained for hours without collapse."
         }, "Floating effortlessly for hours without physical cost is forbidden by canon."),

        ("sb-pow-2", "power", "Flame Inscription", "CONFIRMED CANON",
         "Imperial sorcery used to extract, seal, and burn memories onto parchment tablets.",
         {
             "limitations": "Requires subject's physical contact with molten bronze crucibles."
         }, "Used exclusively by certified inquisitors like Dyren."),

        ("sb-pow-3", "power", "The Obsidian Amulet", "DISCARDED",
         "An obsolete talisman from an earlier draft that granted infinite gravity negation.",
         {
             "reason_discarded": "Discarded because it broke the cost/strain limitation of the magic system."
         }, "DO NOT REINTRODUCE. Marked as DISCARDED by author."),

        # Factions
        ("sb-fac-1", "faction", "The Flame Empire", "CONFIRMED CANON",
         "The supreme continental empire governing through memory tithes and metallurgical sorcery.",
         {
             "leader": "Emperor Sol-Kaelen",
             "territory": "The Central Basins and nine mountain protectorates."
         }, "Oppressive, bureaucratically efficient."),

        ("sb-fac-2", "faction", "The Archive Keepers", "CONFIRMED CANON",
         "A clandestine brotherhood preserving untaxed pre-Inversion history.",
         {
             "goals": "Preserve uncorrupted historical truth."
         }, "Ryu is secretly affiliated with their apprentices."),

        # Timeline
        ("sb-time-1", "timeline", "The Grand Inversion", "CONFIRMED CANON",
         "The cataclysm in Year 842 that permanently suspended Ravelle's spires into high-altitude stasis.",
         {
             "date": "Year 842",
             "consequences": "Birth of the gravity-affinity lineage."
         }, "Foundation of modern Ravelle."),

        ("sb-time-2", "timeline", "Chapter 14: The Mirror Incident", "CONFIRMED CANON",
         "Ren's childhood trauma in Year 859 where a shattered gravity-mirror inflicted acute sensory phobia.",
         {
             "date": "Year 859",
             "characters_involved": "Ren Kurozawa"
         }, "Ren's core trauma foundation.")
    ]

    for eid, cat, name, status, summary, attrs, notes in sb_entries:
        cursor.execute("""
        INSERT INTO story_bible (id, novel_id, category, name, canon_status, summary, attributes_json, notes, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (eid, novel_id, cat, name, status, summary, json.dumps(attrs), notes, now, now))

        cursor.execute("""
        INSERT INTO canon_history (id, novel_id, entry_id, entry_name, category, old_status, new_status, reason, created_at)
        VALUES (?, ?, ?, ?, ?, NULL, ?, 'Initial seed canon establishment', ?)
        """, (str(uuid.uuid4()), novel_id, eid, name, cat, status, now))

    conn.commit()
    conn.close()
    print("Seeded demo novel, chapters, revisions, story bible, and canon history successfully!")

if __name__ == "__main__":
    seed_demo_data()
