from __future__ import annotations

import csv
import html
import json
from collections import Counter
from pathlib import Path

from PIL import Image, ImageOps

from .models import ImageAnalysis


def summary(items: list[ImageAnalysis]) -> dict:
    counts = Counter(item.decision for item in items)
    return {
        "total": len(items),
        "average_score": round(sum(i.score for i in items) / len(items), 2) if items else 0,
        "decisions": dict(sorted(counts.items())),
        "duplicates": sum(bool(i.duplicate_of) for i in items),
        "corrupt": sum(i.corrupt for i in items),
        "screenshots": sum(i.likely_screenshot for i in items),
    }


def write_csv(items: list[ImageAnalysis], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "path", "relative_path", "score", "decision", "width", "height", "megapixels",
        "brightness", "sharpness", "entropy", "has_exif", "camera_make", "camera_model",
        "likely_screenshot", "duplicate_of", "sha256", "reasons",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for item in items:
            row = item.to_dict()
            row["reasons"] = " | ".join(item.reasons)
            writer.writerow({field: row.get(field, "") for field in fields})


def write_json(items: list[ImageAnalysis], path: Path, run_info: dict | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "run": run_info or {},
        "summary": summary(items),
        "images": [i.to_dict() for i in items],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _thumbnail_file(
    source: str, destination: Path, max_size: tuple[int, int] = (320, 240)
) -> bool:
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        with Image.open(source) as opened:
            image = ImageOps.exif_transpose(opened).convert("RGB")
            image.thumbnail(max_size, Image.Resampling.LANCZOS)
            image.save(destination, format="JPEG", quality=75, optimize=True)
        return True
    except Exception:
        return False


def write_gallery(items: list[ImageAnalysis], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    thumbnails = path.parent / "miniaturas"
    stats = summary(items)
    cards: list[str] = []
    for index, item in enumerate(items):
        thumb_name = f"{item.sha256[:16] or index}.jpg"
        thumb_path = thumbnails / thumb_name
        thumb = thumb_path.exists() or _thumbnail_file(item.path, thumb_path)
        image_html = (
            f'<img loading="lazy" src="miniaturas/{thumb_name}" alt="miniatura">'
            if thumb else '<div class="missing">Sin vista previa</div>'
        )
        reasons = "".join(f"<li>{html.escape(reason)}</li>" for reason in item.reasons[:6])
        cards.append(f"""
        <article class="card" data-decision="{html.escape(item.decision)}" data-score="{item.score}">
          {image_html}
          <div class="body">
            <div class="top"><span class="badge {item.decision}">{html.escape(item.decision)}</span><strong>{item.score}/100</strong></div>
            <h3 title="{html.escape(item.path)}">{html.escape(item.relative_path)}</h3>
            <p>{item.width}x{item.height} · {item.megapixels:.2f} MP · nitidez {item.sharpness:.1f}</p>
            <ul>{reasons}</ul>
          </div>
        </article>""")
    decisions = ["all", "important", "useful", "review", "trash_candidate", "corrupt"]
    buttons = "".join(f'<button data-filter="{d}">{d}</button>' for d in decisions)
    document = f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>FotoTriage</title><style>
:root{{--bg:#0b1220;--panel:#131d2e;--text:#e6edf7;--muted:#91a0b7;--accent:#4cc9f0}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--text);font-family:system-ui,sans-serif}}
header{{position:sticky;top:0;z-index:2;background:#0b1220ee;padding:20px;backdrop-filter:blur(10px);border-bottom:1px solid #27334a}}
h1{{margin:0 0 6px}}header p{{margin:0;color:var(--muted)}}.controls{{display:flex;gap:8px;flex-wrap:wrap;margin-top:15px}}
button{{background:#1c2940;color:var(--text);border:1px solid #34445f;border-radius:8px;padding:8px 12px;cursor:pointer}}
button.active{{background:var(--accent);color:#061018}}main{{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:16px;padding:20px}}
.card{{overflow:hidden;border:1px solid #27334a;border-radius:14px;background:var(--panel)}}.card img,.missing{{display:block;width:100%;height:220px;object-fit:contain;background:#050a12}}
.missing{{display:grid;place-items:center;color:var(--muted)}}.body{{padding:14px}}.top{{display:flex;justify-content:space-between;align-items:center}}
.badge{{font-size:.75rem;padding:4px 7px;border-radius:20px;background:#34445f}}.important{{background:#087f5b}}.useful{{background:#1864ab}}.review{{background:#9c6500}}.trash_candidate,.corrupt{{background:#a61e4d}}
h3{{font-size:1rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}p,li{{font-size:.84rem;color:var(--muted)}}ul{{padding-left:18px}}
</style></head><body><header><h1>FotoTriage</h1><p>{stats['total']} archivos · score medio {stats['average_score']} · {stats['duplicates']} duplicados</p><div class="controls">{buttons}</div></header>
<main>{''.join(cards)}</main><script>
const cards=[...document.querySelectorAll('.card')];const buttons=[...document.querySelectorAll('button')];
buttons.forEach(b=>b.onclick=()=>{{buttons.forEach(x=>x.classList.remove('active'));b.classList.add('active');const f=b.dataset.filter;cards.forEach(c=>c.hidden=f!=='all'&&c.dataset.decision!==f)}});buttons[0].click();
</script></body></html>"""
    path.write_text(document, encoding="utf-8")


def write_all(items: list[ImageAnalysis], output: Path, run_info: dict | None = None) -> list[Path]:
    output.mkdir(parents=True, exist_ok=True)
    paths = [output / "resultados.csv", output / "resultados.json", output / "galeria.html"]
    write_csv(items, paths[0])
    write_json(items, paths[1], run_info)
    write_gallery(items, paths[2])
    return paths
