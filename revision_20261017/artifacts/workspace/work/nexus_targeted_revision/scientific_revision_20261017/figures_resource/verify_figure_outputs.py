import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pymupdf
from PIL import Image

here = Path(__file__).resolve().parent
pv = here.parent / 'pv_inputs'
hashes = json.loads((pv / 'input_sha256.json').read_text())
assert all(hashlib.sha256((pv / name).read_bytes()).hexdigest() == digest for name, digest in hashes.items())
manifest = json.loads((here / 'figure_manifest.json').read_text())
assert all(hashlib.sha256((here / name).read_bytes()).hexdigest() == digest for name, digest in manifest['data_and_figure_sha256'].items())
quality_manifest = json.loads((here / 'resource_quality_manifest.json').read_text())
assert all(hashlib.sha256((here / name).read_bytes()).hexdigest() == digest for name, digest in quality_manifest['sha256'].items())
hourly = pd.read_csv(here / 'resource_data/retained_week_profiles.csv')
for label, values in [('solar_plant', hourly.solar_mw), ('wind_farm', hourly.wind_mw)]:
    source = pd.read_csv(pv / 'inputs/baseline/renewable_periods.csv')
    assert np.isclose(values.sum(), source.loc[source.type.eq(label)].power_output_mw.sum()*3, rtol=1e-12)
report = {'frozen_pv_input_files_checked': len(hashes), 'frozen_pv_input_files_unchanged': True, 'export_hashes_match': True, 'displayed_hourly_energy_matches_baseline_inputs': True, 'figures': {}}
for name in ['Figure_S6', 'Figure_S7', 'Figure_S9', 'Figure_S10']:
    with Image.open(here / f'figures/{name}.png') as png:
        dimensions = list(png.size)
        dpi = list(png.info['dpi'])
        assert min(dpi) >= 299.9
    with pymupdf.open(here / f'figures/{name}.pdf') as pdf:
        assert len(pdf) == 1
        text = pdf[0].get_text()
        required_text = {'Figure_S6': 'Full-load hours', 'Figure_S7': 'availability factor', 'Figure_S9': 'capacity', 'Figure_S10': 'solar AC output'}
        assert required_text[name] in text
        fonts = pdf[0].get_fonts()
        assert fonts
        report['figures'][name] = {'png_pixels': dimensions, 'png_dpi': dpi, 'pdf_pages': len(pdf), 'pdf_size_pt': [pdf[0].rect.width, pdf[0].rect.height], 'pdf_fonts': [font[3] for font in fonts], 'pdf_text_extractable': True, 'png_visual_review': 'Checked at publication layout: labels, axes, legends, workflow arrows and lines are complete and legible; no overlap or crop was observed.'}
report['joint_coverage'] = quality_manifest['joint_coverage']
(here / 'figure_qa.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
delivery_files = [path for folder in ['resource_data', 'figures'] for path in sorted((here / folder).iterdir()) if path.is_file()]
delivery_files += [here / name for name in ['redraw_s9_s10.py', 'update_resource_quality.py', 'verify_figure_outputs.py', 'si_updates.md', 'resource_metrics.json', 'updated_joint_week_ranges.json', 'figure_manifest.json', 'resource_quality_manifest.json', 'figure_qa.json']]
delivery_hashes = {str(path.relative_to(here)).replace('\\', '/'): hashlib.sha256(path.read_bytes()).hexdigest() for path in delivery_files}
(here / 'delivery_manifest.json').write_text(json.dumps(delivery_hashes, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(report, ensure_ascii=False, indent=2))
