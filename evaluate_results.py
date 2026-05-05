import os
import ezdxf
from pathlib import Path
from dfx_pro import process_dxf

# Config
INPUT_DIR = Path("input")
OUTPUT_DIR = Path("output")  # Ground Truth
TEST_RESULT_DIR = Path("test_result")
REPORT_FILE = Path("evaluation_report.txt")

def get_dxf_stats(file_path):
    """Extract statistics from a DXF file for comparison."""
    try:
        doc = ezdxf.readfile(str(file_path))
        msp = doc.modelspace()
        
        stats = {
            "layers": sorted([layer.dxf.name for layer in doc.layers]),
            "entity_count": len(msp),
            "layer_counts": {},
        }
        
        # Count entities per layer
        for entity in msp:
            layer = entity.dxf.layer
            stats["layer_counts"][layer] = stats["layer_counts"].get(layer, 0) + 1
            
        return stats
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return None

def compare_stats(test_stats, truth_stats):
    """Compare two sets of stats and return a similarity report."""
    report = []
    
    # Check Layer Existence
    missing_layers = [l for l in test_stats["layers"] if l not in truth_stats["layers"]]
    if missing_layers:
        report.append(f"  [!] Note: Test file has layers not in Ground Truth: {missing_layers}")
    
    # Check common layers entity counts
    common_layers = set(test_stats["layer_counts"].keys()) & set(truth_stats["layer_counts"].keys())
    for layer in sorted(common_layers):
        t_count = test_stats["layer_counts"][layer]
        g_count = truth_stats["layer_counts"][layer]
        diff = t_count - g_count
        if diff == 0:
            report.append(f"  [OK] Layer '{layer}': Exact match ({t_count} entities)")
        else:
            pct = (abs(diff) / g_count) * 100 if g_count > 0 else 100
            report.append(f"  [DIFF] Layer '{layer}': Test={t_count}, Truth={g_count} (Diff={diff}, {pct:.1f}%)")

    # Overall count
    report.append(f"  Overall Entities: Test={test_stats['entity_count']}, Truth={truth_stats['entity_count']}")
    
    return report

def main():
    if not TEST_RESULT_DIR.exists():
        TEST_RESULT_DIR.mkdir(parents=True, exist_ok=True)
        
    print(f"\n{'='*60}")
    print(f"  DXF Processing Evaluator")
    print(f"{'='*60}\n")
    
    input_files = list(INPUT_DIR.glob("*.dxf"))
    
    results = []
    
    for input_file in input_files:
        # Mapping logic: 'con-128_stair INPUT.dxf' -> 'con-128_stair.dxf'
        # Or 'NN-CON-130-stair-V0 INPUT.dxf' -> 'NN-CON-130-stair-V0.dxf'
        base_name = input_file.stem.replace(" INPUT", "")
        truth_file = OUTPUT_DIR / f"{base_name}.dxf"
        test_file = TEST_RESULT_DIR / f"{base_name}_test.dxf"
        
        print(f"Evaluating: {base_name}")
        
        if not truth_file.exists():
            print(f"  [SKIP] Ground truth file not found: {truth_file.name}")
            continue
            
        # 1. Process
        print(f"  Step 1: Processing {input_file.name} ...")
        if not process_dxf(str(input_file), str(test_file)):
            print(f"  [FAIL] Processing failed.")
            continue
            
        # 2. Compare
        print(f"  Step 2: Comparing with ground truth ...")
        test_stats = get_dxf_stats(test_file)
        truth_stats = get_dxf_stats(truth_file)
        
        if test_stats and truth_stats:
            comparison = compare_stats(test_stats, truth_stats)
            results.append((base_name, comparison))
            for line in comparison:
                print(line)
        else:
            print(f"  [FAIL] Could not read stats for comparison.")
            
        print("-" * 40)

    # Write report
    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        f.write("DXF EVALUATION REPORT\n")
        f.write("=" * 30 + "\n\n")
        for name, comp in results:
            f.write(f"File: {name}\n")
            for line in comp:
                f.write(line + "\n")
            f.write("-" * 30 + "\n\n")

    print(f"\nEvaluation complete. Report saved to {REPORT_FILE}")
    print(f"{'='*60}\n")

if __name__ == "__main__":
    main()
