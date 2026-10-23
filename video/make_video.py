"""Record the demo video: Playwright drives the live site, Amazon Polly narrates, ffmpeg muxes.

Each scene waits for its trigger (a page event), notes the time, plays its narration length, then
hands over. The narration clips are laid onto the recording at the noted times, so audio stays in
sync even though the live agent's timing varies. No music, no third-party footage.

    python video/make_video.py --site https://d174bz5yly61n4.cloudfront.net --out video/hypecheck-demo.mp4
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import time
from pathlib import Path

import boto3
from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
VOICE = "Ruth"

SCENES = [  # kept in step with VIDEO.md; every number here is one the site shows
    ("cold", 'After one news storm about statins, an estimated two hundred and nineteen thousand people in the UK stopped their heart medicine. The hype that reached them started in a press release.'),
    ("intro", 'The paper says a cancer referral pathway could be efficacious. The press release says it is saving lives. A third of university releases do this, and most of the news repeats it.'),
    ("hero", 'HypeCheck stops it at the source. Strands Decider 2B rates every sentence on a four-rung ladder: no link, linked, may cause, causes. A sentence that sits higher than the paper is blocked. Claude on Amazon Bedrock rewrites it, and Decider checks the rewrite again.'),
    ("check", 'Here is a real press release from the research data. Decider reads it one sentence at a time on our own server, with no language model. The saving-lives sentence scores point eight: it says causes, where the paper only says may cause. The other three pass.'),
    ("fix", 'Now Claude fixes it. The agent runs on Amazon Bedrock AgentCore Runtime. Claude rewrites only the blocked sentence, Decider reads the rewrite, and nothing is above the threshold.'),
    ("published", "Published, with a decision receipt: every probability and threshold, hashed, so anyone can verify the verdict without a model."),
    ("evidence", "Does it work? On five hundred and sixty-three expert-labelled pairs, Claude asked to judge flagged thirty to forty-five percent of faithful releases. Amazon's own grounding check scored at chance. A keyword rule flagged one honest release in four. Decider, calibrated, flags six point seven percent, and that promise held on unseen data."),
    ("realworld", 'Then we pointed it at the real world. HypeWatch checks eighty-five NIH press releases against their papers every morning. When Claude summarised the same papers, one in nine overclaimed. The gate fixed nine in ten.'),
    ("limits", 'Ten pre-registered experiments, every miss reported and listed. At the strict setting it catches thirty-nine percent of exaggerations: a safety net, not an editor, and it says so.'),
    ("builders", 'The gate is a reusable Strands intervention handler: one typed question, a conformal threshold, Guide, Confirm, Proceed or Deny. Use it over REST or MCP, on your own data, or in your own AWS account.'),
    ("outro", 'HypeCheck. Spell-check for hype. Links are below.'),
]


def synth(out: Path) -> dict[str, tuple[Path, float]]:
    polly = boto3.client("polly", region_name="us-east-1")
    clips = {}
    for name, text in SCENES:
        mp3 = out / f"{name}.mp3"
        audio = polly.synthesize_speech(Text=text, VoiceId=VOICE, Engine="generative", OutputFormat="mp3",
                                        SampleRate="24000")["AudioStream"].read()
        mp3.write_bytes(audio)
        dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of",
                                    "default=nw=1:nk=1", str(mp3)], capture_output=True, text=True).stdout)
        clips[name] = (mp3, dur)
    return clips


def scroll_to(page, selector: str, offset: int = 70) -> None:
    page.evaluate(f"""(() => {{ const el = document.querySelector({json.dumps(selector)});
        window.scrollTo({{top: el.getBoundingClientRect().top + scrollY - {offset}, behavior: 'smooth'}}); }})()""")


def record(site: str, clips: dict, out: Path) -> tuple[Path, list[tuple[str, float]]]:
    timeline: list[tuple[str, float]] = []
    card = (HERE / "card.html").resolve().as_uri()
    with sync_playwright() as p:
        browser = p.chromium.launch()
        # Viewport and recording size must match, or the page is painted into a corner of the frame.
        # 1280x720 with a 1.15x zoom keeps the text legible at 720p.
        ctx = browser.new_context(viewport={"width": 1280, "height": 720}, color_scheme="light",
                                  record_video_dir=str(out), record_video_size={"width": 1280, "height": 720})
        page = ctx.new_page()
        page.add_init_script("document.addEventListener('DOMContentLoaded', () => { document.documentElement.style.zoom = '1.15'; });")
        t0 = time.monotonic()
        busy_until = 0.0

        def scene(name: str, action=None, until=None, pad: float = 0.4) -> None:
            nonlocal busy_until
            if action:
                action()
            if until:
                until()
            now = time.monotonic() - t0
            start = max(now, busy_until)
            if start > now:
                time.sleep(start - now)
            timeline.append((name, start))
            busy_until = start + clips[name][1] + pad
            time.sleep(max(0.0, busy_until - (time.monotonic() - t0)))

        page.goto(f"{card}?s=cold")
        page.wait_for_timeout(600)
        scene("cold", pad=0.3)
        page.goto(f"{card}?s=intro")
        page.wait_for_timeout(600)
        scene("intro")

        page.goto(site)
        page.wait_for_selector("#ex option:nth-child(2)", state="attached")
        page.evaluate("document.documentElement.setAttribute('data-theme','light')")
        page.wait_for_timeout(500)
        scene("hero")

        def start_check():
            # the hero button loads the first real example and runs the Decider-only check
            page.evaluate("document.querySelector('input[value=agentcore]').checked = true")
            page.evaluate("document.querySelector('#heroTry').click()")
            page.wait_for_selector("#results .sent.block", timeout=240_000)
            page.wait_for_timeout(400)
            page.evaluate("document.querySelector('#results .sent.block').scrollIntoView({block:'center', behavior:'smooth'})")
            page.wait_for_timeout(700)
            page.hover("#results .sent.block .score .i")
        scene("check", action=start_check, pad=0.2)
        page.mouse.move(5, 5)

        def show_fix():
            # start Claude's fix as this line begins; the narration plays over the live rounds, and we
            # wait for the published block only as long as the clip leaves room for it
            page.wait_for_selector("#fixBtn", timeout=120_000)
            page.evaluate("document.querySelector('#fixBtn').click()")
        scene("fix", action=show_fix, pad=0.2)

        def land_on_published():
            page.wait_for_selector("#results .final", timeout=300_000)
            page.wait_for_timeout(300)
            page.evaluate("document.querySelector('#results .final').scrollIntoView({block:'center', behavior:'smooth'})")
            page.wait_for_timeout(900)
        scene("published", action=land_on_published, pad=0.2)

        scene("evidence", action=lambda: scroll_to(page, "#chartCard", 90))
        scene("realworld", action=lambda: scroll_to(page, "#hypewatch", 70))

        def show_limits():
            scroll_to(page, ".limits", 140)
        scene("limits", action=show_limits)

        def open_dev():
            page.goto(site.rstrip("/") + "/developers")
            page.wait_for_selector(".grid4", timeout=60_000)
            page.evaluate("document.documentElement.setAttribute('data-theme','light')")
            page.wait_for_timeout(900)
            page.evaluate("window.scrollTo({top: document.querySelector('.grid4').getBoundingClientRect().top + scrollY - 160, behavior:'smooth'})")
        scene("builders", action=open_dev)

        page.goto(f"{card}?s=outro")
        page.wait_for_timeout(300)
        scene("outro", pad=0.3)
        video = Path(page.video.path())
        ctx.close()
        browser.close()
    return video, timeline


def mux(video: Path, clips: dict, timeline: list[tuple[str, float]], dest: Path) -> None:
    args = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(video)]
    filters, labels = [], []
    for i, (name, start) in enumerate(timeline, start=1):
        args += ["-i", str(clips[name][0])]
        ms = int(start * 1000)
        filters.append(f"[{i}:a]adelay={ms}|{ms},aresample=48000[a{i}]")
        labels.append(f"[a{i}]")
    filters.append(f"{''.join(labels)}amix=inputs={len(labels)}:normalize=0:dropout_transition=0[aout]")
    args += ["-filter_complex", ";".join(filters), "-map", "0:v", "-map", "[aout]",
             "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p", "-r", "30",
             "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(dest)]
    subprocess.run(args, check=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", default="https://d174bz5yly61n4.cloudfront.net")
    ap.add_argument("--out", type=Path, default=HERE / "hypecheck-demo.mp4")
    args = ap.parse_args()
    work = HERE / "build"
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(exist_ok=True)
    clips = synth(work)
    print("narration seconds:", round(sum(d for _, d in clips.values()), 1))
    video, timeline = record(args.site, clips, work)
    mux(video, clips, timeline, args.out)
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of",
                                "default=nw=1:nk=1", str(args.out)], capture_output=True, text=True).stdout)
    (HERE / "timeline.json").write_text(json.dumps({"total_seconds": round(dur, 1),
                                                    "scenes": [(n, round(t, 1)) for n, t in timeline]}, indent=1))
    print(f"wrote {args.out} ({dur:.1f} s)")
    if dur >= 178:
        raise SystemExit(f"video is {dur:.1f} s; the rules say under three minutes. Shorten the narration.")


if __name__ == "__main__":
    main()
