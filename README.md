# draw.io C4 → Structurizr DSL

A Claude Code plugin that converts [draw.io](https://app.diagrams.net) C4 diagrams
into a single, well-structured [Structurizr DSL](https://docs.structurizr.com/dsl)
workspace you can paste straight into
[playground.structurizr.com](https://playground.structurizr.com/).

It is built around one principle: **a wrong relationship is worse than a reported
gap.** Where a connector is ambiguous, the plugin flags it for you instead of
guessing.

## Why not just eyeball the XML?

Because draw.io's C4 format has traps that fail *silently*. Every one of these was
found in real diagrams and is handled by the extractor:

| Trap | What happens if you miss it |
| --- | --- |
| Connector labels live in a **separate** cell, not on the edge | Every relationship comes out unlabelled |
| Labels are HTML; only `</div>` looks like a line break | Captions weld together: `"Loads UIRegisters to"` |
| `c4Technology` is often `"\n"`, not empty | `technology "\n"` lands in your DSL |
| draw.io ships example text in the technology field | `"e.g. SpringBoot, ElasticSearch, etc."` becomes a "decision" |
| …and prompt text in the description field | `"Description of component role/responsibility."` ships as real prose |
| C4 boundaries **don't** parent their children | Containment has to come from geometry |
| Component diagrams nest two near-identically named boundaries | Components land under the wrong parent, or externals become components |
| Nested shapes use parent-relative coordinates | Every distance and containment test is wrong |
| Connectors that were never attached have no `source`/`target` | Whole relationships vanish |
| The same element typed differently per diagram | An external system silently becomes your container |

## What it does

0. **Requires all three C4 levels.** Before converting it checks the input set
   covers context, container *and* component, classified from the shapes rather
   than filenames. A missing level is a **blocker**, so you never receive a
   two-view workspace presented as complete.
1. **Extracts** a normalised model from `.drawio`, `.drawio.svg` and compressed
   files — stdlib Python, no dependencies.
2. **Recovers connector endpoints** that were never attached, using geometry, and
   **refuses to guess** when two shapes are similarly close.
3. **Reconciles across diagrams** — one model element per real-world thing; the
   System Context diagram decides what is external.
4. **Audits against the C4 standard** — missing technology, generic labels,
   containers outside boundaries, empty diagrams.
5. **Generates DSL named like code**, applying *Clean Code* to identifiers and
   file structure.
6. **Updates an existing DSL incrementally** — diffs the diagrams against a
   baseline and applies only what changed, never overwriting curated prose or
   renaming identifiers.
7. **Flags the rest** as a checklist of what to fix in draw.io.

It installs nothing without asking, and always offers to just hand you the `.dsl`
for your own server or the Structurizr playground.

## Install

```
/plugin marketplace add miguesj-hub/drawio-to-structurizr
/plugin install drawio-to-structurizr@miguel-architecture-tools
/reload-plugins
```

## Use

Point it at your diagrams — pass them all at once so cross-diagram checks work:

```
Convert my C4 draw.io diagrams to Structurizr DSL
```

Or invoke the agent explicitly:

```
@drawio-to-structurizr:drawio-c4-converter convert context.drawio and containers.drawio
```

The extractor also runs standalone, with no Claude involved:

```bash
python3 plugins/drawio-to-structurizr/scripts/drawio_c4_extract.py \
    *.drawio --json model.json
```

```
37 elements, 38 relationships, 0 blockers, 50 warnings
  [info]    inferred-connector: endpoints inferred from geometry (high confidence).
            source: endpoint touches 'Monolito' (0.0px) / target: touches 'Sistema de correos' (0.7px)
  [warning] inconsistent-type: 'Payment Gateway' is typed differently across diagrams:
            ['component', 'container', 'softwareSystem'].
  [warning] placeholder-technology: container 'Monolito' still carries draw.io's example text.
  [warning] orphan-element: component 'Base de datos' has no relationships on this diagram.
```

Drop the component diagram from the inputs and it refuses to pretend otherwise:

```
18 elements, 17 relationships, 1 blockers, 11 warnings
  [blocker] missing-level-component: No component diagram was found among the inputs.
```

## Keeping a DSL up to date

Diagrams get edited after the first conversion. Regenerating from scratch throws
away descriptions and identifier choices a human curated, so instead keep the
extraction JSON as a baseline and diff against it:

```bash
python3 plugins/drawio-to-structurizr/scripts/drawio_c4_extract.py *.drawio \
    --json model.json --baseline .c4-baseline.json
```

```
Changes since the baseline:
  + C4 level now covered: component
  + component 'Database Adapter'
  ~ 'Payment Gateway' kind: 'container' -> 'component'
  + Cart API -> Cart Component 'Usa'
  - Monolito -> Registro central (gone)
```

The diff compares two extraction snapshots rather than reading the DSL back —
which would mean re-implementing a DSL parser, and would confuse the author's hand
edits with the drawing's content. Removals are reported, never applied silently: a
shape can disappear because someone is mid-edit.

## Rendering: your choice, nothing installed behind your back

Conversion itself needs **only Python 3.9+**. Rendering and validation need
external tools, so the agent surveys what you have, then asks:

- **Translate only** — you get the `.dsl` and take it to
  [playground.structurizr.com](https://playground.structurizr.com/) or your own
  Structurizr server. Nothing installed; the agent tells you plainly that nothing
  parsed it either.
- **Local tooling** — Structurizr Lite or CLI for rendering and `validate`, plus
  Graphviz for layout. Each proposed with its size, and only with your say-so.

### The Graphviz trap

`autoLayout` emits `"implementation": "Graphviz"`, but Graphviz is an external
binary. Without `dot` installed, Structurizr's web UI **silently** falls back to a
weaker built-in layout — you get crossing lines and no explanation. Detect it:

```bash
# Structurizr Lite logs the probe at startup
grep "Graphviz (dot)" server.log      # false => falling back
```

`references/layout.md` covers this plus groups, rank separation, routing, and the
cost of positioning elements by hand (coordinates live in the workspace JSON, not
the DSL, so they do not travel with your file).

## Endpoint inference

Unattached connectors are resolved by distance from the endpoint coordinate to
each shape's rectangle:

| Condition | Verdict |
| --- | --- |
| ≤ 15 px from a shape | `high` — treated as touching |
| Nearest is ≥ 3× closer than runner-up, within 250 px | `medium` — accepted, flagged for review |
| Two candidates similarly close | `unresolved` — refused and flagged |
| > 250 px from everything | `unresolved` — refused and flagged |

Thresholds are constants at the top of the script; tune them for your drawing
style.

## Naming

Identifiers are code, so they follow *Clean Code*:

```
# Before -- from the drawing
frontend  = container "FRONT-END"
backend   = container "Monolito"
dataBase  = container "Data Base"
fe -> backend "Uses"

# After
webApplication    = container "Web Application" "..." "React"
monolithicBackend = container "Monolithic Backend" "..." "Spring Boot"
platformDatabase  = container "Platform Database" "..." "PostgreSQL"
webApplication -> monolithicBackend "Makes API calls to" "HTTPS/JSON"
```

`frontend` is a layer, not a responsibility. `Uses` is explicitly rejected by the
C4 notation rules. Full mapping with worked examples:
[`clean-code-naming.md`](plugins/drawio-to-structurizr/skills/drawio-to-dsl/references/clean-code-naming.md).

## What's inside

```
plugins/drawio-to-structurizr/
├── agents/drawio-c4-converter.md      # the agent: workflow, triage, non-negotiables
├── scripts/drawio_c4_extract.py       # deterministic extractor (stdlib only)
└── skills/drawio-to-dsl/
    ├── SKILL.md
    └── references/
        ├── c4-model.md                # abstractions, diagram types, notation rules
        ├── structurizr-dsl.md         # DSL syntax, views, styles, parse errors
        ├── clean-code-naming.md       # Clean Code → DSL, before/after
        ├── drawio-c4-xml.md           # format traps + inference thresholds
        └── layout.md                  # crossing lines, the Graphviz fallback, manual layout
examples/ecollege/                     # real diagrams, generated DSL, extractor output
```

The split is deliberate: the **script** does what must be reproducible (XML
archaeology, geometry, confidence scoring); the **agent** does what needs
judgement (naming, wording, structure). Mechanical work in code, subjective work
reviewable.

## Example

[`examples/ecollege/`](examples/ecollege) is a genuine conversion: all three C4
diagrams, the extractor's JSON, and the resulting
[`ecollege.dsl`](examples/ecollege/ecollege.dsl) — 14 components across three
views, validated by parsing it in Structurizr Lite. It exercises every interesting
case: six unattached connectors recovered from geometry (the closest at 0.0 px),
three external systems mistyped as containers *and* as components, two
near-identically named nested boundaries, a database nothing connects to, and
placeholder text in both the technology and description fields.

## Requirements

- Python 3.9+ (standard library only)
- Optional, for validation: [Structurizr CLI](https://docs.structurizr.com/cli) or
  [Structurizr Lite](https://docs.structurizr.com/lite)

## Licence

MIT — see [LICENSE](LICENSE).
