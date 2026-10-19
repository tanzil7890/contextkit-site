// A copy button on every code block, and on the install command.
for (const pre of document.querySelectorAll("article pre")) {
  const button = document.createElement("button")
  button.className = "copy"
  button.type = "button"
  button.textContent = "Copy"
  button.addEventListener("click", async () => {
    const code = pre.querySelector("code") || pre
    await navigator.clipboard.writeText(code.textContent.replace(/\n$/, ""))
    button.textContent = "Copied"
    setTimeout(() => (button.textContent = "Copy"), 1500)
  })
  pre.appendChild(button)
}

const copy = document.getElementById("copy")
if (copy) {
  copy.addEventListener("click", async () => {
    await navigator.clipboard.writeText(document.getElementById("cmd").textContent)
    copy.textContent = "Copied"
    setTimeout(() => (copy.textContent = "Copy"), 1500)
  })
}

// The docs menu starts closed on phones.
const docnav = document.querySelector(".docnav")
if (docnav && window.matchMedia("(max-width: 860px)").matches) docnav.open = false

// The version is written in at build time; refresh it from PyPI in case a release
// went out since. The link still works if PyPI is unreachable.
for (const el of document.querySelectorAll("[data-pypi]")) {
  fetch(`https://pypi.org/pypi/${el.dataset.pypi}/json`)
    .then((response) => (response.ok ? response.json() : undefined))
    .then((data) => {
      if (data && data.info && data.info.version) el.textContent = `${el.dataset.prefix ?? "Latest: v"}${data.info.version}`
    })
    .catch(() => {})
}

// Landing hero: highlight what is kept, fade the rest, and set the kept facts in mono.
// The page reads the same without this; it only replays the sequence.
const hero = document.getElementById("hero")
if (hero) {
  const play = () => {
    hero.classList.remove("play")
    void hero.offsetWidth
    hero.classList.add("play")
  }
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(play, play)
  else play()
  const replay = document.getElementById("replay")
  if (replay) replay.addEventListener("click", play)
}

// Landing layers: each switch uncomments its key in the config.
const cfgCode = document.getElementById("cfg-code")
if (cfgCode) {
  const S = (t) => `<span class="s">"${t}"</span>`
  const T = '<span class="k">True</span>'
  const core = [
    '<span class="k">from</span> outhad_contextkit <span class="k">import</span> Memory',
    "",
    "memory = Memory.from_config({",
    `    ${S("vector_store")}: {`,
    `        ${S("provider")}: ${S("qdrant")},`,
    `        ${S("config")}: {${S("path")}: ${S("./memory")}},`,
    "    },",
  ]
  const layers = [
    { id: "vision", name: "Multimodal", lines: [`    ${S("llm")}: {`, `        ${S("provider")}: ${S("openai")},`, `        ${S("config")}: {${S("enable_vision")}: ${T}},`, "    },"] },
    { id: "graph", name: "Graph memory", lines: [`    ${S("graph_store")}: {`, `        ${S("provider")}: ${S("neo4j")},`, `        ${S("config")}: neo4j_config,`, "    },"] },
    { id: "tcmgm", name: "Episodic memory", needs: ["graph"], why: "it stores events in Neo4j", lines: [`    ${S("tcmgm")}: {${S("build_timeline_on_add")}: ${T}},`] },
    { id: "cgl", name: "Context graph", lines: [`    ${S("context_graph")}: {${S("enabled")}: ${T}},`] },
    { id: "mspr", name: "Personalized retrieval", needs: ["cgl"], why: "it re-ranks inside the context graph", lines: [`    ${S("mspr")}: {${S("enabled")}: ${T}},`] },
    { id: "tenant", name: "Tenants", lines: [`    ${S("tenant")}: {${S("enabled")}: ${T}},`] },
    { id: "decay", name: "Decay and versioning", needs: ["cgl"], why: "it scores context-graph nodes", lines: [`    ${S("decay_v2")}: {${S("enabled")}: ${T}},`] },
    { id: "chunking", name: "Chunking", lines: [`    ${S("chunking")}: {${S("enabled")}: ${T}},`] },
  ]
  const byId = Object.fromEntries(layers.map((l) => [l.id, l]))
  const on = { cgl: true }
  let fresh = {}
  const note = document.getElementById("cfg-note")

  const render = () => {
    let html = core.map((l) => `<span class="ln">${l || " "}</span>`).join("")
    for (const l of layers) {
      for (const line of l.lines) {
        html += on[l.id]
          ? `<span class="ln${fresh[l.id] ? " new" : ""}">${line}</span>`
          : `<span class="ln off">    # ${line.replace(/^ {4}/, "")}</span>`
      }
    }
    cfgCode.innerHTML = `${html}<span class="ln">})</span>`
    for (const l of layers) {
      const sw = document.getElementById(`sw-${l.id}`)
      if (sw) sw.setAttribute("aria-checked", on[l.id] ? "true" : "false")
    }
    if (Object.keys(fresh).length) {
      requestAnimationFrame(() =>
        requestAnimationFrame(() => {
          for (const el of cfgCode.querySelectorAll(".new")) el.classList.remove("new")
          fresh = {}
        }),
      )
    }
  }

  const toggle = (id) => {
    const l = byId[id]
    let msg
    if (!on[id]) {
      on[id] = true
      fresh[id] = true
      msg = `<strong>${l.name} is on.</strong> One key added.`
      for (const dep of l.needs || []) {
        if (!on[dep]) {
          on[dep] = true
          fresh[dep] = true
          msg = `<strong>${l.name} is on, and so is ${byId[dep].name.toLowerCase()}</strong>, because ${l.why}.`
        }
      }
    } else {
      on[id] = false
      msg = `<strong>${l.name} is off.</strong> Its line is commented out, and nothing it does runs.`
      for (const d of layers) {
        if (on[d.id] && (d.needs || []).includes(id)) {
          on[d.id] = false
          msg = `<strong>${l.name} is off, and so is ${d.name.toLowerCase()}</strong>, because ${d.why}.`
        }
      }
    }
    note.innerHTML = msg
    render()
  }

  for (const sw of document.querySelectorAll(".switch")) {
    sw.addEventListener("click", () => toggle(sw.id.slice(3)))
  }
  render()
}

// Graph diagrams: hovering or focusing a memory shows only its links and the memories they reach.
for (const svg of document.querySelectorAll("svg.dg-graph")) {
  const nodes = [...svg.querySelectorAll(".gnode")]
  const edges = [...svg.querySelectorAll(".gedge")]
  const show = (key) => {
    svg.classList.toggle("focusing", key !== null)
    const near = new Set()
    for (const edge of edges) {
      const on = key !== null && (edge.dataset.src === key || edge.dataset.dst === key)
      edge.classList.toggle("on", on)
      if (on) near.add(edge.dataset.src).add(edge.dataset.dst)
    }
    for (const node of nodes) {
      node.classList.toggle("on", node.dataset.node === key)
      node.classList.toggle("near", near.has(node.dataset.node))
    }
  }
  for (const node of nodes) {
    node.addEventListener("mouseenter", () => show(node.dataset.node))
    node.addEventListener("focus", () => show(node.dataset.node))
    node.addEventListener("mouseleave", () => show(null))
    node.addEventListener("blur", () => show(null))
  }
}
