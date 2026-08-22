---
name: source-grounded-chat-archive
description: Extract, reconstruct, and archive chat conversations from local JSONL/QQ exports with raw-source fidelity. Use when a task asks to find a person's messages, rebuild adjacent sessions, fill gaps with candidates or fragment extraction, cluster theory development, or write Obsidian archive notes where the source text must remain verbatim.
---

# Source Grounded Chat Archive

## Core rule

Treat the raw export as the source of truth. Generate only note titles/headings as summaries. Keep note bodies as verbatim source text; do not paraphrase, compress, normalize, or turn a theory path into an agent-written narrative.

## Workflow

1. **Locate the project data**
   - Reuse the project's existing `groups.json`, JSONL readers, offsets, sidecars, and completed extraction artifacts.
   - Prefer `饮茶室QA/_extract/extract_fragments.py` and `饮茶室QA/_extract/data/candidates.json` for discovery and gap candidates.
   - Treat candidate previews, cluster labels, TF-IDF matches, and semantic labels as selection aids only; never copy them as the final source text.

2. **Re-read the raw source**
   - Resolve each selected message by raw message ID from the original JSONL/ZIP.
   - Use the raw body/text field and preserve line breaks, punctuation, spelling, capitalization, emoji markers, reply markers, and language exactly.
   - Keep the original timestamp, sender display name, group, and message ID as provenance.
   - For forwarded/nested messages, preserve the nested message as its own source item and retain its nesting/provenance.
   - For image/audio-only messages, retain the exporter's original marker or asset reference; do not invent a transcript.

3. **Reconstruct adjacent sessions**
   - Match the requested numeric `sender.uin` values, not display names or changing nicknames.
   - Sort by source timestamp and deduplicate by `(group, message_id)`.
   - Build sessions from adjacent messages using the project's existing time window; retain the selected messages verbatim.
   - Use semantic clustering only to choose which original blocks deserve headings or separate notes.

4. **Write the Obsidian note**
   - Keep frontmatter limited to provenance and machine metadata.
   - Use a generated title as the summary, for example `## 2021-05-11：Elsa is a test`.
   - Under each heading, paste only source blocks in this form:

     ```markdown
     > *2021-05-11 16:30:25  FrozenHeart*
     > exact source line 1
     > exact source line 2
     ```

   - Do not add `主张`, `推理链`, `证据状态`, `发展路径`, or conclusion paragraphs unless those words and sentences are themselves in the source excerpt.
   - Put computed counts, clustering output, and audit diagnostics in a sidecar JSON/report, not inside a verbatim archive note.

5. **Validate before delivery**
   - Confirm every quoted block maps to a raw message ID.
   - Compare the note's unquoted text with the raw body; candidate-preview differences are a failure signal.
   - Check that headings are the only generated summaries.
   - Verify every claimed file path, backlink, and sidecar artifact exists.

## Project-specific references

- Project rule: `AGENTS.md`
- Raw-source policy: `references/raw-source-policy.md`
- Existing extractor: `饮茶室QA/_extract/extract_fragments.py`
- Candidate index: `饮茶室QA/_extract/data/candidates.json`
- QQ JSONL reader: `饮茶室QA/_extract/jsonl_io.py`
