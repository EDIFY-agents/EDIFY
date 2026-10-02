# Images

## `infinity.svg`

The animation under "The binary" on the README, in the same ink as the CLI. It is not drawn by hand: the lattice of dots
is exactly the grid cells `edify init`'s own animation lights up, imported from
`src/edify/anim.py`, so the curve in the README and the curve in the terminal are
the same curve. Regenerate after any change to `anim`'s geometry:

```bash
python tools/render_infinity.py assets/infinity.svg
```

It animates through SMIL (`animateMotion`), which GitHub renders and which needs
no script — so it plays in the README and stays a still infinity anywhere that
does not animate. `prefers-reduced-motion: reduce` gets the head parked at the
start of the curve instead of the loop.

## `motion/`

The ink clips on the README and in `docs/`. They are the site's own rendered loops
from `site/assets/film/`, scaled down and re-encoded as animated WebP, because a
README plays an animated image but not a video. Nothing is re-shot: the README and
the site show the same frames, and each clip loops seamlessly already.

| file | where it plays |
|---|---|
| `stage.webp` | README header |
| `init.webp` | README install, `docs/quickstart.md` |
| `spec.webp`, `build.webp` | README commands; `build` also in `docs/verification.md` |
| `rt-*.webp` | README runtimes table, `docs/agents.md` |
| `free.webp` | README editions |

Regenerate after a clip changes (needs an `ffmpeg` with libwebp — on PATH, in
`$FFMPEG`, or from `pip install imageio-ffmpeg`):

```bash
python tools/render_motion.py assets/motion            # every clip
python tools/render_motion.py assets/motion stage      # just these
```

Sizes are chosen so the whole README stays under about 7 MB; the header is the
largest at under 2 MB.

## The terminal screenshots

`init.svg`, `doctor.svg`, `governance.svg`, `graph-where.svg`, `license.svg` and
`verify.svg` are real output of the binary, not drawings. Each one is a transcript in
`specs/` captured at a truecolor terminal, so it keeps the escapes the CLI wrote —
`$ ` lines are prompts, the rest is what the command printed, with long lines
wrapped, wide tables trimmed to a few rows, and the machine-specific path in `init`
shortened. `tools/render_terminal.py` draws the escapes as written, in the site's
terminal frame: `--ed-well` behind, square corners, the corner ticks and readout
every clip carries, and the wordmark's half blocks as solid rectangles:

```bash
python tools/render_terminal.py assets/specs/doctor.txt assets/doctor.svg
```

Recapture a transcript whenever the command's output changes; an image of output
the binary no longer prints is worse than no image.
