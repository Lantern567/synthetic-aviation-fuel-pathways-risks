import json

import matplotlib.transforms as transforms


def write_geometry(figure, output, kind, pad_inches=.035):
    figure.canvas.draw()
    renderer = figure.canvas.get_renderer()
    full = figure.get_tightbbox(renderer)
    width, height = (full.width + 2 * pad_inches) * 72, (full.height + 2 * pad_inches) * 72

    def pdf_rect(box, margin=1.5):
        box = box.transformed(figure.dpi_scale_trans.inverted())
        return [max(0, (box.x0 - full.x0 + pad_inches) * 72 - margin),
                max(0, (full.y1 - box.y1 + pad_inches) * 72 - margin),
                min(width, (box.x1 - full.x0 + pad_inches) * 72 + margin),
                min(height, (full.y1 - box.y0 + pad_inches) * 72 + margin)]

    def without_title(axis):
        titles = [axis.title, axis._left_title, axis._right_title]
        visible = [title.get_visible() for title in titles]
        for title in titles:
            title.set_visible(False)
        box = axis.get_tightbbox(renderer)
        for title, state in zip(titles, visible):
            title.set_visible(state)
        return box

    result = {"pdf_size_points": [width, height], "pad_inches": pad_inches}
    if kind == "penalty":
        result["decomposition"] = pdf_rect(without_title(figure.axes[0]))
        result["comparison"] = pdf_rect(without_title(figure.axes[1]))
        result["legend"] = pdf_rect(figure.legends[0].get_window_extent(renderer))
    elif kind == "fingerprint":
        result["metrics"] = pdf_rect(transforms.Bbox.union([without_title(figure.axes[0]), without_title(figure.axes[2])]))
        result["group_centres_x_points"] = [(figure.axes[0].transData.transform((centre, 0))[0] / figure.dpi - full.x0 + pad_inches) * 72 for centre in [1, 4, 7, 10]]
    else:
        raise ValueError(f"Unknown figure geometry: {kind}")
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")

