# Study materials

Every textbook chapter gets one study kit page, `study-<chapter-id>.html`, listed on `study.html`. Every kit has the same five parts, so a reader who has used one knows how to use them all.

The finished example is [`study-neuronal-activity.html`](study-neuronal-activity.html). Copy its patterns.

> This guide adds to [`AGENTS.md`](AGENTS.md); it doesn't replace it. All the rules there still apply: tokens only, your own branch, a pull request, and an AI credit on the page.

## Make your chapter's kit

1. Branch from `main`: `git switch -c page/study-<chapter-id>`.
2. Copy `_study-template.html` to `study-<chapter-id>.html`. Use a short, lowercase, hyphenated id, such as `chronotypes` or `sleep-caffeine-jet-lag`.
3. Replace every `CHAPTER-ID` in the file with that id. It keys each reader's saved progress, so it must be unique.
4. Fill in the five parts below.
5. On `study.html`, turn your chapter's card into a link: wrap the title in `<a href="study-<chapter-id>.html">`, change the tag to `<span class="tag tag--accent">Ready</span>`, and add the `card__footer` line. Copy the neuronal activity card.
6. Fill in the AI credit, then run the checklist in `AGENTS.md` and open a pull request.

You write plain HTML. `assets/js/study.js` finds the slides, flashcards and quiz by their classes and makes them interactive. Don't edit it, and don't write JavaScript for these parts. If you need something it doesn't do, ask in a pull request.

## The five parts

| Part | What to write | How much |
|---|---|---|
| **Objectives** | Your chapter's learning objectives, word for word, each with `data-objective="LO1"` and so on | All of them |
| **Slides** | One idea per slide, in chapter order, with your figures | 10–20 slides |
| **Key terms** | Your chapter's glossary | Every term |
| **Quiz** | Questions with a `data-why` on every option and an explanation | 10–20, at least two per objective |
| **Explain it back** | One open prompt per objective, with a model answer | One per objective |

### Writing good questions

- **Test understanding, not wording.** Ask readers to apply an idea to a new case ("a rat is sniffing and you record 8 Hz...") rather than to recognize a sentence from the chapter.
- **Make wrong options plausible.** Each should be a real misconception, and its `data-why` should name it ("That's repolarization, which comes after the peak").
- **One clearly right answer.** Avoid "all of the above" and "none of the above".
- **Tag every question with an objective.** The results screen scores readers by objective, so untagged questions fall into "Other".
- **Number questions** take `data-answer`, `data-tolerance` (how far off still counts) and `data-unit`, and no options list.

### Slides

- Put the section name in `deck__kicker` so readers can tell where they are in the chapter.
- Each slide needs a unique `id` on its `h3`, matched by `aria-labelledby` on the `section`.
- Figures go in `assets/img/<chapter-id>-<name>.png`. Keep them under about 200 KB and 1400 px wide. Every figure needs `alt` text that says what the figure shows, and a caption with its source. If any generative AI helped make a figure, say so in the caption and in the page's AI credit.
- Equations: write them in MathML inside `<div class="equation">`. Copy the examples on the neuronal activity page, and add your page's CSS file for the `.equation` style.

## Optional extras

A kit can add one interactive demo of its own, like the rhythm explorer on the neuronal activity page. Put its script in `assets/js/study-<chapter-id>.js` and its styles in `assets/css/pages/study-<chapter-id>.css`, and load both only on your page. The page must still make sense with JavaScript off. The rhythm explorer, for example, keeps a band table visible underneath.

## What readers get

- **Slides:** one at a time, with arrow keys, swipe, a progress bar and full screen. The deck remembers the last slide viewed.
- **Flashcards:** flip cards with spaced practice. "Still learning" sends a term back a few cards; "Got it" moves it up a level. A term counts as known after three "Got it"s, across rounds. Progress is saved in the reader's browser only.
- **Quiz:** one question at a time. Readers rate their confidence, see why their pick was right or wrong, and get flagged when they were certain but wrong. The results show a score by learning objective and offer to retry only the missed questions.

With JavaScript off, everything is still there: slides as a stack, terms as a glossary, and quiz answers in "Show the answer" boxes.
