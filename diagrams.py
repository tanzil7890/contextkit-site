"""Diagrams for the docs, drawn as inline SVG when the site is built.

A docs page includes one with a line of its own:

    <!-- diagram: add-decision -->

Each diagram below is a function that draws on a `Fig` and returns it. Colours
come from the `.dg` rules in static/site.css, so diagrams follow the light and
dark themes. The colour language matches the landing page's flows:

    orange outline  an LLM call          (kind="ai")
    blue outline    a scope or policy check (kind="check")
    green outline   what is stored or returned (kind="out")
    dashed          optional, or not connected (kind="opt" / kind="off")
"""
from __future__ import annotations

from dataclasses import dataclass
from html import escape

# Rough advance widths, used only to warn when a label will not fit its box.
CHAR_W = {"t": 7.5, "s": 6.0, "lbl": 6.0, "": 6.6}


@dataclass
class Box:
    x: float
    y: float
    w: float
    h: float

    @property
    def cx(self) -> float:
        return self.x + self.w / 2

    @property
    def cy(self) -> float:
        return self.y + self.h / 2

    @property
    def l(self) -> tuple[float, float]:  # noqa: E743
        return (self.x, self.cy)

    @property
    def r(self) -> tuple[float, float]:
        return (self.x + self.w, self.cy)

    @property
    def t(self) -> tuple[float, float]:
        return (self.cx, self.y)

    @property
    def b(self) -> tuple[float, float]:
        return (self.cx, self.y + self.h)

    def at(self, side: str, frac: float) -> tuple[float, float]:
        """A point on a side, `frac` of the way along it (0 = left/top)."""
        if side == "t":
            return (self.x + self.w * frac, self.y)
        if side == "b":
            return (self.x + self.w * frac, self.y + self.h)
        if side == "l":
            return (self.x, self.y + self.h * frac)
        return (self.x + self.w, self.y + self.h * frac)


class Fig:
    def __init__(self, name: str, width: int, height: int, label: str, caption: str):
        self.name, self.w, self.h = name, width, height
        self.label, self.caption = label, caption
        self.parts: list[str] = []
        self.warnings: list[str] = []

    # ---- primitives

    def text(self, x, y, s, cls="", anchor="start"):
        attr = f' class="{cls}"' if cls else ""
        self.parts.append(f'<text x="{x:g}" y="{y:g}" text-anchor="{anchor}"{attr}>{escape(s)}</text>')

    def _fits(self, s: str, cls: str, width: float):
        if len(s) * CHAR_W.get(cls, 6.6) > width - 10:
            self.warnings.append(f"{self.name}: {s!r} may not fit in {width:g}px")

    def node(self, x, y, w, h, title, sub=None, kind="", sub2=None) -> Box:
        cls = " ".join(["n"] + kind.split())
        self.parts.append(f'<rect class="{cls}" x="{x:g}" y="{y:g}" width="{w:g}" height="{h:g}" rx="7"/>')
        lines = [(title, "t")] + [(s, "s") for s in (sub, sub2) if s]
        gap = 15
        top = y + h / 2 - (len(lines) - 1) * gap / 2 + 4
        for i, (s, c) in enumerate(lines):
            self._fits(s, c, w)
            self.text(x + w / 2, top + i * gap, s, c, "middle")
        return Box(x, y, w, h)

    def store(self, x, y, w, h, title, sub=None, kind="") -> Box:
        """A cylinder: somewhere data stays."""
        ry = 6
        cls = " ".join(["n", "store"] + kind.split())
        self.parts.append(
            f'<path class="{cls}" d="M{x:g},{y + ry:g} a{w / 2:g},{ry} 0 0 1 {w:g},0 v{h - 2 * ry:g} '
            f'a{w / 2:g},{ry} 0 0 1 {-w:g},0 z"/>'
        )
        self.parts.append(
            f'<path class="{cls} lid" d="M{x:g},{y + ry:g} a{w / 2:g},{ry} 0 0 0 {w:g},0"/>'
        )
        lines = [(title, "t")] + ([(sub, "s")] if sub else [])
        top = y + ry + (h - ry) / 2 - (len(lines) - 1) * 7.5 + 2
        for i, (s, c) in enumerate(lines):
            self._fits(s, c, w)
            self.text(x + w / 2, top + i * 15, s, c, "middle")
        return Box(x, y, w, h)

    def arrow(self, *pts, label=None, at=None, kind="", anchor="middle", head=True):
        cls = " ".join(["ln"] + kind.split())
        marker = ""
        if head:
            marker = f' marker-end="url(#{self.name}-{"em" if "em" in kind else "a"})"'
        d = " ".join(f"{x:g},{y:g}" for x, y in pts)
        self.parts.append(f'<polyline class="{cls}" points="{d}"{marker}/>')
        if label:
            if at is None:
                (x1, y1), (x2, y2) = pts[0], pts[1]
                at = ((x1 + x2) / 2, (y1 + y2) / 2 - 6)
            for i, line in enumerate(label.split("\n")):
                self.text(at[0], at[1] + i * 13, line, "lbl" + (" em" if "em" in kind else ""), anchor)

    def group(self, x, y, w, h, label=None, kind=""):
        cls = " ".join(["grp"] + kind.split())
        self.parts.append(f'<rect class="{cls}" x="{x:g}" y="{y:g}" width="{w:g}" height="{h:g}" rx="10"/>')
        if label:
            self.text(x + 10, y + 15, label, "gl")

    def heading(self, x, y, s, anchor="start"):
        self.text(x, y, s, "gl", anchor)

    def raw(self, svg: str):
        self.parts.append(svg)

    # ---- output

    def render(self) -> str:
        defs = (
            f'<defs>'
            f'<marker id="{self.name}-a" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" '
            f'orient="auto-start-reverse"><path class="head" d="M0,0 L10,5 L0,10 z"/></marker>'
            f'<marker id="{self.name}-em" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" '
            f'orient="auto-start-reverse"><path class="head em" d="M0,0 L10,5 L0,10 z"/></marker>'
            f'</defs>'
        )
        svg = (
            f'<svg class="dg" viewBox="0 0 {self.w} {self.h}" role="img" aria-label="{escape(self.label)}" '
            f'xmlns="http://www.w3.org/2000/svg">{defs}{"".join(self.parts)}</svg>'
        )
        return f'<figure class="diagram" id="fig-{self.name}">{svg}<figcaption>{self.caption}</figcaption></figure>'


KEY_AI = '<span class="k ai">orange</span>: an LLM call'
KEY_CHECK = '<span class="k check">blue</span>: a scope or policy check'
KEY_OUT = '<span class="k out">green</span>: what is stored or returned'


def key(*items: str) -> str:
    return f'<span class="keys">{" · ".join(items)}</span>'


# =============================================================== Overview


def how_it_works() -> Fig:
    f = Fig(
        "how-it-works", 720, 330,
        "add extracts facts with the LLM, compares each with the five nearest stored memories in the same scope, "
        "and lets the LLM decide ADD, UPDATE, DELETE or NONE before writing to the vector store and history. "
        "search embeds the query and reads the nearest memories in scope from the vector store.",
        "<code>add</code> spends two LLM calls to decide what to keep; <code>search</code> only embeds the query "
        "and reads, so it makes no LLM call unless a graph store is configured. "
        + key(KEY_AI, KEY_CHECK, KEY_OUT),
    )
    f.heading(20, 22, "add")
    msgs = f.node(20, 32, 96, 46, "messages")
    ext = f.node(140, 32, 122, 46, "extract facts", "LLM", "ai")
    near = f.node(286, 32, 138, 46, "5 nearest", "per fact, same scope", "check")
    dec = f.node(448, 32, 156, 46, "decide each fact", "ADD UPDATE DELETE NONE", "ai")
    f.arrow(msgs.r, ext.l)
    f.arrow(ext.r, near.l)
    f.arrow(near.r, dec.l)

    vec = f.store(286, 142, 150, 58, "vector store", "facts + embeddings", "out")
    hist = f.store(460, 142, 120, 58, "history", "SQLite", "out")
    graph = f.store(604, 142, 104, 58, "graph store", "optional", "opt")
    f.arrow((330, 142), (330, 78), label="reads", at=(336, 116), anchor="start")
    f.arrow((520, 78), (520, 142), label="writes", at=(526, 116), anchor="start")
    f.arrow((470, 78), (470, 104), (410, 104), (410, 142))
    f.arrow((68, 32), (68, 12), (656, 12), (656, 142), kind="dash",
            label="entities + relations, in parallel", at=(650, 26), anchor="end")

    f.heading(20, 262, "search")
    q = f.node(20, 272, 96, 46, "query")
    emb = f.node(140, 272, 122, 46, "embed query")
    srch = f.node(286, 272, 138, 46, "nearest in scope", "+ metadata filters", "check")
    res = f.node(448, 272, 156, 46, "results", "+ relations", "out")
    f.arrow(q.r, emb.l)
    f.arrow(emb.r, srch.l)
    f.arrow(srch.r, res.l)
    f.arrow((355, 200), (355, 272), label="reads", at=(361, 240), anchor="start")
    f.arrow((656, 200), (656, 236), (580, 236), (580, 272), kind="dash",
            label="relations (LLM)", at=(650, 230), anchor="end")
    return f


# =============================================================== Quickstart


def agent_loop() -> Fig:
    f = Fig(
        "agent-loop", 720, 230,
        "Each turn: search memory for the user's message, put the hits in the prompt, answer with your LLM, "
        "then add the message and the answer so the next turn can find them.",
        "Memory sits on both sides of your model call: <code>search</code> before it, <code>add</code> after it. "
        "What this turn adds is what the next turn's search can find. " + key(KEY_AI, KEY_CHECK),
    )
    u = f.node(20, 40, 110, 50, "user message")
    s = f.node(160, 40, 140, 50, "memory.search", "query = message", "check")
    p = f.node(330, 40, 140, 50, "build prompt", "memories + message")
    a = f.node(500, 40, 110, 50, "your LLM", "answers", "ai")
    r = f.node(640, 40, 64, 50, "reply")
    f.arrow(u.r, s.l)
    f.arrow(s.r, p.l, label="top memories", at=(315, 30))
    f.arrow(p.r, a.l)
    f.arrow(a.r, r.l)
    add = f.node(430, 150, 180, 50, "memory.add", "message + answer", "ai")
    f.arrow((555, 90), (555, 150), label="after answering", at=(561, 124), anchor="start")
    f.arrow((430, 175), (230, 175), (230, 90), kind="dash", label="next turn finds it", at=(330, 168))
    return f


# =============================================================== Memory operations


def add_decision() -> Fig:
    f = Fig(
        "add-decision", 720, 300,
        "Two facts are extracted. The first is compared with the stored memory 'Is vegetarian', shown to the LLM "
        "as id 0, and the LLM answers UPDATE 0. The second has no close match and is added. Both changes write a "
        "history row. With infer=False each message is stored as written and no LLM is called.",
        "<code>add</code> decides per fact. Existing memories are shown to the LLM as <code>0</code>, "
        "<code>1</code>, <code>2</code>… instead of their real ids, so it cannot invent one; the ids are mapped "
        "back before anything is written. " + key(KEY_AI, KEY_CHECK, KEY_OUT),
    )
    cols = [20, 220, 400, 540]
    f.heading(cols[0], 22, "1 · facts")
    f.heading(cols[1], 22, "2 · nearest in scope")
    f.heading(cols[2], 22, "3 · decision")
    f.heading(cols[3], 22, "4 · written")
    a1 = f.node(cols[0], 36, 176, 50, "Eats fish, no meat", "extracted by the LLM", "ai")
    a2 = f.node(cols[1], 36, 156, 50, "0: Is vegetarian", "1: Likes spicy food", "check")
    a3 = f.node(cols[2], 36, 116, 50, "UPDATE 0", "same topic, new fact", "ai")
    a4 = f.node(cols[3], 36, 166, 50, "a3f1… updated", "history: old → new", "out")
    f.arrow(a1.r, a2.l)
    f.arrow(a2.r, a3.l)
    f.arrow(a3.r, a4.l)
    f.text(cols[3] + 83, 102, "0 is mapped back to a3f1…", "lbl", "middle")
    b1 = f.node(cols[0], 116, 176, 50, "Allergic to peanuts", "extracted by the LLM", "ai")
    b2 = f.node(cols[1], 116, 156, 50, "nothing close", "", "check")
    b3 = f.node(cols[2], 116, 116, 50, "ADD", "new fact", "ai")
    b4 = f.node(cols[3], 116, 166, 50, "4f1c… added", "history: ADD", "out")
    f.arrow(b1.r, b2.l)
    f.arrow(b2.r, b3.l)
    f.arrow(b3.r, b4.l)
    f.text(cols[2] + 58, 196, "also: DELETE (contradicted), NONE (known)", "lbl", "middle")
    f.group(10, 222, 700, 70, "infer=False")
    c1 = f.node(cols[0], 238, 176, 44, "each message", "stored as written", "")
    c4 = f.node(cols[3], 238, 166, 44, "one memory each", "chunked if long", "out")
    f.arrow(c1.r, c4.l, kind="dash", label="no LLM call", at=(368, 254))
    return f


# =============================================================== Scoping


def scoping() -> Fig:
    f = Fig(
        "scoping", 720, 252,
        "Four memories with different ids, and which of three searches return them: user_id alice returns the two "
        "tagged alice; agent_id travel returns the three tagged travel; agent_id travel with run_id trip-118 "
        "returns only the one tagged with both.",
        "Ids narrow: a memory is returned only if it carries every id you pass. Memories with no matching id are "
        "never searched, whatever the query.",
    )
    rows = [
        ("Prefers morning meetings", "user_id=alice", {0}),
        ("Booked the Lisbon trip", "agent_id=travel  run_id=trip-118", {1, 2}),
        ("Asked for a window seat", "agent_id=travel  run_id=trip-120", {1}),
        ("Flies from Lisbon", "user_id=alice  agent_id=travel", {0, 1}),
    ]
    cols = [430, 550, 665]
    f.heading(20, 30, "memory and its ids")
    heads = [("search(", "user_id=alice)"), ("search(", "agent_id=travel)"), ("agent_id=travel,", "run_id=trip-118")]
    for cx, (h1, h2) in zip(cols, heads):
        f.text(cx, 24, h1, "mono s", "middle")
        f.text(cx, 38, h2, "mono s", "middle")
    for i, (text, ids, hits) in enumerate(rows):
        y = 64 + i * 48
        f.raw(f'<rect class="row" x="12" y="{y - 6}" width="700" height="42" rx="6"/>')
        f.text(24, y + 12, text)
        f.text(24, y + 28, ids, "mono s")
        for j, cx in enumerate(cols):
            if j in hits:
                f.raw(f'<circle class="dot hit" cx="{cx}" cy="{y + 15}" r="7"/>')
            else:
                f.raw(f'<circle class="dot" cx="{cx}" cy="{y + 15}" r="4"/>')
    return f


# =============================================================== Graph memory


def graph_memory() -> Fig:
    f = Fig(
        "graph-memory", 720, 310,
        "Adding text to the graph: the LLM finds entities, then relations between them, then which stored "
        "relations the new text contradicts; contradicted relations are deleted and new ones merged into the "
        "graph, reusing nodes at least 0.9 similar. Searching: the LLM finds entities in the query, nodes at "
        "least 0.7 similar are matched, their relations in both directions are collected and ranked with BM25, "
        "top 5 returned.",
        "On the graph side, <code>add</code> costs three LLM calls and <code>search</code> one. Search returns "
        "relations around the entities your query names, not facts. " + key(KEY_AI, KEY_CHECK, KEY_OUT),
    )
    f.heading(20, 22, "add")
    t = f.node(20, 32, 92, 50, "text")
    e = f.node(132, 32, 128, 50, "find entities", "name + type", "ai")
    r = f.node(280, 32, 134, 50, "find relations", "source → rel → target", "ai")
    c = f.node(434, 32, 132, 50, "find conflicts", "vs. stored relations", "ai")
    w = f.node(586, 32, 120, 50, "write", "delete, then MERGE", "out")
    for a, b in ((t, e), (e, r), (r, c), (c, w)):
        f.arrow(a.r, b.l)
    g = f.store(286, 132, 160, 62, "Neo4j / Memgraph", "entities + relations", "out")
    f.arrow((500, 82), (500, 112), (420, 112), (420, 132), label="reads stored", at=(506, 104), anchor="start")
    f.arrow((646, 82), (646, 163), (446, 163), label="nodes reused if ≥ 0.9 similar", at=(640, 156), anchor="end")
    f.heading(20, 246, "search")
    q = f.node(20, 256, 92, 46, "query")
    qe = f.node(132, 256, 128, 46, "find entities", "LLM", "ai")
    m = f.node(280, 256, 134, 46, "match nodes", "similarity ≥ 0.7", "check")
    h = f.node(434, 256, 132, 46, "their relations", "in and out, 1 hop")
    k = f.node(586, 256, 120, 46, "BM25 → top 5", "relations", "out")
    for a, b in ((q, qe), (qe, m), (m, h), (h, k)):
        f.arrow(a.r, b.l)
    f.arrow((347, 194), (347, 256), label="reads", at=(353, 232), anchor="start")
    return f


def fused_search() -> Fig:
    f = Fig(
        "fused-search", 720, 300,
        "Fused search: vector search runs first. Then four stages run in parallel: the entity graph, the timeline "
        "(only with a time window), causal chains seeded from the top three vector results (usually empty), and "
        "cross-modal search (not connected, always empty). Reciprocal rank fusion merges everything into "
        "fused_ranking.",
        "<code>search(use_tcmgm=True)</code> fans out after the vector search and merges by reciprocal rank "
        "fusion. Dashed stages return nothing today: causal chains start from memory ids, which are not event "
        "ids, and cross-modal search is not connected. " + key(KEY_AI, KEY_CHECK, KEY_OUT),
    )
    q = f.node(20, 118, 76, 50, "query")
    v = f.node(116, 118, 128, 50, "vector search", "runs first", "check")
    f.arrow(q.r, v.l)
    sx, sw, sh = 300, 176, 52
    g = f.node(sx, 22, sw, sh, "entity graph", "LLM finds entities", "ai")
    tl = f.node(sx, 84, sw, sh, "timeline", "only with time_window", "check")
    cc = f.node(sx, 146, sw, sh, "causal chains", "from top 3 vector ids", "off", sub2="usually empty")
    mm = f.node(sx, 208, sw, sh, "cross-modal", "not connected", "off", sub2="always empty")
    f.arrow((244, 143), (272, 143), head=False)
    f.raw('<polyline class="ln" points="272,48 272,234" />')
    for b, k in ((g, ""), (tl, ""), (cc, "dash"), (mm, "dash")):
        f.arrow((272, b.cy), b.l, kind=k)
    f.text(272, 14, "then, in parallel", "lbl", "middle")
    fu = f.node(522, 118, 92, 50, "RRF", "rank fusion")
    for b, k in ((g, ""), (tl, ""), (cc, "dash"), (mm, "dash")):
        f.arrow(b.r, (500, b.cy), (500, 143), (522, 143), kind=k, head=(b is g))
    f.arrow((180, 168), (180, 282), (568, 282), (568, 168), label="vector results", at=(373, 276))
    out = f.node(634, 118, 76, 50, "fused", "ranking", "out")
    f.arrow(fu.r, out.l)
    return f


# =============================================================== Episodic memory (TCMGM)


def tcmgm_write() -> Fig:
    f = Fig(
        "tcmgm-write", 720, 250,
        "build_timeline: the LLM pulls events out of the messages and dates them from session_start, two minutes "
        "apart. Causal links are found by the LLM, by rules, or both. Each event becomes its own Neo4j node, named "
        "by its event id, and the causal links become CAUSAL edges between those nodes. Each event also goes "
        "through entity extraction for the entity graph.",
        "<code>build_timeline</code> (or <code>tcmgm.build_timeline_on_add</code>) writes one node per event and "
        "one <code>CAUSAL</code> edge per link. Event times come from <code>session_start</code>, not from the text. "
        + key(KEY_AI, KEY_OUT),
    )
    m = f.node(20, 50, 100, 52, "messages")
    ev = f.node(146, 50, 156, 52, "find events", "dated from session_start", "ai")
    ca = f.node(328, 50, 140, 52, "find causes", "llm · rules · cascade", "ai")
    f.arrow(m.r, ev.l)
    f.arrow(ev.r, ca.l)
    f.store(500, 20, 206, 192, "", None, "out")
    f.text(603, 46, "Neo4j", "t", "middle")
    en = f.node(516, 62, 174, 36, "event nodes", None, "out")
    ce = f.node(516, 112, 174, 36, "CAUSAL edges", None, "out")
    er = f.node(516, 162, 174, 36, "entities + relations", None, "")
    f.arrow((224, 50), (224, 30), (490, 30), (490, 80), (516, 80), label="1 node per event", at=(357, 24))
    f.arrow((398, 102), (398, 130), (516, 130), label="1 edge per link", at=(406, 124), anchor="start")
    ent = f.node(146, 156, 156, 50, "entity extraction", "per event, 3 LLM calls", "ai")
    f.arrow((224, 102), (224, 156))
    f.arrow(ent.r, (516, 180))
    f.text(20, 238, "event_1_dev-team_2026-10-12T09:00:00  is the name a CAUSAL edge attaches to", "mono s")
    return f


def tcmgm_chain() -> Fig:
    f = Fig(
        "tcmgm-chain", 720, 270,
        "Three events on a time axis at 09:00, 09:02 and 09:04: shipped the caching layer, checkout timing out, "
        "rollback fixed the timeouts. CAUSAL edges run from the first to the second and from the second to the "
        "third. get_causal_chain on the second event, backward, returns the first; forward from the first returns "
        "chains to the second and third. get_timeline returns all three in time order.",
        "Events are nodes, causes are edges. <code>get_causal_chain</code> walks the edges backward "
        "(“why did this happen?”) or forward (“what did it lead to?”); <code>get_timeline</code> reads the nodes "
        "in time order.",
    )
    xs = [130, 360, 590]
    names = [("e0", "shipped caching layer"), ("e1", "checkout timing out"), ("e2", "rollback fixed it")]
    boxes = [f.node(x - 80, 100, 160, 50, n, s, "out") for x, (n, s) in zip(xs, names)]
    f.arrow(boxes[0].r, boxes[1].l, label="caused_by", at=(245, 116))
    f.arrow(boxes[1].r, boxes[2].l, label="leads_to", at=(475, 116))
    # backward query from e1
    f.arrow((360, 92), (360, 62), (130, 62), (130, 92), kind="em")
    f.text(245, 52, "get_causal_chain(e1) → [e0, e1]", "mono s em", "middle")
    # forward query from e0
    f.arrow((150, 158), (150, 188), (590, 188), (590, 158), kind="em")
    f.text(370, 206, 'get_causal_chain(e0, direction="forward") → [e0, e1], [e0, e1, e2]', "mono s em", "middle")
    # time axis
    f.raw('<line class="axis" x1="20" y1="236" x2="700" y2="236" />')
    for x, t in zip(xs, ("09:00", "09:02", "09:04")):
        f.raw(f'<line class="axis" x1="{x}" y1="231" x2="{x}" y2="241" />')
        f.text(x, 256, t, "mono s", "middle")
    f.text(700, 228, "get_timeline: oldest first", "lbl", "end")
    return f


# =============================================================== Chunking


def chunking() -> Fig:
    f = Fig(
        "chunking", 720, 290,
        "A long document added with infer=False is split into six overlapping chunks, numbered 0 to 5, each stored "
        "as its own memory with the same document_id. A search matches chunks 2 and 3; with a context window of 1, "
        "chunks 1 to 4 are joined into one result whose id is the document_id and whose score is the best chunk's.",
        "Chunks overlap (shaded) so a sentence cut at a boundary is whole in one of them. At search time, matching "
        "chunks of one document plus their neighbours come back as a single result. " + key(KEY_OUT),
    )
    f.node(20, 24, 680, 36, "handbook.md", "infer=False · longer than min_document_size and chunk_size")
    step, cw = 104, 132
    for i in range(6):
        x = 20 + i * step
        y = 84 if i % 2 == 0 else 120
        kind = "out" if i in (2, 3) else ("out opt" if i in (1, 4) else "")
        f.node(x, y, cw, 28, f"chunk {i}", None, kind)
    for i in range(1, 6):
        ox = 20 + i * step
        f.raw(f'<rect class="ov" x="{ox}" y="84" width="{cw - step}" height="64" rx="3"/>')
    f.text(20, 172, "shaded: overlap = chunk_overlap", "lbl", "start")
    f.text(400, 172, "matches: chunks 2, 3 · window 1 adds 1, 4", "lbl em", "middle")
    x1, x2 = 20 + 1 * step, 20 + 4 * step + cw
    f.arrow((400, 180), (400, 214))
    f.node(x1, 216, x2 - x1, 48, "1 result: chunks 1–4 joined", "id = document_id · score = best chunk", "out")
    return f


# =============================================================== Privacy


def privacy() -> Fig:
    f = Fig(
        "privacy", 720, 250,
        "Privacy tools run in your code before add: classify finds sensitive spans with regular expressions or an "
        "optional LLM classifier, redact_text replaces them, and the clean text goes to memory.add. "
        "EncryptionManager encrypts single values with a key file. Setting ppmf.enabled in the Memory config does "
        "not call any of these.",
        "The privacy tools are functions you call on text before <code>add</code>. Turning on "
        "<code>ppmf.enabled</code> in the config does not route <code>add</code> or <code>search</code> through "
        "them. " + key(KEY_CHECK, KEY_OUT),
    )
    f.group(10, 10, 700, 158, "your code")
    m = f.node(24, 40, 86, 46, "message")
    c = f.node(128, 40, 140, 46, "classify", "regex · optional LLM", "check")
    r = f.node(286, 40, 176, 46, "redact_text", "REPLACE MASK HASH REMOVE")
    a = f.node(480, 40, 100, 46, "memory.add", "clean text")
    f.store(598, 34, 100, 58, "vector", "store", "out")
    f.arrow(m.r, c.l)
    f.arrow(c.r, r.l)
    f.arrow(r.r, a.l)
    f.arrow(a.r, (598, 63))
    val = f.node(24, 108, 86, 44, "a value")
    em = f.node(128, 108, 140, 44, "EncryptionManager", "FERNET · AES-256-GCM")
    ct = f.node(286, 108, 176, 44, "ciphertext + meta", "you store it", "out")
    f.arrow(val.r, em.l)
    f.arrow(em.r, ct.l)
    f.node(24, 192, 150, 44, "ppmf.enabled", "in MemoryConfig", "off")
    f.arrow((174, 214), (530, 214), (530, 86), kind="dash")
    f.raw('<line class="x" x1="344" y1="206" x2="360" y2="222"/><line class="x" x1="360" y1="206" x2="344" y2="222"/>')
    f.text(372, 232, "not called by add or search", "lbl warn", "start")
    return f


# =============================================================== Multimodal


def multimodal() -> Fig:
    f = Fig(
        "multimodal", 720, 240,
        "A message with an image goes to a vision LLM, which describes it. The description replaces the image in the "
        "message and goes through fact extraction like text, and the facts are stored. The image itself is not "
        "stored. CLIP and CLAP embedders from the multimodal extra are not connected to search.",
        "Images become text before anything is stored: the vision model's description goes through the normal "
        "fact pipeline, and the image is dropped. " + key(KEY_AI, KEY_OUT),
    )
    m = f.node(20, 44, 120, 50, "message", "text + image_url")
    d = f.node(164, 44, 150, 50, "describe image", "vision LLM", "ai")
    x = f.node(338, 44, 140, 50, "extract facts", "LLM, as for text", "ai")
    f.store(504, 38, 196, 62, "vector store", "facts about the picture", "out")
    f.arrow(m.r, d.l)
    f.arrow(d.r, x.l, label="description", at=(326, 36))
    f.arrow(x.r, (504, 69))
    f.arrow((80, 94), (80, 150), (160, 150), kind="dash")
    f.node(160, 128, 154, 44, "the image itself", "not kept", "off")
    f.text(326, 156, "store its URL in metadata to show it again", "lbl", "start")
    f.node(20, 190, 200, 40, "CLIP · CLAP embedders", "[multimodal] extra", "off")
    f.node(420, 190, 140, 40, "search", None, "off")
    f.arrow((220, 210), (420, 210), kind="dash", label="not connected", at=(320, 202))
    return f


# =============================================================== Cloud


def cloud() -> Fig:
    f = Fig(
        "cloud", 720, 220,
        "Your app uses the SDK, which only needs httpx. It sends HTTPS requests with the API key. The server checks "
        "the key, finds the organisation and project, and runs the request on that project's memory engine, which "
        "holds the models and the stores.",
        "With the cloud SDK nothing heavy runs in your process: the key picks the project on the server, and the "
        "project's engine does the LLM calls and storage. Test and live keys see separate data. "
        + key(KEY_AI, KEY_CHECK, KEY_OUT),
    )
    f.group(10, 30, 180, 156, "your process")
    app = f.node(26, 58, 148, 44, "your app")
    sdk = f.node(26, 120, 148, 44, "MemoryClient", "depends on httpx only")
    f.arrow(app.b, sdk.t)
    f.group(280, 30, 430, 156, "api.contextkit.outhad.com")
    k = f.node(296, 118, 118, 48, "check key", "→ org, project", "check")
    e = f.node(432, 118, 128, 48, "project engine", "LLM · embedder", "ai")
    f.store(576, 112, 122, 60, "project data", "live or test", "out")
    f.arrow(sdk.r, k.l, label="HTTPS + key", at=(235, 134))
    f.arrow(k.r, e.l)
    f.arrow(e.r, (576, 142))
    f.text(360, 208, "same add / search / get_all calls as the library, sent as JSON", "lbl", "middle")
    return f


# =============================================================== Context graph


def cgl_links() -> Fig:
    f = Fig(
        "cgl-links", 720, 290,
        "Five memories as graph nodes. 'I love pizza' and 'Italian is the best' were added five minutes apart in "
        "the same run, so they get REPLY_TO (1.0) and TEMPORAL_NEXT (0.6). Two menu memories share a doc_id and get "
        "DOCUMENT_LINK (0.8). 'Menu: margherita' is topic-similar to 'I love pizza' (0.79). 'Pizza is the best' "
        "belongs to another user and is still linked to 'Italian is the best' by TOPIC_SIMILAR (0.88).",
        "Edges come from where and when memories were added (<code>REPLY_TO</code>, <code>TEMPORAL_NEXT</code>, "
        "<code>DOCUMENT_LINK</code>) and from how alike their embeddings are (<code>TOPIC_SIMILAR</code>, weighted by "
        "the cosine). Topic links are not limited to one user, which is why the highlighted memory can sit one hop "
        "from yours.",
    )
    a1 = f.node(20, 40, 150, 54, "I love pizza", "u1 · run r1 · 10:00")
    b1 = f.node(290, 40, 152, 54, "Italian is the best", "u1 · run r1 · 10:05")
    c1 = f.node(570, 40, 140, 54, "Pizza is the best", "u2 · another user", "warnbox")
    a2 = f.node(20, 196, 150, 54, "Menu: margherita", "u1 · doc_id=menu.pdf")
    b2 = f.node(290, 196, 152, 54, "Menu prices changed", "u1 · doc_id=menu.pdf")
    f.arrow(a1.at("r", 0.72), b1.at("l", 0.72), label="REPLY_TO 1.0\nTEMPORAL_NEXT 0.6", at=(230, 52))
    f.arrow(c1.at("l", 0.72), b1.at("r", 0.72), kind="warn", label="TOPIC_SIMILAR 0.88\ncrosses users", at=(506, 52))
    f.arrow(b2.at("l", 0.72), a2.at("r", 0.72), label="DOCUMENT_LINK 0.8\nsame doc_id", at=(230, 208))
    f.arrow(a2.t, a1.b, label="TOPIC_SIMILAR 0.79", at=(108, 150), anchor="start")
    f.text(500, 214, "Edges point from the newer memory", "lbl", "start")
    f.text(500, 228, "to the older one; search follows", "lbl", "start")
    f.text(500, 242, "them in both directions.", "lbl", "start")
    return f


def cgl_search() -> Fig:
    f = Fig(
        "cgl-search", 720, 300,
        "Graph-first search: the top 10 vector matches become seeds; the graph is expanded from them up to two hops "
        "(or by personalised PageRank), ignoring edges under 0.1 and stopping at 50 candidates; each candidate is "
        "scored 0.55 times dense similarity plus 0.15 times lexical overlap plus 0.30 times graph reach, multiplied "
        "by the node's relevance.",
        "Seeds come from the vector store, neighbours from the graph, and every candidate is scored the same way. "
        "Graph reach is 1.0 for a seed and the product of edge weights along the path for a neighbour, so a "
        "neighbour two weak hops away scores low. " + key(KEY_CHECK, KEY_OUT),
    )
    q = f.node(20, 34, 76, 50, "query")
    s = f.node(116, 34, 150, 50, "vector search", "top 10 = seeds", "check")
    e = f.node(286, 34, 156, 50, "expand", "BFS 2 hops, or PPR")
    r = f.node(462, 34, 140, 50, "re-rank", "every candidate")
    o = f.node(622, 34, 88, 50, "results", "+ subgraph", "out")
    for a, b in ((q, s), (s, e), (e, r), (r, o)):
        f.arrow(a.r, b.l)
    f.text(364, 102, "edges ≥ 0.1 · ≤ 50 candidates", "lbl", "middle")
    f.text(364, 116, "archived nodes skipped", "lbl", "middle")
    f.arrow((532, 84), (532, 132), head=True)
    f.text(20, 150, "score =", "mono")
    xs = [20, 195, 370, 545]
    terms = ["0.55 · dense", "+ 0.15 · lexical", "+ 0.30 · graph", "× relevance"]
    for x, t in zip(xs, terms):
        f.text(x + 81, 172, t, "t", "middle")
        f.arrow((x + 81, 180), (x + 81, 204))
    f.node(xs[0], 206, 162, 64, "dense", "vector similarity;", sub2="neighbours: cos to query")
    f.node(xs[1], 206, 162, 64, "lexical", "share of query words", sub2="in the memory, not BM25")
    f.node(xs[2], 206, 162, 64, "graph", "seed 1.0; neighbour:", sub2="edge weights multiplied")
    f.node(xs[3], 206, 162, 64, "relevance", "node relevance, decays;", sub2="feedback raises it")
    f.text(536, 140, "per candidate", "lbl", "start")
    return f


def cgl_decay() -> Fig:
    f = Fig(
        "cgl-decay", 720, 270,
        "Edge weight against days: a REPLY_TO edge starting at 1.0, a DOCUMENT_LINK edge at 0.8 and a TEMPORAL_NEXT "
        "edge at 0.6 halve every 30 days and are pruned when they drop below 0.05, after about 130, 120 and 108 "
        "days. CONTRADICTS edges keep their weight.",
        "With the default 30-day half-life, how long an edge lasts depends on where it starts: the 0.05 floor takes "
        "about 130 days to reach from 1.0 and about 108 from 0.6. Node relevance follows its strongest live edge, so "
        "a memory whose edges are gone drops toward archiving.",
    )
    import math

    x0, x1, y0, y1 = 150, 690, 24, 214
    days = 150

    def px(d):
        return x0 + (x1 - x0) * d / days

    def py(w):
        return y1 - (y1 - y0) * w

    for d in (0, 30, 60, 90, 120, 150):
        f.raw(f'<line class="grid" x1="{px(d):g}" y1="{y0}" x2="{px(d):g}" y2="{y1}"/>')
        f.text(px(d), y1 + 18, str(d), "lbl", "middle")
    f.raw(f'<line class="axis" x1="{x0}" y1="{y1}" x2="{x1}" y2="{y1}"/>')
    f.raw(f'<line class="axis" x1="{x0}" y1="{y0}" x2="{x0}" y2="{y1}"/>')
    f.text((x0 + x1) / 2, y1 + 38, "days since the edge was written", "lbl", "middle")
    f.text(x0 - 10, y1 + 4, "0", "lbl", "end")
    f.raw(f'<line class="ln dash warn" x1="{x0}" y1="{py(0.05):g}" x2="{x1}" y2="{py(0.05):g}"/>')
    f.text(px(4), py(0.05) - 6, "pruned below 0.05", "lbl warn", "start")
    stagger = {1.0: 52, 0.8: 38, 0.6: 24}
    for w0, name in ((1.0, "REPLY_TO 1.0"), (0.8, "DOCUMENT_LINK 0.8"), (0.6, "TEMPORAL_NEXT 0.6")):
        end = 30 * math.log2(w0 / 0.05)
        ds = [i * 2.5 for i in range(int(end / 2.5) + 1)] + [end]
        pts = [(px(d), py(w0 * 0.5 ** (d / 30))) for d in ds]
        f.raw('<polyline class="ln curve" points="' + " ".join(f"{x:.1f},{y:.1f}" for x, y in pts) + '"/>')
        f.text(x0 - 10, py(w0) + 4, name, "lbl", "end")
        ex, ey = pts[-1]
        f.raw(f'<circle class="dot hit" cx="{ex:.1f}" cy="{ey:.1f}" r="3.5"/>')
        ly = ey - stagger[w0]
        f.raw(f'<line class="grid" x1="{ex:.1f}" y1="{ey - 5:.1f}" x2="{ex:.1f}" y2="{ly + 4:.1f}"/>')
        f.text(ex, ly, f"≈{end:.0f} d", "lbl", "middle")
    f.raw(f'<line class="ln dash" x1="{x0}" y1="{py(0.7):g}" x2="{x1}" y2="{py(0.7):g}"/>')
    f.text(x0 - 10, py(0.7) + 4, "CONTRADICTS", "lbl", "end")
    f.text(x1, py(0.7) - 6, "never decays", "lbl", "end")
    return f


def cgl_persist() -> Fig:
    f = Fig(
        "cgl-persist", 720, 220,
        "Left, the default networkx backend: the graph lives in the process's memory, is loaded from persist_path "
        "when Memory starts, and is written back only when you call snapshot(); changes after the last snapshot are "
        "lost when the process exits. Right, the neo4j backend: every process reads and writes the same Neo4j "
        "database, so the graph is shared and survives restarts.",
        "The default backend saves nothing on its own: <code>persist_path</code> is read at start and written only "
        "by <code>snapshot()</code>. The <code>neo4j</code> backend writes as the graph changes, into the database "
        "your <code>graph_store</code> already points at. " + key(KEY_OUT),
    )
    f.group(10, 10, 340, 200, "networkx · default")
    f.node(28, 52, 140, 52, "graph", "in process memory")
    f.store(214, 44, 120, 66, "persist_path", ".pkl file", "out")
    f.arrow((214, 64), (168, 64), label="load at start", at=(191, 40))
    f.arrow((168, 92), (214, 92), label="snapshot()", at=(191, 124))
    f.raw('<line class="x" x1="90" y1="150" x2="104" y2="164"/><line class="x" x1="104" y1="150" x2="90" y2="164"/>')
    f.text(114, 161, "process exits: changes since the", "lbl warn", "start")
    f.text(114, 175, "last snapshot() are gone", "lbl warn", "start")
    f.group(370, 10, 340, 200, "neo4j")
    a = f.node(388, 40, 124, 42, "process A")
    b = f.node(388, 104, 124, 42, "process B")
    f.store(560, 40, 146, 106, "Neo4j", "MemoryNode · CTX_EDGE", "out")
    f.arrow(a.r, (560, 61))
    f.arrow(b.r, (560, 125))
    f.text(536, 89, "reads", "lbl", "middle")
    f.text(536, 102, "+ writes", "lbl", "middle")
    f.text(540, 178, "same database as graph_store;", "lbl", "middle")
    f.text(540, 192, "shared, survives restarts", "lbl", "middle")
    return f


def cgl_changes() -> Fig:
    f = Fig(
        "cgl-changes", 720, 300,
        "Every change to the context graph, from add, update, delete, search-time decay and feedback, is appended "
        "to an SQLite change log. Each subscription has its own queue of up to 10,000 events and its own thread; "
        "when the queue is full the oldest event is dropped. A subscriber can be your function or a sink: webhook, "
        "Kafka or server-sent events. replay_context_graph rebuilds a fresh graph from the log up to a time, and "
        "snapshot_context_graph exports the current nodes and edges to a JSONL file.",
        "The change log is the record; subscriptions, sinks and replay all read from it. A slow subscriber only "
        "loses its own oldest events, and <code>from_event_id</code> lets a new one catch up from the log first. "
        + key(KEY_OUT),
    )
    srcs = [("add · update · delete", None), ("search", "decay ticks"), ("record_feedback", None)]
    for i, (t, s) in enumerate(srcs):
        b = f.node(16, 30 + i * 52, 166, 40, t, s)
        f.arrow(b.r, (190, b.cy), (190, 100), (200, 100), head=(i == 1))
    cg = f.node(200, 64, 120, 72, "context graph", "nodes + edges")
    f.store(356, 50, 150, 100, "change log", "SQLite, append-only", "out")
    f.arrow(cg.r, (356, 100))
    f.node(542, 26, 168, 50, "replay(until)", "fresh graph as of then", "out")
    f.node(542, 100, 168, 66, "subscribe(callback)", "queue 10,000; drops oldest", sub2="from_event_id: past first")
    f.arrow((506, 80), (524, 80), (524, 51), (542, 51))
    f.arrow((506, 120), (524, 120), (524, 133), (542, 133))
    targets = [("your function", None, 326, 104), ("WebhookSink", "HMAC, retries", 438, 100),
               ("KafkaSink", "key target_id", 546, 92), ("SSESink", "stream()", 646, 64)]
    f.raw('<polyline class="ln" points="626,166 626,206" />')
    f.raw('<polyline class="ln" points="378,206 678,206" />')
    f.text(632, 190, "callback", "lbl", "start")
    for t, s, x, w in targets:
        f.node(x, 226, w, 46, t, s)
        f.arrow((x + w / 2, 206), (x + w / 2, 226))
    f.node(162, 226, 152, 46, "JSONL file", "snapshot_context_graph", "out")
    f.arrow((260, 136), (260, 226))
    return f


# =============================================================== Personalized retrieval (MSPR)


def mspr() -> Fig:
    f = Fig(
        "mspr", 720, 420,
        "MSPR runs inside the context graph's search. Vector seeds may be filtered by a role policy in hard mode; "
        "the intent of the query shifts the dense, lexical and graph weights; the graph is expanded; each candidate "
        "is scored from seven signals. Personal comes from feedback events, success from per-query verdicts, "
        "frequency and relevance from the graph node. record_feedback writes all three stores, and every search "
        "with frequency on adds one access to the results it returns.",
        "Every MSPR signal is a term in the context graph's score, which is why MSPR does nothing with the context "
        "graph off, and why the dashed terms add nothing until you give them a weight. The feedback loop at the "
        "bottom is what makes ranking learn. Feedback is pooled across users in this build. "
        + key(KEY_AI, KEY_CHECK, KEY_OUT),
    )
    q = f.node(20, 30, 70, 52, "query")
    sd = f.node(108, 30, 120, 52, "vector seeds", "top 10", "check")
    rl = f.node(246, 30, 126, 52, "role filter", "hard mode, seeds", "check opt")
    it = f.node(390, 30, 126, 52, "intent", "regex, then LLM", "ai opt")
    ex = f.node(534, 30, 110, 52, "expand", "graph, 2 hops")
    for a, b in ((q, sd), (sd, rl), (rl, it), (it, ex)):
        f.arrow(a.r, b.l)
    f.arrow((453, 82), (453, 112), (145, 112), (145, 160), label="shifts α β γ for this query", at=(300, 106))
    f.arrow((589, 82), (589, 160), label="candidates", at=(595, 124), anchor="start")
    f.text(20, 148, "score =", "mono")
    chips = [
        ("dense", "α 0.55", ""), ("lexical", "β 0.15", ""), ("graph", "γ 0.30", ""),
        ("personal", "δ 0", "opt"), ("success", "ζ 0", "opt"), ("frequency", "ε 0", "opt"),
    ]
    boxes = []
    for i, (t, s, k) in enumerate(chips):
        boxes.append(f.node(20 + i * 86, 160, 78, 46, t, s, k))
    rel = f.node(536, 160, 78, 46, "relevance", "× all", "")
    f.text(312 + 86, 150, "added by MSPR · weight 0 by default", "lbl", "middle")
    res = f.node(636, 160, 74, 46, "results", None, "out")
    f.arrow(rel.r, res.l)
    fb = f.store(258, 256, 106, 58, "feedback", "events", "out")
    qs = f.store(372, 256, 98, 58, "success", "per query", "out")
    cn = f.store(478, 256, 136, 58, "graph node", "relevance · uses", "out")
    f.arrow((311, 256), (311, 206))
    f.arrow((403, 256), (403, 206))
    f.arrow((503, 256), (503, 206))
    f.arrow((575, 256), (575, 206))
    f.arrow((673, 206), (673, 285), (614, 285), label="+1 use", at=(668, 246), anchor="end")
    app = f.node(20, 360, 190, 46, "your app", "after the answer")
    rf = f.node(258, 360, 356, 46, "record_feedback(id, helpful, query=…)", None, "")
    f.arrow(app.r, rf.l)
    f.arrow((311, 360), (311, 314), label="+0.15 / −0.10", at=(317, 344), anchor="start")
    f.arrow((420, 360), (420, 314), label="if query=", at=(426, 344), anchor="start")
    f.arrow((546, 360), (546, 314), label="relevance bump", at=(552, 344), anchor="start")
    return f


# =============================================================== Tenants


def tenants() -> Fig:
    f = Fig(
        "tenants", 720, 330,
        "Left, the tenant registry in SQLite: tenant acme, its sub-tenants finance and sales, and role bindings. "
        "Right, the data path: add writes memories with tenant_id in metadata into one shared collection; search "
        "filters on tenant_id; an optional TenantIsolationPolicy checks seeds. The registry is not consulted by add "
        "or search; history() is the call that resolves a tenant.",
        "Tenant boundaries in your data come from the <code>tenant_id</code> you put in metadata and the filter you "
        "search with. The registry of tenants, sub-tenants and roles serves the admin API, <code>history()</code> "
        "and export / import, not <code>add</code> or <code>search</code>. " + key(KEY_CHECK, KEY_OUT),
    )
    f.group(10, 10, 280, 310, "registry · SQLite")
    acme = f.node(90, 36, 120, 44, "acme", "tenant")
    fin = f.node(28, 116, 116, 44, "finance", "department")
    sal = f.node(156, 116, 116, 44, "sales", "department")
    f.arrow((130, 80), (130, 98), (86, 98), (86, 116))
    f.arrow((170, 80), (170, 98), (214, 98), (214, 116))
    f.node(28, 196, 244, 54, "role bindings", "alice → admin @ acme", sub2="bob → member @ finance")
    f.text(150, 282, "admin API · export · import · migrate", "lbl", "middle")
    f.text(150, 298, "a tenant role covers its sub-tenants", "lbl", "middle")
    add = f.node(340, 40, 180, 50, "memory.add", "metadata tenant_id=acme")
    st = f.store(556, 34, 154, 62, "vector store", "one shared collection", "out")
    f.arrow(add.r, (556, 65), label="writes", at=(538, 57))
    se = f.node(340, 136, 180, 50, "memory.search", "filters tenant_id=acme", "check")
    f.arrow((520, 161), (633, 161), (633, 96), label="only acme rows", at=(578, 154))
    po = f.node(340, 216, 180, 50, "TenantIsolationPolicy", "optional · MSPR roles", "check opt")
    f.arrow((430, 216), (430, 186), kind="dash", label="checks seeds", at=(436, 206), anchor="start")
    hi = f.node(540, 216, 170, 50, "history(id, tenant_id)", None, "")
    f.arrow((290, 241), (300, 241), (300, 296), (633, 296), (633, 266), label="resolves the tenant", at=(470, 290))
    f.arrow((290, 100), (325, 100), (325, 161), (340, 161), kind="dash")
    f.raw('<line class="x" x1="318" y1="124" x2="332" y2="138"/><line class="x" x1="332" y1="124" x2="318" y2="138"/>')
    f.text(304, 118, "not read", "lbl warn", "end")
    return f


# =============================================================== Decay and versioning


def decay_lifecycle() -> Fig:
    f = Fig(
        "decay-lifecycle", 720, 300,
        "The decay score is 0.6 times recency plus 0.3 times frequency plus 0.1 times feedback. Active memories "
        "below 0.05 are archived by archive_low or the hourly scheduler; archived memories are flagged in the graph "
        "but still in the vector store. demote_to_cold moves a memory out of the vector store into cold storage; "
        "promote_from_cold re-embeds it and puts it back with the same id.",
        "Archiving only flags the graph node: the memory still comes back from the vector search, it is just not "
        "reached through graph links. Cold storage is the step that takes it out of search, and nothing moves a "
        "memory there automatically. " + key(KEY_CHECK, KEY_OUT),
    )
    chips = [("recency", "0.6 · halves in 30 days"), ("frequency", "0.3 · uses, log scale"),
             ("feedback", "0.1 · helpful − unhelpful")]
    for i, (t, s) in enumerate(chips):
        b = f.node(20 + i * 166, 24, 158, 48, t, s)
        f.arrow(b.b, (b.cx, 90), (520, 90), head=False)
    sc = f.node(540, 24, 170, 48, "decay score", "0 stale … 1 fresh", "check")
    f.arrow((520, 90), (520, 48), (540, 48))
    act = f.node(20, 170, 170, 54, "active", "vector store + graph", "out")
    arc = f.node(275, 164, 180, 66, "archived", "graph node flagged;", sub2="vector search still finds it")
    cold = f.store(540, 164, 170, 66, "cold storage", "JSON · disk or S3")
    f.arrow((625, 72), (625, 130), (232, 130), (232, 186), kind="dash", head=False)
    f.text(240, 152, "score < 0.05", "lbl em", "start")
    f.arrow(act.r, arc.l)
    f.text(232, 246, "archive_low, or", "lbl", "middle")
    f.text(232, 260, "the hourly scheduler", "lbl", "middle")
    f.arrow(arc.r, (540, 197), label="demote_to_cold", at=(498, 189))
    f.text(498, 215, "manual only", "lbl warn", "middle")
    f.arrow((625, 230), (625, 284), (105, 284), (105, 224), label="promote_from_cold: re-embed, same id", at=(365, 278))
    return f


# =============================================================== Configuration


def config_layers() -> Fig:
    f = Fig(
        "config-layers", 720, 384,
        "Four keys build the core: llm, embedder, vector_store and history_db_path. The opt-in keys depend on "
        "others: tcmgm comes with graph_store; mspr and decay_v2 need context_graph; tenant stamps graph nodes if "
        "the graph is on. chunking works only on text added with infer=False. ppmf configures tools you call "
        "yourself and is not used by add or search.",
        "Arrows mean “does nothing without”. Turning on <code>mspr</code> or <code>decay_v2</code> without "
        "<code>context_graph</code> changes nothing, and <code>tcmgm</code> comes with <code>graph_store</code>.",
    )
    f.heading(20, 20, "core · always built")
    core = [("llm", "facts and decisions"), ("embedder", "memory + query vectors"),
            ("vector_store", "where memories live"), ("history_db_path", "every change")]
    for i, (t, s) in enumerate(core):
        f.node(20 + i * 174, 30, 162, 48, t, s, "out")
    f.heading(20, 114, "opt-in")
    gs = f.node(20, 124, 162, 48, "graph_store", "entities, relations")
    cg = f.node(194, 124, 510, 48, "context_graph", "links memories to each other")
    tc = f.node(20, 222, 162, 48, "tcmgm", "timelines need neo4j")
    ms = f.node(194, 222, 162, 48, "mspr", "ranking signals")
    dv = f.node(368, 222, 162, 48, "decay_v2", "decay score, archive")
    tn = f.node(542, 222, 162, 48, "tenant", "registry + roles")
    f.arrow(tc.t, gs.b)
    f.arrow(ms.t, cg.at("b", (ms.cx - 194) / 510))
    f.arrow(dv.t, cg.at("b", (dv.cx - 194) / 510))
    f.arrow(tn.t, cg.at("b", (tn.cx - 194) / 510), kind="dash", label="stamps nodes, if on", at=(617, 200), anchor="end")
    f.heading(20, 312, "independent")
    f.node(20, 322, 162, 48, "chunking", "infer=False text only")
    f.node(194, 322, 336, 48, "ppmf", "tools you call yourself; not used by add or search", "off")
    return f


DIAGRAMS = {
    "cgl-links": cgl_links,
    "cgl-search": cgl_search,
    "cgl-decay": cgl_decay,
    "cgl-persist": cgl_persist,
    "cgl-changes": cgl_changes,
    "mspr": mspr,
    "tenants": tenants,
    "decay-lifecycle": decay_lifecycle,
    "config-layers": config_layers,
    "how-it-works": how_it_works,
    "agent-loop": agent_loop,
    "add-decision": add_decision,
    "scoping": scoping,
    "graph-memory": graph_memory,
    "fused-search": fused_search,
    "tcmgm-write": tcmgm_write,
    "tcmgm-chain": tcmgm_chain,
    "chunking": chunking,
    "privacy": privacy,
    "multimodal": multimodal,
    "cloud": cloud,
}


def render(name: str) -> str:
    if name not in DIAGRAMS:
        raise SystemExit(f"unknown diagram {name!r}; known: {', '.join(sorted(DIAGRAMS))}")
    fig = DIAGRAMS[name]()
    for warning in fig.warnings:
        print(f"diagram warning: {warning}")
    return fig.render()
