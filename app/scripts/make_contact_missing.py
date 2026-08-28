from PIL import Image, ImageDraw
import json
from pathlib import Path
root=Path(__file__).resolve().parents[1]
out=root/"runtime_captures"/"contact_missing.jpg"
rows=json.loads((root/"runtime_captures"/"revisao_live_2026-07"/"revisao_temporaria.json").read_text(encoding="utf-8"))
sel=[]
for i,r in enumerate(rows):
    if (not r.get("piece") or not r.get("section")) and r.get("source_path"):
        sel.append((i+1,r))
sel=sel[60:80]
thumbs=[]
for idx,r in sel:
    try:
        im=Image.open(r["source_path"]).convert("RGB")
        pix=im.load(); xs=[];ys=[]
        for y in range(0,im.height,max(1,im.height//400)):
            for x in range(0,im.width,max(1,im.width//400)):
                rr,gg,bb=pix[x,y]
                if rr>170 and 45<gg<190 and bb<125 and rr-gg>45: xs.append(x);ys.append(y)
        if xs:
            pad=20; box=(max(0,min(xs)-pad),max(0,min(ys)-pad),min(im.width,max(xs)+pad),min(im.height,max(ys)+pad)); im=im.crop(box)
        im.thumbnail((360,260))
        canvas=Image.new("RGB",(380,300),"white"); canvas.paste(im,((380-im.width)//2,25)); ImageDraw.Draw(canvas).text((8,5),f"Entrada {idx}",fill="black"); thumbs.append(canvas)
    except Exception: pass
sheet=Image.new("RGB",(380*4,300*5),(220,220,220))
for k,im in enumerate(thumbs): sheet.paste(im,((k%4)*380,(k//4)*300))
sheet.save(out,quality=92)
print(out)
