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

## Verified

- **axe-core, WCAG 2.2 AA plus best practice:** 0 violations on the home page (with a real result and ladder rendered), HypeWatch and Developers,
  in both light and dark themes.
- **Mobile:** no horizontal overflow at 390 px.
- **Check script:** `tests/ui/a11y_check.py`.
