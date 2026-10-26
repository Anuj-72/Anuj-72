# Figma-based static GitHub profile SVGs

This package contains the original Figma-exported light SVG, a Python generator, and generated static light/dark profile SVGs.

## Generate both themes

From this directory, run:

```bash
python3 generate_profile.py
```

The script writes `profile-light.svg` and `profile-dark.svg` beside itself. Add
`--no-sweep` for a still card with the bloom, or `--no-glow` for a flat card. To choose
a different source or output directory:

```bash
python3 generate_profile.py "GitHub README Light.svg" --out-dir .
```

No third-party Python modules are required. The original Figma SVG is never modified. The script replaces the left information block, rescales the cactus illustration, and resizes the surrounding Figma card; the exported artwork, chrome, gradients, and shadow are retained.

## Edit content

Edit the `PERSONAL_ROWS`, `CODING_ROWS`, and `CONTACT_ROWS` lists in
`generate_profile.py`.

The `Uptime:` row is generated, not typed. `UPTIME_EPOCH` (currently `2005-08-02`) is
the date it counts from, and `elapsed_label()` renders the completed years, months and
days. The count uses the UTC date, so the row advances once just after 00:00 UTC.
`DAILY_DOWNTIME` is a static string (`8-10 Hours`); edit it if the joke changes.

## Daily refresh

`.github/workflows/refresh-profile.yml` regenerates both SVGs every day at 18:30 UTC
(00:00 IST) and on manual dispatch. It runs `python3 generate_profile.py` with no
third-party packages, then commits `profile-light.svg` and `profile-dark.svg` only when
their content changed — an identical run leaves the history untouched. The push uses
the workflow's own token via `permissions: contents: write`.

The workflow assumes the repository root contains the script, `fonts/`, the source SVG
and the two generated files — the layout of this folder. If you keep them in a
subdirectory, add `working-directory:` to the run step and adjust the `git add` paths.
Preview PNGs under `preview/` are development artifacts and are not committed by the
workflow.

Scheduled workflows only run from the default branch, and they need Actions enabled and
a token allowed to push there; branch protection that blocks direct pushes will stop
the commit step. GitHub also disables cron schedules after 60 days of repository
inactivity, which a manual dispatch re-arms.

## Layout

The cactus block is scaled as one unit (`ART_SCALE`, `ART_TOP`, `ART_LEFT`) so it starts and ends level with the text column instead of running past it. The card and canvas dimensions in the `Card geometry` block are sized around the two columns, so shrinking the illustration also narrows the image. The canvas runs from -22 to 1206, leaving a transparent gutter for the card shadow and the neon halo.

Rendered previews can be regenerated with headless Chrome:

```bash
for t in light dark; do
  google-chrome --headless=new --disable-gpu --hide-scrollbars \
    --window-size=1206,578 --default-background-color=00000000 \
    --screenshot="preview/profile-$t.png" "file://$PWD/profile-$t.svg"
done
```

## Fonts

The card uses JetBrains Mono for the information and Space Grotesk SemiBold for the
section headings. Small ASCII-only WOFF subsets live in `fonts/` and are inlined into
each SVG as base64, so the type does not depend on what the viewer has installed.
That is what keeps the dotted leaders aligned and the card identical on GitHub.

Labels are 13.8px regular, values are 15.2px semibold, and headings are 19.5px. The
weight and size gap between labels and values is what makes the facts stand out. If
`fonts/` is missing, the script warns and falls back to SF Mono / Menlo / Consolas.

## Neon bloom

By default the card gets a static neon bloom: a glowing frame around the card edge and
a halo on every value. It is built from two SVG filters in `<defs>`:

- `neon-frame-glow` blurs the frame's alpha (`BORDER_GLOW_STD`), floods it with the
theme's `glow` color, and merges it under the crisp stroke.
- `neon-value-glow` does the same at a tighter radius for the values, using the
`value_glow` color.

The halo itself is static and adds about 1.6 KB per SVG. The canvas gutter keeps it
from being clipped, and the source artwork and text render crisply under the bloom.
Run `python3 generate_profile.py --no-glow` to omit both filters, the frame and
the scan band for the flat version.

## Scan band

On top of the bloom, the card gets a looping CRT-style scan: a 78px-thick soft gradient
(theme `glow` color, transparent at both ends) that crosses the card diagonally from
the top-left corner toward the bottom-right. The band's long axis runs perpendicular to
the travel direction (`SWEEP_ANGLE = -45`), and it is clipped to the rounded card, so it
passes over the text and cactus like a screen refresh but never spills into the halo
gutter. Both cards also get a CRT grid (`SWEEP_GRID_OPACITY`, 22px cells) for the band
to cross: cyan hairlines on the dark card, pale warm gold on the light one. The grid is
not visible all over the card — a soft mask the height of `SWEEP_GLOW_HEIGHT` travels
with the band, so the lines only light up in a halo around the sweep and fade behind
it. At rest, with the band off-screen, the card shows no grid at all.

It is declarative CSS inside the SVG — no SMIL, no script, no external request — and
adds about 1.8 KB including the mask and grid. Only `transform` is animated: the band
and the mask share the same keyframes, and the glow filters are not re-blurred on every
frame. One pass takes 5.2s of the 7.4s cycle; the remaining 2.2s is the rest.
The band starts above the top-left corner, so a still frame (native GitHub clients,
screenshots, `--no-sweep`) shows the finished card with no partial band.

- `SWEEP_ANGLE`, `SWEEP_HEIGHT`, `SWEEP_BAND_WIDTH`, `SWEEP_TRAVEL` and
`SWEEP_DURATION` control direction, width, distance and timing; travel always occupies
70% of the cycle.
- `SWEEP_OPACITY` sets peak strength per theme (0.20 light, 0.24 dark, before the
gradient's own 0.55 stop opacity). Both are low enough that text under the band stays
legible; the dark card is deliberately a touch stronger because cyan reads better on
near-black than gold does on cream.
- `SWEEP_GRID_SIZE`, `SWEEP_GLOW_HEIGHT` and `SWEEP_GRID_OPACITY` control the CRT grid
(22px cells, 300px halo, 0.55 light / 0.16 dark). The base opacity is higher than an
unmasked grid because the mask fades most of it away. The grid color is
`palette["grid"]`; the light theme uses pale gold `#F7E3A6` rather than the saturated
frame gold, because the lighter line keeps the contact rows at 4.6:1 contrast instead
of dipping under 4.5:1 at the halo peak. Set an opacity to `0.0` to remove the grid
from that theme.
- `python3 generate_profile.py --no-sweep` keeps the bloom and writes a still
card; the grid belongs to the scan layer, so it goes too. `--no-glow` omits the bloom,
the grid and the band together.

The SVG declares
`@media (prefers-reduced-motion:reduce){.neon-sweep,.neon-grid{display:none}}`, so both
the band and the grid glow are removed for viewers who ask for reduced motion. This was
verified with a browser-level reduced-motion setting, both standalone and through an
`<img>`; a per-page DevTools emulation may not reach the SVG image document.

GitHub's image proxy caches aggressively. If you change the band, rename the files or
add a `?v=` query to the README URL so visitors do not keep the old cached SVG.

## Theme colors

The theme colors are defined in `PALETTES`:

- Light: Monokai Pro Light (filter Sun) — `#F8EFE7` cream background, `#EEE5DE` chrome,
  `#2473B6` title (`blue`), `#CE4770` headings (`keyword`), `#756864` labels (comment,
  darkened for legibility), `#9C5B02` values (string amber), `#D2C3B6` rules/divider, and
  `#D4572B` wordmark (`orange`). Sun's published palette is used; the official theme
  JSON is not public. The glow uses `#E0A800` (warm gold) for the frame and `#D98200`
  for values, and the grid uses pale gold `#F7E3A6`.
- Dark: classic Monokai, taken from the Sublime Text package — `#282923` background
  (`black3`), `#3E3D32` chrome (`yellow4`), `#67D8EF` title (`blue`), `#F92472` headings
  (`red2`), `#9A9682` labels (a legible tint of comment `yellow5`), `#E7DB74` values
  (`yellow`), `#5E5A49` leaders, and `#FD9621` wordmark (`orange`). The glow uses
  `#67D8EF` for the frame and `#F7EC9B` for values; the grid reuses the frame cyan.

## Checking the output

`python3 generate_profile.py` re-parses both written files before reporting success, so malformed SVG output fails the run. Build the flags you intend to publish (`--no-sweep`, `--no-glow`) once more before committing.

The card artwork and text are vector, not GIF frames, so they stay crisp at any scale; only the scan band and its grid halo are animated, and the previews in `preview/` show the resting frame. The existing README can continue using `profile-dark.svg` and `profile-light.svg` in its `<picture>` element.
