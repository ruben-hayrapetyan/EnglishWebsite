/* Settings page. Every form control's name is a preference name from
   assets/js/a11y.js; changing a control applies and saves it at once
   through window.A11y (a11y.js loads first, in <head>). This file only
   keeps the form and A11y in step. */

const root = document.documentElement;
const form = document.querySelector("[data-settings-form]");
const statusLine = document.querySelector("[data-settings-status]");
const contrastNote = document.querySelector("[data-contrast]");
const customSwatch = document.querySelector("[data-custom-swatch]");
const sampleButtons = document.querySelectorAll("[data-speak-sample]");
const voiceSelect = form.elements.voice;
const notesCount = document.querySelector("[data-notes-count]");
const notesClear = document.querySelector("[data-notes-clear]");
const HEX = /^#[0-9a-f]{6}$/i;
const MIN_CONTRAST = 4.5;

const formats = {
  textSize: (value) => [`${value}%`, `${value} percent`],
  rate: (value) => [`${Number(value).toFixed(1)}×`, `${Number(value).toFixed(1)} times normal speed`],
  pitch: (value) => [Number(value).toFixed(1), Number(value).toFixed(1)],
  volume: (value) => [`${Math.round(value * 100)}%`, `${Math.round(value * 100)} percent`],
};

function controls() {
  return [...form.elements].filter((el) => el.name && el.name in A11y.defaults);
}

// The preference value a control currently stands for.
function valueOf(input) {
  if (input.type === "checkbox") {
    if (input.value === "on") return input.checked;
    return input.checked ? input.value : input.dataset.unchecked;
  }
  if (input.type === "range" && input.dataset.values) return input.dataset.values.split(" ")[input.value];
  return input.value;
}

// ---- Form <- preferences ---------------------------------------------------
function sync() {
  const prefs = A11y.get();
  for (const input of controls()) {
    const value = prefs[input.name];
    if (input.type === "radio") input.checked = input.value === String(value);
    else if (input.type === "checkbox") input.checked = input.value === "on" ? value : value === input.value;
    else if (input.type === "range" && input.dataset.values) {
      const values = input.dataset.values.split(" ");
      const index = values.indexOf(value);
      input.value = index === -1 ? values.indexOf(String(A11y.defaults[input.name])) : index;
    } else if (input.type === "color") input.value = HEX.test(value) ? value : currentColor(input.name);
    else input.value = value;
  }
  if (voiceSelect.value !== prefs.voice) voiceSelect.value = "";

  const osReducesMotion = matchMedia("(prefers-reduced-motion: reduce)").matches;
  form.elements.motion.checked ||= osReducesMotion;
  form.elements.motion.disabled = osReducesMotion;
  if (osReducesMotion) {
    document.querySelector("[data-motion-hint]").textContent = "Your device already asks for less motion, so animations are off on every page.";
  }

  if (root.dataset.customScheme) customSwatch.dataset.customScheme = root.dataset.customScheme;
  else delete customSwatch.dataset.customScheme;

  updateOutputs();
  updateContrast();
  updateNoteCount();
}

function updateNoteCount() {
  const pages = A11y.countNotedPages();
  notesCount.textContent = pages
    ? `You have notes on ${pages} ${pages === 1 ? "page" : "pages"}.`
    : "You don't have any notes yet.";
  notesClear.disabled = pages === 0;
}

// Custom pickers start from the colors of the theme in use.
function currentColor(name) {
  const token = { customBg: "--color-bg", customText: "--color-text", customAccent: "--color-accent" }[name];
  const value = getComputedStyle(root).getPropertyValue(token).trim();
  return HEX.test(value) ? value : "#000000";
}

function updateOutputs() {
  for (const output of form.querySelectorAll("[data-output]")) {
    const input = form.elements[output.dataset.output];
    const [shown, spoken] = formats[input.name](valueOf(input));
    output.textContent = shown;
    input.setAttribute("aria-valuetext", spoken);
  }
}

function updateContrast() {
  const { customBg, customText, customAccent } = form.elements;
  const text = A11y.contrast(customText.value, customBg.value);
  const links = A11y.contrast(customAccent.value, customBg.value);
  const low = [text < MIN_CONTRAST && "text", links < MIN_CONTRAST && "link"].filter(Boolean);
  const many = low.length > 1;
  const ratios = `Contrast: text ${text.toFixed(1)} to 1, links and buttons ${links.toFixed(1)} to 1.`;
  contrastNote.className = low.length ? "field__error" : "field__hint";
  contrastNote.textContent = low.length
    ? `${ratios} The ${low.join(" and ")} ${many ? "colors are" : "color is"} too close to the background for many readers. Make ${many ? "them" : "it"} darker or lighter until ${many ? "each reaches" : "it reaches"} ${MIN_CONTRAST} to 1.`
    : `${ratios} Both pass the ${MIN_CONTRAST} to 1 minimum for readable text.`;
}

// ---- Form -> preferences ---------------------------------------------------
form.addEventListener("input", (event) => {
  const input = event.target;
  if (!(input.name in A11y.defaults)) return;
  const changes = { [input.name]: valueOf(input) };

  // Any custom color switches to the custom theme, keeping all three in step.
  if (input.type === "color") {
    const { customBg, customText, customAccent } = form.elements;
    Object.assign(changes, { theme: "custom", customBg: customBg.value, customText: customText.value, customAccent: customAccent.value });
  }
  A11y.set(changes);
});

form.addEventListener("change", (event) => {
  if (event.target.name in A11y.defaults) announce(`${settingName(event.target)} saved.`);
});

function settingName(input) {
  if (input.type === "color") return "Custom colors";
  const group = input.closest(".settings__group");
  const legend = group?.querySelector("legend:not(.visually-hidden)");
  if (input.type === "radio" && legend) return legend.textContent.trim();
  return input.labels?.[0]?.textContent.trim() || "Setting";
}

function announce(message) {
  statusLine.textContent = message;
}

document.querySelector("[data-settings-reset]").addEventListener("click", () => {
  A11y.reset();
  announce("All settings are back to their defaults.");
});

document.addEventListener("a11y:change", sync);

notesClear.addEventListener("click", () => {
  const pages = A11y.countNotedPages();
  if (!confirm(`Delete your notes on all ${pages} ${pages === 1 ? "page" : "pages"}? This can't be undone.`)) return;
  A11y.clearNotes();
  updateNoteCount();
  announce("All your notes are deleted.");
});

// ---- Read aloud -------------------------------------------------------------
function fillVoices() {
  const voices = A11y.speech.voices();
  if (!voices.length) return;
  const isEnglish = (voice) => voice.lang.toLowerCase().startsWith("en");
  const byName = (a, b) => a.lang.localeCompare(b.lang) || a.name.localeCompare(b.name);
  const groups = [
    ["English voices", voices.filter(isEnglish).sort(byName)],
    ["Other languages", voices.filter((voice) => !isEnglish(voice)).sort(byName)],
  ];

  const options = [voiceSelect.options[0]];
  for (const [label, list] of groups) {
    if (!list.length) continue;
    const group = document.createElement("optgroup");
    group.label = label;
    group.append(...list.map((voice) => new Option(`${voice.name} (${voice.lang})`, voice.voiceURI)));
    options.push(group);
  }
  voiceSelect.replaceChildren(...options);
  voiceSelect.value = A11y.get().voice;
  if (voiceSelect.value !== A11y.get().voice) voiceSelect.value = "";
}

function updateSampleButtons(state) {
  for (const button of sampleButtons) {
    button.textContent = state === "idle" ? button.dataset.label : "Stop reading";
  }
}

if (A11y.speech.supported) {
  fillVoices();
  speechSynthesis.addEventListener("voiceschanged", fillVoices);
  const sample = document.querySelector("[data-settings-sample]");
  for (const button of sampleButtons) {
    button.disabled = false;
    button.addEventListener("click", () => {
      if (A11y.speech.state === "idle") A11y.speech.readPage([sample]);
      else A11y.speech.stop();
    });
  }
  document.addEventListener("a11y:speech", (event) => updateSampleButtons(event.detail.state));
} else {
  document.querySelector("[data-speech-unsupported]").hidden = false;
  document.querySelector("[data-speech-controls]").disabled = true;
}

// ---- Start --------------------------------------------------------------------
sync();
document.querySelector("[data-settings-controls]").disabled = false;
