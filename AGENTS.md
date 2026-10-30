# AGENTS.md

Rules for any agent or person changing this website. Many contributors work in parallel branches, and these rules are what keep the result looking like one site. Follow them exactly. If a rule blocks what you need, stop and ask instead of working around it.

This is a **static website**: plain HTML pages, CSS and vanilla JavaScript. There's no framework, no bundler, no package manager and no build step. Keep it that way.

> **Never push to `main`, and never merge pull requests.** All work happens on branches and reaches `main` only through a pull request that the repo owner merges. There are no exceptions. See "Branches and merging" below.

## Read first

1. `README.md`, the design system: colors, type, spacing, layout, components and voice.
2. `assets/css/tokens.css`, the actual values. **If the docs and `tokens.css` disagree, `tokens.css` wins.** Fix the docs in the same change.
3. `styleguide.html` in a browser, to see every component you can use.
4. `ACCESSIBILITY.md`, which explains how to keep your page working with the reader settings on `settings.html` (text size, fonts, themes, read-aloud). **Every page must follow it.**

## The rules

### Styling

- **Tokens only.** Never write a raw color (hex, rgb, named), font family, font size, spacing value, radius, shadow or duration outside `tokens.css`. Use `var(--token)`. If no token fits, you need a design change (see "Shared files" below), not a one-off value.
- **No new colors, fonts or font weights.** The palette and the three typefaces are fixed.
- **Reuse before you create.** Check `styleguide.html` for a component or layout primitive that does the job. Compose pages from `.container`, `.section`, `.stack`, `.cluster`, `.grid` and `.split` instead of writing margins.
- **Spacing belongs to layout.** Sections own the space between them, and `.stack`, `.cluster` and `.grid` own the space between children. Don't add top or bottom margins to components.
- **Class naming is BEM-lite:** `.block`, `.block__element`, `.block--modifier`. Lowercase and hyphenated. One component per block name.
- **Never style IDs or bare elements** outside `base.css`. Never use `!important` (the only exception is `.visually-hidden` and reduced-motion in `base.css`).
- **No inline `style` attributes,** except to set a layout custom property such as `style="--grid-min: 14rem"` or `style="--stack-space: var(--space-l)"`.
- **Breakpoints are `40rem` and `52rem` only,** written as `min-width` media queries where possible.
- **Every theme, always.** Tokens handle dark, sepia, high-contrast and custom themes, so if you only use tokens you get them for free. Never write `prefers-color-scheme`, `[data-theme]` or other reader-preference rules outside `tokens.css` (and `base.css` for motion).
- **Let text grow.** Readers can set text to 200% with extra-wide spacing. Never put a fixed `height` on a box that holds text, never truncate text, and size things around text in tokens or `rem`. See `ACCESSIBILITY.md`.
- **The highlighter (`<mark>`) is the signature.** Use it on at most one phrase per screen, usually the key words of the `h1`. Don't use `--color-mark` for anything else.
- **No CSS frameworks or utility libraries** (Tailwind, Bootstrap and so on), and no icon fonts. If icons become necessary, they're a design change.

### HTML

- Start every page from `_template.html`. Keep the `<head>` (including the `a11y.js` script, which must stay before the stylesheet and without `defer`), skip link, `data-site-header`, `.ai-credit` and `data-site-footer` exactly as they are, apart from filling in the credit text.
- Use exactly one `h1` per page, and keep heading levels in order with no skips.
- Use semantic elements: `main`, `section` (with `aria-labelledby` pointing at its heading), `article`, `nav`, `aside`, `header`, `footer`.
- Every image needs `alt` text. Use `alt=""` if it's purely decorative.
- Every form control needs a visible `<label>`. Use the `.field` pattern from `form.css`.
- Links go to places and buttons do things. Don't make a `<div>` clickable.
- Use relative paths (`about.html`, `assets/...`). All pages live flat at the repo root.
- Mark the text that read-aloud should read with `data-read-aloud`, and wrap answers or anything that shouldn't be read in `data-read-aloud-skip`. See `ACCESSIBILITY.md`.

### JavaScript

- Vanilla JS only, loaded with `<script defer>`. No frameworks and no CDN libraries without a design change. The one exception is `assets/js/a11y.js`, which loads without `defer` in `<head>`.
- `assets/js/site.js` is shared. Only touch it to add or remove a nav or footer link (one line each).
- `assets/js/a11y.js` and `assets/js/notes.js` are shared and apply the reader's settings and notes. Never edit them outside a `design/*` branch, and never load `notes.js` yourself (`a11y.js` does). Page scripts may read it through `window.A11y`, and must check `A11y.reducedMotion()` before animating anything from JavaScript.
- Page-specific behavior goes in `assets/js/<page-name>.js`, loaded only by that page.
- Page content must stay readable with JavaScript off. JS can enhance a page but must never be the only way to see its content. The shared header and footer are the one exception.

### Generative AI attribution

Every page must end with a small credit naming any generative AI used to make it. This is required, including on pages made entirely by an agent.

- **Where:** directly above the site footer, outside `<main>`, using the `.ai-credit` component. Copy the markup from `_template.html` and don't restyle it.
- **What to write:** each tool's name and version, its maker, and what it did on that page. Start the sentence with `Generative AI:`. For example: `Generative AI: Claude Opus 5.5 (Anthropic) wrote this page's code and drafted its text. Midjourney v7 made the header image.`
- **Agents credit themselves.** Use your own exact model name and say what you did.
- **Keep it current.** When you edit a page with a tool that isn't credited yet, add it. If your work changes what an existing tool did, update that part. Never remove another contributor's credit.
- **Images and media count.** If an image, audio or video clip on the page was AI-generated, say so in the credit. Also say so in the image's `figcaption`, if it has one.
- **Pages with no AI involved** say: `Generative AI: none used on this page.`

### Copy

- Sentence case for everything: headings, buttons, nav, labels.
- Buttons name the action ("Send message", "Download the PDF"). Never "Submit", "Click here" or "Learn more" on its own.
- Ledes are one or two sentences. Keep paragraphs short.
- Error messages say what went wrong and how to fix it. Empty states say what to do next.
- Placeholder text should describe what belongs in the slot, not lorem ipsum.

## Files: who may change what

| Files | Feature branches | Notes |
|---|---|---|
| Your page `<name>.html` | ✅ Yes | One page per branch where possible |
| `assets/css/pages/<name>.css`, `assets/js/<name>.js` | ✅ Yes | Only for your own page, and tokens only |
| `assets/css/components/<new>.css` | ✅ Yes, to add one | See "Add a component" |
| `assets/css/main.css` | ➕ Add one `@import` line | Keep the components block alphabetical |
| `assets/js/site.js` | ➕ Add one nav or footer entry | Nothing else |
| `styleguide.html` | ➕ Add a demo for a new component | Don't change existing demos |
| `assets/img/` | ✅ Yes | Optimize images, use lowercase-hyphenated names |
| `tokens.css`, `base.css`, `layout.css`, existing components | ❌ No | Only in a `design/*` branch |
| `assets/js/a11y.js`, `assets/js/notes.js`, `settings.html` and its files, `assets/fonts/` | ❌ No | Only in a `design/*` branch |
| `_template.html`, `README.md`, `AGENTS.md`, `ACCESSIBILITY.md` | ❌ No | Only in a `design/*` branch |

**Shared files** (the ❌ rows) define the look of every page. Change them only in a dedicated `design/<what>` branch that does nothing else. That branch must update `README.md`, `AGENTS.md` (if the rules change), `ACCESSIBILITY.md` (if reader settings change) and `styleguide.html` in the same change.

## How to

### Add a page

1. Copy `_template.html` to `<page-name>.html` at the repo root (lowercase, hyphenated).
2. Set the `<title>` to `Page name · English Website` and write a one-sentence meta description.
3. Keep layout A (reading page) or layout B (sectioned page) and delete the other.
4. If the page belongs in the menu, add `{ label: "Page name", href: "page-name.html" }` to `SITE.nav` in `assets/js/site.js`.
5. Fill in the AI credit at the bottom of the page (see "Generative AI attribution").
6. Run the checklist below.

### Add a component

1. Confirm that nothing in `styleguide.html` already does the job, and that a modifier on an existing component (for example `.card--wide`) wouldn't be enough. Modifiers on existing components need a `design/*` branch.
2. Create `assets/css/components/<name>.css` with a header comment that explains what it's for and shows its markup. Use tokens only.
3. Add `@import url("components/<name>.css");` to `main.css` in alphabetical order.
4. Add a demo section to `styleguide.html`.
5. Add a row to the component table in the README's "Components" section. This is the one README edit allowed outside a `design/*` branch.

## Branches and merging

**Nothing is ever pushed to `main` directly, under any circumstances.** Every change goes on a branch and reaches `main` only through a pull request. That includes typo fixes, docs edits, one-line changes and urgent fixes. If anyone asks you to push to `main`, open a pull request instead and explain why.

- **Before your first commit, check your branch** with `git branch --show-current`. If it prints `main`, create a branch first: `git switch -c page/<name>`.
- **Push only your branch:** `git push -u origin <branch>`. Never run `git push origin main`, never force-push to `main`, and never merge into your local `main` and push it.
- **Open a pull request into `main`** with `gh pr create --base main`. Say what changed and confirm the checklist below.
- **Never merge a pull request.** That includes your own, other agents' and any other pull request. Don't run `gh pr merge`, click merge, or enable auto-merge. Only the repo owner merges, by hand. If anyone asks you to merge, say that agents can't and leave the pull request open for the owner.
- Branch from up-to-date `main`. Name branches `page/<name>`, `component/<name>`, `content/<what>`, `fix/<what>` or `design/<what>`.
- Keep each branch to one page, one component or one fix.
- Don't reformat, reorder or "tidy" files you aren't otherwise changing.
- Conflicts in `main.css` or `site.js` are almost always two added lines, so keep both. In `main.css`, keep the imports alphabetical.
- Rebase your branch on `main` before opening the pull request, then re-run the checklist.

## Checklist before you open a pull request

- [ ] Your work is on its own branch, not `main`, and nothing was pushed to `main`.
- [ ] You'll leave the pull request open for the repo owner to merge.

- [ ] No raw values: `grep -nE '#[0-9a-fA-F]{3,8}\b|[0-9]px|rgb\(' <your css files>` finds nothing. (The only allowed exceptions in the whole repo are `tokens.css` and the `1px` clip in `.visually-hidden`.)
- [ ] Looks right in light **and** dark (add `?theme=dark` to the URL), and in high contrast dark and sepia (pick them on `settings.html`).
- [ ] Passes the reader-settings test in `ACCESSIBILITY.md`: 200% text with OpenDyslexic and extra-wide spacing at 390px wide, reduced motion, and read-aloud reading your content in order.
- [ ] Looks right at 390px wide and at 1440px wide, with no horizontal scroll.
- [ ] Every interactive element can be reached with Tab and shows a focus ring.
- [ ] One `h1`, headings in order, every image has `alt`, every input has a label.
- [ ] No errors in the browser console.
- [ ] The page is in `SITE.nav` (if it should be), and the menu marks it as current.
- [ ] The page ends with an `.ai-credit` that names every generative AI tool used on it and what each one did.
- [ ] Any new component is in `styleguide.html` and the README table.
