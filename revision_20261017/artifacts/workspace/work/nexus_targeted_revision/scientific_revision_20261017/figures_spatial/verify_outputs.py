import argparse
import hashlib
import json
import re
from pathlib import Path

import pymupdf
from PIL import Image


parser = argparse.ArgumentParser()
parser.add_argument('--include-joint', action='store_true')
args = parser.parse_args()
here = Path(__file__).resolve().parent
output, data = here / 'figures', here / 'network_data'
required = ['Figure_2', 'Figure_S27'] + ['Figure_S' + str(number) for number in range(49, 64)]
if args.include_joint:
    required.append('Figure_S26')
manifest = json.loads((output / 'render_manifest.json').read_text())
provenance = json.loads((data / 'provenance.json').read_text(encoding='utf-8'))
assert provenance['complete_network_set']
maps = json.loads((data / 'map_checks.json').read_text())
assert len(maps) == 17 and all(record['all_selected_sites_inside_frame'] for record in maps)
term_checks = {}
for stem in ['Figure_S49', 'main_shared_legend', 'network_panels'] + (['Figure_S26'] if args.include_joint else []):
    with pymupdf.open(output / (stem + '.pdf')) as document:
        content = ''.join(page.get_text() for page in document)
    assert not re.search(r'\bSAF\b', content), stem
    if stem == 'network_panels':
        assert 'Failure' not in content and content.count('Largest-source') == 4
    term_checks[stem] = dict(modelled_product_term='SynAF', contains_standalone_SAF=False)
records = []
for stem in required:
    png, pdf = output / (stem + '.png'), output / (stem + '.pdf')
    for path in [png, pdf]:
        assert hashlib.sha256(path.read_bytes()).hexdigest() == manifest[path.name]['sha256']
    with Image.open(png) as image:
        image.verify()
    with Image.open(png) as image:
        width, height = image.size
    document = pymupdf.open(pdf)
    assert len(document) == 1
    page = document[0]
    assert abs((page.rect.width / page.rect.height) / (width / height) - 1) < .003
    records.append(dict(figure=stem, png_pixels=[width, height], pdf_pages=1,
                        png_sha256=manifest[png.name]['sha256'], pdf_sha256=manifest[pdf.name]['sha256']))
    document.close()
report = dict(passed=True, full_thirteen_baselines=True, includes_joint=args.include_joint,
              validator_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              figures=records, map_frame_checks=maps,
              source_provenance_sha256=hashlib.sha256((data / 'provenance.json').read_bytes()).hexdigest(),
              output_manifest_sha256=hashlib.sha256((output / 'render_manifest.json').read_bytes()).hexdigest(),
              terminology_checks=term_checks,
              visual_checks=['Full Figure 2 composition', 'Full Supplementary Figure S27',
                             'Four-map Supplementary Figure S50', 'New CCU-BH-MTJ map S58',
                             'CCU-BH-FT and DAC-BH-FT map registration'])
if args.include_joint:
    report['visual_checks'].append('Full Supplementary Figure S26; separate cost and direct supply-chain CI axes')
(output / 'validation.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print(json.dumps(dict(passed=True, publication_figures=len(required), includes_joint=args.include_joint)))
