# EnglishWebsite

A static website built with plain HTML, CSS and a little JavaScript. There's no framework, no build step and no dependencies. It is set up so that several people or agents can work on separate pages in separate branches and still produce one consistent site.

> **Working on this repo as an agent?** Read [`AGENTS.md`](AGENTS.md) first. It holds the rules. This README explains the design.

## Run it

Open `index.html` in a browser, or serve the folder:

```sh
python3 -m http.server 8000
# then visit http://localhost:8000
```

Open `styleguide.html` to see every token and component rendered live. Add `?theme=dark` or `?theme=light` to any page URL to force a theme.

## Project structure

```
EnglishWebsite/
├── index.html              Home page
├── about.html              Example reading page (prose layout)
├── styleguide.html         Live reference of every token and component
├── settings.html           Reader settings: text size, fonts, themes, read-aloud
├── _template.html          Copy this to start a new page (not a real page)
├── assets/
│   ├── css/
│   │   ├── main.css        The only stylesheet pages link; imports everything below
│   │   ├── tokens.css      Design tokens: the single source of truth
│   │   ├── base.css        Reset and bare-element styles
│   │   ├── layout.css      Layout primitives (.container, .stack, .grid, .section...)
│   │   ├── components/     One file per component
│   │   └── pages/          Optional page-only styles, one file per page
│   ├── js/
│   │   ├── a11y.js         Applies reader settings on every page; read-aloud and ruler
│   │   ├── notes.js        Highlights and notes (loaded by a11y.js)
│   │   ├── site.js         Renders the shared header and footer; holds the nav list
│   │   ├── settings.js     Binds the settings form to a11y.js
│   │   └── styleguide.js   Prints live token values on the style guide
│   ├── fonts/              Self-hosted OpenDyslexic (SIL Open Font License)
│   └── img/                Images and the favicon
├── README.md               This file: the design system
├── AGENTS.md               Rules for anyone (human or agent) changing the site
└── ACCESSIBILITY.md        How to keep a page working with the reader settings
```

---

## Design system

### Direction

Quiet and legible, with one memorable detail. The page is cool, slightly green-tinted paper with green-black ink. A single viridian accent carries every interactive thing: links, buttons, focus rings. Highlighter yellow is reserved for the **signature mark**, a hand-drawn-looking stroke behind the few words that matter most. Everything else stays disciplined so that mark keeps its meaning.

The site is deliberately subject-neutral. It should fit whatever content it ends up holding without a redesign.

### Color

All colors are CSS custom properties in `assets/css/tokens.css`. Dark mode swaps the values automatically, so components never need theme-specific rules.

| Token | Light | Dark | Use |
|---|---|---|---|
| `--color-bg` | `#f4f6f5` | `#111614` | Page background |
| `--color-surface` | `#ffffff` | `#19201d` | Cards, inputs, raised panels |
| `--color-surface-sunken` | `#e9edeb` | `#0c100e` | Tinted sections, code blocks |
| `--color-text` | `#17201d` | `#e6ece9` | Body text and headings |
| `--color-text-muted` | `#4e5a55` | `#a3b0aa` | Captions, meta, ledes, secondary text |
| `--color-border` | `#d3dad6` | `#2c3632` | Hairlines, card and input borders |
| `--color-border-strong` | `#a9b5af` | `#4a5852` | Hovered or emphasized borders |
| `--color-accent` | `#1d6b57` | `#5cc4a4` | Links, primary buttons, focus ring |
| `--color-accent-strong` | `#14503f` | `#85d9bf` | Hover and pressed accent |
| `--color-accent-soft` | `#dcebe5` | `#1a3a31` | Backgrounds behind accent content |
| `--color-on-accent` | `#ffffff` | `#0b1411` | Text on an accent background |
| `--color-mark` | `#ffd84a` | yellow at 42% | The highlighter, and nothing else |
| `--color-mark-soft` | `#fff3c4` | yellow at 12% | Large highlighted areas (`.callout--mark`) |
| `--color-danger` | `#b3261e` | `#ff8a80` | Errors and destructive actions |
| `--color-danger-soft` | `#f9e3e1` | `#3a1c1a` | Error backgrounds |

Each text color meets WCAG AA contrast on every background it's used on.

**Reader themes.** Readers can also choose Sepia, High contrast light, High contrast dark or their own three colors on `settings.html`. Each theme redefines the full set of color tokens in `tokens.css` (under "Reader preferences"), so components never need theme rules. Custom themes mix the other tokens from the reader's background, text and accent colors with `color-mix()`.

### Typography

| Role | Typeface | Where |
|---|---|---|
| Display | **Young Serif** (one weight, 400) | `h1` to `h3`, the brand name, pull quotes |
| Body | **Atkinson Hyperlegible Next** (400, 600, 700, italic) | Everything people read: text, UI, buttons, forms, `h4` to `h6` |
| Utility | **Atkinson Hyperlegible Mono** (400, 600) | Small uppercase labels, tags, code |

All three load from Google Fonts in `main.css`. The display face has a lot of personality, so it's used only for headings. Never set body text or buttons in it.

**Reader fonts.** On `settings.html` readers can swap the role tokens (`--font-body`, `--font-display`) for OpenDyslexic (self-hosted in `assets/fonts/`), Lexend (Google Fonts), Georgia, their device's font or Atkinson Hyperlegible Mono. These download only when chosen. Raw families live in `--family-*` tokens; pages always use the `--font-*` role tokens. Readers can also change text size (`--text-scale`, 75–200%, which scales every `rem`), weight (`--weight-body`, `--weight-strong`), line spacing, letter and word spacing (`--tracking-body`, `--word-spacing`) and line length. See `ACCESSIBILITY.md`.

**Type scale** (fluid: each step grows smoothly between phone and desktop widths):

| Token | Approx. size | Use |
|---|---|---|
| `--step-5` | 40–70px | Home hero `h1` |
| `--step-4` | 33–51px | Page title `h1` |
| `--step-3` | 28–38px | `h2` |
| `--step-2` | 23–29px | `h3`, card titles |
| `--step-1` | 19–22px | `h4`, ledes |
| `--step-0` | 16–18px | Body text |
| `--step--1` | 13–14px | UI text: buttons, nav, labels, captions |
| `--step--2` | 12px | Mono labels and tags |

Running text is capped at `--measure` (66 characters per line). Ledes use `--measure-narrow` (48ch). Headings use `--leading-tight` (1.08), UI uses `--leading-snug` (1.3), body text uses `--leading-body` (1.62).

### Spacing

One t-shirt scale, in rem: `--space-3xs` (4px), `2xs` (8), `xs` (12), `s` (16), `m` (24), `l` (32), `xl` (48), `2xl` (64), `3xl` (96). Between page sections there's `--space-section`, which grows from 56px on phones to 112px on wide screens.

### Layout

- **Container:** content is centered with a maximum width of `--container-max` (72rem, about 1150px). Reading pages use `.container--narrow` (46rem).
- **Gutter:** side padding is `--gutter`, 16px on phones growing to 40px.
- **Alignment:** left-aligned throughout. Headlines hang on the left edge with open space to the right. Nothing is centered except buttons' contents.
- **Breakpoints:** two, and only two. `40rem` (640px) is where the menu collapses. `52rem` (832px) is where two-column `.split` layouts form. Everything else reflows on its own with `.grid` and `.cluster`.
- **Header:** sticky, solid page background, hairline bottom border. Brand on the left in the display face, nav on the right.
- **AI credit:** every page ends with one line of small, muted text naming any generative AI used to make it, directly above the footer. See `AGENTS.md` for what it must say.
- **Footer:** hairline top border, site name, footer links, year.

Two page layouts, both in `_template.html`:

```
LAYOUT A: reading page              LAYOUT B: sectioned page
┌──────────────────────────┐        ┌──────────────────────────────────┐
│ header                   │        │ header                           │
├──────────────────────────┤        ├──────────────────────────────────┤
│   meta                   │        │ Hero title with ▇key words▇      │
│   Title with ▇key▇       │        │ Lede                             │
│   Lede                   │        │ [Primary] [Secondary]            │
│                          │        │                                  │
│   prose (66ch max)       │        │ Section heading                  │
│   ## heading             │        │ [card] [card] [card]             │
│   paragraphs, lists,     │        │──────── tinted section ──────────│
│   quotes, tables         │        │ text column     │ callout        │
│                          │        │                                  │
│   Generative AI: ...     │        │ Generative AI: ...               │
├──────────────────────────┤        ├──────────────────────────────────┤
│ footer                   │        │ footer                           │
└──────────────────────────┘        └──────────────────────────────────┘
```

### Shape, depth and motion

- **Corners:** `--radius-s` (4px) for buttons, inputs and tags. `--radius-m` (10px) for cards, callouts and images. `--radius-full` for pills.
- **Borders:** 1px hairlines (`--border-width`) everywhere, plus a 3px accent rule (`--border-width-thick`) on the left edge of callouts and pull quotes.
- **Depth:** borders do most of the work. `--shadow-s` sits under cards at rest, and `--shadow-m` shows only on hover or for floating menus.
- **Motion:** short and purposeful. `--duration-fast` (120ms) for color changes, `--duration-base` (220ms) for movement, `--duration-slow` (700ms) for the one-time highlighter draw. All motion is turned off for people who set "reduce motion".

### Signature: the highlighter

The one element people should remember. It's a yellow marker stroke behind a short phrase, with a slight slant and uneven ends like a real highlighter. It shows up in three places:

1. **Key words in a page title.** Wrap them in `<mark class="highlight--draw">` and the stroke draws itself in once on load.
2. **The current page in the menu.** This is automatic.
3. **Link hover.** Links get a thin highlighter sweep under them.

Use it on one phrase per screen at most. If everything is highlighted, nothing is.

### Components

All of these are shown live in `styleguide.html`.

| Component | Classes | File |
|---|---|---|
| Page header | `.page-header`, `--hero`, `__title`, `__lede`, `__meta`, `__actions` | `components/page-header.css` |
| Button | `.button`, `--secondary`, `--quiet`, `--small` | `components/button.css` |
| Card | `.card`, `__title`, `__body`, `__meta`, `__footer` | `components/card.css` |
| Callout | `.callout`, `--accent`, `--mark`, `--danger`, `__title` | `components/callout.css` |
| Tag | `.tag`, `--accent` | `components/tag.css` |
| Form field | `.field`, `__label`, `__hint`, `__error`, `.input`, `.checkbox` | `components/form.css` |
| Prose | `.prose` (styles plain HTML inside it) | `components/prose.css` |
| Highlight | `mark`, `.highlight`, `.highlight--draw` | `components/highlight.css` |
| AI credit | `.ai-credit` (required on every page, above the footer) | `components/ai-credit.css` |
| Reader bar | `.reader-bar`, `__group`, `[data-read-aloud-current]` (added by `a11y.js`) | `components/reader-bar.css` |
| Notes | `.notes-highlight`, `--active`, `.notes-menu`, `.notes-panel` and its elements (added by `notes.js`) | `components/notes.css` |
| Reading ruler | `.reading-ruler` (added by `a11y.js`) | `components/reading-ruler.css` |
| Header and footer | Rendered by `site.js` | `components/site-header.css`, `site-footer.css` |

Layout primitives in `layout.css`: `.container`, `.container--narrow`, `.page-body`, `.section`, `.section--tinted`, `.section__header`, `.section__intro`, `.stack`, `.cluster`, `.grid`, `.split`, `.split--even`, `.visually-hidden`, `.skip-link`.

### Voice and copy

- Plain words, sentence case everywhere: titles, buttons, nav.
- Buttons say exactly what happens ("Send message", not "Submit").
- One idea per sentence. Ledes are one or two sentences.
- Errors say what went wrong and how to fix it, without apologizing.

---

## Contributing

All work happens on branches off `main`, one page or one component per branch. **Nothing is ever pushed to `main` directly.** Changes reach `main` only through pull requests, and only the repo owner merges them. Agents never do. The full rules (what you may change, naming, and the pre-merge checklist) are in [`AGENTS.md`](AGENTS.md). The short version:

1. Build only from tokens and existing components.
2. Start new pages from `_template.html`, and add them to the menu in `assets/js/site.js`.
3. End every page with an AI credit naming any generative AI used to make it.
4. New components go in their own file under `assets/css/components/` and get added to the style guide.
5. Changes to the design system itself (tokens, base, layout) go in a separate `design/*` branch and update this README in the same change.
