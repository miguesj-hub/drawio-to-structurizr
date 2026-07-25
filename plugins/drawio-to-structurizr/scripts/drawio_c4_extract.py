#!/usr/bin/env python3
"""Extract a normalised C4 model from draw.io files.

This script does the mechanical, deterministic half of a draw.io -> Structurizr
DSL conversion: parse the XML, resolve which shape each connector joins, work
out what lives inside which boundary, and report what it could not resolve.

It deliberately does NOT write DSL. Naming, wording and file structure need
judgement, so an agent does that step using this script's JSON as ground truth.
Splitting it this way keeps the error-prone part (XML archaeology) reproducible
and the subjective part (naming) reviewable.

Usage:
    drawio_c4_extract.py FILE [FILE ...] [--json out.json] [--quiet]

Output: a JSON document on stdout (or --json) with `diagrams`, `elements`,
`relationships` and `flags`. Exit status is 0 even when there are flags -- flags
are findings for a human, not script failures. Exit 2 means no file could be read.

Standard library only, so it runs anywhere Python 3.9+ does.
"""

from __future__ import annotations

import argparse
import base64
import html
import json
import re
import sys
import urllib.parse
import xml.etree.ElementTree as ElementTree
import zlib
from dataclasses import dataclass, field, asdict
from pathlib import Path

# --- Tuning constants -------------------------------------------------------
# A connector endpoint this close to a shape is treated as touching it.
TOUCHING_DISTANCE_PX = 15.0
# Beyond TOUCHING, an endpoint is only accepted if it is this much nearer to the
# winner than to the runner-up. Prevents guessing between two equidistant shapes.
AMBIGUITY_RATIO = 3.0
# An endpoint further than this from every shape is never guessed.
MAX_INFERENCE_DISTANCE_PX = 250.0

# draw.io's C4 shapes ship with example text in the technology field. Users who
# never edit it leave a "technology" that is really a placeholder, which would
# otherwise be copied into the DSL as if it were a real decision.
PLACEHOLDER_TECHNOLOGY_MARKERS = ("e.g.", "eg.", "etc.", "example", "your tech", "tbd")

# The same problem for descriptions: the C4 shapes ship with prompt text in the
# description field, which reads as real prose and would be copied verbatim.
PLACEHOLDER_DESCRIPTION_MARKERS = (
    "description of",
    "role/responsibility",
    "describe ",
    "lorem ipsum",
)

# draw.io's C4 shape library stores the abstraction in a `c4Type` attribute.
C4_TYPE_ALIASES = {
    "person": "person",
    "external person": "person",
    "software system": "softwareSystem",
    "external software system": "softwareSystem",
    "system": "softwareSystem",
    "container": "container",
    "external container": "container",
    "component": "component",
    "external component": "component",
    "database": "container",
    "systemscopeboundary": "boundary",
    "containerscopeboundary": "boundary",
    "enterprisescopeboundary": "boundary",
    "boundary": "boundary",
}

# Fallback when a shape is not from the C4 library: guess from its mxCell style.
STYLE_TYPE_HINTS = (
    ("shape=cylinder", "container"),
    ("shape=datastore", "container"),
    ("shape=actor", "person"),
    ("shape=umlActor", "person"),
    ("mxgraph.c4.person", "person"),
    ("mxgraph.c4.software", "softwareSystem"),
    ("mxgraph.c4.container", "container"),
    ("mxgraph.c4.component", "component"),
)


@dataclass
class Shape:
    """A vertex: a person, system, container, component or boundary."""

    id: str
    name: str
    kind: str  # person | softwareSystem | container | component | boundary | unknown
    description: str = ""
    technology: str = ""
    diagram: str = ""
    external: bool = False
    x: float = 0.0
    y: float = 0.0
    width: float = 0.0
    height: float = 0.0
    parent_boundary: str | None = None
    # For a boundary shape: the original c4Type, so callers can tell a
    # SystemScopeBoundary from a ContainerScopeBoundary. Component diagrams nest
    # the two, and only the inner one names the container a component belongs to.
    boundary_kind: str = ""
    from_c4_library: bool = True

    @property
    def area(self) -> float:
        return self.width * self.height

    @property
    def right(self) -> float:
        return self.x + self.width

    @property
    def bottom(self) -> float:
        return self.y + self.height

    def distance_to(self, px: float, py: float) -> float:
        """Euclidean distance from a point to this shape's rectangle (0 if inside)."""
        dx = max(self.x - px, 0.0, px - self.right)
        dy = max(self.y - py, 0.0, py - self.bottom)
        return (dx * dx + dy * dy) ** 0.5

    def contains(self, other: "Shape") -> bool:
        return (
            self.x <= other.x
            and self.y <= other.y
            and self.right >= other.right
            and self.bottom >= other.bottom
            and self.id != other.id
        )


@dataclass
class Relationship:
    """A connector between two shapes."""

    id: str
    diagram: str
    source: str | None
    target: str | None
    description: str = ""
    technology: str = ""
    source_inferred: bool = False
    target_inferred: bool = False
    confidence: str = "certain"  # certain | high | medium | unresolved
    notes: list[str] = field(default_factory=list)


@dataclass
class Flag:
    """Something a human needs to decide or fix."""

    severity: str  # blocker | warning | info
    code: str
    diagram: str
    message: str
    hint: str = ""


# --- draw.io file decoding --------------------------------------------------


def _inflate_diagram(payload: str) -> str | None:
    """Decode draw.io's compressed <diagram> payload (base64 + raw deflate + URL)."""
    try:
        raw = base64.b64decode(payload)
        xml_text = zlib.decompress(raw, -15).decode("utf-8")
        return urllib.parse.unquote(xml_text)
    except Exception:
        return None


def load_diagrams(path: Path) -> list[tuple[str, ElementTree.Element]]:
    """Return (diagram_name, mxGraphModel root) for every page in a file.

    Handles the three shapes a draw.io file can take: plain XML, compressed
    payloads, and .drawio.svg exports that embed the source in an attribute.
    """
    text = path.read_text(encoding="utf-8", errors="replace")

    # .drawio.svg / .png embed the original file in a content attribute.
    if path.suffix.lower() == ".svg" or "<svg" in text[:512]:
        match = re.search(r'content="([^"]+)"', text)
        if not match:
            return []
        text = html.unescape(match.group(1))

    try:
        root = ElementTree.fromstring(text)
    except ElementTree.ParseError:
        return []

    pages: list[tuple[str, ElementTree.Element]] = []
    diagram_nodes = list(root.iter("diagram")) or ([root] if root.tag == "mxGraphModel" else [])

    for index, node in enumerate(diagram_nodes):
        name = node.get("name") or f"page-{index + 1}"
        model = node.find("mxGraphModel")
        if model is None and (node.text or "").strip():
            decoded = _inflate_diagram(node.text.strip())
            if decoded:
                try:
                    model = ElementTree.fromstring(decoded)
                except ElementTree.ParseError:
                    model = None
        if model is None and node.tag == "mxGraphModel":
            model = node
        if model is not None:
            pages.append((name, model))
    return pages


# --- text handling ---------------------------------------------------------


def clean_label(raw: str | None) -> str:
    """Turn a draw.io HTML label into plain text, preserving line breaks."""
    if not raw:
        return ""
    text = re.sub(r"<br\s*/?>", "\n", raw, flags=re.I)
    # Both the opening and closing block tags start a new line. Missing the
    # opening one silently welds two captions together ("Loads UIRegisters to").
    text = re.sub(r"<(div|p)\b[^>]*>", "\n", text, flags=re.I)
    text = re.sub(r"</(div|p)>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text).replace("\xa0", " ")
    lines = [" ".join(line.split()) for line in text.split("\n")]
    return "\n".join(line for line in lines if line)


def split_description_and_technology(label: str) -> tuple[str, str]:
    """Separate a connector label into intent and technology.

    C4 notates technology in square brackets, e.g. "Makes API calls to\n[JSON/HTTPS]".
    Only square brackets are treated as technology: parentheses are ambiguous in
    practice ("Sends payment request (credit card info)" is payload, not protocol),
    so they stay in the description for a human to judge.
    """
    if not label:
        return "", ""
    description_lines: list[str] = []
    technology_parts: list[str] = []

    for line in label.split("\n"):
        bracketed = re.fullmatch(r"\[(.+)\]", line.strip())
        if bracketed:
            technology_parts.append(bracketed.group(1).strip())
        else:
            description_lines.append(line.strip())

    description = " ".join(description_lines).strip()
    inline = re.search(r"\[([^\]]+)\]\s*$", description)
    if inline:
        technology_parts.append(inline.group(1).strip())
        description = description[: inline.start()].strip()

    return description, ", ".join(technology_parts)


def normalise_kind(c4_type: str | None, style: str) -> tuple[str, bool]:
    """Map a draw.io type/style to a C4 abstraction. Returns (kind, is_external)."""
    if c4_type:
        key = c4_type.strip().lower()
        external = key.startswith("external")
        if key in C4_TYPE_ALIASES:
            return C4_TYPE_ALIASES[key], external
        for alias, kind in C4_TYPE_ALIASES.items():
            if alias in key:
                return kind, external
    lowered = (style or "").lower()
    for needle, kind in STYLE_TYPE_HINTS:
        if needle in lowered:
            return kind, False
    return "unknown", False


# --- parsing ---------------------------------------------------------------


def _geometry(mxcell: ElementTree.Element) -> tuple[float, float, float, float]:
    geo = mxcell.find("mxGeometry")
    if geo is None:
        return 0.0, 0.0, 0.0, 0.0
    return (
        float(geo.get("x", 0) or 0),
        float(geo.get("y", 0) or 0),
        float(geo.get("width", 0) or 0),
        float(geo.get("height", 0) or 0),
    )


def _endpoint(mxcell: ElementTree.Element, which: str) -> tuple[float, float] | None:
    geo = mxcell.find("mxGeometry")
    if geo is None:
        return None
    for point in geo.findall("mxPoint"):
        if point.get("as") == f"{which}Point":
            return float(point.get("x", 0) or 0), float(point.get("y", 0) or 0)
    return None


def parse_page(diagram_name: str, model: ElementTree.Element):
    """Extract shapes, raw edges and label carriers from one page."""
    shapes: dict[str, Shape] = {}
    edges: list[tuple[str, ElementTree.Element, ElementTree.Element]] = []
    edge_labels: dict[str, list[str]] = {}
    parent_of: dict[str, str] = {}

    for node in model.iter():
        if node.tag == "object":
            mxcell = node.find("mxCell")
            if mxcell is None:
                continue
            attributes = node.attrib
            label_source = node
        elif node.tag == "mxCell":
            # Skip cells already handled as an <object> wrapper's child.
            if node.get("id") is None:
                continue
            mxcell = node
            attributes = node.attrib
            label_source = node
        else:
            continue

        cell_id = attributes.get("id") or mxcell.get("id")
        if not cell_id or cell_id in ("0", "1"):
            continue

        style = mxcell.get("style", "") or ""
        parent = mxcell.get("parent")
        if parent:
            parent_of[cell_id] = parent

        if mxcell.get("edge") == "1":
            edges.append((cell_id, label_source, mxcell))
            continue

        raw_value = attributes.get("value") or mxcell.get("value") or ""
        # A vertex with connectable=0 or an edgeLabel style is a connector caption.
        if "edgelabel" in style.lower() or (
            mxcell.get("vertex") == "1" and mxcell.get("connectable") == "0"
        ):
            caption = clean_label(raw_value)
            if caption and parent:
                edge_labels.setdefault(parent, []).append(caption)
            continue

        if mxcell.get("vertex") != "1":
            continue

        c4_name = attributes.get("c4Name")
        name = clean_label(c4_name or raw_value)
        if not name:
            continue

        kind, external = normalise_kind(attributes.get("c4Type"), style)
        x, y, width, height = _geometry(mxcell)
        shapes[cell_id] = Shape(
            id=cell_id,
            name=name,
            kind=kind,
            description=clean_label(attributes.get("c4Description") or ""),
            technology=clean_label(attributes.get("c4Technology") or ""),
            diagram=diagram_name,
            external=external,
            x=x,
            y=y,
            width=width,
            height=height,
            boundary_kind=(attributes.get("c4Type") or "").strip() if kind == "boundary" else "",
            from_c4_library=bool(c4_name),
        )

    _absolutise(shapes, parent_of)
    return shapes, edges, edge_labels


def _absolutise(shapes: dict[str, Shape], parent_of: dict[str, str]) -> None:
    """draw.io child coordinates are parent-relative; make them absolute."""
    for shape in shapes.values():
        offset_x = offset_y = 0.0
        parent = parent_of.get(shape.id)
        guard = 0
        while parent and parent in shapes and guard < 20:
            offset_x += shapes[parent].x
            offset_y += shapes[parent].y
            parent = parent_of.get(parent)
            guard += 1
        shape.x += offset_x
        shape.y += offset_y


def infer_endpoint(
    point: tuple[float, float] | None, candidates: list[Shape]
) -> tuple[str | None, str, str]:
    """Resolve a dangling connector end by proximity.

    Returns (shape_id, confidence, note). Refuses to guess when two shapes are
    similarly close -- a wrong relationship is worse than a flagged one.
    """
    if point is None:
        return None, "unresolved", "connector end has no coordinates"
    if not candidates:
        return None, "unresolved", "no candidate shapes on this page"

    ranked = sorted(((shape.distance_to(*point), shape) for shape in candidates), key=lambda r: r[0])
    best_distance, best = ranked[0]

    if best_distance > MAX_INFERENCE_DISTANCE_PX:
        return None, "unresolved", f"nearest shape '{best.name}' is {best_distance:.0f}px away"

    runner_up_distance = ranked[1][0] if len(ranked) > 1 else float("inf")

    if best_distance <= TOUCHING_DISTANCE_PX:
        return best.id, "high", f"endpoint touches '{best.name}' ({best_distance:.1f}px)"

    if runner_up_distance >= best_distance * AMBIGUITY_RATIO:
        return (
            best.id,
            "medium",
            f"nearest is '{best.name}' ({best_distance:.0f}px), "
            f"next is {runner_up_distance:.0f}px away",
        )

    return (
        None,
        "unresolved",
        f"ambiguous: '{best.name}' at {best_distance:.0f}px vs "
        f"'{ranked[1][1].name}' at {runner_up_distance:.0f}px",
    )


#: The C4 levels a complete conversion must cover, in order.
REQUIRED_LEVELS = ("context", "container", "component")


def classify_level(shapes: list[Shape]) -> str:
    """Name the C4 level a page describes, from the most detailed shape on it.

    A page holding components is a component diagram even though it also shows
    the surrounding containers and systems for context.
    """
    kinds = {shape.kind for shape in shapes}
    if "component" in kinds:
        return "component"
    if "container" in kinds:
        return "container"
    if kinds & {"softwareSystem", "person"}:
        return "context"
    return "unknown"


def check_level_coverage(diagrams: list[dict], flags: list[Flag]) -> None:
    """Require all three C4 levels. A missing level is a blocker, not a warning.

    The whole point of C4 is the set of complementary views; a workspace missing
    a level is incomplete rather than merely sparse. Reporting it as a blocker
    stops a caller from quietly shipping two views out of three.
    """
    found = {diagram["level"] for diagram in diagrams}
    for level in REQUIRED_LEVELS:
        if level not in found:
            flags.append(
                Flag(
                    "blocker",
                    f"missing-level-{level}",
                    "(input set)",
                    f"No {level} diagram was found among the inputs.",
                    f"A complete C4 workspace needs all of {', '.join(REQUIRED_LEVELS)}. "
                    f"Add the {level} diagram, or state explicitly that the output is "
                    f"partial -- do not invent the missing level.",
                )
            )

    for level in sorted(found - set(REQUIRED_LEVELS)):
        if level == "unknown":
            flags.append(
                Flag("warning", "unclassified-diagram", "(input set)",
                     "A page's C4 level could not be determined from its shapes.",
                     "It may use plain shapes instead of the C4 library.")
            )


def check_component_wiring(shapes: dict[str, Shape], relationships: list[Relationship],
                           flags: list[Flag]) -> None:
    """Flag modelled elements nothing connects to.

    An element drawn but never wired is usually an unfinished thought. It is
    legal C4, so this is a warning -- but it is worth a human's attention.
    """
    connected: set[tuple[str, str]] = set()
    for relationship in relationships:
        for endpoint in (relationship.source, relationship.target):
            if endpoint:
                connected.add((relationship.diagram, endpoint))

    for key, shape in shapes.items():
        diagram, _, shape_id = key.partition("::")
        if shape.kind == "boundary":
            continue
        if (diagram, shape_id) not in connected:
            flags.append(
                Flag("warning", "orphan-element", diagram,
                     f"{shape.kind} '{shape.name}' has no relationships on this diagram.",
                     "Either it is unused, or a connector to it was never attached.")
            )


def extract(paths: list[Path]):
    all_shapes: dict[str, Shape] = {}
    all_relationships: list[Relationship] = []
    flags: list[Flag] = []
    diagrams: list[dict] = []

    for path in paths:
        pages = load_diagrams(path)
        if not pages:
            flags.append(
                Flag("blocker", "unreadable-file", path.name, f"Could not parse '{path.name}'.",
                     "Re-export it from draw.io as .drawio (XML) and retry.")
            )
            continue

        for page_name, model in pages:
            diagram_label = f"{path.name}"
            shapes, edges, edge_labels = parse_page(diagram_label, model)

            real_shapes = [s for s in shapes.values() if s.kind != "boundary"]
            boundaries = [s for s in shapes.values() if s.kind == "boundary"]

            diagrams.append(
                {
                    "file": path.name,
                    "page": page_name,
                    "shapes": len(real_shapes),
                    "boundaries": len(boundaries),
                    "connectors": len(edges),
                    "level": classify_level(real_shapes),
                }
            )

            if not real_shapes and not edges:
                flags.append(
                    Flag("blocker", "empty-diagram", diagram_label,
                         f"'{path.name}' (page '{page_name}') contains no shapes or connectors.",
                         "Nothing can be generated from it. Draw the diagram, or drop this level "
                         "from the conversion.")
                )
                continue

            # Boundary membership by geometry: draw.io does not nest these as
            # XML children, so containment is positional. Boundaries themselves
            # nest (a ContainerScopeBoundary inside a SystemScopeBoundary), so
            # take the SMALLEST enclosing one -- that is the direct parent.
            for shape in real_shapes:
                enclosing = [b for b in boundaries if b.contains(shape)]
                if enclosing:
                    innermost = min(enclosing, key=lambda b: b.area)
                    shape.parent_boundary = innermost.name
                    shape.boundary_kind = innermost.boundary_kind

            for shape in real_shapes:
                if shape.kind == "unknown":
                    flags.append(
                        Flag("warning", "untyped-shape", diagram_label,
                             f"Shape '{shape.name}' has no recognisable C4 type.",
                             "It was drawn with a plain shape instead of the C4 library. "
                             "Confirm whether it is a person, system, container or component.")
                    )
                lowered_description = shape.description.lower()
                if lowered_description and any(
                    m in lowered_description for m in PLACEHOLDER_DESCRIPTION_MARKERS
                ):
                    shape.description = ""
                    flags.append(
                        Flag("warning", "placeholder-description", diagram_label,
                             f"{shape.kind} '{shape.name}' still carries draw.io's prompt text "
                             f"in its description field.",
                             "Treated as missing. Do not copy it into the DSL; derive the "
                             "responsibility from the element's relationships and say so, "
                             "or ask the author.")
                    )

                if shape.kind in ("container", "component"):
                    lowered_technology = shape.technology.lower()
                    if not shape.technology:
                        flags.append(
                            Flag("warning", "missing-technology", diagram_label,
                                 f"{shape.kind} '{shape.name}' declares no technology.",
                                 "C4 asks every container and component to state its technology.")
                        )
                    elif any(m in lowered_technology for m in PLACEHOLDER_TECHNOLOGY_MARKERS):
                        shape.technology = ""
                        flags.append(
                            Flag("warning", "placeholder-technology", diagram_label,
                                 f"{shape.kind} '{shape.name}' still carries draw.io's example "
                                 f"technology text, which is not a real choice.",
                                 "Treated as missing. Ask the user for the actual technology "
                                 "instead of copying the placeholder into the DSL.")
                        )
                all_shapes.setdefault(f"{diagram_label}::{shape.id}", shape)

            candidates = real_shapes
            for edge_id, label_node, mxcell in edges:
                label = clean_label(
                    label_node.get("c4Description")
                    or label_node.get("value")
                    or mxcell.get("value")
                    or ""
                )
                for caption in edge_labels.get(edge_id, []):
                    label = f"{label}\n{caption}" if label else caption

                description, technology = split_description_and_technology(label)
                technology = technology or clean_label(label_node.get("c4Technology") or "")

                source_id, target_id = mxcell.get("source"), mxcell.get("target")
                relationship = Relationship(
                    id=edge_id,
                    diagram=diagram_label,
                    source=source_id,
                    target=target_id,
                    description=description,
                    technology=technology,
                )

                worst = "certain"
                for which, attribute in (("source", source_id), ("target", target_id)):
                    if attribute and attribute in shapes:
                        continue
                    guessed, confidence, note = infer_endpoint(
                        _endpoint(mxcell, which), candidates
                    )
                    setattr(relationship, which, guessed)
                    setattr(relationship, f"{which}_inferred", True)
                    relationship.notes.append(f"{which}: {note}")
                    order = ["certain", "high", "medium", "unresolved"]
                    if order.index(confidence) > order.index(worst):
                        worst = confidence
                relationship.confidence = worst

                if not relationship.description:
                    flags.append(
                        Flag("warning", "unlabelled-connector", diagram_label,
                             f"Connector {edge_id} has no label.",
                             "C4 requires a specific label describing intent. "
                             "Generic words like 'Uses' do not qualify.")
                    )

                if worst == "unresolved":
                    endpoints = " / ".join(relationship.notes)
                    flags.append(
                        Flag("blocker", "unresolved-connector", diagram_label,
                             f"Connector {edge_id} "
                             f"(label: {relationship.description or 'none'!r}) "
                             f"could not be attached to shapes. {endpoints}",
                             "Open the diagram and reattach both ends, then re-run.")
                    )
                elif worst in ("high", "medium"):
                    flags.append(
                        Flag("info", "inferred-connector", diagram_label,
                             f"Connector {edge_id} was not attached in draw.io; "
                             f"endpoints inferred from geometry ({worst} confidence). "
                             f"{' / '.join(relationship.notes)}",
                             "Verify this relationship is what you intended.")
                    )

                all_relationships.append(relationship)

    _reconcile_across_diagrams(all_shapes, flags)
    check_level_coverage(diagrams, flags)
    check_component_wiring(all_shapes, all_relationships, flags)
    return diagrams, all_shapes, all_relationships, flags


def _reconcile_across_diagrams(shapes: dict[str, Shape], flags: list[Flag]) -> None:
    """Cross-check the same element appearing on several diagrams.

    A frequent modelling slip: an external system is drawn as a Container on the
    container diagram. If it sits outside the system boundary and is a Software
    System elsewhere, it is external -- not a container of this system.
    """
    by_name: dict[str, list[Shape]] = {}
    for shape in shapes.values():
        by_name.setdefault(shape.name.strip().lower(), []).append(shape)

    for name, group in by_name.items():
        kinds = {shape.kind for shape in group}
        if len(kinds) > 1:
            display = group[0].name
            flags.append(
                Flag("warning", "inconsistent-type", ", ".join(sorted({s.diagram for s in group})),
                     f"'{display}' is typed differently across diagrams: {sorted(kinds)}.",
                     "Usually means an external system was drawn as a Container. "
                     "The System Context diagram is the authority on what is external.")
            )
        for shape in group:
            if shape.kind == "container" and shape.parent_boundary is None:
                flags.append(
                    Flag("warning", "container-outside-boundary", shape.diagram,
                         f"Container '{shape.name}' sits outside every system boundary.",
                         "A container must live inside a software system. If it is a "
                         "third party, model it as an external softwareSystem instead.")
                )


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract a C4 model from draw.io files.")
    parser.add_argument("files", nargs="+", type=Path)
    parser.add_argument("--json", type=Path, help="write JSON here instead of stdout")
    parser.add_argument("--quiet", action="store_true", help="suppress the human summary")
    args = parser.parse_args()

    existing = [path for path in args.files if path.exists()]
    for missing in set(args.files) - set(existing):
        print(f"warning: no such file: {missing}", file=sys.stderr)
    if not existing:
        print("error: no readable input files", file=sys.stderr)
        return 2

    diagrams, shapes, relationships, flags = extract(existing)

    def shape_ref(key: str | None, diagram: str) -> str | None:
        if key is None:
            return None
        shape = shapes.get(f"{diagram}::{key}")
        return shape.name if shape else None

    document = {
        "diagrams": diagrams,
        "elements": [
            {**asdict(shape), "key": key} for key, shape in sorted(shapes.items())
        ],
        "relationships": [
            {
                **asdict(relationship),
                "source_name": shape_ref(relationship.source, relationship.diagram),
                "target_name": shape_ref(relationship.target, relationship.diagram),
            }
            for relationship in relationships
        ],
        "flags": [asdict(flag) for flag in flags],
        "summary": {
            "diagrams": len(diagrams),
            "elements": len(shapes),
            "relationships": len(relationships),
            "blockers": sum(1 for f in flags if f.severity == "blocker"),
            "warnings": sum(1 for f in flags if f.severity == "warning"),
            "levels_found": sorted({d["level"] for d in diagrams}),
            "levels_missing": [
                level for level in REQUIRED_LEVELS
                if level not in {d["level"] for d in diagrams}
            ],
        },
    }

    payload = json.dumps(document, indent=2, ensure_ascii=False)
    if args.json:
        args.json.write_text(payload + "\n", encoding="utf-8")
    else:
        print(payload)

    if not args.quiet:
        stream = sys.stderr
        summary = document["summary"]
        print(
            f"\n{summary['elements']} elements, {summary['relationships']} relationships, "
            f"{summary['blockers']} blockers, {summary['warnings']} warnings",
            file=stream,
        )
        for flag in flags:
            print(f"  [{flag.severity}] {flag.code}: {flag.message}", file=stream)

    return 0


if __name__ == "__main__":
    sys.exit(main())
