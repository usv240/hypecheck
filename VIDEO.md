# HypeCheck demo video: script (v2, for the redesigned site)

Target: under 3:00 (the rules say under three minutes). Budget about 400 words of narration; the
previous render of 397 words ran 2:49. Narration is Amazon Polly ("Ruth", generative). No music,
no third-party footage, no logos other than our own. `video/make_video.py` drives the live site
with Playwright and lays these lines onto the recording at the moment each scene starts.

Every number below is one the site shows today. If a number on the site changes, change it here
too; `make_video.py` and this file must say the same thing.

| # | Scene (what's on screen) | Narration | Words |
|---|---|---|---|
| 1 | **Title card:** a paper's conclusion ("could be efficacious") above a release's sentence ("is saving lives"), the second one turning red | The paper says an urgent cancer referral pathway *could be* efficacious. The press release says it *is saving lives*. In four hundred and sixty-two university press releases, a third turned an association into a cause, and when the release exaggerated, most of the news did too. | 50 |
| 2 | **Home page, hero.** The replay card runs: BLOCK 0.80, the ladder lights up, Claude's rewrite, OK 0.17 | HypeCheck stops it at the source. Strands Decider 2B rates every sentence on a four-rung ladder: no link, linked, may cause, causes. If a sentence sits higher than the paper, it is blocked. Claude on Amazon Bedrock rewrites only that sentence, and Decider checks the rewrite again. | 52 |
| 3 | **Try it.** The first real example loads and "Check with Decider only" runs; rows turn green one by one; the "saving lives" row turns red with the ladder and the quoted cue words | Here is a real press release from the research data. Decider reads it one sentence at a time, on our own server, with no language model. The saving-lives sentence scores point eight: it says *causes*, where the paper only says *may cause*. The other three sentences pass. | 50 |
| 4 | **Let Claude fix it →** is clicked. The round appears below: diff of the rewrite, re-check, green "Published" block with the receipt hash | Now Claude fixes it. The agent runs on Amazon Bedrock AgentCore Runtime. Decider reads the rewrite, nothing is above the threshold, and the release is published, with a decision receipt: every probability and threshold, hashed, so anyone can verify the verdict without a model. | 46 |
| 5 | **Evidence section.** The bar chart: Decider 6.7% against Claude 29.6, 40.0, 44.9, Guardrails 13.3, keyword rule 26.4 | Does it work? On five hundred and sixty-three expert-labelled pairs, Claude asked to judge flagged thirty to forty-five percent of faithful releases. Amazon's own grounding check ranked exaggerations at chance. A keyword rule flagged one honest release in four. Decider, with a calibrated threshold, flags six point seven percent, and the threshold's promise held on data it had never seen. | 60 |
| 6 | **Then we ran it on text nobody chose for us.** HypeWatch card, then the AI-summaries card with the "can save lives" example | Then we pointed it at the real world. HypeWatch checks eighty-five NIH press releases against their papers every morning. And when Claude summarised the same papers, about one summary in nine overclaimed. The gate fixed nine in ten. | 39 |
| 7 | **Limits card**, then the README's "Every miss listed" link | Ten pre-registered experiments, every missed prediction reported, and every mistake listed by direction. At the strict setting it catches thirty-nine percent of exaggerations. It is a safety net, not an editor, and it says so. | 36 |
| 8 | **Developers page** (API key, MCP, bring your own data, bring your own AWS), then the pattern code | The gate is a reusable Strands intervention handler: one typed question, a conformal threshold, Guide, Confirm, Proceed or Deny. Use it over REST, over MCP, calibrated on your own data, or deployed into your own AWS account. | 37 |
| 9 | **Outro card:** HypeCheck, the live URL, the repo | HypeCheck. Spell-check for hype. Links are below. | 8 |

Total: about 378 words, roughly 2:40 at Polly's pace plus scene pauses, inside the three-minute limit.

## Recording notes

- Light theme, 1120×630 viewport scaled to 720p (text reads about 14% larger), as `make_video.py` does.
- Scene 3 uses "Check with Decider only" first, then scene 4 clicks "Let Claude fix it →"; that is the
  flow the site now leads with. Set the engine to AgentCore before scene 4.
- Hover one ⓘ during scene 3 so the tooltip is visible for a beat.
- If the CPU server is slow, the agent run can take 20–30 s; the script waits for the "Published"
  block before scene 5, so timing adapts.
- Keep the whole render under 2:58. `make_video.py` refuses to write a file at or over 178 s.

## What changed from v1

- Opens on the ladder instead of a plain title; the ladder is the brand now.
- Check first, then "Let Claude fix it", matching the redesigned flow.
- Adds the decision receipt, Guardrails, the keyword rule, the AI summaries, and the miss list.
- Drops the separate "info buttons" scene (now folded into scene 3) and the timing-bar line.
- Says "matches the best published system", not "edges it": the confidence interval made that a tie.
