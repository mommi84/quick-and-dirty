# award

A 3D-printable trophy: a black stepped base, a cup with handles, and a separate black plaque with white text.
Assembled it is 70 × 47 × 98 mm.

| File | Colour | Notes |
|---|---|---|
| `award_base.stl` | black | Prints upright. The peg on top locates the cup, and the front pocket takes the plaque. |
| `award_cup.stl` | your choice (gold, for the full effect) | Prints upright on its foot. There's a socket underneath for the peg. |
| `award_plaque.stl` | black, then white | Single-extruder version. Prints flat, text up. Add a filament change at **z = 1.6 mm** (the first layer above the plate). |
| `award_plaque_black.stl` + `award_plaque_white.stl` | black + white | The same plaque split into two bodies for multi-material printers (AMS/MMU). Import both and keep them aligned. |
| `award_plaque_frame.stl` | white | Just the border frame, with no text. It sits at z = 1.6–2.2 mm, on top of `award_plaque_black.stl`. Use the two together to add your own text in Bambu Studio (see below). |

None of the parts need supports. Glue the plaque into the pocket and the cup onto the peg. The parts have 0.2 mm of clearance; change `FIT` if your printer disagrees.

```
pip install trimesh manifold3d shapely mapbox_earcut matplotlib
python award.py --text "BEST\nHUMAN" --out .
```

Long text is shrunk to fit the plaque. Print the plaque at 0.12 to 0.16 mm layers so the small letters stay crisp.

## Adding your own text in Bambu Studio

1. Import `award_plaque_black.stl` and `award_plaque_frame.stl` together. When it asks whether to load them as a single object with multiple parts, say **yes**. That keeps the frame on top of the plate.
2. Give the frame part white filament and the plate black.
3. Right-click the object, choose **Add part → Text**, and click the top of the plate to place the text. Set the depth to **0.6 mm** so it's level with the frame, and give it white filament.

## Treble clef version

`clef.py` makes a topper that replaces the cup and fits the same base and plaque.

| File | Notes |
|---|---|
| `award_clef.stl` | Prints flat, so no supports. It's 6 mm thick, and its edges are thickened by 0.7 mm so the thin strokes don't snap. |
| `award_clef_stand.stl` | Prints upright. It has the same foot as the cup and the same socket for the peg, plus a slot on top for the clef's tab. |

Glue the clef's tab into the stand's slot, then glue the stand onto the base's peg. The glyph comes from FreeSerif (`apt install fonts-freefont-ttf`); to use another font with U+1D11E, pass `--font`.

```
python clef.py --out .
```
