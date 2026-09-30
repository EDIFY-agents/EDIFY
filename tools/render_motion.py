#!/usr/bin/env python3
"""Render the site's ink clips into animated WebP the README can play.

A README cannot play a `<video>`, but it plays an animated image. The clips here
are not re-shot for GitHub: each one is the site's own rendered loop
(`site/assets/film/`), scaled down and re-encoded, so the README and the site
show the same frames. Each clip already loops seamlessly — every motion in it
turns a whole number of times per loop — so no trimming is needed.

    python tools/render_motion.py assets/motion            # every clip
    python tools/render_motion.py assets/motion stage      # just these

It needs an `ffmpeg` built with libwebp: on PATH, named by `$FFMPEG`, or the one
`pip install imageio-ffmpeg` bundles. The package itself still has no
dependencies; this is a tool for whoever changes the clips.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

#: Where the clips live here, and where they live in the public tree.
FILM = ("edify-public-site/site/assets/film", "site/assets/film")

#: name, source clip, output width, frames per second, WebP quality.
CLIPS = (
    ("stage", "home/stage.mp4", 800, 12, 55),
    ("init", "clips/init.mp4", 800, 15, 65),
    ("spec", "clips/spec.mp4", 400, 15, 68),
    ("build", "clips/build.mp4", 400, 15, 68),
    ("free", "clips/free.mp4", 800, 15, 65),
    ("rt-claude", "clips/rt-claude.mp4", 320, 12, 65),
    ("rt-codex", "clips/rt-codex.mp4", 320, 12, 65),
    ("rt-cursor", "clips/rt-cursor.mp4", 320, 12, 65),
    ("rt-gemini", "clips/rt-gemini.mp4", 320, 12, 65),
    ("rt-github", "clips/rt-github.mp4", 320, 12, 65),
    ("rt-windsurf", "clips/rt-windsurf.mp4", 320, 12, 65),
)


def ffmpeg() -> str:
    found = os.environ.get("FFMPEG") or shutil.which("ffmpeg")
    if found:
        return found
    try:
        import imageio_ffmpeg
    except ImportError:
        sys.exit("no ffmpeg: put one on PATH, set $FFMPEG, or pip install imageio-ffmpeg")
    return imageio_ffmpeg.get_ffmpeg_exe()


def film() -> Path:
    for rel in FILM:
        if (ROOT / rel).is_dir():
            return ROOT / rel
    sys.exit(f"no clips under any of {', '.join(FILM)}")


def render(exe: str, source: Path, target: Path, width: int, fps: int, quality: int) -> None:
    subprocess.run(
        [
            exe, "-hide_banner", "-loglevel", "error", "-y",
            "-i", str(source),
            "-vf", f"fps={fps},scale={width}:-2:flags=lanczos",
            "-an", "-c:v", "libwebp_anim", "-lossless", "0",
            "-q:v", str(quality), "-compression_level", "6",
            "-loop", "0", "-map_metadata", "-1",
            str(target),
        ],
        check=True,
    )


def main(argv: list[str]) -> int:
    out = Path(argv[1] if len(argv) > 1 else ROOT / "assets" / "motion")
    only = set(argv[2:])
    out.mkdir(parents=True, exist_ok=True)
    exe, src = ffmpeg(), film()
    for name, clip, width, fps, quality in CLIPS:
        if only and name not in only:
            continue
        target = out / f"{name}.webp"
        render(exe, src / clip, target, width, fps, quality)
        print(f"{target.name:18} {target.stat().st_size / 1024:7.0f} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
