---
name: drawio-to-dsl
description: Convert draw.io / diagrams.net C4 diagrams into a single Structurizr DSL workspace. Use when the user has .drawio or .drawio.svg architecture diagrams (System Context, Container, Component) and wants Structurizr DSL for playground.structurizr.com or Structurizr Lite, or wants their draw.io C4 diagrams audited for modelling errors, unlabelled connectors, or connectors that were never attached.
---

# draw.io C4 → Structurizr DSL

Turn one or more draw.io C4 drawings into a single, well-named, Clean-Code
structured Structurizr DSL workspace — recovering connector labels, inferring
endpoints for connectors that were never wired, and flagging what cannot be
resolved instead of guessing.

## When to use

- "Convert these .drawio diagrams to Structurizr DSL"
- "Turn my C4 draw.io files into a structurizr playground workspace"
- "My DSL file is incomplete — regenerate it from the diagrams"
- "Check my draw.io C4 diagrams for modelling errors"

## Step 1 — Extract (always run this first)

Never parse the XML by hand; coordinates and label ownership are easy to get
wrong and the failures are silent. Pass **all** diagrams in one invocation so
cross-diagram checks work:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/drawio_c4_extract.py" \
    *.drawio --json /tmp/c4-model.json
```

Stdlib-only, Python 3.9+. Handles plain, compressed and `.drawio.svg` inputs.
Returns `diagrams`, `elements`, `relationships`, `flags`, `summary`.

Exit code is 0 even with flags — flags are findings for a human, not failures.
Exit 2 means nothing could be read.

## Step 2 — Read the flags before writing DSL

Every `blocker` needs a decision. See the table in the
`drawio-c4-converter` agent, or:

- `empty-diagram` → report it; never fabricate that abstraction level
- `unresolved-connector` → `# TODO(unresolved)` comment, ask the user to reattach
- `inferred-connector` → include, mark `# inferred:`, list for confirmation
- `inconsistent-type` / `container-outside-boundary` → almost always an external
  system drawn as a Container; the Context diagram decides
- `missing-technology` → ask or emit `technology "TODO"`; never invent a stack

## Step 3 — Merge into one model

One element per real-world thing, deduplicated by name across diagrams. Boundary
membership is geometric. The Context diagram is authoritative on what is external.
Details and rationale: `references/drawio-c4-xml.md`.

## Step 4 — Name and structure

This is where the value is added. Identifiers are code:

- Intention-revealing: `studentWebApplication`, not `frontend` / `fe` / `c1`
- No type encoding — the `container` keyword already says it
- Verb phrases for relationships; C4 rejects bare `"Uses"`
- Keep the author's domain vocabulary and their original prose in `description`

Full mapping with worked before/after examples: `references/clean-code-naming.md`.

## Step 5 — Emit DSL

Syntax and pitfalls: `references/structurizr-dsl.md`. Requirements:

- `!identifiers hierarchical`
- Newspaper order: people → system in scope → externals → relationships → views
- Four-space indent, blank line between concept groups
- Every container/component declares a technology (C4 requires it)
- Every view gets an explicit `title` and `autoLayout` — without `autoLayout`
  everything renders stacked at the origin
- Tag externals and style once by tag; never restyle per element

## Step 6 — Validate, then report honestly

Parse before handing over — `structurizr-cli validate -workspace workspace.dsl`,
or load it in Structurizr Lite. If no parser was available, say so plainly rather
than implying it was verified.

Report: counts; decisions made (retypings, merges, renames old → new); inferred
connectors to confirm; unresolved items as a fix-list; remaining TODOs.

## References

| File | Contents |
| --- | --- |
| `references/c4-model.md` | C4 abstractions, diagram types, notation rules, conversion checklist |
| `references/structurizr-dsl.md` | DSL syntax, views, styles, common parse errors |
| `references/clean-code-naming.md` | *Clean Code* mapped to DSL, with before/after |
| `references/drawio-c4-xml.md` | draw.io format traps and the endpoint-inference thresholds |
