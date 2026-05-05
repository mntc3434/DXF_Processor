import ezdxf
from pathlib import Path

def get_layer_stats(path):
    doc = ezdxf.readfile(str(path))
    msp = doc.modelspace()
    stats = {}
    for e in msp:
        l = e.dxf.layer
        stats[l] = stats.get(l, 0) + 1
    return stats

input_stats = get_layer_stats("input/con-128_stair INPUT.dxf")
test_stats = get_layer_stats("test_result/con-128_stair_test.dxf")
truth_stats = get_layer_stats("output/con-128_stair.dxf")

layers = sorted(set(input_stats.keys()) | set(test_stats.keys()) | set(truth_stats.keys()))

print(f"{'Layer':<25} | {'Input':<6} | {'Test':<6} | {'Truth':<6}")
print("-" * 55)
for l in layers:
    print(f"{l:<25} | {input_stats.get(l, 0):<6} | {test_stats.get(l, 0):<6} | {truth_stats.get(l, 0):<6}")
