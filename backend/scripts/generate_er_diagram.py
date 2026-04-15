from __future__ import annotations

import argparse
import math
from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path

import pydot
from PIL import Image, ImageDraw, ImageFont

from _bootstrap import ensure_backend_on_path


backend_dir, REPO_ROOT = ensure_backend_on_path()

from app.models import Base  # noqa: E402


BG = "#f8fbff"
ENTITY_FILL = "#ffffff"
ENTITY_BORDER = "#1f4f82"
ATTR_FILL = "#f7fafc"
ATTR_BORDER = "#5d7288"
REL_FILL = "#e7f0fb"
REL_BORDER = "#1f4f82"
TEXT = "#23364a"
TITLE = "#0f2740"
SUB = "#5d7288"
KEY = "#8b1e3f"
EDGE = "#6d879f"
LABEL_FILL = "#ffffff"
LABEL_BORDER = "#c5d4e2"

TITLE_TOP = 30
CONTENT_TOP = 110
MARGIN_X = 56
MARGIN_BOTTOM = 44
LEVEL_GAP = 180
ENTITY_GAP = 110
ATTR_TOP_GAP = 38
ATTR_ROW_GAP = 18
ATTR_COL_GAP = 28
ENTITY_W_MIN = 170
ENTITY_H = 58
ATTR_W_MIN = 170
ATTR_H = 36
REL_W = 120
REL_H = 58


@dataclass(frozen=True)
class Attr:
    name: str
    type_name: str
    is_key: bool
    is_fk: bool
    nullable: bool

    @property
    def label(self) -> str:
        flags: list[str] = []
        if self.is_key:
            flags.append("PK")
        if self.is_fk:
            flags.append("FK")
        if not self.nullable:
            flags.append("NN")
        prefix = f"[{', '.join(flags)}] " if flags else ""
        return f"{prefix}{self.name}: {self.type_name}"


@dataclass(frozen=True)
class Entity:
    name: str
    attrs: tuple[Attr, ...]


@dataclass(frozen=True)
class Relation:
    name: str
    left: str
    right: str
    left_card: str
    right_card: str


@dataclass(frozen=True)
class EntityBox:
    entity: Entity
    x: int
    y: int
    w: int
    h: int
    attr_w: int
    attr_cols: int
    footprint_h: int

    @property
    def cx(self) -> int:
        return self.x + self.w // 2

    @property
    def cy(self) -> int:
        return self.y + self.h // 2

    @property
    def right(self) -> int:
        return self.x + self.w

    @property
    def bottom(self) -> int:
        return self.y + self.h


@dataclass(frozen=True)
class AttrBox:
    entity_name: str
    attr: Attr
    x: int
    y: int
    w: int
    h: int

    @property
    def cx(self) -> int:
        return self.x + self.w // 2

    @property
    def cy(self) -> int:
        return self.y + self.h // 2


@dataclass(frozen=True)
class RelBox:
    rel: Relation
    cx: int
    cy: int

    @property
    def points(self) -> tuple[tuple[int, int], ...]:
        return (
            (self.cx, self.cy - REL_H // 2),
            (self.cx + REL_W // 2, self.cy),
            (self.cx, self.cy + REL_H // 2),
            (self.cx - REL_W // 2, self.cy),
        )


def args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Generate a Chen-style ER diagram with pydot.")
    p.add_argument("--output-stem", default="project-er-diagram")
    p.add_argument("--title", default="Graduation Project ER Diagram")
    return p.parse_args()


def font(size: int, bold: bool = False):
    for path in [
        Path("C:/Windows/Fonts/msyhbd.ttc" if bold else "C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/simhei.ttf"),
        Path("C:/Windows/Fonts/simsun.ttc"),
        Path("C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf"),
        Path("C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf"),
    ]:
        if path.exists():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


F_TITLE = font(24, True)
F_SUB = font(13)
F_ENTITY = font(17, True)
F_REL = font(15, True)
F_ATTR = font(12)
F_CARD = font(11, True)


def text_size(text: str, f) -> tuple[int, int]:
    left, top, right, bottom = f.getbbox(text)
    return right - left, bottom - top


def unique_cols(table, cols: tuple[str, ...]) -> bool:
    target = set(cols)
    if target == {c.name for c in table.primary_key.columns}:
        return True
    for c in table.constraints:
        if c.__class__.__name__ == "UniqueConstraint" and {col.name for col in c.columns} == target:
            return True
    for idx in table.indexes:
        if idx.unique and {col.name for col in idx.columns} == target:
            return True
    return False


REL_LABELS = {
    ("users", "import_runs", ("owner_user_id",)): "拥有",
    ("import_runs", "import_manifests", ("import_run_id",)): "生成清单",
    ("import_runs", "trading_records", ("import_run_id",)): "包含记录",
    ("import_runs", "import_artifacts", ("import_run_id",)): "关联产物",
    ("import_manifests", "import_artifacts", ("manifest_id",)): "产出产物",
}


def rel_name(child: str, cols: tuple[str, ...]) -> str:
    if cols:
        return "/".join(col.removesuffix("_id") for col in cols)
    return f"{child}_rel"


def rel_label(parent: str, child: str, cols: tuple[str, ...]) -> str:
    exact = REL_LABELS.get((parent, child, cols))
    if exact is not None:
        return exact
    if cols:
        return cols[0].removesuffix("_id")
    return rel_name(child, cols)


def dot_id(*parts: str) -> str:
    safe_parts = []
    for part in parts:
        safe = []
        for ch in part:
            safe.append(ch if ch.isalnum() else "_")
        safe_parts.append("".join(safe))
    return "__".join(safe_parts)


def schema() -> tuple[list[Entity], list[Relation]]:
    entities: list[Entity] = []
    relations: list[Relation] = []

    for table in sorted(Base.metadata.tables.values(), key=lambda t: t.fullname):
        attrs = [
            Attr(col.name, str(col.type), bool(col.primary_key), bool(col.foreign_keys), bool(col.nullable))
            for col in table.columns
        ]
        attrs.sort(key=lambda a: (0 if a.is_key else 1, 0 if a.is_fk else 1, a.name))
        entities.append(Entity(table.fullname, tuple(attrs)))

    for table in sorted(Base.metadata.tables.values(), key=lambda t: t.fullname):
        for fk in table.foreign_key_constraints:
            parent = next(iter(fk.elements)).column.table.fullname
            cols = tuple(elem.parent.name for elem in fk.elements)
            relations.append(
                Relation(
                    rel_label(parent, table.fullname, cols),
                    parent,
                    table.fullname,
                    "1",
                    "1" if unique_cols(table, cols) else "N",
                )
            )
    relations.sort(key=lambda r: (r.left, r.right, r.name))
    return entities, relations


def levels(names: list[str], relations: list[Relation]) -> dict[str, int]:
    children: dict[str, set[str]] = defaultdict(set)
    indegree = {name: 0 for name in names}
    for rel in relations:
        if rel.right not in children[rel.left]:
            children[rel.left].add(rel.right)
            indegree[rel.right] += 1
    q = deque(sorted(name for name, deg in indegree.items() if deg == 0))
    out = {name: 0 for name in q}
    while q:
        cur = q.popleft()
        for child in sorted(children[cur]):
            out[child] = max(out.get(child, 0), out[cur] + 1)
            indegree[child] -= 1
            if indegree[child] == 0:
                q.append(child)
    for name in names:
        out.setdefault(name, 0)
    return out


def dims(entity: Entity) -> tuple[int, int, int, int]:
    ew = max(ENTITY_W_MIN, text_size(entity.name, F_ENTITY)[0] + 42)
    aw = max(ATTR_W_MIN, max((text_size(attr.label, F_ATTR)[0] + 28 for attr in entity.attrs), default=ATTR_W_MIN))
    cols = 1 if len(entity.attrs) <= 8 else 2
    rows = max(1, math.ceil(len(entity.attrs) / cols))
    fh = ENTITY_H + ATTR_TOP_GAP + rows * ATTR_H + max(0, rows - 1) * ATTR_ROW_GAP
    return ew, aw, cols, fh


def build_layout(title: str, entities: list[Entity], relations: list[Relation]):
    subtitle = "Chen notation via pydot"
    lv = levels([e.name for e in entities], relations)
    by_level: dict[int, list[Entity]] = defaultdict(list)
    for entity in entities:
        by_level[lv[entity.name]].append(entity)
    order = sorted(by_level)
    dm = {e.name: dims(e) for e in entities}
    level_w = {k: max(max(dm[e.name][0], dm[e.name][1] * dm[e.name][2] + ATTR_COL_GAP * (dm[e.name][2] - 1)) for e in v) for k, v in by_level.items()}
    level_h = {k: sum(dm[e.name][3] for e in v) + ENTITY_GAP * max(0, len(v) - 1) for k, v in by_level.items()}
    max_h = max(level_h.values(), default=0)

    x_map: dict[int, int] = {}
    cursor = MARGIN_X
    for level in order:
        x_map[level] = cursor
        cursor += level_w[level] + LEVEL_GAP

    title_h = text_size(title, F_TITLE)[1]
    sub_h = text_size(subtitle, F_SUB)[1]
    top = CONTENT_TOP + title_h + sub_h // 2

    entity_boxes: list[EntityBox] = []
    attr_boxes: list[AttrBox] = []
    for level in order:
        y = top + max(0, (max_h - level_h[level]) // 2)
        for entity in sorted(by_level[level], key=lambda e: e.name):
            ew, aw, cols, fh = dm[entity.name]
            ex = x_map[level] + (level_w[level] - ew) // 2
            entity_boxes.append(EntityBox(entity, ex, y, ew, ENTITY_H, aw, cols, fh))
            grid_w = cols * aw + (cols - 1) * ATTR_COL_GAP
            gx = x_map[level] + (level_w[level] - grid_w) // 2
            ay = y + ENTITY_H + ATTR_TOP_GAP
            for i, attr in enumerate(entity.attrs):
                col = i % cols
                row = i // cols
                attr_boxes.append(AttrBox(entity.name, attr, gx + col * (aw + ATTR_COL_GAP), ay + row * (ATTR_H + ATTR_ROW_GAP), aw, ATTR_H))
            y += fh + ENTITY_GAP

    e_lookup = {box.entity.name: box for box in entity_boxes}
    grouped: dict[tuple[str, str], list[Relation]] = defaultdict(list)
    for rel in relations:
        grouped[(rel.left, rel.right)].append(rel)
    rel_index: dict[tuple[str, str], int] = defaultdict(int)
    rel_boxes: list[RelBox] = []
    for rel in relations:
        pair = (rel.left, rel.right)
        idx = rel_index[pair]
        rel_index[pair] += 1
        count = len(grouped[pair])
        offset = 0 if count == 1 else int((idx - (count - 1) / 2) * 52)
        left = e_lookup[rel.left]
        right = e_lookup[rel.right]
        rel_boxes.append(RelBox(rel, (left.cx + right.cx) // 2, (left.cy + right.cy) // 2 + offset))

    width = cursor - LEVEL_GAP + MARGIN_X
    height = top + max_h + MARGIN_BOTTOM
    return subtitle, width, height, tuple(entity_boxes), tuple(attr_boxes), tuple(rel_boxes)


def p_rect(cx: int, cy: int, hw: int, hh: int, tx: int, ty: int) -> tuple[int, int]:
    dx, dy = tx - cx, ty - cy
    if abs(dx) * hh > abs(dy) * hw:
        x = cx + (hw if dx > 0 else -hw)
        y = cy if dx == 0 else cy + int(dy * (hw / abs(dx)))
    else:
        y = cy + (hh if dy > 0 else -hh)
        x = cx if dy == 0 else cx + int(dx * (hh / abs(dy)))
    return x, y


def p_diamond(box: RelBox, tx: int, ty: int) -> tuple[int, int]:
    dx, dy = tx - box.cx, ty - box.cy
    scale = 1 / ((abs(dx) / (REL_W / 2)) + (abs(dy) / (REL_H / 2)))
    return box.cx + int(dx * scale), box.cy + int(dy * scale)


def path(a: tuple[int, int], b: tuple[int, int]) -> tuple[tuple[int, int], ...]:
    if a[0] == b[0] or a[1] == b[1]:
        return a, b
    mx = (a[0] + b[0]) // 2
    return a, (mx, a[1]), (mx, b[1]), b


def card(draw: ImageDraw.ImageDraw, text: str, x: int, y: int) -> None:
    tw, th = text_size(text, F_CARD)
    draw.rounded_rectangle((x - 6, y - 3, x + tw + 6, y + th + 3), radius=8, fill=LABEL_FILL, outline=LABEL_BORDER, width=1)
    draw.text((x, y - 1), text, font=F_CARD, fill=TEXT)


def write_png(title: str, subtitle: str, width: int, height: int, entities: tuple[EntityBox, ...], attrs: tuple[AttrBox, ...], rels: tuple[RelBox, ...], out: Path) -> None:
    image = Image.new("RGB", (width, height), BG)
    draw = ImageDraw.Draw(image)
    e_lookup = {e.entity.name: e for e in entities}
    a_group: dict[str, list[AttrBox]] = defaultdict(list)
    for attr in attrs:
        a_group[attr.entity_name].append(attr)

    draw.text((MARGIN_X, TITLE_TOP), title, font=F_TITLE, fill=TITLE)
    draw.text((MARGIN_X, TITLE_TOP + text_size(title, F_TITLE)[1] + 12), subtitle, font=F_SUB, fill=SUB)

    for rel in rels:
        left = e_lookup[rel.rel.left]
        right = e_lookup[rel.rel.right]
        a1 = p_rect(left.cx, left.cy, left.w // 2, left.h // 2, rel.cx, rel.cy)
        a2 = p_rect(right.cx, right.cy, right.w // 2, right.h // 2, rel.cx, rel.cy)
        d1 = p_diamond(rel, a1[0], a1[1])
        d2 = p_diamond(rel, a2[0], a2[1])
        draw.line(path(a1, d1), fill=EDGE, width=3, joint="curve")
        draw.line(path(d2, a2), fill=EDGE, width=3, joint="curve")
        card(draw, rel.rel.left_card, (a1[0] + d1[0]) // 2 - 12, (a1[1] + d1[1]) // 2 - 18)
        card(draw, rel.rel.right_card, (a2[0] + d2[0]) // 2 - 12, (a2[1] + d2[1]) // 2 - 18)

    for entity in entities:
        for attr in a_group[entity.entity.name]:
            draw.line(path((entity.cx, entity.bottom), (attr.cx, attr.y)), fill=EDGE, width=2, joint="curve")

    for rel in rels:
        draw.polygon(rel.points, fill=REL_FILL, outline=REL_BORDER, width=2)
        tw, th = text_size(rel.rel.name, F_REL)
        draw.text((rel.cx - tw // 2, rel.cy - th // 2 - 1), rel.rel.name, font=F_REL, fill=TITLE)

    for entity in entities:
        draw.rounded_rectangle((entity.x, entity.y, entity.x + entity.w, entity.y + entity.h), radius=14, fill=ENTITY_FILL, outline=ENTITY_BORDER, width=2)
        tw, th = text_size(entity.entity.name, F_ENTITY)
        draw.text((entity.cx - tw // 2, entity.cy - th // 2 - 1), entity.entity.name, font=F_ENTITY, fill=TITLE)

    for attr in attrs:
        outline = KEY if attr.attr.is_key else ATTR_BORDER
        draw.ellipse((attr.x, attr.y, attr.x + attr.w, attr.y + attr.h), fill=ATTR_FILL, outline=outline, width=2 if attr.attr.is_key else 1)
        tw, th = text_size(attr.attr.label, F_ATTR)
        tx = attr.cx - tw // 2
        ty = attr.cy - th // 2 - 1
        draw.text((tx, ty), attr.attr.label, font=F_ATTR, fill=TEXT)
        if attr.attr.is_key:
            draw.line((tx, ty + th + 1, tx + tw, ty + th + 1), fill=KEY, width=1)

    draw.text((MARGIN_X, height - 24), "Chen ER: rectangle=entity, oval=attribute, diamond=relationship", font=F_SUB, fill=SUB)
    image.save(out)


def write_dot(entities: list[Entity], relations: list[Relation], out: Path, title: str) -> None:
    graph = pydot.Dot("graduation_project_er_chen", graph_type="graph", rankdir="LR", splines="ortho", bgcolor=BG, label=title, labelloc="t", labeljust="l", fontname="Segoe UI", fontsize="24", fontcolor=TITLE)
    for entity in entities:
        entity_id = dot_id("entity", entity.name)
        graph.add_node(pydot.Node(entity_id, label=entity.name, shape="box", style="rounded,filled", fillcolor=ENTITY_FILL, color=ENTITY_BORDER, penwidth="2", fontname="Segoe UI", fontsize="16", fontcolor=TITLE))
        for attr in entity.attrs:
            aid = dot_id("attr", entity.name, attr.name)
            graph.add_node(pydot.Node(aid, label=attr.label, shape="ellipse", style="filled", fillcolor=ATTR_FILL, color=KEY if attr.is_key else ATTR_BORDER, penwidth="2" if attr.is_key else "1", fontname="Segoe UI", fontsize="11", fontcolor=TEXT))
            graph.add_edge(pydot.Edge(entity_id, aid, color=EDGE, penwidth="1.5"))
    for rel in relations:
        rid = dot_id("rel", rel.left, rel.name, rel.right)
        left_id = dot_id("entity", rel.left)
        right_id = dot_id("entity", rel.right)
        graph.add_node(pydot.Node(rid, label=rel.name, shape="diamond", style="filled", fillcolor=REL_FILL, color=REL_BORDER, penwidth="2", fontname="Segoe UI", fontsize="13", fontcolor=TITLE))
        graph.add_edge(pydot.Edge(left_id, rid, color=EDGE, penwidth="2", headlabel=rel.left_card, fontname="Segoe UI", fontsize="11", fontcolor=TEXT))
        graph.add_edge(pydot.Edge(rid, right_id, color=EDGE, penwidth="2", headlabel=rel.right_card, fontname="Segoe UI", fontsize="11", fontcolor=TEXT))
    graph.write_raw(str(out), encoding="utf-8")


def main() -> int:
    cli = args()
    entities, relations = schema()
    subtitle, width, height, entity_boxes, attr_boxes, rel_boxes = build_layout(cli.title, entities, relations)
    out_dir = REPO_ROOT / "images"
    out_dir.mkdir(parents=True, exist_ok=True)
    dot_path = out_dir / f"{cli.output_stem}.dot"
    png_path = out_dir / f"{cli.output_stem}.png"
    write_dot(entities, relations, dot_path, cli.title)
    write_png(cli.title, subtitle, width, height, entity_boxes, attr_boxes, rel_boxes, png_path)
    print(f"DOT ER diagram written to: {dot_path}")
    print(f"PNG ER diagram written to: {png_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
