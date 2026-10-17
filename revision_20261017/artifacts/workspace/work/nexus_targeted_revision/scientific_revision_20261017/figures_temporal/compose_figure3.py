from pathlib import Path
import json

import fitz
import numpy as np
import pandas as pd
from PIL import Image

from build_inputs import PROJECT, digest, read_json, write_json


ORIGINAL = PROJECT / "Nexus返稿_实习生交接包_20260928/02_Nexus原投稿/03_图件/Figure 3 Source File.png"
FONT_PATH = Path("C:/Windows/Fonts/timesbd.ttf")
PIXELS_PER_POINT = 300 / 72


def compose(output):
    width, height = Image.open(ORIGINAL).size
    document = fitz.open()
    page = document.new_page(width=width / PIXELS_PER_POINT, height=height / PIXELS_PER_POINT)
    page.draw_rect(page.rect, color=None, fill=(1, 1, 1))
    font = fitz.Font(fontfile=str(FONT_PATH))
    page.insert_font(fontname="TimesBold", fontfile=str(FONT_PATH))
    panels = []

    def panel(name, clip, target, geometry=None):
        path = output / name
        with fitz.open(path) as source:
            if len(source) != 1:
                raise ValueError(f"A composed panel must have one PDF page: {path}")
            if geometry is not None and not np.allclose([source[0].rect.width, source[0].rect.height], geometry["pdf_size_points"], atol=3, rtol=0):
                raise ValueError(f"PDF geometry differs from renderer coordinates: {path}")
            clipping = source[0].rect if clip is None else fitz.Rect(clip)
            page.show_pdf_page(fitz.Rect(*(value / PIXELS_PER_POINT for value in target)), source, 0, clip=clipping, keep_proportion=False)
            panels.append({"source": str(path), "source_sha256": digest(path), "clip_pdf_points": list(clipping), "target_pixel_bounds": list(target)})

    def text(value, x, y, size, center=False):
        points = size / PIXELS_PER_POINT
        measured = font.text_length(value, fontsize=points)
        anchor = x / PIXELS_PER_POINT - measured / 2 if center else x / PIXELS_PER_POINT
        page.insert_text((anchor, (y + size) / PIXELS_PER_POINT), value, fontname="TimesBold", fontsize=points, color=(0, 0, 0))

    penalty = read_json(output / "pareto_penalty_comparison_latest.geometry.json")
    fingerprint = read_json(output / "pareto_penalty_driver_heatmap_latest.geometry.json")
    panel("pareto_temporal_distribution_latest.pdf", None, (22, 22, 1490, 2053))
    panel("pareto_penalty_comparison_latest.pdf", penalty["decomposition"], (1490, 128, 2948, 1115), penalty)
    panel("pareto_penalty_comparison_latest.pdf", penalty["comparison"], (2950, 128, 4180, 1115), penalty)
    panel("pareto_penalty_comparison_latest.pdf", penalty["legend"], (1790, 14, 2935, 125), penalty)
    panel("pareto_penalty_driver_heatmap_latest.pdf", fingerprint["metrics"], (1500, 1255, 4180, 2057), fingerprint)
    for label, x, y in [("(a)", 215, 48), ("(b)", 1620, 48), ("(c)", 2972, 48), ("(d)", 1620, 1165)]:
        text(label, x, y, 63)
    clip = fingerprint["metrics"]
    for label, center in zip(["Utilization and low load", "Weekly operation", "Renewable availability", "Capacity premiums"], fingerprint["group_centres_x_points"]):
        text(label, 1500 + (center - clip[0]) / (clip[2] - clip[0]) * 2680, 1168, 44, center=True)
    metrics_path = output / "temporal_robustness_metrics_latest.csv"
    metrics = pd.read_csv(metrics_path).set_index("Scenario")
    selected = []
    for scenario in ["GTL-BH", "GTL", "CCU-GH-FT"]:
        row = metrics.loc[scenario]
        mean, worst = row.SAFMean / 100, row.WorstWeekMean / 100
        expected = [(1 / mean - 1) * 100, (1 / worst - 1 / mean) * 100]
        if not np.allclose(row[["ChronicPenaltyPct", "RobustnessPenaltyPct"]].astype(float), expected, atol=1e-6, rtol=1e-8):
            raise ValueError(f"Composed figure premiums differ from actual utilization: {scenario}")
        selected.append({"scenario": scenario, "demand_fulfillment_ratio": row.DemandFulfillmentRatio,
                         "mean_synaf_utilization": mean, "worst_week_retention": row.WorstWeekRetention / 100,
                         "mean_utilization_capacity_premium_pct": expected[0], "additional_worst_week_capacity_premium_pct": expected[1]})
    pdf, png = output / "Figure_3.pdf", output / "Figure_3.png"
    document.save(pdf, garbage=4, deflate=True)
    page.get_pixmap(dpi=300, alpha=False).save(png)
    preview = Image.open(png)
    preview.thumbnail((2110, 1100))
    preview.save(output / "Figure_3_preview.png")
    manifest = {"figure": "Figure 3", "pixels": [width, height], "original_layout": str(ORIGINAL),
                "original_layout_sha256": digest(ORIGINAL), "png_sha256": digest(png), "pdf_sha256": digest(pdf),
                "metric_source_sha256": digest(metrics_path), "panels": panels, "selected_configuration_metrics": selected,
                "vector_panels_preserved": True, "visual_review_complete": False,
                "bubble_encoding": "A monotone rescaling of total capacity premium; bubble area is not directly proportional to premium.",
                "metric_scope": "Capacity-demand proxies for the selected schedules; low-load episodes and ramps are evaluated within representative weeks."}
    write_json(output / "Figure_3_manifest.json", manifest)
    document.close()
    return manifest


if __name__ == "__main__":
    raise RuntimeError("Use render_temporal.py after the complete real baseline input manifest has passed")
