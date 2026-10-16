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
      if (data && data.info && data.info.version) el.textContent = `Latest: v${data.info.version}`
    })
    .catch(() => {})
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
