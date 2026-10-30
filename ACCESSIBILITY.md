# Accessibility: making your page work with reader settings

Readers can change how the whole site looks and sounds on [`settings.html`](settings.html): text size (75–200%), font (including OpenDyslexic), text weight, line, letter and word spacing, line length, color theme (light, dark, sepia, two high-contrast themes or their own colors), reduced motion, stronger focus outlines, a reading ruler, read-aloud, and highlights with notes.

**Most of this works on your page for free, as long as you follow the rules below.** The settings change design tokens, not your page. So a page that uses tokens and normal HTML just works, and a page that hardcodes things breaks for the readers who need the settings most.

> This guide adds to [`AGENTS.md`](AGENTS.md); it doesn't replace it. Chapter, unit and study-kit pages all follow it.

## How it works (30 seconds)

1. `assets/js/a11y.js` loads in `<head>` on every page. It reads the saved settings and puts them on `<html>` as attributes, such as `data-theme="sepia"` and `data-text-size="150"`.
2. The "Reader preferences" blocks in `tokens.css` turn those attributes into token values (`--color-bg`, `--font-body`, `--leading-body`, `--text-scale` and so on).
3. Every component reads tokens, so everything follows the reader's settings.
4. If the reader turns them on, `a11y.js` also adds the reader bar (read-aloud and notes buttons) and the reading ruler to every page, and loads `assets/js/notes.js` for highlights and notes. Pages never load `notes.js` themselves.

## Rules for every page

### 1. Keep the head exactly as the template has it

Start from `_template.html` (or `_study-template.html` for study kits). The line below must come **before** the stylesheet and must **not** have `defer`. Otherwise the page flashes in the wrong theme and size before the settings apply.

```html
<script src="assets/js/a11y.js"></script>
<link rel="stylesheet" href="assets/css/main.css">
```

Templates or pages made before this change (for example on the `page/study-materials` branch) need this line added.

### 2. Colors: tokens only, and nothing that depends on the background

- Use only `var(--color-*)`. A raw hex value stays the same in every theme, so it can disappear in dark or high-contrast mode.
- Never set `data-theme` yourself, and never write `prefers-color-scheme` rules.
- **Images:** a diagram with a transparent background and dark lines vanishes in dark themes. Give figures their own solid background (a white PNG background is fine), or use inline SVG with `fill="currentColor"` / `stroke="currentColor"`.
- Never show information through color alone. Pair it with text or an icon, such as "Correct" next to a green mark.

### 3. Text size and spacing: let text grow

Readers can make text twice as big, with extra-wide letter, word and line spacing, in a font that's wider than the default. Your page has to survive that.

- Size things in tokens or `rem`/`em`, never `px`, for anything around text.
- **Never give a box with text in it a fixed `height`** (or `max-height` with `overflow: hidden`). Use `min-height` if you must, so the box can grow.
- Use `--measure` for line length, not a fixed width.
- Don't truncate text with `text-overflow: ellipsis` or `-webkit-line-clamp`.
- Grid columns that hold text should be `minmax(0, 1fr)`, not plain `1fr`, so long words wrap instead of pushing the page wider. `.grid` and `.split` already do this.

### 4. Fonts: use the role tokens

Use `var(--font-body)`, `var(--font-display)` and `var(--font-mono)`. They swap when a reader picks another font. The `--family-*` tokens are fixed families for the settings page samples only, so don't use them on content pages. Use `var(--weight-*)` for weights, and use `<strong>` for emphasis so the "Bold" setting keeps it distinct.

### 5. Motion: check before you animate

CSS transitions and animations are switched off automatically for readers who ask for less motion. **JavaScript** animation is not, so check first:

```js
const smooth = !window.A11y?.reducedMotion();
element.scrollIntoView({ behavior: smooth ? "smooth" : "auto" });
```

Don't autoplay anything that moves for more than five seconds without a pause button.

### 6. Read aloud: write real text in reading order

With no words selected, read-aloud starts at the top and reads the whole page. With words selected, it reads only those (from the reader bar, or the "Read aloud" button that pops up beside the selection). It reads the page's text block by block (paragraphs, headings, list items, table cells, buttons and so on), highlighting each block as it goes. It skips anything hidden. For it to work well:

- **Mark the main reading text.** On chapter and unit pages, wrap the text people should hear in `data-read-aloud`. Without it, the reader reads all of `<main>`.
  ```html
  <article class="prose" data-read-aloud> …chapter text… </article>
  ```
  You can use `data-read-aloud` on more than one element. They're read in page order.
- **Skip what shouldn't be read** with `data-read-aloud-skip`: quiz answer keys, model answers, repeated navigation, decorative text.
  ```html
  <div class="reveal" data-read-aloud-skip> …model answer… </div>
  ```
- Hidden content (`hidden`, `display: none`, `aria-hidden="true"`) is skipped automatically, so collapsed answers stay secret.
- Put text in HTML, not in images. Images are read as "Image:" plus their `alt` text, so write `alt` that makes sense out loud.
- Mark text in other languages with `lang` (for example `<i lang="fr">je ne sais quoi</i>`). The reader switches to a matching voice if the device has one.
- Don't use CSS `::before` or `::after` content for words people need. It isn't read.

### 7. Highlights and notes: keep your text stable

Readers can select words in the reading area (the same `data-read-aloud` containers, or `<main>`) and add a note. The words get a highlight and the note opens in a side panel. Notes are saved per page in the reader's browser and found again by their words, so:

- **Don't rebuild text with JavaScript after the page loads** (for example by replacing `innerHTML` of a passage). That removes the reader's highlights. Interactive parts may show and hide content, but shouldn't rewrite it.
- **Keep the page's file name.** Notes are stored by page address, so renaming `chapter-3.html` loses every reader's notes on it.
- Fixing a typo is fine. If the highlighted words themselves change, the note stays in the panel with a message that the words have changed.
- Highlights use the accent color, never `<mark>` or `--color-mark`, so they never clash with the page's own highlighter.

### 8. Interactive parts (flashcards, quizzes, slides)

- Use real `<button>`s and `<a>`s with visible focus. The "stronger focus outlines" setting only thickens rings that already exist.
- Announce results in an `aria-live="polite"` region, for example "Correct" or "Card 3 of 12".
- If a script needs to react to settings, listen for the change event:
  ```js
  document.addEventListener("a11y:change", (event) => {
    const prefs = event.detail; // same shape as A11y.get()
  });
  ```

## What you never do

- Edit `a11y.js`, the preference blocks in `tokens.css`, or `settings.html` outside a `design/*` branch.
- Add your own font-size, theme or dark-mode toggle to a page. Point readers to Settings instead.
- Use `!important`, which can stop a reader's setting from applying.

## Test before you open a pull request

Open `settings.html`, set the combination, then open your page. Settings carry across pages and tabs.

- [ ] **Text size 200%** with **OpenDyslexic** and **extra-wide** line, letter and word spacing: nothing overlaps, gets cut off or scrolls sideways at 390px wide.
- [ ] **High contrast dark** and **Sepia**: every word, line, icon and figure is still visible.
- [ ] **Turn off animations**: nothing on the page still moves.
- [ ] **Read aloud** on: "Read page aloud" reads your content in the right order, skips answers, and doesn't read anything twice.
- [ ] **Reading ruler** on: it doesn't block clicking anything.
- [ ] **Notes:** select some words, add a note, reload the page. The highlight and note are still there.
- [ ] Everything works with the keyboard alone, and you can always see where focus is.

`Reset all settings` at the bottom of the settings page puts everything back.

## Reference: what the reader can set

| Setting | Attribute on `<html>` | Tokens it changes |
|---|---|---|
| Color theme | `data-theme`: `light`, `dark`, `sepia`, `contrast-light`, `contrast-dark`, `custom` (absent: follow the device) | every `--color-*`, `--shadow-*` |
| Text size | `data-text-size`: `75`, `80`, `90`, `112`, `125`, `150`, `175`, `200` | `--text-scale` (scales every `rem`) |
| Font | `data-font`: `hyperlegible`, `opendyslexic`, `lexend`, `serif`, `system`, `mono` | `--font-body`, `--font-display`, `--weight-display` |
| Text weight | `data-weight`: `semibold`, `bold` | `--weight-body`, `--weight-strong` |
| Line spacing | `data-line-spacing`: `wide`, `wider` | `--leading-*` |
| Letter and word spacing | `data-text-spacing`: `wide`, `wider` | `--tracking-body`, `--tracking-tight`, `--word-spacing` |
| Line length | `data-line-length`: `narrow` | `--measure`, `--measure-narrow` |
| Turn off animations | `data-motion`: `reduce` | `--duration-*`, `--lift`, `--press` |
| Stronger links and focus | `data-emphasis`: `strong` | `--underline-width`, `--focus-ring`, `--focus-offset` |
| Reading ruler, read aloud, notes | `data-notes-open` while the notes panel is open | `.reading-ruler`, `.reader-bar` and `.notes-*` components |

Settings are stored in `localStorage` under `english-website:reader-preferences`, and notes under `english-website:notes:<page path>`, on the reader's own device only. Read-aloud uses the browser's built-in Web Speech API, which is free and needs no account or API key. Voices come from the reader's device and browser. Online voices, such as Edge's "Natural" ones, send the text to the browser maker to be spoken, but nothing is sent to us.
