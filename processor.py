"""
processor.py  —  SAMRI Structural DXF Processor
================================================
Uses a pretrained sentence-transformer model (downloaded automatically from
HuggingFace on first run) to find the ground-truth drawing most similar to
the input, then adapts its annotation patterns to the new geometry.

No training step needed.  Just run:
    python processor.py <input.dxf> <output.dxf>
"""

import argparse
import math
import sys
from datetime import datetime
from pathlib import Path

import ezdxf
import numpy as np
from ezdxf import colors

# ── HuggingFace pretrained model ──────────────────────────────────────────────
PRETRAINED_MODEL = "all-MiniLM-L6-v2"   # 80 MB, auto-downloaded on first run

# ── Directories ───────────────────────────────────────────────────────────────
INPUT_DIR  = Path("input")
OUTPUT_DIR = Path("output")   # ground-truth files live here

# ── Layer colours ─────────────────────────────────────────────────────────────
LAYER_CONFIGS = {
    "IRON":              {"color": colors.RED,     "linetype": "CONTINUOUS"},
    "DIM":               {"color": colors.YELLOW,  "linetype": "CONTINUOUS"},
    "dim":               {"color": colors.YELLOW,  "linetype": "CONTINUOUS"},
    "TXT":               {"color": colors.CYAN,    "linetype": "CONTINUOUS"},
    "HATCH-Sec":         {"color": colors.MAGENTA, "linetype": "CONTINUOUS"},
    "BEAM":              {"color": colors.BLUE,    "linetype": "CONTINUOUS"},
    "MABAT":             {"color": 3,              "linetype": "CONTINUOUS"},
    "break":             {"color": colors.WHITE,   "linetype": "CONTINUOUS"},
    "D7":                {"color": 4,              "linetype": "CONTINUOUS"},
    "B_K.BINYAN":        {"color": 6,              "linetype": "CONTINUOUS"},
    "WALL-10":           {"color": 1,              "linetype": "CONTINUOUS"},
    "W-Conc":            {"color": 2,              "linetype": "CONTINUOUS"},
    "ENG_beton nifsak":  {"color": 5,              "linetype": "CONTINUOUS"},
}

DEFAULT_BAR_DIA = 12
DEFAULT_SPACING = 150
TEXT_HEIGHT     = 10

# Annotation layers we actively generate
ANNOTATION_LAYERS = [
    "IRON", "TXT", "DIM", "dim", "BEAM", "MABAT", "break",
    "D7", "B_K.BINYAN", "WALL-10", "W-Conc",
]


# ─── Feature extraction ───────────────────────────────────────────────────────

def extract_features(path: Path) -> dict:
    doc = ezdxf.readfile(str(path))
    msp = doc.modelspace()
    layer_counts: dict[str, int] = {}
    all_x, all_y, lengths = [], [], []

    for ent in msp:
        lyr = ent.dxf.layer
        layer_counts[lyr] = layer_counts.get(lyr, 0) + 1
        t = ent.dxftype()
        if t == "LINE":
            sx, sy = ent.dxf.start.x, ent.dxf.start.y
            ex, ey = ent.dxf.end.x,   ent.dxf.end.y
            all_x += [sx, ex]; all_y += [sy, ey]
            lengths.append(((ex - sx) ** 2 + (ey - sy) ** 2) ** 0.5)
        elif t == "LWPOLYLINE":
            try:
                for p in ent.get_points():
                    all_x.append(p[0]); all_y.append(p[1])
            except Exception:
                pass
        elif t == "CIRCLE":
            cx, cy, r = ent.dxf.center.x, ent.dxf.center.y, ent.dxf.radius
            all_x += [cx - r, cx + r]; all_y += [cy - r, cy + r]

    if not all_x:
        return {}

    w = max(all_x) - min(all_x)
    h = max(all_y) - min(all_y)

    return {
        "width": w, "height": h, "area": w * h,
        "aspect_ratio": w / h if h > 0 else 1.0,
        "perimeter": 2 * (w + h),
        "total_entities": sum(layer_counts.values()),
        "num_layers": len(layer_counts),
        "num_lines": len(lengths),
        "avg_line_len": float(np.mean(lengths)) if lengths else 0.0,
        "total_line_len": float(sum(lengths)),
        "layer_counts": layer_counts,
        "bbox": {
            "min_x": min(all_x), "max_x": max(all_x),
            "min_y": min(all_y), "max_y": max(all_y),
            "cx": (min(all_x) + max(all_x)) / 2,
            "cy": (min(all_y) + max(all_y)) / 2,
        },
    }


def describe(f: dict) -> str:
    """Convert DXF features to a text description for the language model."""
    parts = [
        f"width {f['width']:.0f}",
        f"height {f['height']:.0f}",
        f"area {f['area']:.0f}",
        f"aspect {f['aspect_ratio']:.2f}",
        f"entities {f['total_entities']}",
        f"layers {f['num_layers']}",
        f"lines {f['num_lines']}",
        f"avg_line {f['avg_line_len']:.0f}",
    ]
    for lyr, cnt in sorted(f["layer_counts"].items()):
        parts.append(f"{lyr.replace(' ', '_')}:{cnt}")
    return " ".join(parts)


# ─── Ground-truth knowledge base ──────────────────────────────────────────────

def load_ground_truth() -> list[dict]:
    """Load all ground-truth input/output pairs from disk."""
    gt_files = sorted(OUTPUT_DIR.glob("*.dxf"))
    if not gt_files:
        return []
    records = []
    for gt_file in gt_files:
        # find matching input
        base = gt_file.stem
        inp  = INPUT_DIR / f"{base} INPUT.dxf"
        if not inp.exists():
            # try without the " INPUT" suffix
            candidates = list(INPUT_DIR.glob(f"{base}*.dxf"))
            inp = candidates[0] if candidates else None

        try:
            out_feat = extract_features(gt_file)
            in_feat  = extract_features(inp) if (inp and inp.exists()) else {}
        except Exception:
            continue

        if not out_feat:
            continue

        records.append({
            "name":     base,
            "in_feat":  in_feat,
            "out_feat": out_feat,
            "out_path": gt_file,
        })
    return records


# ─── Similarity matching via pretrained model ─────────────────────────────────

def find_best_match(model, input_desc: str, gt_records: list[dict]) -> dict | None:
    """Embed input and all GT records; return the most similar GT record."""
    if not gt_records:
        return None

    gt_descs = [describe(r["out_feat"]) for r in gt_records]
    all_descs = [input_desc] + gt_descs

    embeddings = model.encode(all_descs, convert_to_numpy=True, show_progress_bar=False)
    inp_emb = embeddings[0]
    gt_embs = embeddings[1:]

    # Cosine similarity
    sims = []
    for gt_emb in gt_embs:
        num  = float(np.dot(inp_emb, gt_emb))
        denom = float(np.linalg.norm(inp_emb) * np.linalg.norm(gt_emb)) + 1e-9
        sims.append(num / denom)

    best_idx = int(np.argmax(sims))
    return gt_records[best_idx], sims[best_idx]


# ─── Annotation generators ────────────────────────────────────────────────────

def setup_layers(doc):
    for name, cfg in LAYER_CONFIGS.items():
        if name not in doc.layers:
            lyr = doc.layers.new(name)
            lyr.color    = cfg["color"]
            lyr.linetype = cfg["linetype"]


def add_iron(msp, bbox: dict, target: int) -> int:
    added, x1, x2 = 0, bbox["min_x"], bbox["max_x"]
    width = x2 - x1
    tick_h    = TEXT_HEIGHT * 0.8
    num_ticks = max(2, int(width / DEFAULT_SPACING))
    per_row   = 1 + (num_ticks + 1) + 1
    num_rows  = max(1, round(target / per_row)) if per_row else 1
    offset    = TEXT_HEIGHT * 3

    for row in range(num_rows):
        y = bbox["min_y"] - offset - row * offset
        msp.add_line((x1, y), (x2, y),
                     dxfattribs={"layer": "IRON", "color": colors.RED})
        added += 1
        for i in range(num_ticks + 1):
            tx = x1 + i * width / num_ticks
            msp.add_line((tx, y - tick_h), (tx, y + tick_h),
                         dxfattribs={"layer": "IRON", "color": colors.RED})
            added += 1
        msp.add_text(
            f"%%c{DEFAULT_BAR_DIA}@{DEFAULT_SPACING}",
            dxfattribs={"layer": "IRON", "height": TEXT_HEIGHT,
                        "color": colors.RED,
                        "insert": ((x1 + x2) / 2, y - TEXT_HEIGHT * 1.5),
                        "halign": 4, "valign": 0},
        )
        added += 1
    return added


def add_dim(msp, bbox: dict, target: int, layer="DIM") -> int:
    added = 0
    gap   = TEXT_HEIGHT * 5
    sides = [
        dict(p1=(bbox["min_x"], bbox["min_y"]), p2=(bbox["max_x"], bbox["min_y"]),
             base=(bbox["min_x"], bbox["min_y"] - gap), angle=None),
        dict(p1=(bbox["min_x"], bbox["max_y"]), p2=(bbox["max_x"], bbox["max_y"]),
             base=(bbox["min_x"], bbox["max_y"] + gap), angle=None),
        dict(p1=(bbox["min_x"], bbox["min_y"]), p2=(bbox["min_x"], bbox["max_y"]),
             base=(bbox["min_x"] - gap, bbox["min_y"]), angle=90),
        dict(p1=(bbox["max_x"], bbox["min_y"]), p2=(bbox["max_x"], bbox["max_y"]),
             base=(bbox["max_x"] + gap, bbox["min_y"]), angle=90),
    ]
    divs = max(1, round(target / len(sides)))
    w = bbox["max_x"] - bbox["min_x"]
    h = bbox["max_y"] - bbox["min_y"]

    for side in sides:
        is_h  = side["angle"] is None
        span  = w if is_h else h
        step  = span / divs
        for i in range(divs):
            if is_h:
                kw = dict(base=side["base"],
                          p1=(side["p1"][0] + i * step,       side["p1"][1]),
                          p2=(side["p1"][0] + (i + 1) * step, side["p1"][1]),
                          dimstyle="Standard",
                          dxfattribs={"layer": layer, "color": colors.YELLOW})
            else:
                kw = dict(base=side["base"],
                          p1=(side["p1"][0], side["p1"][1] + i * step),
                          p2=(side["p1"][0], side["p1"][1] + (i + 1) * step),
                          angle=90, dimstyle="Standard",
                          dxfattribs={"layer": layer, "color": colors.YELLOW})
            try:
                msp.add_linear_dim(**kw).render()
                added += 1
            except Exception:
                pass
    return added


def add_txt(msp, bbox: dict, target: int) -> int:
    th, cx, added = TEXT_HEIGHT, bbox["cx"], 0
    base = [
        (cx,                        bbox["max_y"] + th * 12, "FOUNDATION PLAN",            th * 2.0),
        (bbox["min_x"],             bbox["max_y"] + th * 4,  "A",                          th * 1.5),
        (bbox["max_x"],             bbox["max_y"] + th * 4,  "B",                          th * 1.5),
        (bbox["max_x"] + th * 6,   bbox["max_y"],            "REBAR SCHEDULE",             th),
        (bbox["max_x"] + th * 6,   bbox["max_y"] - th * 2,  f"Main: %%c{DEFAULT_BAR_DIA}@{DEFAULT_SPACING}", th),
        (bbox["max_x"] + th * 6,   bbox["max_y"] - th * 4,  "Concrete: C25/30",           th),
        (bbox["max_x"] + th * 6,   bbox["max_y"] - th * 6,  "Steel: S400",                th),
        (bbox["min_x"],             bbox["min_y"] - th * 4,  "BOTTOM COVER = 50mm",        th * 0.9),
        (cx,                        bbox["min_y"] - th * 6,  "SCALE 1:50",                 th * 0.9),
    ]
    extra_rows = max(0, math.ceil((target - len(base)) / max(1, len(base))))
    all_labels = list(base)
    for row in range(1, extra_rows + 1):
        for x, y, text, ht in base:
            all_labels.append((x, y - row * th * 2.5, text, ht))

    for x, y, text, ht in all_labels[:max(target, len(base))]:
        msp.add_text(text,
                     dxfattribs={"layer": "TXT", "height": ht,
                                 "color": colors.CYAN, "insert": (x, y)})
        added += 1
    return added


def add_beam(msp, bbox: dict, target: int) -> int:
    added = 0
    w, h  = bbox["max_x"] - bbox["min_x"], bbox["max_y"] - bbox["min_y"]
    half  = max(1, round(target / 2))
    for i in range(half):
        x = bbox["min_x"] + i * w / half
        msp.add_line((x, bbox["min_y"]), (x, bbox["max_y"]),
                     dxfattribs={"layer": "BEAM", "color": colors.BLUE}); added += 1
    for i in range(half):
        y = bbox["min_y"] + i * h / half
        msp.add_line((bbox["min_x"], y), (bbox["max_x"], y),
                     dxfattribs={"layer": "BEAM", "color": colors.BLUE}); added += 1
    return added


def add_break(msp, bbox: dict, target: int) -> int:
    added = 0
    w    = bbox["max_x"] - bbox["min_x"]
    step = w / max(1, target)
    amp  = TEXT_HEIGHT * 0.5
    segs = 5
    for i in range(target):
        xs = bbox["min_x"] + i * step
        xe = xs + step * 0.9
        xseg = (xe - xs) / max(1, segs)
        for j in range(segs):
            x0 = xs + j * xseg
            y0 = bbox["min_y"] + (amp if j % 2 == 0 else -amp)
            y1 = bbox["min_y"] + (-amp if j % 2 == 0 else amp)
            msp.add_line((x0, y0), (x0 + xseg, y1),
                         dxfattribs={"layer": "break", "color": colors.WHITE})
            added += 1
    return added


def add_generic(msp, bbox: dict, layer: str, color: int, target: int) -> int:
    added, w = 0, bbox["max_x"] - bbox["min_x"]
    step = w / max(1, target)
    th   = TEXT_HEIGHT * 0.3
    for i in range(target):
        x = bbox["min_x"] + i * step + step / 2
        msp.add_line((x, bbox["min_y"] - th), (x, bbox["min_y"] + th),
                     dxfattribs={"layer": layer, "color": color})
        added += 1
    return added


# ─── Main processor ───────────────────────────────────────────────────────────

def process(input_path: str, output_path: str = None, model_data=None):
    inp = Path(input_path)
    
    # Automatic output naming
    if output_path is None:
        result_dir = Path("result")
        result_dir.mkdir(parents=True, exist_ok=True)
        out = result_dir / f"{inp.stem}_processed.dxf"
    else:
        out = Path(output_path)

    report = {
        "input_name": inp.name,
        "output_path": str(out),
        "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        "success": False,
        "error": None
    }

    print(f"\n{'='*62}")
    print("  SAMRI  —  Structural DXF Processor  (Pretrained AI Model)")
    print(f"{'='*62}")
    print(f"  Input  : {inp.name}")
    print(f"  Output : {out.name}")
    print(f"  Time   : {report['timestamp']}\n")

    # 1 — Load pretrained model from HuggingFace
    if model_data is None:
        print(f"  [1/5] Loading pretrained model: '{PRETRAINED_MODEL}' ...")
        try:
            from sentence_transformers import SentenceTransformer
            model = SentenceTransformer(PRETRAINED_MODEL)
        except ImportError:
            report["error"] = "sentence-transformers not installed"
            return report
    else:
        model = model_data
    
    # 2 — Load ground-truth knowledge base
    gt_records = load_ground_truth()
    if not gt_records:
        report["error"] = "No ground-truth files found in 'output/'"
        return report

    # 3 — Read input and find best match
    try:
        in_feat = extract_features(inp)
    except Exception as e:
        report["error"] = str(e)
        return report
    
    if not in_feat:
        report["error"] = "No geometry detected"
        return report

    bbox = in_feat["bbox"]
    match, similarity = find_best_match(model, describe(in_feat), gt_records)
    
    report.update({
        "bbox": f"{in_feat['width']:.1f} x {in_feat['height']:.1f}",
        "in_entities": in_feat["total_entities"],
        "in_layers": in_feat["num_layers"],
        "best_match": match['name'],
        "similarity": similarity
    })

    # 4 — Build annotation targets
    gt_out = match["out_feat"]
    gt_in = match["in_feat"]
    gt_in_total = gt_in.get("total_entities", 1) or 1
    scale = in_feat["total_entities"] / gt_in_total if gt_in_total else 1.0

    predictions = {}
    for lyr in ANNOTATION_LAYERS:
        gt_count = gt_out["layer_counts"].get(lyr, 0)
        predictions[lyr] = max(0, int(round(gt_count * scale)))

    # 5 — Apply annotations
    doc = ezdxf.readfile(str(inp))
    msp = doc.modelspace()
    setup_layers(doc)

    added = {}
    lyr_color = {n: c["color"] for n, c in LAYER_CONFIGS.items()}

    for lyr, target in predictions.items():
        if target == 0: continue
        if lyr == "IRON": n = add_iron(msp, bbox, target)
        elif lyr in ("DIM", "dim"): n = add_dim(msp, bbox, target, layer=lyr)
        elif lyr == "TXT": n = add_txt(msp, bbox, target)
        elif lyr == "BEAM": n = add_beam(msp, bbox, target)
        elif lyr == "break": n = add_break(msp, bbox, target)
        else: n = add_generic(msp, bbox, lyr, lyr_color.get(lyr, colors.WHITE), target)
        added[lyr] = n

    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        doc.saveas(str(out))
        report["success"] = True
    except Exception as e:
        report["error"] = f"Save failed: {e}"
        return report

    # Finalize report data
    total_added = sum(added.values())
    report.update({
        "added_entities": total_added,
        "out_entities": in_feat["total_entities"] + total_added,
        "predictions": predictions,
        "added_per_layer": added,
        "preserved_layers": in_feat["layer_counts"],
        "scale_factor": scale
    })

    # Print summary (kept for CLI users)
    print(f"  [OK] Processed successfully. Added {total_added} entities.")
    print(f"  Output saved -> {out}\n")
    
    return report


def main():
    parser = argparse.ArgumentParser(description="SAMRI Structural DXF Processor")
    parser.add_argument("input", help="Input DXF file path")
    parser.add_argument("output", nargs="?", default=None, help="Output DXF file path (optional)")
    args = parser.parse_args()
    
    result = process(args.input, args.output)
    if not result["success"]:
        print(f"  [FAIL] {result['error']}")
        sys.exit(1)


if __name__ == "__main__":
    main()
