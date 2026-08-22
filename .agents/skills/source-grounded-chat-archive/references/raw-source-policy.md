# Raw source policy

## Selection versus publication

Use fragment extraction, candidate indexes, theory clusters, and similarity search to locate material. These outputs are indexes, not quotations. Before writing a note, resolve the original message ID from the raw JSONL/ZIP and copy the raw body.

## Verbatim block format

Use a generated heading followed by source-attributed blocks:

```markdown
## 2021-05-11：generated topic title

> *2021-05-11 16:30:25  Sender Name*
> original text exactly as exported
```

Keep multiline source text line-for-line. Preserve source markers such as replies, forwards, image names, emoji tokens, and mixed-language spelling.

## Machine artifacts

Store counts, session boundaries, candidate scores, cluster IDs, similarity scores, and validation logs in JSON or a separate audit report. Do not place those derived explanations inside a verbatim source note.

## Verification

For each source block, record or retain its raw message ID during generation. Re-read the source after writing and compare the note text with the raw body. A candidate preview that differs from the raw body must be discarded in favor of the raw body.
