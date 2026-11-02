"""Contact sheet of review renders: tools/contact_sheet.py <dir> <out.png> [columns]
Reads <dir>/index.json (written by tools/render_rooms.py) and tiles the renders with a label band.
Usage: .venv/bin/python -I tools/contact_sheet.py reports/room_previews/xl reports/room_previews/xl/contact_sheet_xl.png
"""
from __future__ import annotations

import json
import os
import sys

from PIL import Image, ImageDraw, ImageFont


def main() -> int:
    src, out = sys.argv[1], sys.argv[2]
    cols = int(sys.argv[3]) if len(sys.argv) > 3 else 2
    index = json.load(open(os.path.join(src, "index.json"), encoding="utf-8"))
    tiles = []
    for r in index["renders"]:
        im = Image.open(os.path.join(src, r["file"])).convert("RGB")
        im = im.resize((640, int(640 * im.height / im.width)))
        size = r.get("size", {})
        label = f'd{r["depth"]}  {r["template"]}  {size.get("w")}x{size.get("d")}x{size.get("h")} studs'
        if r.get("decor") is not None:
            label += f'  decor {r["decor"]}'
        if r.get("fallback"):
            label += "  [fallback]"
        band = Image.new("RGB", (im.width, 26), (32, 48, 85))
        ImageDraw.Draw(band).text((8, 6), label, fill=(255, 255, 255), font=ImageFont.load_default())
        tile = Image.new("RGB", (im.width, im.height + 26))
        tile.paste(band, (0, 0))
        tile.paste(im, (0, 26))
        tiles.append(tile)
    rows = (len(tiles) + cols - 1) // cols
    tw, th = tiles[0].size
    sheet = Image.new("RGB", (tw * cols, th * rows), (245, 247, 250))
    for i, t in enumerate(tiles):
        sheet.paste(t, ((i % cols) * tw, (i // cols) * th))
    sheet.save(out)
    print("wrote", out, sheet.size)
    return 0


if __name__ == "__main__":
    sys.exit(main())
