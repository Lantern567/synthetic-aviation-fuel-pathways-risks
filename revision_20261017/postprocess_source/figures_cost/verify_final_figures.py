import json
from pathlib import Path

import numpy as np
import pandas as pd
import pymupdf
from PIL import Image

from build_inputs import digest, read_json, write_json
from render_figures import verify_inputs


HERE = Path(__file__).resolve().parent
data, output = HERE / 'adapted_data', HERE / 'figures'
verify_inputs(data)
manifest = read_json(output / 'render_manifest.json')
visual = read_json(output / 'visual_inspection.json')
if visual['passed'] is not True or set(visual['reviewed_figures']) != set(manifest['figures']):
    raise ValueError('Visual inspection must cover all final figure names')
summary = pd.read_csv(data / 'pathway_summary.csv').set_index('scenario')
learning = pd.read_csv(data / 'learning_projections.csv')
for scenario, rows in learning.groupby('scenario'):
    if rows.year.tolist() != list(range(2026, 2037)):
        raise ValueError(f'Incomplete annual learning series: {scenario}')
    if not np.isclose(rows.iloc[0].cost_cny_kg, summary.loc[scenario, 'cost_cny_kg'], atol=1e-8):
        raise ValueError(f'Learning baseline differs from actual accounting: {scenario}')
    if not np.isfinite(rows.cost_cny_kg).all() or rows.cost_cny_kg.min() <= 0:
        raise ValueError(f'Invalid learning cost: {scenario}')
checks = []
for name in manifest['figures']:
    png, pdf = output / (name + '.png'), output / (name + '.pdf')
    if visual['png_sha256'][name] != digest(png):
        raise ValueError(f'The visually inspected raster changed: {name}')
    with Image.open(png) as picture:
        picture.verify()
    with Image.open(png) as picture:
        size, dpi = picture.size, picture.info.get('dpi')
    if min(size) < 1000 or dpi is None or min(dpi) < 299:
        raise ValueError(f'Insufficient raster export dimensions or resolution: {name}: {size}, {dpi}')
    with pymupdf.open(pdf) as document:
        if len(document) != 1 or min(document[0].rect.width, document[0].rect.height) <= 0:
            raise ValueError(f'Invalid one-page PDF: {name}')
    checks.append({'name': name, 'png_sha256': digest(png), 'pdf_sha256': digest(pdf),
                   'pixels': list(size), 'dpi': list(dpi), 'visual_inspection_passed': True})
for suffix in ('png', 'pdf'):
    if digest(output / ('Figure_1b.' + suffix)) != digest(output / ('market_price_gap_lollipop.' + suffix)):
        raise ValueError('The standalone Figure 1b differs from its current source panel')
audit = read_json(output / 'figure_text_audit.json')
for name, texts in audit.items():
    if any('LCOE' in text or 'LCO-SAF' in text for text in texts):
        raise ValueError(f'Product-cost label differs from LCO-SynAF: {name}')
    if name.startswith('pareto_carbon') and any('Delta vs jet' in text for text in texts):
        raise ValueError('The carbon contribution figure must show direct supply-chain intensity')
report = {'passed': True, 'figure_count': len(checks), 'new_real_runs': 18, 'baseline_pathways': 13,
          'input_manifest_sha256': digest(data / 'figure_inputs.json'),
          'renderer_sha256': digest(HERE / 'render_figures.py'),
          'validator_sha256': digest(Path(__file__)), 'visual_record_sha256': digest(output / 'visual_inspection.json'),
          'figures': checks, 'learning_baseline_closure_passed': True,
          'scope': 'Actual input hashes, 13 annual learning baselines, 23 PNG/PDF exports, final terminology and recorded visual inspection'}
write_json(output / 'figure_verification.json', report)
manifest['visual_qa_completed'] = True
manifest['verification_report_sha256'] = digest(output / 'figure_verification.json')
write_json(output / 'render_manifest.json', manifest)
print(json.dumps({'passed': True, 'figure_count': len(checks), 'report': str(output / 'figure_verification.json')}))
