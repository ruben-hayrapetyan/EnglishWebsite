/* Rhythm explorer for study-neuronal-activity.html. Pick a frequency and a
   sampling rate; see the band, the period, how many cycles fit in a day, and
   what happens when the sampling rate drops below twice the frequency
   (aliasing). Without JavaScript the panel stays hidden; the band table
   beside it carries the same facts. */

const BANDS = [
  { name: "Delta", symbol: "δ", min: 1, max: 4 },
  { name: "Theta", symbol: "θ", min: 4, max: 8 },
  { name: "Alpha", symbol: "α", min: 8, max: 12 },
  { name: "Beta", symbol: "β", min: 15, max: 30 },
  { name: "Gamma", symbol: "γ", min: 30, max: 100 },
];

const WINDOW_SECONDS = 0.25; // the plot shows a quarter of a second
const VIEW = { width: 600, height: 220, pad: 16 };
const SVG_NS = "http://www.w3.org/2000/svg";

// Band edges are shared (8 Hz is the top of theta and the bottom of alpha).
// The chapter treats an 8 Hz peak as theta, so a frequency on an edge
// belongs to the slower band.
function bandFor(hz) {
  const band = BANDS.find((b) => hz >= b.min && hz <= b.max);
  if (band) return `${band.name} (${band.symbol})`;
  if (hz >= 12 && hz < 15) return "Between alpha and beta";
  return hz > 100 ? "Above gamma" : "Below delta";
}

function svg(tag, attrs) {
  const node = document.createElementNS(SVG_NS, tag);
  Object.entries(attrs).forEach(([k, v]) => node.setAttribute(k, v));
  return node;
}

// x(t) = sin(2πft), drawn across the window as a polyline path.
function wavePath(hz) {
  const { width, height, pad } = VIEW;
  const steps = 900;
  const mid = height / 2;
  const amp = mid - pad;
  let d = "";
  for (let i = 0; i <= steps; i += 1) {
    const t = (i / steps) * WINDOW_SECONDS;
    const x = (i / steps) * width;
    const y = mid - amp * Math.sin(2 * Math.PI * hz * t);
    d += `${i ? "L" : "M"}${x.toFixed(1)} ${y.toFixed(1)}`;
  }
  return d;
}

function initExplorer(root) {
  const panel = root.querySelector("[data-explorer-panel]");
  if (!panel) return;

  const freq = panel.querySelector("[data-explorer-frequency]");
  const rate = panel.querySelector("[data-explorer-rate]");
  const out = (name) => panel.querySelector(`[data-explorer-out="${name}"]`);
  const status = panel.querySelector("[data-explorer-status]");

  const plot = panel.querySelector(".explorer__svg");
  plot.setAttribute("viewBox", `0 0 ${VIEW.width} ${VIEW.height}`);
  const axis = svg("line", { class: "explorer__axis", x1: 0, x2: VIEW.width, y1: VIEW.height / 2, y2: VIEW.height / 2 });
  const wave = svg("path", { class: "explorer__wave" });
  const alias = svg("path", { class: "explorer__alias" });
  const samples = svg("g", {});
  plot.append(axis, wave, alias, samples);

  function update() {
    const hz = Number(freq.value);
    const fs = Number(rate.value);
    const nyquist = fs / 2;
    // The frequency the samples actually trace out (signed, so the phase matches).
    const folded = hz - fs * Math.round(hz / fs);
    const aliased = hz > nyquist;

    out("frequency").textContent = `${hz} Hz`;
    out("rate").textContent = `${fs} Hz`;
    out("band").textContent = bandFor(hz);
    out("period").textContent = `${(1000 / hz).toLocaleString(undefined, { maximumFractionDigits: 1 })} ms`;
    out("per-day").textContent = (hz * 86400).toLocaleString();
    out("nyquist").textContent = `${nyquist} Hz`;

    wave.setAttribute("d", wavePath(hz));
    alias.setAttribute("d", aliased ? wavePath(folded) : "");

    const { width, height, pad } = VIEW;
    const count = Math.floor(WINDOW_SECONDS * fs);
    const radius = count > 120 ? 1.6 : 3;
    samples.replaceChildren();
    for (let n = 0; n <= count; n += 1) {
      const t = n / fs;
      samples.append(svg("circle", {
        class: "explorer__sample",
        r: radius,
        cx: ((t / WINDOW_SECONDS) * width).toFixed(1),
        cy: (height / 2 - (height / 2 - pad) * Math.sin(2 * Math.PI * hz * t)).toFixed(1),
      }));
    }

    status.toggleAttribute("data-alias", aliased);
    status.textContent = aliased
      ? `Aliasing: sampled at ${fs} Hz, this ${hz} Hz rhythm is indistinguishable from a ${Math.abs(folded).toLocaleString(undefined, { maximumFractionDigits: 1 })} Hz one. Raise the sampling rate above ${hz * 2} Hz.`
      : `Sampled fast enough: ${fs} Hz is more than twice ${hz} Hz, so the rhythm can be recovered.`;
    plot.setAttribute("aria-label", `${hz} hertz sine wave sampled at ${fs} hertz. ${status.textContent}`);
  }

  panel.querySelectorAll("[data-explorer-preset]").forEach((button) => {
    button.addEventListener("click", () => {
      const [hz, fs] = button.dataset.explorerPreset.split(",");
      freq.value = hz;
      rate.value = fs;
      update();
    });
  });

  freq.addEventListener("input", update);
  rate.addEventListener("input", update);
  panel.hidden = false;
  update();
}

document.querySelectorAll("[data-explorer]").forEach(initExplorer);
