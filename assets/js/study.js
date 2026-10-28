/* ==========================================================================
   Study materials engine. Shared by every study-<chapter>.html page.
   It finds three kinds of plain HTML and makes them interactive:
     [data-deck]        slides      -> one at a time, keys, swipe, full screen
     [data-flashcards]  glossary    -> flip cards with spaced practice
     [data-quiz]        questions   -> one at a time, confidence, feedback
   The value of each data attribute is the chapter id, used to remember
   progress in this browser. Without this script the HTML is still complete:
   slides are a stack, flashcards a glossary and quiz answers sit in .reveal.
   Authors never edit this file; they only write the HTML (see _study-template.html).
   ========================================================================== */

/* ---- Helpers ------------------------------------------------------------ */

// Progress is a per-browser convenience. Storage can be blocked (private
// windows, strict settings), so every read and write is allowed to fail.
const store = {
  get(key, fallback) {
    try {
      const value = localStorage.getItem(key);
      return value === null ? fallback : JSON.parse(value);
    } catch {
      return fallback;
    }
  },
  set(key, value) {
    try {
      localStorage.setItem(key, JSON.stringify(value));
    } catch {
      /* Progress just won't be remembered. */
    }
  },
  remove(key) {
    try {
      localStorage.removeItem(key);
    } catch {
      /* Nothing to clear. */
    }
  },
};

// Builds an element: h("button", { class: "button", type: "button" }, "Label")
function h(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [name, value] of Object.entries(attrs)) {
    if (value === false || value === null || value === undefined) continue;
    if (name === "html") node.innerHTML = value;
    else if (name.startsWith("on")) node.addEventListener(name.slice(2), value);
    else node.setAttribute(name, value === true ? "" : value);
  }
  node.append(...children.flat().filter((child) => child !== null && child !== undefined));
  return node;
}

function shuffle(items) {
  const copy = [...items];
  for (let i = copy.length - 1; i > 0; i -= 1) {
    const j = Math.floor(Math.random() * (i + 1));
    [copy[i], copy[j]] = [copy[j], copy[i]];
  }
  return copy;
}

function isTyping(event) {
  return event.target.closest("input, textarea, select, [contenteditable]");
}

const LETTERS = "ABCDEFGHIJ";

/* ---- Deck ----------------------------------------------------------------- */

function initDeck(deck) {
  const stage = deck.querySelector(".deck__stage");
  const slides = [...deck.querySelectorAll(".deck__slide")];
  if (!stage || slides.length < 2) return;

  const key = `study:${deck.dataset.deck}:slide`;
  let current = Math.min(Math.max(store.get(key, 0), 0), slides.length - 1);

  deck.dataset.enhanced = "";
  stage.tabIndex = 0;
  stage.setAttribute("role", "region");
  stage.setAttribute("aria-roledescription", "slide deck");
  stage.setAttribute("aria-label", deck.getAttribute("aria-label") || "Slides");
  slides.forEach((slide, i) => {
    slide.setAttribute("aria-roledescription", "slide");
    slide.dataset.index = String(i + 1);
  });

  const prev = h("button", { class: "button button--secondary button--small", type: "button" }, "Previous slide");
  const next = h("button", { class: "button button--small", type: "button" }, "Next slide");
  const counter = h("span", { class: "deck__counter", "aria-live": "polite" });
  const fill = h("div", { class: "deck__progress-fill" });
  const progress = h("div", { class: "deck__progress", "aria-hidden": "true" }, fill);
  const controls = h("div", { class: "deck__controls" }, prev, progress, counter, next);

  if (document.fullscreenEnabled) {
    const full = h("button", { class: "button button--quiet button--small", type: "button" }, "Full screen");
    full.addEventListener("click", () => {
      if (document.fullscreenElement) document.exitFullscreen();
      else deck.requestFullscreen().then(() => stage.focus()).catch(() => {});
    });
    document.addEventListener("fullscreenchange", () => {
      full.textContent = document.fullscreenElement === deck ? "Exit full screen" : "Full screen";
    });
    controls.append(full);
  }

  deck.append(controls);
  deck.append(h("p", { class: "deck__hint" }, "Use the arrow keys or swipe to move between slides."));

  function show(index) {
    current = Math.min(Math.max(index, 0), slides.length - 1);
    slides.forEach((slide, i) => {
      slide.toggleAttribute("data-current", i === current);
      slide.toggleAttribute("data-before", i < current);
      slide.inert = i !== current;
    });
    counter.textContent = `${current + 1} / ${slides.length}`;
    fill.style.setProperty("--progress", (current + 1) / slides.length);
    prev.disabled = current === 0;
    next.disabled = current === slides.length - 1;
    store.set(key, current);
  }

  prev.addEventListener("click", () => show(current - 1));
  next.addEventListener("click", () => show(current + 1));

  deck.addEventListener("keydown", (event) => {
    if (isTyping(event)) return;
    const moves = { ArrowLeft: -1, ArrowRight: 1, PageUp: -1, PageDown: 1 };
    if (event.key in moves) show(current + moves[event.key]);
    else if (event.key === "Home") show(0);
    else if (event.key === "End") show(slides.length - 1);
    else return;
    event.preventDefault();
  });

  // Swipe on touch screens: a mostly horizontal drag of a fair distance.
  let startX = null;
  let startY = null;
  stage.addEventListener("pointerdown", (event) => {
    if (event.pointerType !== "mouse") [startX, startY] = [event.clientX, event.clientY];
  });
  stage.addEventListener("pointerup", (event) => {
    if (startX === null) return;
    const dx = event.clientX - startX;
    const dy = event.clientY - startY;
    startX = null;
    if (Math.abs(dx) > 48 && Math.abs(dx) > Math.abs(dy) * 1.5) show(current + (dx < 0 ? 1 : -1));
  });

  show(current);
}

/* ---- Flashcards --------------------------------------------------------
   Spaced practice in the Leitner style. Each term sits in a box from 0 to 3.
   "Got it" moves it up a box and out of this round; "Still learning" drops
   it to box 0 and brings it back a few cards later. A round only deals terms
   below box 3, weakest first, so practice goes where it is needed. */

const KNOWN_BOX = 3;

function initFlashcards(root) {
  const list = root.querySelector(".flashcards__list");
  if (!list) return;
  const cards = [...list.querySelectorAll(".flashcards__item")].map((item) => ({
    term: item.querySelector(".flashcards__term").textContent.trim(),
    definition: item.querySelector(".flashcards__definition").textContent.trim(),
  }));
  if (!cards.length) return;

  const id = root.dataset.flashcards;
  const boxesKey = `study:${id}:cards`;
  const directionKey = `study:${id}:cards-direction`;
  let boxes = store.get(boxesKey, {});
  let definitionFirst = store.get(directionKey, false);
  let queue = [];
  let dealt = 0;
  let flipped = false;

  const boxOf = (card) => boxes[card.term] || 0;

  // ---- Build the app ----
  const status = h("span");
  const tally = h("span");
  const known = h("div", { class: "flashcards__meter-known" });
  const learning = h("div", { class: "flashcards__meter-learning" });
  const meter = h("div", { class: "flashcards__meter", role: "img" }, known, learning);

  const frontLabel = h("span", { class: "flashcards__label" });
  const frontText = h("span", { class: "flashcards__prompt" });
  const backLabel = h("span", { class: "flashcards__label" });
  const backText = h("span", { class: "flashcards__prompt" });
  const front = h("span", { class: "flashcards__face flashcards__face--front" },
    frontLabel,
    frontText,
    h("span", { class: "flashcards__hint" }, "Recall it, then tap the card or press Space to check."));
  const back = h("span", { class: "flashcards__face flashcards__face--back", "aria-hidden": "true" },
    backLabel, backText,
    h("span", { class: "flashcards__hint" }, "Be honest: rate yourself below."));
  const card = h("button", { class: "flashcards__card", type: "button" }, front, back);

  const reveal = h("button", { class: "button", type: "button" }, "Show the answer");
  const again = h("button", { class: "button button--secondary", type: "button", hidden: true }, "Still learning");
  const good = h("button", { class: "button", type: "button", hidden: true }, "Got it");
  const rate = h("div", { class: "cluster" }, reveal, again, good);

  const done = h("div", { class: "flashcards__done", hidden: true });
  const directionId = `${id}-cards-direction`;
  const direction = h("input", { type: "checkbox", id: directionId });
  direction.checked = definitionFirst;
  const reset = h("button", { class: "button button--quiet button--small", type: "button" }, "Reset my progress");
  const options = h("div", { class: "cluster", style: "--cluster-space: var(--space-m)" },
    h("label", { class: "checkbox", for: directionId }, direction, "Show the definition first"),
    reset);

  const app = h("div", { class: "flashcards__app" },
    h("div", { class: "flashcards__status" }, status, tally),
    meter, card, done, rate, options);

  // The glossary stays available, folded under the app.
  const browse = h("details", { class: "reveal" },
    h("summary", { class: "reveal__summary" }, `Browse all ${cards.length} terms`),
    h("div", { class: "reveal__body" }));
  list.replaceWith(browse);
  browse.querySelector(".reveal__body").append(list);
  root.prepend(app);

  // ---- Behavior ----
  function updateTally() {
    const counts = cards.reduce((acc, c) => {
      const box = boxOf(c);
      if (box >= KNOWN_BOX) acc.known += 1;
      else if (box > 0) acc.learning += 1;
      else acc.fresh += 1;
      return acc;
    }, { known: 0, learning: 0, fresh: 0 });
    tally.textContent = `${counts.known} known · ${counts.learning} getting there · ${counts.fresh} new`;
    known.style.setProperty("--known", counts.known / cards.length);
    learning.style.setProperty("--learning", counts.learning / cards.length);
    meter.setAttribute("aria-label", `${counts.known} of ${cards.length} terms known`);
  }

  function newRound() {
    const due = cards.filter((c) => boxOf(c) < KNOWN_BOX);
    // Weakest first, shuffled within each box.
    queue = [0, 1, 2].flatMap((box) => shuffle(due.filter((c) => boxOf(c) === box)));
    dealt = 0;
    render();
  }

  function setFlipped(value) {
    flipped = value;
    card.toggleAttribute("data-flipped", flipped);
    front.setAttribute("aria-hidden", String(flipped));
    back.setAttribute("aria-hidden", String(!flipped));
    reveal.hidden = flipped;
    again.hidden = !flipped;
    good.hidden = !flipped;
  }

  function render() {
    updateTally();
    const current = queue[0];
    if (!current) {
      showDone();
      return;
    }
    card.hidden = false;
    done.hidden = true;
    rate.hidden = false;
    const ask = definitionFirst ? current.definition : current.term;
    const answer = definitionFirst ? current.term : current.definition;
    frontLabel.textContent = definitionFirst ? "Definition" : "Term";
    backLabel.textContent = definitionFirst ? "Term" : "Definition";
    frontText.textContent = ask;
    backText.textContent = answer;
    frontText.classList.toggle("flashcards__prompt--text", definitionFirst);
    backText.classList.toggle("flashcards__prompt--text", !definitionFirst);
    status.textContent = `${queue.length} left in this round`;
    setFlipped(false);
  }

  function showDone() {
    card.hidden = true;
    rate.hidden = true;
    done.hidden = false;
    const remaining = cards.filter((c) => boxOf(c) < KNOWN_BOX).length;
    status.textContent = "Round complete";
    done.replaceChildren();
    if (remaining === 0) {
      done.append(
        h("p", { class: "flashcards__done-title" }, `You know all ${cards.length} terms.`),
        h("p", {}, "Come back in a day or two and run them again; spacing out reviews is what makes them stick."),
        h("div", { class: "cluster" },
          h("button", { class: "button", type: "button", onclick: () => { boxes = {}; store.set(boxesKey, boxes); newRound(); } }, "Practice all terms again")));
    } else {
      done.append(
        h("p", { class: "flashcards__done-title" }, `Round done. ${remaining} ${remaining === 1 ? "term needs" : "terms need"} more practice.`),
        h("p", {}, "The next round deals only those, weakest first."),
        h("div", { class: "cluster" },
          h("button", { class: "button", type: "button", onclick: newRound }, "Start the next round")));
    }
    done.querySelector("button").focus();
  }

  function grade(gotIt) {
    const current = queue.shift();
    if (!current) return;
    dealt += 1;
    if (gotIt) {
      boxes[current.term] = Math.min(boxOf(current) + 1, KNOWN_BOX);
    } else {
      boxes[current.term] = 0;
      // Bring it back after a few other cards, so recalling it takes effort.
      queue.splice(Math.min(3, queue.length), 0, current);
    }
    store.set(boxesKey, boxes);
    render();
    if (queue.length) card.focus();
  }

  card.addEventListener("click", () => setFlipped(!flipped));
  reveal.addEventListener("click", () => {
    setFlipped(true);
    good.focus();
  });
  again.addEventListener("click", () => grade(false));
  good.addEventListener("click", () => grade(true));
  direction.addEventListener("change", () => {
    definitionFirst = direction.checked;
    store.set(directionKey, definitionFirst);
    render();
  });
  reset.addEventListener("click", () => {
    boxes = {};
    store.remove(boxesKey);
    newRound();
  });

  // 1 = still learning, 2 = got it, once the card is turned over.
  app.addEventListener("keydown", (event) => {
    if (isTyping(event) || !flipped) return;
    if (event.key === "1") grade(false);
    else if (event.key === "2") grade(true);
  });

  newRound();
}

/* ---- Quiz ----------------------------------------------------------------
   Asks for a confidence rating with each answer. Feedback then explains the
   option picked, and flags confident mistakes: those are the ones most worth
   correcting, and the ones people tend to remember once corrected. */

const CONFIDENCE = [
  { value: "guess", label: "Guessing" },
  { value: "unsure", label: "Fairly sure" },
  { value: "sure", label: "Certain" },
];

function readQuestions(quiz) {
  return [...quiz.querySelectorAll(".quiz__item")].map((item, index) => {
    const options = [...item.querySelectorAll(".quiz__options > li")].map((option) => ({
      html: option.innerHTML.trim(),
      correct: option.hasAttribute("data-correct"),
      why: option.dataset.why || "",
    }));
    const explanation = item.querySelector(".quiz__explanation");
    return {
      index,
      prompt: item.querySelector(".quiz__question").innerHTML.trim(),
      options,
      explanation: explanation ? explanation.innerHTML.trim() : "",
      objective: item.dataset.objective || "",
      answer: item.dataset.answer === undefined ? null : Number(item.dataset.answer),
      tolerance: Number(item.dataset.tolerance || 0),
      unit: item.dataset.unit || "",
    };
  });
}

// Learning objectives come from a list on the page marked data-objectives,
// whose items carry data-objective="LO1" and the objective text.
function readObjectives() {
  const map = new Map();
  document.querySelectorAll("[data-objectives] [data-objective]").forEach((item) => {
    map.set(item.dataset.objective, item.textContent.replace(/\s+/g, " ").trim());
  });
  return map;
}

function initQuiz(quiz) {
  const questions = readQuestions(quiz);
  if (!questions.length) return;
  const objectives = readObjectives();
  const id = quiz.dataset.quiz;
  const bestKey = `study:${id}:quiz-best`;

  let round = questions;
  let position = 0;
  let results = [];

  const app = h("div", { class: "quiz__app", role: "region", "aria-label": "Practice quiz" });
  quiz.hidden = true;
  quiz.after(app);

  function objectiveTag(code) {
    if (!code) return null;
    const text = objectives.get(code) || code;
    const level = text.match(/\(([^)]+)\)/);
    return h("span", { class: "tag tag--accent", title: text }, level ? `${code} · ${level[1]}` : code);
  }

  function header(label, fraction) {
    return [
      h("div", { class: "quiz__header" }, h("span", { class: "quiz__count" }, label), objectiveTag(round[position]?.objective)),
      h("div", { class: "quiz__progress", "aria-hidden": "true" },
        h("div", { class: "quiz__progress-fill", style: `--progress: ${fraction}` })),
    ];
  }

  function askQuestion() {
    const q = round[position];
    const name = `${id}-q${q.index}`;
    const error = h("p", { class: "field__error", id: `${name}-error`, hidden: true });
    let answerField;

    if (q.options.length) {
      answerField = h("fieldset", { class: "quiz__fieldset" },
        h("legend", { class: "quiz__prompt", html: q.prompt }),
        q.options.map((option, i) =>
          h("label", { class: "quiz__option" },
            h("input", { type: "radio", name, value: String(i) }),
            h("span", { class: "quiz__letter", "aria-hidden": "true" }, LETTERS[i]),
            h("span", { class: "quiz__option-text", html: option.html }))));
    } else {
      const inputId = `${name}-input`;
      answerField = h("div", { class: "quiz__fieldset" },
        h("p", { class: "quiz__prompt", id: `${name}-prompt`, html: q.prompt }),
        h("div", { class: "field" },
          h("label", { class: "field__label", for: inputId }, q.unit ? `Your answer, in ${q.unit}` : "Your answer"),
          h("input", { class: "input quiz__number", id: inputId, type: "text", inputmode: "decimal", autocomplete: "off", "aria-describedby": `${name}-prompt ${name}-error` })));
    }

    const confidence = h("fieldset", { class: "quiz__confidence" },
      h("legend", { class: "quiz__confidence-label" }, "How sure are you?"),
      h("span", { class: "quiz__segments" },
        CONFIDENCE.map((c) =>
          h("label", { class: "quiz__segment" },
            h("input", { type: "radio", name: `${name}-confidence`, value: c.value }), c.label))));

    const submit = h("button", { class: "button", type: "submit" }, "Check answer");
    const form = h("form", { class: "quiz__form", novalidate: true },
      answerField, confidence, error, h("div", { class: "cluster" }, submit));

    form.addEventListener("submit", (event) => {
      event.preventDefault();
      checkAnswer(q, form, error);
    });

    app.replaceChildren(...header(`Question ${position + 1} of ${round.length}`, position / round.length), form);
  }

  function checkAnswer(q, form, error) {
    const chosen = form.querySelector(`input[name="${id}-q${q.index}"]:checked`);
    const numberInput = form.querySelector(".quiz__number");
    const confidence = form.querySelector(`input[name="${id}-q${q.index}-confidence"]:checked`)?.value || "";
    let correct;
    let pickedWhy = "";
    let given = "";

    if (q.options.length) {
      if (!chosen) {
        error.textContent = "Pick an answer first, even if it's a guess.";
        error.hidden = false;
        form.querySelector('input[type="radio"]').focus();
        return;
      }
      const pick = Number(chosen.value);
      correct = q.options[pick].correct;
      pickedWhy = q.options[pick].why;
      form.querySelectorAll(".quiz__option").forEach((label, i) => {
        const option = q.options[i];
        label.dataset.result = option.correct ? "correct" : i === pick ? "incorrect" : "dimmed";
      });
    } else {
      const value = Number(numberInput.value.replace(/,/g, "").trim());
      if (numberInput.value.trim() === "" || Number.isNaN(value)) {
        error.textContent = "Type a number, like 25 or 0.5.";
        error.hidden = false;
        numberInput.setAttribute("aria-invalid", "true");
        numberInput.focus();
        return;
      }
      given = `${value}${q.unit ? ` ${q.unit}` : ""}`;
      correct = Math.abs(value - q.answer) <= q.tolerance;
    }

    form.querySelectorAll("input").forEach((input) => { input.disabled = true; });
    form.querySelector('button[type="submit"]').remove();
    error.hidden = true;
    results.push({ question: q, correct, confidence });

    const rightOption = q.options.findIndex((o) => o.correct);
    const answerText = q.options.length
      ? `The answer is ${LETTERS[rightOption]}.`
      : `The answer is ${q.answer.toLocaleString()}${q.unit ? ` ${q.unit}` : ""}${correct ? "" : `; you said ${given}`}.`;

    let nudge = null;
    if (!correct && confidence === "sure") {
      nudge = "You were certain about this one, so it's worth a second look. Confident mistakes are the easiest ones to fix once you see why.";
    } else if (correct && confidence === "guess") {
      nudge = "Right, but you were guessing. Read the explanation so you know it next time.";
    }

    const isLast = position === round.length - 1;
    const next = h("button", { class: "button", type: "button" }, isLast ? "See my results" : "Next question");
    next.addEventListener("click", () => {
      position += 1;
      if (position < round.length) askQuestion();
      else showResults();
      app.querySelector("input, button")?.focus();
    });

    const feedback = h("div", { class: `quiz__feedback${correct ? "" : " quiz__feedback--incorrect"}`, tabindex: "-1", role: "status" },
      h("p", { class: "quiz__feedback-title" }, correct ? "Correct." : "Not quite."),
      pickedWhy && !correct ? h("p", { html: pickedWhy }) : null,
      h("p", { class: "quiz__key" }, answerText),
      q.explanation ? h("div", { class: "quiz__explanation", html: q.explanation }) : null,
      nudge ? h("p", { class: "quiz__nudge" }, nudge) : null);

    form.append(feedback, h("div", { class: "cluster" }, next));
    feedback.focus({ preventScroll: true });
    feedback.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }

  function showResults() {
    const score = results.filter((r) => r.correct).length;
    const isFullRound = round.length === questions.length;
    const best = store.get(bestKey, null);
    if (isFullRound && (best === null || score > best)) store.set(bestKey, score);

    // Score by learning objective.
    const byObjective = new Map();
    results.forEach(({ question, correct }) => {
      const code = question.objective || "Other";
      const entry = byObjective.get(code) || { right: 0, total: 0 };
      entry.right += correct ? 1 : 0;
      entry.total += 1;
      byObjective.set(code, entry);
    });
    const breakdown = h("ul", { class: "quiz__breakdown" },
      [...byObjective].map(([code, { right, total }]) =>
        h("li", { class: "quiz__objective" },
          h("span", {}, h("strong", {}, code), objectives.has(code) ? ` ${objectives.get(code).replace(/^LO\d+\s*/, "")}` : ""),
          h("span", { class: "quiz__objective-score" }, `${right}/${total}`),
          h("span", { class: "quiz__bar", "aria-hidden": "true" },
            h("span", { class: "quiz__bar-fill", style: `--value: ${right / total}`, "data-low": right / total < 0.6 })))));

    const missed = results.filter((r) => !r.correct).map((r) => r.question);
    const confidentMisses = results.filter((r) => !r.correct && r.confidence === "sure").length;
    const message = score === results.length
      ? "Every one right. Try the explain-it-back prompts next, or come back in a few days and see if it holds."
      : `Look at the objectives with the shortest bars first, then retry the ${missed.length} you missed.`;

    const actions = h("div", { class: "cluster" });
    if (missed.length) {
      actions.append(h("button", { class: "button", type: "button", onclick: () => start(missed) },
        `Retry the ${missed.length} I missed`));
    }
    actions.append(h("button", { class: `button${missed.length ? " button--secondary" : ""}`, type: "button", onclick: () => start(shuffle(questions)) },
      "Start over in a new order"));

    position = round.length;
    app.replaceChildren(...[
      ...header(isFullRound ? "Your results" : "Retry results", 1),
      h("p", { class: "quiz__score" }, String(score), h("span", { class: "quiz__score-total" }, `out of ${results.length}`)),
      h("p", {}, message),
      confidentMisses ? h("p", { class: "quiz__nudge" }, `${confidentMisses} of your misses ${confidentMisses === 1 ? "was" : "were"} marked "Certain". Reread those explanations first.`) : null,
      best !== null && isFullRound ? h("p", { class: "quiz__count" }, `Your previous best: ${best} of ${questions.length}`) : null,
      h("p", { class: "quiz__confidence-label" }, "By learning objective"),
      breakdown,
      actions,
    ].filter(Boolean));
  }

  function start(list) {
    round = list;
    position = 0;
    results = [];
    askQuestion();
  }

  start(questions);
}

/* ---- Start ---------------------------------------------------------------- */

document.querySelectorAll("[data-deck]").forEach(initDeck);
document.querySelectorAll("[data-flashcards]").forEach(initFlashcards);
document.querySelectorAll("[data-quiz]").forEach(initQuiz);
