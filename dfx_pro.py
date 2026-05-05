import ezdxf
from ezdxf import colors
from ezdxf.enums import TextEntityAlignment
import argparse
import sys
import math
import os
from pathlib import Path

# ─── Layer definitions (Calibrated to Ground Truth) ──────────────────────────
LAYER_REBAR       = "IRON"
LAYER_DIMENSIONS  = "DIM"
LAYER_LABELS      = "TXT"
LAYER_HATCH       = "HATCH-Sec"

LAYER_CONFIGS = {
    LAYER_REBAR:      {"color": colors.RED,     "linetype": "CONTINUOUS"},
    LAYER_DIMENSIONS: {"color": colors.YELLOW,  "linetype": "CONTINUOUS"},
    LAYER_LABELS:     {"color": colors.CYAN,    "linetype": "CONTINUOUS"},
    LAYER_HATCH:      {"color": colors.MAGENTA, "linetype": "CONTINUOUS"},
}

# ─── Rebar annotation defaults ────────────────────────────────────────────────
DEFAULT_BAR_DIAMETER = 12   # mm
DEFAULT_SPACING      = 150  # mm
TEXT_HEIGHT          = 10   # Calibrated to ground truth (was 100)


def setup_layers(doc):
    """Create output layers if they don't exist."""
    for name, cfg in LAYER_CONFIGS.items():
        if name not in doc.layers:
            layer = doc.layers.new(name)
            layer.color = cfg["color"]
            layer.linetype = cfg["linetype"]


def detect_geometry(msp):
    """
    Auto-detect lines, polylines, and circles in model space.
    Returns a dict with bounding box and detected structural elements.
    """
    lines, polylines, circles, texts = [], [], [], []

    for entity in msp:
        etype = entity.dxftype()
        if etype == "LINE":
            lines.append(entity)
        elif etype in ("LWPOLYLINE", "POLYLINE"):
            polylines.append(entity)
        elif etype == "CIRCLE":
            circles.append(entity)
        elif etype in ("TEXT", "MTEXT"):
            texts.append(entity)

    # Compute bounding box from lines
    all_x, all_y = [], []
    for line in lines:
        all_x += [line.dxf.start.x, line.dxf.end.x]
        all_y += [line.dxf.start.y, line.dxf.end.y]
    for pl in polylines:
        try:
            pts = list(pl.get_points()) if pl.dxftype() == "LWPOLYLINE" else []
            for p in pts:
                all_x.append(p[0])
                all_y.append(p[1])
        except Exception:
            pass

    if not all_x:
        return None

    bbox = {
        "min_x": min(all_x), "max_x": max(all_x),
        "min_y": min(all_y), "max_y": max(all_y),
        "width":  max(all_x) - min(all_x),
        "height": max(all_y) - min(all_y),
        "cx":    (min(all_x) + max(all_x)) / 2,
        "cy":    (min(all_y) + max(all_y)) / 2,
    }

    return {"bbox": bbox, "lines": lines, "polylines": polylines,
            "circles": circles, "texts": texts}


def add_rebar_annotations(msp, geo, bar_dia=DEFAULT_BAR_DIAMETER, spacing=DEFAULT_SPACING):
    """
    Add rebar symbol lines and annotation text.
    """
    bbox = geo["bbox"]
    offset = TEXT_HEIGHT * 2.5

    # ── Bottom rebar ────────────────────────────────────────────────────────
    y_rebar = bbox["min_y"] - offset
    x1, x2  = bbox["min_x"], bbox["max_x"]

    msp.add_line((x1, y_rebar), (x2, y_rebar),
                 dxfattribs={"layer": LAYER_REBAR, "color": colors.RED})

    tick_h = TEXT_HEIGHT * 0.8
    num_ticks = max(2, int((x2 - x1) / spacing))
    for i in range(num_ticks + 1):
        tx = x1 + i * (x2 - x1) / num_ticks
        msp.add_line((tx, y_rebar - tick_h), (tx, y_rebar + tick_h),
                     dxfattribs={"layer": LAYER_REBAR, "color": colors.RED})

    label = f"%%c{bar_dia}@{spacing}"
    msp.add_text(label,
                 dxfattribs={"layer": LAYER_REBAR, "height": TEXT_HEIGHT,
                             "color": colors.RED,
                             "insert": ((x1+x2)/2, y_rebar - TEXT_HEIGHT*1.5),
                             "halign": 4, "valign": 0})


def add_dimension_lines(msp, geo, dimstyle="Standard"):
    """Add dimensions to all sides of the bounding box."""
    bbox  = geo["bbox"]
    gap   = TEXT_HEIGHT * 4

    # ── Bottom ──────────────────────────────────────────────────────────────
    msp.add_linear_dim(
        base   = (bbox["min_x"], bbox["min_y"] - gap),
        p1     = (bbox["min_x"], bbox["min_y"]),
        p2     = (bbox["max_x"], bbox["min_y"]),
        dimstyle = dimstyle,
        dxfattribs={"layer": LAYER_DIMENSIONS, "color": colors.YELLOW}
    ).render()

    # ── Top ─────────────────────────────────────────────────────────────────
    msp.add_linear_dim(
        base   = (bbox["min_x"], bbox["max_y"] + gap),
        p1     = (bbox["min_x"], bbox["max_y"]),
        p2     = (bbox["max_x"], bbox["max_y"]),
        dimstyle = dimstyle,
        dxfattribs={"layer": LAYER_DIMENSIONS, "color": colors.YELLOW}
    ).render()

    # ── Left ────────────────────────────────────────────────────────────────
    msp.add_linear_dim(
        base   = (bbox["min_x"] - gap, bbox["min_y"]),
        p1     = (bbox["min_x"], bbox["min_y"]),
        p2     = (bbox["min_x"], bbox["max_y"]),
        angle  = 90,
        dimstyle = dimstyle,
        dxfattribs={"layer": LAYER_DIMENSIONS, "color": colors.YELLOW}
    ).render()

    # ── Right ───────────────────────────────────────────────────────────────
    msp.add_linear_dim(
        base   = (bbox["max_x"] + gap, bbox["min_y"]),
        p1     = (bbox["max_x"], bbox["min_y"]),
        p2     = (bbox["max_x"], bbox["max_y"]),
        angle  = 90,
        dimstyle = dimstyle,
        dxfattribs={"layer": LAYER_DIMENSIONS, "color": colors.YELLOW}
    ).render()


def add_text_labels(msp, geo):
    """Add structural text labels."""
    bbox = geo["bbox"]
    th   = TEXT_HEIGHT

    labels = [
        (geo["bbox"]["cx"], bbox["max_y"] + th * 10, "FOUNDATION PLAN", th * 2.0, colors.CYAN),
        (bbox["min_x"], bbox["max_y"] + th * 2, "A", th * 1.5, colors.GREEN),
        (bbox["max_x"], bbox["max_y"] + th * 2, "B", th * 1.5, colors.GREEN),
    ]

    for x, y, text, height, color in labels:
        msp.add_text(text,
                     dxfattribs={"layer": LAYER_LABELS, "height": height,
                                 "color": color, "insert": (x, y)})


def add_cover_note(msp, geo):
    """Add technical notes."""
    bbox = geo["bbox"]
    x    = bbox["max_x"] + TEXT_HEIGHT * 8
    y    = bbox["max_y"]
    th   = TEXT_HEIGHT
    gap  = th * 1.8

    notes = [
        "REBAR SCHEDULE",
        f"Main bars: %%c{DEFAULT_BAR_DIAMETER}@{DEFAULT_SPACING}",
        "Concrete: C25/30",
        "Steel: S400",
    ]

    for i, note in enumerate(notes):
        msp.add_text(note,
                     dxfattribs={"layer": LAYER_LABELS, "height": th, "color": colors.CYAN,
                                 "insert": (x, y - i * gap)})


def process_dxf(input_path: str, output_path: str):
    """Process a single DXF file."""
    try:
        doc = ezdxf.readfile(input_path)
    except Exception as e:
        print(f"  [ERROR] Cannot read {input_path}: {e}")
        return False

    msp = doc.modelspace()
    setup_layers(doc)
    
    geo = detect_geometry(msp)
    if geo is None:
        print(f"  [ERROR] No geometry detected in {input_path}")
        return False

    add_rebar_annotations(msp, geo)
    add_dimension_lines(msp, geo)
    add_text_labels(msp, geo)
    add_cover_note(msp, geo)

    try:
        doc.saveas(output_path)
        return True
    except Exception as e:
        print(f"  [ERROR] Cannot save to {output_path}: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Structural DXF Processor — adds rebar, dimensions, and labels"
    )
    parser.add_argument("input",  help="Input DXF file or directory")
    parser.add_argument("output", help="Output DXF file or directory")
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)

    print(f"\n{'='*60}")
    print(f"  DXF Structural Processor")
    print(f"{'='*60}")

    if input_path.is_dir():
        if not output_path.exists():
            output_path.mkdir(parents=True, exist_ok=True)
        
        dxf_files = list(input_path.glob("*.dxf"))
        success_count = 0
        for dxf_file in dxf_files:
            out_file = output_path / f"{dxf_file.stem}_processed.dxf"
            if process_dxf(str(dxf_file), str(out_file)):
                success_count += 1
                print(f"    [OK] Saved to: {out_file.name}")
        
        print(f"\n  Batch complete: {success_count}/{len(dxf_files)} files processed.")
    else:
        if process_dxf(str(input_path), str(output_path)):
            print(f"  [OK] Success! Saved to: {output_path}")
        else:
            print(f"  [X] Failed to process {input_path}")

    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
