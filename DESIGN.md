# Design notes for the demo site

**Goal:** someone who has never heard of Strands Decider, conformal prediction or press-release
research should understand why this matters, and what it does, within the first screen. Judges
spend three to five minutes in total.

## Story order: lead with impact

1. **Hero: the problem, as a claim.** "Most health hype is written before a journalist ever
   sees it." Beside it, a replay of a real catch: BLOCK 0.80, then Claude's rewrite, then OK 0.17.
2. **Why it matters: the chain.** paper → press release (33% overclaim) → news (81% repeat it)
   → public (≈219,000 UK patients estimated to stop statins after one news storm, with the
   authors' caveat that causation is unproven). The gate is placed at the one step where a
   single correction changes everything downstream. The RCT callout shows the fix works and
   costs nothing.
3. How it works.
4. Try it.
5. Evidence, as a chart.
6. HypeWatch, the real-world run.
7. For builders.
8. FAQ.

## Principles and where they show up

| Principle | Source | Applied as |
|---|---|---|
| Make the value clear in the first seconds; most attention lands on the first screen | Nielsen, *How Long Do Users Stay on Web Pages?* (NN/g, 2011; users often leave within 10–20 s); NN/g eye-tracking on above-the-fold attention | Impact headline, the live catch and both calls to action are above the fold; three proof numbers below them |
| Lead with one big idea | Knaflic, *Storytelling with Data* (2015) | Each section opens with a one-sentence claim headline ("A gate that cries wolf gets switched off"), then evidence |
| Direct attention with preattentive attributes, used sparingly | Knaflic, ch. 4 | One accent colour in the chart (Decider) against grey (Claude); a red/amber gradient only on the hero's key phrase; large numerals for the four chain numbers |
| Emphasis chart, not categorical colour, when one series is the point | dataviz method (`choosing-a-form`) | Accent bar vs de-emphasis grey, values at the bar tips, tooltip on each bar, table view kept, 24 px bars with 4 px rounded ends |
| Validate colour, don't eyeball it | dataviz `validate_palette.js` | Accent `#2a78d6` (light) and `#3987e5` (dark) pass every check in both modes. The grey's contrast warning is covered by visible value labels and the table |
| Visibility of system status | Nielsen, *10 Usability Heuristics* #1 | Sentences colour one at a time; progress counter; queue position; where-the-time-went bar |
| Match the real world; recognition over recall | Nielsen #2, #6 | Plain words first, technical term inside an ⓘ; real examples one click away |
| Help in context | Nielsen #10 | An ⓘ on every control, label, score and number; 30-second guided tour; FAQ |
| Progressive disclosure | NN/g, *Progressive Disclosure* | Full results table and architecture diagram live in disclosures; the headline numbers are always visible |
| Content on hover/focus: dismissible, hoverable, persistent | WCAG 2.2 SC 1.4.13 | Tooltips open on hover, focus or tap; Esc closes them; they stay while hovered |
| Don't rely on colour alone | WCAG 2.2 SC 1.4.1 | BLOCK ✕ / REVIEW ! / OK ✓ text chips; chart bars labelled with names and values |
| User-selectable theme, respecting system preference | WCAG 2.2 SC 1.4.3 (contrast in each theme); `prefers-color-scheme` | ☾/☀ toggle on both pages. It starts from the system setting, remembers the choice, and is applied before first paint (no flash). Dark mode is its own palette, not an inversion |
| Respect reduced motion | WCAG 2.2 SC 2.3.3 | The hero replay and bar growth are skipped under `prefers-reduced-motion`, which shows the final state instead |

## Second pass (2026-10-21): explain every verdict, shorten time to value

| Change | Why | Source |
|---|---|---|
| Every BLOCK or REVIEW sentence shows a four-rung claim ladder (no link / linked / may cause / causes) with the paper's rung and the sentence's rung, plus the phrases that usually signal each ("saving lives" vs "could") | A visible reason helps people decide when to trust an AI verdict; a confident score with no reason earns unwarranted trust | NN/g's explainable-AI guidance, as summarised in secondary sources (the original article was not retrieved); adapted from TraceMate's quote-the-evidence review |
| Cue words are underlined only in flagged rows, and only those matching the rung Decider assigned | An early version underlined "increase" in a sentence marked OK. That is noise that contradicts the verdict | Heuristic review |
| The hero button runs the fast Decider-only check first, then offers "Let Claude fix it →" | Cuts the time to first result from the full Claude loop (20–30 s on the CPU server) to the check alone; progressive disclosure | NN/g, *Progressive Disclosure*; Nielsen heuristic 1 |
| HypeWatch uses the same ladder | Consistency and standards | Nielsen heuristic 4 |
| On phones the verdict chip sits on its own row | The label column squeezed each sentence to about five words per line | Mobile review at 390 px |
| Ladder text uses the surface colour | axe flagged 2.0:1 contrast in dark mode | WCAG 2.2 SC 1.4.3 |

## Third pass (2026-10-21): the claim ladder is the brand

The method was an Impeccable critique (one design-review agent, one detector agent), plus the
design-taste-frontend house rules and Emil Kowalski's motion rules. The site scored 26/40. The
review found that HypeCheck's own moments (the replay and the ladder) sat inside a generic
AI-startup frame. It also found two phone bugs that the second pass had claimed were fixed. They
were not.

| Change | Why |
|---|---|
| One typeface, Schibsted Grotesk, which was drawn for a news publisher | The system font read as unbranded. A news grotesk fits a product about health news |
| Flat ink hero. No gradient text, glass, side stripes or resting shadows. Cards are tone steps, not outlined boxes | These are the most recognisable generated-site tells; the detector flagged 14 |
| The hero card shows the claim ladder moving: the paper sits at *may cause*, the release climbs to *causes*, and the rewrite comes back down | The ladder explains every verdict, so it now leads instead of appearing only after a run |
| Uppercase section labels removed (9 on home, 6 on Developers). On Developers they are folded into the headings ("REST API: check text…") | Section labels repeated what the headings said |
| The paper → release → news → public chain and the four steps are real `<ol>` lists with no "1 ·" numbers | The order is carried by position |
| HypeWatch and AI summaries merged into one section ("Then we ran it on text nobody chose for us"). Stat tiles became plain facts in sentences | Removed five clusters of competing big-number tiles |
| Hero stats: 0.498 accuracy replaced by "run on 85 real NIH releases and 170 AI summaries"; "a year of NIH releases" corrected; HypeWatch's 0.20 vs 0.19 non-result moved into the reading note | "0.498 accuracy" read like a coin flip; the date wording contradicted the data |
| "Let Claude fix it" adds the fix below the check instead of wiping it. The view follows each run. The run ends on a green "Published" block. Timing is folded into a closed "Where the time went". There is a Stop button | The flow used to hide its own payoff, especially on phones |
| Phone result rows: the verdict, the sentence and the score each get their own row | At 390 px each sentence was squeezed to 1–2 words per line |
| HypeWatch and Developers no longer scroll sideways. The nav becomes a second scrollable row instead of disappearing. Grid columns use `minmax(0,1fr)` | Both pages overflowed at 390 px |
| SVG icons replace the ✕ ✓ ! ☾ ☀ ☁ ▣ glyphs | Glyphs render differently per platform |
| Motion: buttons scale to 0.97 when pressed. Tooltips and the tour fade and scale in (140–160 ms, strong ease-out). Hover is gated behind `(hover:hover)`. Chart labels arrive with their bars. The hero replay plays twice, then again on hover or focus | Emil Kowalski's rules: responsive press, no pop-in, no endless loops |
| `::selection`, caret, accent colour, scrollbar colour, link underline offset and tabular figures are set from the palette | The browser's own surfaces belong to the design too |
| A "Review" row whose sentence sits below the paper colours that rung amber, not red | Red implied an overclaim that wasn't there |
| One token block, footer and nav across all three pages | Each page had had its own accent, radius and nav |

## Verified (2026-10-21, after the third pass)

- **Impeccable detector:** 0 findings on all three pages, down from 18.
- **axe-core 4.10.2, WCAG 2.2 AA plus best practice:** 0 violations on the home page (with a rendered result, ladder and published block), HypeWatch and Developers, in both themes. One false positive remains: a `region` warning on an element injected by the testing browser extension.
- **Phone, 390 px:** `scrollWidth` equals `clientWidth` on all three pages, and result rows wrap at full width.
- **Check script:** `tests/ui/a11y_check.py`.
