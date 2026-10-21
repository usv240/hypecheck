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

SCENES = [
    ("intro", "The paper says an urgent cancer referral pathway could be efficacious. The press release says "
              "it is saving lives. In four hundred and sixty-two university press releases, a third turned an "
              "association into a cause, and when the release exaggerated, most of the news did too."),
    ("hero", "HypeCheck stops it at the source. Strands Decider 2B checks every sentence against the paper, "
             "Claude on Amazon Bedrock rewrites what overclaims, and Decider checks the rewrite again."),
    ("how", "One overclaim travels from a press office to millions of readers. A third of releases turn a link "
            "into a cause, most news repeats it, and health news changes what people do. HypeCheck sits at the "
            "one point where a single fix changes everything downstream."),
    ("run", "Here is a real press release from the research data. The agent is running on Amazon Bedrock "
            "AgentCore Runtime, and Decider reads the draft one sentence at a time."),
    ("blocked", "The saving-lives sentence scores point eight: a definite cause, where the paper only says the "
                "pathway could be efficacious. Publishing is blocked, and the gate hands Claude its turn back "
                "with the reason."),
    ("published", "Claude rewrites only that sentence. Decider checks the rewrite, nothing is above the "
                  "threshold, and the release is published. The bar shows the time split between Decider and "
                  "Claude."),
    ("info", "Every label, score and number has an info button that explains it in plain words."),
    ("evidence", "Does it work? On five hundred and sixty-three expert-labelled release and paper pairs, Claude "
                 "asked to judge flagged thirty to forty-five percent of faithful releases as exaggerated, Opus "
                 "included. Decider, with a calibrated threshold, flags six point seven percent, and matches the best "
                 "published system on overall accuracy without training on the task."),
    ("hypewatch", "Then we pointed it at the real world. HypeWatch checks every research release from the US "
                  "National Institutes of Health in the past year against the paper it cites, with Claude's "
                  "suggested fix, verified by Decider, beside every flag. It updates every morning."),
    ("limits", "Every experiment was pre-registered, and the limits are on the page: at its strictest setting it "
               "catches thirty-nine percent of exaggerations. It's a safety net, not an editor."),
    ("builders", "The gate is a reusable Strands intervention handler: one typed question, a calibrated "
                 "threshold, and Guide, Confirm or Proceed. The same code runs a patient-leaflet writer unchanged."),
    ("outro", "HypeCheck. Spell-check for hype. Links are below."),
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
        # A slightly smaller viewport scaled up to 720p makes on-screen text about 14% larger.
        ctx = browser.new_context(viewport={"width": 1120, "height": 630}, color_scheme="dark",
                                  record_video_dir=str(out), record_video_size={"width": 1280, "height": 720})
        page = ctx.new_page()
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

        page.goto(f"{card}?s=intro")
        page.wait_for_timeout(600)
        scene("intro")
        page.goto(site)
        page.wait_for_selector("#ex option:nth-child(2)", state="attached")
        page.wait_for_timeout(400)
        scene("hero")
        scene("how", action=lambda: scroll_to(page, "#impact", 64))

        def start_run():
            page.select_option("#ex", "0")
            scroll_to(page, "#out", 64)
            page.wait_for_timeout(900)
            page.evaluate("document.querySelector('#run').click()")  # a JS click doesn't scroll the view away
        scene("run", action=start_run)
        def show_block():
            page.wait_for_selector(".act.guide", timeout=240_000)
            scroll_to(page, "#out", 64)
        scene("blocked", until=show_block)

        def show_end():
            page.wait_for_function("document.querySelector('#statusText').textContent.startsWith('Done')", timeout=300_000)
            page.evaluate("document.querySelector('#results').lastElementChild.scrollIntoView({block:'end', behavior:'smooth'})")
            page.wait_for_timeout(700)
        scene("published", until=show_end)

        def hover_info():
            scroll_to(page, "#top", 0)
            page.wait_for_timeout(700)
            page.hover(".proof .i")
        scene("info", action=hover_info)
        page.mouse.move(5, 5)
        scene("evidence", action=lambda: scroll_to(page, "#chartCard", 90))
        def open_hypewatch():
            page.goto(site.rstrip("/") + "/hypewatch")
            page.wait_for_selector(".rel", timeout=60_000)
            page.wait_for_timeout(1500)
            page.evaluate("window.scrollTo({top: document.querySelector('.rel').getBoundingClientRect().top + scrollY - 70, behavior:'smooth'})")
        scene("hypewatch", action=open_hypewatch, pad=1.0)

        def back_to_limits():
            page.goto(site)
            page.wait_for_selector(".limits")
            scroll_to(page, ".limits", 260)
        scene("limits", action=back_to_limits)
        scene("builders", action=lambda: scroll_to(page, "#builders", 80))
        page.goto(f"{card}?s=outro")
        page.wait_for_timeout(300)
        scene("outro", pad=1.5)
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
