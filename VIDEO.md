# HypeCheck demo video: script (v2, for the redesigned site)

Target: under 3:00 (the rules say under three minutes). Budget about 400 words of narration; the
previous render of 397 words ran 2:49. Narration is Amazon Polly ("Ruth", generative). No music,
no third-party footage, no logos other than our own. `video/make_video.py` drives the live site
with Playwright and lays these lines onto the recording at the moment each scene starts.

Every number below is one the site shows today. If a number on the site changes, change it here
too; `make_video.py` and this file must say the same thing.

| # | Scene (what's on screen) | Narration | Words |
|---|---|---|---|
| 0 | **Cold open card:** the statin storm, one line | After one news storm about statins, an estimated two hundred and nineteen thousand people in the UK stopped their heart medicine. The hype that reached them started in a press release. | 31 |
| 1 | **Title card:** paper vs release, "is saving lives" struck through, then the ladder | The paper says a cancer referral pathway could be efficacious. The press release says it is saving lives. A third of university releases do this, and most of the news repeats it. | 32 |
| 2 | **Home page hero.** The replay card runs | HypeCheck stops it at the source. Strands Decider 2B rates every sentence on a four-rung ladder: no link, linked, may cause, causes. A sentence that sits higher than the paper is blocked. Claude on Amazon Bedrock rewrites it, and Decider checks the rewrite again. | 44 |
| 3 | **Try it.** "Check with Decider only" on the first real example; the "saving lives" row turns red with the ladder, cue words and the score tooltip | Here is a real press release from the research data. Decider reads it one sentence at a time on our own server, with no language model. The saving-lives sentence scores point eight: it says causes, where the paper only says may cause. The other three pass. | 46 |
| 4 | **Let Claude fix it →** is clicked; rounds build live, the agent on AgentCore | Now Claude fixes it. The agent runs on Amazon Bedrock AgentCore Runtime. Claude rewrites only the blocked sentence, Decider reads the rewrite, and nothing is above the threshold. | 28 |
| 5 | Green **Published** block with the receipt hash | Published, with a decision receipt: every probability and threshold, hashed, so anyone can verify the verdict without a model. | 19 |
| 6 | **Evidence section**, the bar chart | Does it work? On five hundred and sixty-three expert-labelled pairs, Claude asked to judge flagged thirty to forty-five percent of faithful releases. Amazon's own grounding check scored at chance. A keyword rule flagged one honest release in four. Decider, calibrated, flags six point seven percent, and that promise held on unseen data. | 52 |
| 7 | **Then we ran it on text nobody chose for us:** HypeWatch and AI-summaries cards | Then we pointed it at the real world. HypeWatch checks eighty-five NIH press releases against their papers every morning. When Claude summarised the same papers, one in nine overclaimed. The gate fixed nine in ten. | 35 |
| 8 | **Limits card** | Ten pre-registered experiments, every miss reported and listed. At the strict setting it catches thirty-nine percent of exaggerations: a safety net, not an editor, and it says so. | 28 |
| 9 | **Developers page** | The gate is a reusable Strands intervention handler: one typed question, a conformal threshold, Guide, Confirm, Proceed or Deny. Use it over REST or MCP, on your own data, or in your own AWS account. | 35 |
| 10 | **Outro card:** the two links | HypeCheck. Spell-check for hype. Links are below. | 7 |

Total: 357 words of narration; the 2026-10-23 render ran 2:53 against the live site, inside the three-minute limit.

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
