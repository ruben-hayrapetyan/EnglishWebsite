/* ==========================================================================
   Highlights and notes. a11y.js loads this on every page while "Highlights
   and notes" is on in settings.html; pages never load it themselves.

   Select text in the page's reading area ([data-read-aloud], or <main>) and
   a small menu offers "Add note" and "Read aloud". A note highlights the
   words and opens the notes panel beside the page, where it can be edited
   or deleted. Notes save as you type, per page, in this browser only.
   They're found again by their words (plus a little text either side), so
   they survive reloads and edits elsewhere on the page.
   Shared file: change it only in a design/* branch.
   ========================================================================== */

(function () {
  const A11y = window.A11y;
  if (!A11y || A11y.notes) return;

  const root = document.documentElement;
  const storageKey = A11y.notesKey();
  const CONTEXT = 32; // characters kept either side of a quote to find it again
  const EXCLUDED = "script, style, noscript, template, textarea, .reader-bar, .notes-menu, .notes-panel";
  const NO_NOTES = "button, input, select, textarea, label, [contenteditable], .reader-bar, .notes-menu, .notes-panel";
  const BLOCKS = "p, li, h1, h2, h3, h4, h5, h6, blockquote, figcaption, caption, dt, dd, th, td, pre";

  let notes = [];
  let missing = new Set(); // ids of notes whose words are no longer on the page
  let active = false;
  let menu, panel, list, toggle, selectionTimer;

  // ---- Storage --------------------------------------------------------------
  function load() {
    try {
      const saved = JSON.parse(localStorage.getItem(storageKey));
      if (Array.isArray(saved)) return saved.filter((n) => n && typeof n.id === "string" && typeof n.quote === "string");
    } catch (error) {
      // Storage blocked or corrupt: start with no notes.
    }
    return [];
  }

  function save() {
    try {
      if (notes.length) localStorage.setItem(storageKey, JSON.stringify(notes));
      else localStorage.removeItem(storageKey);
    } catch (error) {
      // Private mode or storage full: notes last until the page closes.
    }
  }

  // ---- Finding text -------------------------------------------------------------
  // Every text node in the reading area, with its offset in one long string.
  function textIndex() {
    const nodes = [];
    let text = "";
    for (const scope of A11y.scopes()) {
      const walker = document.createTreeWalker(scope, NodeFilter.SHOW_TEXT, {
        acceptNode: (node) => (node.parentElement.closest(EXCLUDED) ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT),
      });
      for (let node = walker.nextNode(); node; node = walker.nextNode()) {
        nodes.push({ node, start: text.length });
        text += node.data;
      }
    }
    return { nodes, text };
  }

  // Offset in the index of a range boundary.
  function offsetOf(container, offset, index) {
    if (container.nodeType === Node.TEXT_NODE) {
      const entry = index.nodes.find((item) => item.node === container);
      if (entry) return entry.start + offset;
    }
    const point = document.createRange();
    point.setStart(container, offset);
    const next = index.nodes.find((item) => point.comparePoint(item.node, 0) >= 0);
    return next ? next.start : index.text.length;
  }

  function sharedLength(a, b, fromEnd) {
    let n = 0;
    while (n < a.length && n < b.length) {
      const x = fromEnd ? a[a.length - 1 - n] : a[n];
      const y = fromEnd ? b[b.length - 1 - n] : b[n];
      if (x !== y) break;
      n += 1;
    }
    return n;
  }

  // Where a note's quote is now, preferring the copy with matching context.
  function locate(note, text) {
    let best = -1;
    let bestScore = -1;
    for (let i = text.indexOf(note.quote); i !== -1; i = text.indexOf(note.quote, i + 1)) {
      const before = text.slice(Math.max(0, i - CONTEXT), i);
      const after = text.slice(i + note.quote.length, i + note.quote.length + CONTEXT);
      const score = sharedLength(before, note.prefix || "", true) + sharedLength(after, note.suffix || "", false);
      if (score > bestScore) {
        best = i;
        bestScore = score;
      }
    }
    return best;
  }

  // ---- Highlights ---------------------------------------------------------------
  function wrap(note, start, end, index) {
    for (const { node, start: nodeStart } of index.nodes) {
      const nodeEnd = nodeStart + node.data.length;
      if (nodeEnd <= start || nodeStart >= end) continue;
      const from = Math.max(start, nodeStart) - nodeStart;
      const to = Math.min(end, nodeEnd) - nodeStart;
      if (!node.data.slice(from, to).trim()) continue;
      let target = node;
      if (to < target.data.length) target.splitText(to);
      if (from > 0) target = target.splitText(from);
      const span = document.createElement("span");
      span.className = "notes-highlight";
      span.dataset.noteId = note.id;
      target.before(span);
      span.append(target);
    }
  }

  function highlightsFor(id) {
    return document.querySelectorAll(`.notes-highlight[data-note-id="${id}"]`);
  }

  function unwrap(id) {
    for (const span of highlightsFor(id)) {
      const parent = span.parentNode;
      span.replaceWith(...span.childNodes);
      parent.normalize();
    }
  }

  function highlightAll() {
    missing = new Set();
    for (const note of notes) {
      const index = textIndex();
      const at = locate(note, index.text);
      if (at === -1) missing.add(note.id);
      else wrap(note, at, at + note.quote.length, index);
    }
  }

  // ---- Creating a note ----------------------------------------------------------
  function selectedRange() {
    const selection = getSelection();
    if (!selection.rangeCount || selection.isCollapsed || !A11y.selectedText()) return null;
    const range = selection.getRangeAt(0);
    const touches = (node) => (node.nodeType === Node.ELEMENT_NODE ? node : node.parentElement)?.closest(NO_NOTES);
    if (touches(range.startContainer) || touches(range.endContainer)) return null;
    return range;
  }

  function addNote() {
    const range = selectedRange();
    if (!range) return;
    const index = textIndex();
    let start = offsetOf(range.startContainer, range.startOffset, index);
    let end = offsetOf(range.endContainer, range.endOffset, index);
    while (start < end && /\s/.test(index.text[start])) start += 1;
    while (end > start && /\s/.test(index.text[end - 1])) end -= 1;
    if (start === end) return;

    const note = {
      id: Date.now().toString(36) + Math.random().toString(36).slice(2, 6),
      quote: index.text.slice(start, end),
      prefix: index.text.slice(Math.max(0, start - CONTEXT), start),
      suffix: index.text.slice(end, end + CONTEXT),
      text: "",
      created: new Date().toISOString(),
    };
    getSelection().removeAllRanges();
    hideMenu();
    wrap(note, start, end, index);

    // Keep notes in page order, so the panel reads top to bottom.
    notes.push(note);
    notes.sort((a, b) => order(a) - order(b));
    save();
    render();
    openPanel(note.id);
  }

  function order(note) {
    const first = highlightsFor(note.id)[0];
    if (!first) return Number.MAX_SAFE_INTEGER;
    return [...document.querySelectorAll(".notes-highlight")].indexOf(first);
  }

  function deleteNote(id) {
    const position = notes.findIndex((note) => note.id === id);
    if (position === -1) return;
    notes.splice(position, 1);
    unwrap(id);
    save();
    render();
    const next = list.querySelectorAll("textarea")[Math.min(position, notes.length - 1)];
    if (next) next.focus();
    else panel.querySelector("[data-notes-close]").focus();
    announce("Note deleted.");
  }

  // ---- Selection menu -------------------------------------------------------------
  function buildMenu() {
    menu = document.createElement("span");
    menu.className = "notes-menu";
    menu.setAttribute("data-read-aloud-skip", "");
    menu.hidden = true;
    menu.innerHTML = `
      <button class="button button--small" type="button" data-notes-add>Add note</button>
      ${A11y.speech.supported ? '<button class="button button--small button--secondary" type="button" data-notes-read>Read aloud</button>' : ""}`;
    menu.addEventListener("mousedown", (event) => event.preventDefault());
    menu.querySelector("[data-notes-add]").addEventListener("click", addNote);
    menu.querySelector("[data-notes-read]")?.addEventListener("click", () => {
      A11y.speech.readText(A11y.selectedText());
      hideMenu();
    });
  }

  function onSelectionChange() {
    clearTimeout(selectionTimer);
    selectionTimer = setTimeout(updateMenu, 150);
  }

  // Shown just below the selection. It's placed in the page right after the
  // selected words, so keyboard users can Tab straight to it.
  function updateMenu() {
    const range = selectedRange();
    if (!range) {
      if (!menu.contains(document.activeElement)) hideMenu();
      return;
    }
    const endElement = range.endContainer.nodeType === Node.ELEMENT_NODE ? range.endContainer : range.endContainer.parentElement;
    const host = endElement.closest(BLOCKS) || endElement;
    if (menu.parentNode !== host) host.append(menu);
    menu.hidden = false;
    position(range);
  }

  function position(range) {
    const box = range.getBoundingClientRect();
    const gap = 8;
    const width = menu.offsetWidth;
    const height = menu.offsetHeight;
    let x = Math.min(Math.max(gap, box.left), innerWidth - width - gap);
    let y = box.bottom + gap;
    if (y + height > innerHeight - gap) y = Math.max(gap, box.top - height - gap);
    menu.style.setProperty("--menu-x", `${x}px`);
    menu.style.setProperty("--menu-y", `${y}px`);
    // A transformed ancestor changes what "fixed" is relative to: correct for it.
    const actual = menu.getBoundingClientRect();
    x += x - actual.left;
    y += y - actual.top;
    menu.style.setProperty("--menu-x", `${x}px`);
    menu.style.setProperty("--menu-y", `${y}px`);
  }

  function hideMenu() {
    if (menu) menu.hidden = true;
  }

  function onViewportChange() {
    if (menu.hidden) return;
    const range = selectedRange();
    if (range) position(range);
    else hideMenu();
  }

  // ---- Panel -----------------------------------------------------------------------
  function buildPanel() {
    panel = document.createElement("aside");
    panel.className = "notes-panel";
    panel.id = "notes-panel";
    panel.setAttribute("aria-labelledby", "notes-panel-title");
    panel.setAttribute("data-read-aloud-skip", "");
    panel.hidden = true;
    panel.innerHTML = `
      <div class="notes-panel__header">
        <h2 class="notes-panel__title" id="notes-panel-title">Your notes</h2>
        <button class="button button--quiet button--small" type="button" data-notes-close>Close</button>
      </div>
      <p class="notes-panel__hint">Notes save as you type, in this browser only. To add one, select words on the page and choose "Add note".</p>
      <ol class="notes-panel__list"></ol>
      <p class="visually-hidden" role="status" data-notes-status></p>`;
    list = panel.querySelector(".notes-panel__list");
    panel.querySelector("[data-notes-close]").addEventListener("click", () => closePanel(true));
    panel.addEventListener("keydown", (event) => {
      if (event.key === "Escape") closePanel(true);
    });
    document.body.append(panel);

    toggle = document.createElement("button");
    toggle.className = "button button--small button--secondary";
    toggle.type = "button";
    toggle.setAttribute("aria-controls", "notes-panel");
    toggle.setAttribute("aria-expanded", "false");
    toggle.addEventListener("click", () => (panel.hidden ? openPanel() : closePanel(false)));
  }

  function render() {
    list.replaceChildren(...notes.map(renderItem));
    toggle.textContent = `Notes (${notes.length})`;
    if (notes.length && !toggle.isConnected) A11y.toolbar.add(toggle);
    if (!notes.length && toggle.isConnected) A11y.toolbar.remove(toggle);
  }

  function renderItem(note) {
    const item = document.createElement("li");
    item.className = "notes-panel__item";
    item.dataset.noteId = note.id;
    const fieldId = `note-${note.id}`;
    item.innerHTML = `
      <blockquote class="notes-panel__quote"></blockquote>
      <p class="field__error" hidden>These words have changed on the page, so they're no longer highlighted. Your note is still saved.</p>
      <div class="field">
        <label class="field__label" for="${fieldId}">Note</label>
        <textarea class="input" id="${fieldId}" rows="3" placeholder="A thought, a question, or a word to look up"></textarea>
      </div>
      <div class="cluster">
        <button class="button button--quiet button--small" type="button" data-notes-show>Show in text</button>
        <button class="button button--quiet button--small" type="button" data-notes-delete>Delete note</button>
      </div>`;

    const quote = note.quote.length > 180 ? `${note.quote.slice(0, 180).trim()}…` : note.quote;
    item.querySelector("blockquote").textContent = quote;
    const isMissing = missing.has(note.id);
    item.querySelector(".field__error").hidden = !isMissing;
    item.querySelector("[data-notes-show]").hidden = isMissing;

    const textarea = item.querySelector("textarea");
    textarea.value = note.text || "";
    textarea.addEventListener("input", () => {
      note.text = textarea.value;
      note.updated = new Date().toISOString();
      save();
    });
    textarea.addEventListener("focus", () => setActive(note.id));
    textarea.addEventListener("blur", () => setActive(null));
    item.querySelector("[data-notes-show]").addEventListener("click", () => showInText(note.id));
    item.querySelector("[data-notes-delete]").addEventListener("click", () => deleteNote(note.id));
    return item;
  }

  function setActive(id) {
    for (const span of document.querySelectorAll(".notes-highlight--active")) span.classList.remove("notes-highlight--active");
    if (id) highlightsFor(id).forEach((span) => span.classList.add("notes-highlight--active"));
  }

  function showInText(id) {
    const first = highlightsFor(id)[0];
    if (!first) return;
    first.scrollIntoView({ block: "center", behavior: A11y.reducedMotion() ? "auto" : "smooth" });
    setActive(id);
  }

  function openPanel(focusId) {
    panel.hidden = false;
    root.setAttribute("data-notes-open", "");
    toggle.setAttribute("aria-expanded", "true");
    const target = focusId ? panel.querySelector(`#note-${focusId}`) : list.querySelector("textarea") || panel.querySelector("[data-notes-close]");
    target?.focus();
  }

  function closePanel(returnFocus) {
    if (panel.hidden) return;
    panel.hidden = true;
    root.removeAttribute("data-notes-open");
    toggle.setAttribute("aria-expanded", "false");
    setActive(null);
    if (returnFocus && toggle.isConnected) toggle.focus();
  }

  function announce(message) {
    panel.querySelector("[data-notes-status]").textContent = message;
  }

  // Clicking highlighted words opens their note (the panel's "Show in text"
  // is the keyboard route the other way).
  function onClick(event) {
    const span = event.target.closest(".notes-highlight");
    if (!span || event.target.closest("a") || !getSelection().isCollapsed) return;
    if (!notes.some((note) => note.id === span.dataset.noteId)) return;
    openPanel(span.dataset.noteId);
  }

  // ---- Turning notes on and off ------------------------------------------------------
  function start() {
    if (active) return;
    active = true;
    if (!panel) {
      buildMenu();
      buildPanel();
    }
    notes = load();
    highlightAll();
    render();
    document.addEventListener("selectionchange", onSelectionChange);
    document.addEventListener("click", onClick);
    addEventListener("scroll", onViewportChange, { passive: true });
    addEventListener("resize", onViewportChange);
  }

  function stop() {
    if (!active) return;
    active = false;
    closePanel(false);
    hideMenu();
    menu.remove();
    notes.forEach((note) => unwrap(note.id));
    notes = [];
    render();
    document.removeEventListener("selectionchange", onSelectionChange);
    document.removeEventListener("click", onClick);
    removeEventListener("scroll", onViewportChange);
    removeEventListener("resize", onViewportChange);
  }

  document.addEventListener("a11y:change", (event) => (event.detail.notes ? start() : stop()));
  document.addEventListener("a11y:notes-cleared", () => {
    if (!active) return;
    stop();
    start();
  });

  A11y.notes = {
    get: () => notes.map((note) => ({ ...note })),
    open: () => openPanel(),
  };

  if (A11y.get().notes) start();
})();
