# award

A 3D-printable trophy: a black stepped base, a cup with handles, and a separate black plaque with white text.
Assembled it is 70 × 47 × 98 mm.

| File | Colour | Notes |
|---|---|---|
| `award_base.stl` | black | Prints upright. The peg on top locates the cup, and the front pocket takes the plaque. |
| `award_cup.stl` | your choice (gold, for the full effect) | Prints upright on its foot. There's a socket underneath for the peg. |
| `award_plaque.stl` | black, then white | Single-extruder version. Prints flat, text up. Add a filament change at **z = 1.6 mm** (the first layer above the plate). |
| `award_plaque_black.stl` + `award_plaque_white.stl` | black + white | The same plaque split into two bodies for multi-material printers (AMS/MMU). Import both and keep them aligned. |
| `award_plaque_blank.stl` | black + white | The plate and border with no text, so you can add your own in Bambu Studio (see below). |

None of the parts need supports. Glue the plaque into the pocket and the cup onto the peg. The parts have 0.2 mm of clearance; change `FIT` if your printer disagrees.

```
pip install trimesh manifold3d shapely mapbox_earcut matplotlib
python award.py --text "BEST\nHUMAN" --out .
```

Long text is shrunk to fit the plaque. Print the plaque at 0.12 to 0.16 mm layers so the small letters stay crisp.

## Adding your own text in Bambu Studio

1. Import `award_plaque_blank.stl`. It lies flat with the border facing up.
2. Right-click the plaque and choose **Add part → Text**, then click the top face to place the text. Set the text height to about 4 to 5 mm and the depth (emboss) to **0.6 mm** so it's level with the border.
3. To make the border and text white, right-click the plaque, choose **Height range modifier**, set it from **1.6 to 2.2 mm**, and assign it white filament. On a single-extruder printer, add a filament change at layer 1.6 mm instead.
