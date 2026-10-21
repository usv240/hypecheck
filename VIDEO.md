# Demo video: shot list and script (target 2:30, hard limit 3:00)

Record at 1080p with the browser at 125% zoom so the red/green rows are legible. No music
(the rules forbid copyrighted audio). Narration can be read from this script.

## 0:00–0:20 — The problem (slide or README screenshot)

> "A study finds that people who use an urgent cancer-referral pathway *tend* to live longer.
> The press release says the pathway *is saving lives*. That is how most exaggeration in health
> news starts: a 2014 BMJ study of 462 university press releases found causal overclaims in
> a third of them, and when the release exaggerated, 81% of the news did too."

## 0:20–0:40 — What HypeCheck is (demo page, nothing clicked yet)

> "HypeCheck reads a draft press release next to the paper it reports, flags every sentence
> that claims more than the study found, has Claude rewrite it, and re-checks the rewrite
> before anything is published. The check is made by Strands Decider 2B, a small decision model on our own server.
> The writing is done by Claude on Amazon Bedrock."

## 0:40–1:30 — Live run (pick the first example, keep "AgentCore Runtime" selected, click "Run the agent")

Point at the screen as the events arrive:

> "The agent is running on Amazon Bedrock AgentCore Runtime; you can see the badge. Round one:
> Decider reads the draft one sentence at a time. The 'saving lives' sentence
> scores 0.81 for claiming more than the paper's hedged conclusion. Everything else is green.
> The publish call is blocked, and Claude gets the feedback."

> "Round two: Claude changed 'is saving lives' to 'could be efficacious', and softened the
> advice. Decider reads the rewrite again, nothing is above threshold, and the release is
> published. The bar at the bottom shows where the time went: green is Decider, blue is
> Claude."

## 1:30–2:05 — Why Decider, with the numbers (README results table)

> "Why not ask Claude to check itself? We did. On 563 expert-labelled press-release pairs,
> Claude flagged 30 to 45% of the *faithful* releases as exaggerated, depending on the model,
> Opus included. Decider, with a threshold fitted by conformal calibration, flags 6.7%, and
> still catches twice as many real exaggerations as Haiku at that false-flag rate. Zero-shot, it also matches the best
> published system on this benchmark. And because Decider cannot generate text, Claude cannot
> talk it out of a verdict."

## 2:05–2:30 — The reusable pattern and the limits (repo)

> "The decision pattern is a plain Strands InterventionHandler: typed questions, a conformal
> threshold, Guide, Confirm or Proceed. The same gate runs a patient-leaflet writer in the
> examples folder. Two limits are measured, not hidden: recall at the strict threshold is 39%,
> and the animal-to-human check is weak, AUROC 0.61, so it is shown as a hint only. Every number
> was pre-registered before the run; the predictions we missed are in the repo too."

## 2:30–2:40 — Close

> "HypeCheck. Spell-check for hype. Repo, article and live demo in the description."

## Recording checklist

- Decider server up and warm (run one check before recording so the first call is not slow).
- Browser: dark or light theme, 125% zoom, window about 1500 px wide.
- Have the README open in a second tab at the results table.
- Upload unlisted or public on YouTube; paste the link into the submission and the article.
