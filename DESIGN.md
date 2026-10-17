# Design notes for the demo site

The page has to make sense to someone who has never heard of Strands Decider, conformal
prediction or press-release research, in the three to five minutes a judge spends. Each rule below
names a source and how it shows up on the page.

| Principle | Source | Applied as |
|---|---|---|
| Visibility of system status | Nielsen, *10 Usability Heuristics* (heuristic 1) | Sentences colour one by one as Decider reads them; progress counter; queue position; time split between Decider and Claude |
| Match between system and the real world | Nielsen heuristic 2 | Plain words first ("claims more than the paper"), the technical term second, inside an ⓘ |
| Recognition rather than recall | Nielsen heuristic 6 | Real benchmark examples one click away; no blank-page start |
| Error prevention, clear error messages | Nielsen heuristics 5 and 9 | Inputs validated before a run; errors say what to do next |
| Help and documentation, in context | Nielsen heuristic 10 | An ⓘ on every control, label, score and number; a glossary; a 30-second guided tour |
| Progressive disclosure | Nielsen Norman Group, *Progressive Disclosure* | The headline and the tool sit above the fold; evidence, method and limits below; detail in ⓘ and accordions |
| Content on hover or focus must be dismissible, hoverable and persistent | WCAG 2.2 SC 1.4.13 | Tooltips open on hover, keyboard focus or tap; Esc closes them; the pointer can move onto them; they stay until dismissed |
| Don't use colour alone | WCAG 2.2 SC 1.4.1 | Every verdict carries a text chip and an icon: BLOCK ✕ / REVIEW ! / OK ✓ |
| Contrast ≥ 4.5:1 for text | WCAG 2.2 SC 1.4.3 | Palette checked in light and dark themes |
| Keyboard operable, visible focus | WCAG 2.2 SC 2.1.1, 2.4.7 | Every ⓘ is a real `<button>`; focus ring kept |
| Respect reduced motion | WCAG 2.2 SC 2.3.3 / `prefers-reduced-motion` | Animations off when the user asks |
| One primary action per view | Material Design, *Buttons: emphasis* | "Run the agent" is the only filled button; "Check with Decider only" is secondary |
| Readable line length | Butterick, *Practical Typography* (45–90 characters) | Prose capped at about 70ch |
