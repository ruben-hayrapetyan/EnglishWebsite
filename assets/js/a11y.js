/* ==========================================================================
   Reader preferences. Applies the choices made on settings.html to every
   page, and adds the read-aloud buttons, reading ruler and notes (by
   loading assets/js/notes.js) when they're on.

   Every page loads this in <head>, BEFORE the stylesheet and WITHOUT defer,
   so the saved theme and text size are in place before the first paint:
     <script src="assets/js/a11y.js"></script>

   It only writes data-* attributes on <html>; tokens.css turns those into
   token values. Page scripts can use window.A11y (see ACCESSIBILITY.md):
     A11y.get()            the current preferences
     A11y.reducedMotion()  true when the reader wants less motion
     "a11y:change"         event on document when preferences change
   Shared file: change it only in a design/* branch.
   ========================================================================== */

(function () {
  const STORAGE_KEY = "english-website:reader-preferences";

  const DEFAULTS = {
    theme: "auto",          // auto | light | dark | sepia | contrast-light | contrast-dark | custom
    customBg: "",           // #rrggbb, used by the custom theme
    customText: "",
    customAccent: "",
    textSize: "100",        // percent: 75 | 80 | 90 | 100 | 112 | 125 | 150 | 175 | 200
    font: "default",        // default | hyperlegible | lexend | opendyslexic | serif | system | mono
    weight: "regular",      // regular | semibold | bold
    lineSpacing: "default", // default | wide | wider
    textSpacing: "default", // default | wide | wider (letters and words)
    lineLength: "default",  // default | narrow
    motion: "auto",         // auto | reduce
    emphasis: "default",    // default | strong (thicker underlines and focus rings)
    ruler: false,
    notes: true,            // highlight text and keep notes (assets/js/notes.js)
    speech: false,          // show the read-aloud buttons on every page
    voice: "",              // SpeechSynthesisVoice.voiceURI; "" is the browser default
    rate: 1,
    pitch: 1,
    volume: 1,
    followAlong: true,      // highlight and scroll to the part being read
  };

  // Preference name -> attribute on <html>. The default value removes it.
  const ATTRIBUTES = {
    theme: "data-theme",
    textSize: "data-text-size",
    font: "data-font",
    weight: "data-weight",
    lineSpacing: "data-line-spacing",
    textSpacing: "data-text-spacing",
    lineLength: "data-line-length",
    motion: "data-motion",
    emphasis: "data-emphasis",
  };

  const HEX = /^#[0-9a-f]{6}$/i;
  const root = document.documentElement;
  const scriptUrl = document.currentScript?.src || "assets/js/a11y.js";
  const NOTES_PREFIX = "english-website:notes:";
  let prefs = load();

  function load() {
    let saved = {};
    try {
      saved = JSON.parse(localStorage.getItem(STORAGE_KEY)) || {};
    } catch (error) {
      // Storage blocked or corrupt: fall back to the defaults.
    }
    const loaded = { ...DEFAULTS };
    for (const key of Object.keys(DEFAULTS)) {
      if (typeof saved[key] === typeof DEFAULTS[key]) loaded[key] = saved[key];
    }
    return loaded;
  }

  function save() {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(prefs));
    } catch (error) {
      // Private mode or storage full: settings still apply to this page.
    }
  }

  function coerce(key, value) {
    const type = typeof DEFAULTS[key];
    if (type === "number") return Number(value);
    if (type === "boolean") return Boolean(value);
    return String(value);
  }

  // ---- Color helpers (WCAG relative luminance and contrast) ---------------
  function luminance(hex) {
    const channels = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255);
    const [r, g, b] = channels.map((c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4));
    return 0.2126 * r + 0.7152 * g + 0.0722 * b;
  }

  function contrast(a, b) {
    const [high, low] = [luminance(a), luminance(b)].sort((x, y) => y - x);
    return (high + 0.05) / (low + 0.05);
  }

  // ---- Apply to <html> (runs immediately, before first paint) --------------
  function applyRoot() {
    for (const [key, attribute] of Object.entries(ATTRIBUTES)) {
      if (prefs[key] === DEFAULTS[key]) root.removeAttribute(attribute);
      else root.setAttribute(attribute, prefs[key]);
    }

    const custom = { "--custom-bg": prefs.customBg, "--custom-text": prefs.customText, "--custom-accent": prefs.customAccent };
    for (const [property, value] of Object.entries(custom)) {
      if (HEX.test(value)) root.style.setProperty(property, value);
      else root.style.removeProperty(property);
    }
    if (HEX.test(prefs.customBg) && luminance(prefs.customBg) < 0.18) root.dataset.customScheme = "dark";
    else delete root.dataset.customScheme;
  }

  // ---- Apply to the page body (once the DOM is ready) ----------------------
  function applyBody() {
    if (prefs.ruler) ruler.enable();
    else ruler.disable();
    if (prefs.speech && speech.supported) bar.show();
    else bar.hide();
    if (prefs.notes) loadNotes();
  }

  // notes.js is loaded on demand, so pages only ever need the one a11y.js tag.
  let notesRequested = false;
  function loadNotes() {
    if (notesRequested) return;
    notesRequested = true;
    const script = document.createElement("script");
    script.src = new URL("notes.js", scriptUrl).href;
    document.head.append(script);
  }

  function whenReady(fn) {
    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", fn, { once: true });
    else fn();
  }

  function changed() {
    applyRoot();
    whenReady(applyBody);
    document.dispatchEvent(new CustomEvent("a11y:change", { detail: { ...prefs } }));
  }

  function reducedMotion() {
    return prefs.motion === "reduce" || matchMedia("(prefers-reduced-motion: reduce)").matches;
  }

  // ---- Reading ruler --------------------------------------------------------
  const ruler = {
    el: null,

    enable() {
      if (this.el) return;
      this.el = document.createElement("div");
      this.el.className = "reading-ruler";
      this.el.setAttribute("aria-hidden", "true");
      this.el.hidden = true;
      document.body.append(this.el);
      addEventListener("pointermove", this.onPointer, { passive: true });
      document.addEventListener("focusin", this.onFocus);
    },

    disable() {
      if (!this.el) return;
      this.el.remove();
      this.el = null;
      removeEventListener("pointermove", this.onPointer);
      document.removeEventListener("focusin", this.onFocus);
    },

    moveTo(y) {
      if (!ruler.el) return;
      ruler.el.hidden = false;
      ruler.el.style.setProperty("--ruler-y", `${Math.round(y)}px`);
    },

    onPointer(event) {
      ruler.moveTo(event.clientY);
    },

    onFocus(event) {
      const box = event.target.getBoundingClientRect();
      ruler.moveTo(box.top + Math.min(box.height, innerHeight) / 2);
    },
  };

  // ---- Read aloud (Web Speech API: free, built into the browser) -----------
  // Text is gathered from [data-read-aloud] containers if the page has any,
  // otherwise from <main>, block by block in reading order.
  const BLOCKS = "p, li, h1, h2, h3, h4, h5, h6, blockquote, figcaption, caption, dt, dd, th, td, summary, legend, label, pre, button";
  const SKIP = "[data-read-aloud-skip], [hidden], [aria-hidden='true'], script, style, noscript, template, svg, .visually-hidden";
  const MAX_CHUNK = 220; // long utterances can stall in some browsers, so speak a sentence or two at a time

  const speech = {
    supported: "speechSynthesis" in window && "SpeechSynthesisUtterance" in window,
    state: "idle", // idle | playing | paused
    queue: [],
    index: 0,
    utterance: null,
    currentEl: null,

    voices() {
      return speech.supported ? speechSynthesis.getVoices() : [];
    },

    // Read the default scope, or the elements given.
    readPage(scopes) {
      const targets = scopes || defaultScopes();
      speech.start(collectSegments(targets));
    },

    readText(text) {
      const lang = root.lang;
      speech.start(chunk(text.replace(/\s+/g, " ")).map((part) => ({ el: null, text: part, lang })));
    },

    start(queue) {
      if (!speech.supported) return;
      speech.stop();
      if (!queue.length) return;
      speech.queue = queue;
      speech.index = 0;
      speech.setState("playing");
      speech.next();
    },

    next() {
      if (speech.state !== "playing") return;
      if (speech.index >= speech.queue.length) {
        speech.stop();
        return;
      }
      const item = speech.queue[speech.index];
      speech.highlight(item.el);

      const utterance = new SpeechSynthesisUtterance(item.text);
      const voice = pickVoice(item.lang);
      if (voice) utterance.voice = voice;
      utterance.lang = voice ? voice.lang : item.lang;
      utterance.rate = prefs.rate;
      utterance.pitch = prefs.pitch;
      utterance.volume = prefs.volume;
      const advance = () => {
        if (speech.utterance !== utterance) return;
        speech.index += 1;
        speech.next();
      };
      utterance.addEventListener("end", advance);
      utterance.addEventListener("error", (event) => {
        if (event.error !== "interrupted" && event.error !== "canceled") advance();
      });
      speech.utterance = utterance;
      speechSynthesis.speak(utterance);
    },

    // Pausing cancels and remembers the place: speechSynthesis.pause() is
    // unreliable across browsers. Resuming repeats the current sentence.
    pause() {
      if (speech.state !== "playing") return;
      speech.setState("paused");
      speech.utterance = null;
      speechSynthesis.cancel();
    },

    resume() {
      if (speech.state !== "paused") return;
      speech.setState("playing");
      speech.next();
    },

    stop() {
      speech.queue = [];
      speech.index = 0;
      speech.utterance = null;
      if (speech.supported) speechSynthesis.cancel();
      speech.highlight(null);
      speech.setState("idle");
    },

    highlight(el) {
      if (speech.currentEl === el) return;
      speech.currentEl?.removeAttribute("data-read-aloud-current");
      speech.currentEl = el;
      if (!el || !prefs.followAlong) return;
      el.setAttribute("data-read-aloud-current", "");
      el.scrollIntoView({ block: "nearest", behavior: reducedMotion() ? "auto" : "smooth" });
    },

    setState(state) {
      if (speech.state === state) return;
      speech.state = state;
      bar.update();
      document.dispatchEvent(new CustomEvent("a11y:speech", { detail: { state } }));
    },
  };

  function defaultScopes() {
    const marked = document.querySelectorAll("[data-read-aloud]");
    if (marked.length) return [...marked];
    return [document.querySelector("main") || document.body];
  }

  function isRendered(el) {
    if (el.checkVisibility) return el.checkVisibility({ visibilityProperty: true, checkVisibilityCSS: true });
    return el.getClientRects().length > 0;
  }

  // Groups the visible text in each scope by its nearest block element, so
  // each item can be highlighted while it's read.
  function collectSegments(scopes) {
    const segments = [];
    for (const scope of scopes) {
      const walker = document.createTreeWalker(scope, NodeFilter.SHOW_ELEMENT | NodeFilter.SHOW_TEXT, {
        acceptNode(node) {
          if (node.nodeType === Node.TEXT_NODE) {
            return node.data.trim() ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT;
          }
          if (node.matches(SKIP) || !isRendered(node)) return NodeFilter.FILTER_REJECT;
          return node.matches("img[alt]:not([alt=''])") ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_SKIP;
        },
      });

      for (let node = walker.nextNode(); node; node = walker.nextNode()) {
        const isText = node.nodeType === Node.TEXT_NODE;
        const el = isText ? node.parentElement : node;
        let block = el.closest(BLOCKS);
        if (!block || !scope.contains(block)) block = el;
        const text = isText ? node.data : ` Image: ${node.alt}. `;
        const last = segments[segments.length - 1];
        if (last && last.el === block) last.text += text;
        else segments.push({ el: block, text, lang: block.closest("[lang]")?.lang || root.lang });
      }
    }

    return segments.flatMap((segment) => {
      const text = segment.text.replace(/\s+/g, " ").trim();
      return text ? chunk(text).map((part) => ({ ...segment, text: part })) : [];
    });
  }

  function chunk(text) {
    const sentences = text.match(/[^.!?]*[.!?]+["'”’)\]]*\s*|[^.!?]+$/g) || [text];
    const parts = [];
    let buffer = "";
    for (const sentence of sentences) {
      if (buffer && (buffer + sentence).length > MAX_CHUNK) {
        parts.push(buffer.trim());
        buffer = "";
      }
      buffer += sentence;
    }
    if (buffer.trim()) parts.push(buffer.trim());
    return parts;
  }

  // The chosen voice, unless the text is in another language (lang="...").
  function pickVoice(lang) {
    const voices = speech.voices();
    const chosen = voices.find((voice) => voice.voiceURI === prefs.voice);
    const base = (lang || "").toLowerCase().split("-")[0];
    const speaks = (voice) => voice.lang.toLowerCase().replace("_", "-").split("-")[0] === base;
    if (chosen && (!base || speaks(chosen))) return chosen;
    if (!base) return null;
    return voices.find((voice) => speaks(voice) && voice.default) || voices.find(speaks) || null;
  }

  // ---- Reader bar: the floating controls for read-aloud and notes --------
  // Shown only while something is in it. Groups are added with toolbar.add().
  const toolbar = {
    el: null,

    add(group, atStart) {
      if (!toolbar.el) {
        toolbar.el = document.createElement("div");
        toolbar.el.className = "reader-bar";
        toolbar.el.setAttribute("role", "region");
        toolbar.el.setAttribute("aria-label", "Reading tools");
        toolbar.el.setAttribute("data-read-aloud-skip", "");
        // Clicking a button here mustn't clear the reader's text selection.
        toolbar.el.addEventListener("mousedown", (event) => {
          if (event.target.closest("button")) event.preventDefault();
        });
        // First in <main>, so it's early in the tab order but out of the text.
        const main = document.querySelector("main");
        if (main) main.prepend(toolbar.el);
        else document.body.append(toolbar.el);
      }
      if (atStart) toolbar.el.prepend(group);
      else toolbar.el.append(group);
    },

    remove(group) {
      group.remove();
      if (toolbar.el && !toolbar.el.children.length) {
        toolbar.el.remove();
        toolbar.el = null;
      }
    },
  };

  // ---- Read-aloud buttons ---------------------------------------------------
  // With text selected, reads only the selection; otherwise the whole page
  // from the top.
  const bar = {
    group: null,
    main: null,
    stopButton: null,
    selection: "",

    show() {
      if (bar.group) return;
      bar.group = document.createElement("div");
      bar.group.className = "reader-bar__group";
      bar.group.innerHTML = `
        <button class="button button--small" type="button"></button>
        <button class="button button--small button--secondary" type="button" hidden>Stop</button>`;
      [bar.main, bar.stopButton] = bar.group.querySelectorAll("button");

      bar.main.addEventListener("click", () => {
        if (speech.state === "playing") speech.pause();
        else if (speech.state === "paused") speech.resume();
        else if (bar.selection) speech.readText(bar.selection);
        else speech.readPage();
      });
      bar.stopButton.addEventListener("click", speech.stop);
      document.addEventListener("selectionchange", bar.onSelection);
      toolbar.add(bar.group, true);
      bar.onSelection();
    },

    hide() {
      if (!bar.group) return;
      speech.stop();
      document.removeEventListener("selectionchange", bar.onSelection);
      toolbar.remove(bar.group);
      bar.group = null;
    },

    onSelection() {
      bar.selection = selectedText();
      bar.update();
    },

    update() {
      if (!bar.group) return;
      const labels = {
        playing: "Pause",
        paused: "Resume",
        idle: bar.selection ? "Read selection aloud" : "Read page aloud",
      };
      bar.main.textContent = labels[speech.state];
      bar.stopButton.hidden = speech.state === "idle";
    },
  };

  // The selected text, if the selection is inside the page's reading area.
  function selectedText() {
    const selection = getSelection();
    if (!selection.rangeCount || selection.isCollapsed) return "";
    const inScope = defaultScopes().some((scope) => scope.contains(selection.anchorNode));
    return inScope ? selection.toString().trim() : "";
  }

  // ---- Notes storage (used by notes.js and settings.html) ------------------
  function noteKeys() {
    const keys = [];
    try {
      for (let i = 0; i < localStorage.length; i += 1) {
        const key = localStorage.key(i);
        if (key.startsWith(NOTES_PREFIX)) keys.push(key);
      }
    } catch (error) {
      // Storage blocked: there are no saved notes to find.
    }
    return keys;
  }

  // ---- Wiring -----------------------------------------------------------------
  if (speech.supported) {
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && speech.state !== "idle") speech.stop();
    });
    addEventListener("pagehide", () => speechSynthesis.cancel());
  }

  // Keep other open tabs in step.
  addEventListener("storage", (event) => {
    if (event.key !== STORAGE_KEY) return;
    prefs = load();
    changed();
  });

  window.A11y = {
    defaults: { ...DEFAULTS },

    get() {
      return { ...prefs };
    },

    set(changes) {
      for (const [key, value] of Object.entries(changes)) {
        if (key in DEFAULTS) prefs[key] = coerce(key, value);
      }
      save();
      changed();
    },

    reset() {
      prefs = { ...DEFAULTS };
      save();
      changed();
    },

    reducedMotion,
    contrast,
    scopes: defaultScopes,
    selectedText,
    toolbar,
    notesKey: (path = location.pathname) => NOTES_PREFIX + path,

    // How many pages have saved notes.
    countNotedPages() {
      return noteKeys().length;
    },

    clearNotes() {
      try {
        noteKeys().forEach((key) => localStorage.removeItem(key));
      } catch (error) {
        // Storage blocked: nothing was saved.
      }
      document.dispatchEvent(new CustomEvent("a11y:notes-cleared"));
    },
    speech,
  };

  applyRoot();
  whenReady(applyBody);
})();
