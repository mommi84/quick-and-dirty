# award

A 3D-printable trophy: a stepped base, a plaque on the front with raised text, and a cup with handles.
It is 70 x 47 x 98 mm and prints upright with no supports (every overhang is at 45° or less).

```
pip install trimesh manifold3d shapely mapbox_earcut matplotlib
python award.py --text "BEST\nHUMAN" --out award.stl
```

Long text is shrunk to fit the plaque. For crisp letters, use a 0.4 mm nozzle and a layer height of 0.12 to 0.16 mm.
