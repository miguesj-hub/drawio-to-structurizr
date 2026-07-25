# The draw.io C4 file format — what actually bites

Findings from real C4 diagrams drawn with draw.io's built-in C4 shape library.
These are the traps the extractor exists to absorb; read this before debugging a
conversion.

## File shapes

A `.drawio` file is `<mxfile>` wrapping one `<diagram>` per page. The page content
comes in three forms:

1. **Plain XML** — `<diagram><mxGraphModel>…` (draw.io desktop, "uncompressed")
2. **Compressed** — `<diagram>` text is base64 → raw deflate (`zlib` wbits `-15`)
   → URL-encoded XML
3. **`.drawio.svg` / `.drawio.png`** — an export with the source embedded in the
   SVG's `content="…"` attribute (HTML-escaped) or a PNG `mxfile` text chunk

All three carry the same model. Always handle all three; users share exports far
more often than source.

## C4 shapes are `<object>`, not `<mxCell>`

The C4 library wraps each shape in an `<object>` carrying the semantics, with a
geometry-only `<mxCell>` child:

```xml
<object placeholders="1" c4Name="Alumno" c4Type="Person"
        c4Description="Alumno de curso"
        label="&lt;font ...&gt;%c4Name%&lt;/font&gt;&lt;div&gt;[%c4Type%]&lt;/div&gt;"
        id="j3UO1AglKh7utOd2yK0e-1">
  <mxCell style="shape=mxgraph.c4.person;..." vertex="1" parent="1">
    <mxGeometry x="670" y="-380" width="200" height="180" as="geometry"/>
  </mxCell>
</object>
```

Read `c4Name`, `c4Type`, `c4Description`, `c4Technology` from the **object**.
Ignore `label` — it is a `%c4Name%` placeholder template, not content.

Shapes drawn *without* the C4 library have no `c4Type`; fall back to the `style`
string and the element's name.

### `c4Type` values seen in the wild

`Person`, `External Person`, `Software System`, `External Software System`,
`Container`, `Component`, `Database`, and boundary types
`SystemScopeBoundary`, `ContainerScopeBoundary`, `EnterpriseScopeBoundary`.

## Trap 1 — `c4Technology` is often whitespace, not absent

```xml
c4Technology="&#10;"    <!-- a bare newline -->
```

Testing `if technology:` passes on `"\n"`. Normalise whitespace before deciding a
technology is missing, or you will emit `technology "\n"` into the DSL.

## Trap 2 — connector labels live in a *separate* cell

An edge usually has no `value`. Its caption is a child vertex whose `parent` is
the edge id, marked `edgeLabel` and/or `connectable="0"`:

```xml
<mxCell id="edge-1" edge="1" source="A" target="B" style="edgeStyle=..."/>
<mxCell value="&lt;font&gt;Makes api calls to&lt;/font&gt;" style="edgeLabel;..."
        vertex="1" connectable="0" parent="edge-1"/>
```

Reading only `edge.value` yields **every relationship unlabelled** — the single
most common cause of a useless conversion. Collect child label cells and attach
them to their parent edge.

## Trap 3 — labels are HTML, and block tags matter

```html
<font style="font-size: 14px;">Loads UI</font><div><font size="3">Registers to</font></div>
```

Strip tags, but convert **both** `<div>` and `</div>` to line breaks. Handling only
the closing tag welds captions together: `"Loads UIRegisters to"`. Also unescape
entities and `&nbsp;` (`\xa0`).

A multi-line caption often means description + technology. C4 notates technology
in square brackets (`[JSON/HTTPS]`). Treat **only** square brackets as technology:
parentheses are ambiguous — in `"Sends payment request (credit card info)"` the
parenthetical is payload, not protocol.

## Trap 4 — boundaries do not contain their children

You would expect containers inside a `SystemScopeBoundary` to have
`parent="<boundary-id>"`. They usually do **not** — every shape is `parent="1"`
and the boundary is merely drawn around them.

Membership is therefore **geometric**: a shape belongs to the boundary whose
rectangle encloses it. Compare absolute coordinates.

Corollary: when a shape *is* nested via `parent`, its `mxGeometry` is
**parent-relative**. Resolve to absolute by summing ancestor offsets before any
containment or distance test.

## Trap 5 — connectors that were never attached

An edge is only wired when it has `source` and `target` attributes. Users
frequently drop a line that merely *looks* connected:

```xml
<mxCell id="Dzy9JkdPgCEiqWZl8QQP-1" edge="1" parent="1"
        style="...exitX=0;exitY=0.5;...entryX=0.465;entryY=1.014;...dashed=1;">
  <mxGeometry relative="1" as="geometry">
    <mxPoint x="994" y="359" as="sourcePoint"/>
    <mxPoint x="441.6" y="240.68" as="targetPoint"/>
  </mxGeometry>
</mxCell>
```

No `source`, no `target` — but `sourcePoint`/`targetPoint` give coordinates. Resolve
by distance to each shape's rectangle (0 when the point is inside).

In the diagram above, `sourcePoint` sits **0.0 px** from one container and
`targetPoint` **0.7 px** from another, while the runner-up is ~496 px away. That
gap is the signal: recover the endpoint.

### When to refuse

Proximity alone is not enough — two shapes can be equally near. Rules the
extractor applies:

| Condition | Verdict |
| --- | --- |
| ≤ 15 px from a shape | `high` — treat as touching |
| Nearest is ≥ 3× closer than runner-up, within 250 px | `medium` — accept, flag for review |
| Two candidates similarly close | `unresolved` — refuse, flag |
| > 250 px from everything | `unresolved` — refuse, flag |

A wrong relationship is worse than a reported gap: it misinforms silently.

## Trap 6 — the same element typed differently per diagram

A recurring modelling slip: an external system is a `Software System` on the
Context diagram but drawn as a `Container` on the Container diagram, sitting
outside the boundary. Cross-reference by name across all files at once — this is
undetectable from one file. The Context diagram is authoritative on externality.

## Trap 7 — empty pages

A file can be 240 bytes of scaffolding with no shapes:

```xml
<mxGraphModel><root><mxCell id="0"/><mxCell id="1" parent="0"/></root></mxGraphModel>
```

Ids `0` and `1` are the model root and default layer, never content. Detect and
report as a blocker; do not invent that abstraction level.

## Duplicated names across diagrams

The same person appears on Context *and* Container diagrams. These are one model
element rendered twice, not two elements. Deduplicate by name when merging, and
keep the richest description.
