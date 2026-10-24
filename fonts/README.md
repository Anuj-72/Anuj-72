# Embedded fonts

`ProfileMono-Regular.woff`, `ProfileMono-SemiBold.woff`, and
`ProfileDisplay-SemiBold.woff` are ASCII-only subsets (U+0020–U+007E) of two OFL
typefaces, inlined into the generated SVGs as base64 WOFF by
`generate_profile.py`.

| File | Family in the SVG | Upstream |
| --- | --- | --- |
| `ProfileMono-Regular.woff` | `Profile Mono` 400 | [JetBrains Mono](https://www.jetbrains.com/lp/mono/) Regular |
| `ProfileMono-SemiBold.woff` | `Profile Mono` 600 | JetBrains Mono SemiBold |
| `ProfileDisplay-SemiBold.woff` | `Profile Display` 600 | [Space Grotesk](https://github.com/floriankarsten/space-grotesk) at weight 600 |

Both are licensed under the SIL Open Font License 1.1:

- `OFL-JetBrainsMono.txt` — Copyright 2020 The JetBrains Mono Project Authors.
- `OFL-SpaceGrotesk.txt` — Copyright 2020 The Space Grotesk Project Authors.

The subsets are renamed (`Profile Mono`, `Profile Display`) because the originals are
distributed under their own names; outlines, metrics, and copyright notices are
unchanged. Only the printable ASCII range is kept, so accented characters fall back
to the system stack declared in the SVG.

Rebuild a subset after downloading the upstream TTF:

```bash
python3 -m fontTools.subset JetBrainsMono-Regular.ttf \
  --unicodes=U+0020-007E --flavor=woff --no-hinting \
  --output-file=ProfileMono-Regular.woff
```

The display face is instanced from the Space Grotesk variable font at `wght=600`
before subsetting. Rename the family in the name table (IDs 1, 3, 4, 6, 16) to
`Profile Mono` / `Profile Display` as the checked-in files do.
