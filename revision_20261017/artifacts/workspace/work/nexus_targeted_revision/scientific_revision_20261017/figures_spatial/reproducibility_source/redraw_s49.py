import argparse
import hashlib
import json
from pathlib import Path

import render_spatial as draw


parser = argparse.ArgumentParser()
parser.add_argument('--workspace-root', type=Path, default=draw.ROOT)
parser.add_argument('--legacy-figures', type=Path)
parser.add_argument('--external-project', type=Path)
parser.add_argument('--output', type=Path, default=draw.HERE / 'figures')
args = parser.parse_args()
draw.configure_sources(args.workspace_root, args.legacy_figures, args.external_project)
args.output.mkdir(parents=True, exist_ok=True)
draw.supplement_legend(args.output)
manifest_path = args.output / 'render_manifest.json'
manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
for suffix in ['png', 'pdf']:
    path = args.output / ('Figure_S49.' + suffix)
    manifest[path.name] = dict(sha256=draw.checksum(path), bytes=path.stat().st_size)
manifest_path.write_text(json.dumps(manifest, indent=2), encoding='utf-8')
provenance_path = args.output / 'render_provenance.json'
provenance = json.loads(provenance_path.read_text()) if provenance_path.exists() else {}
provenance['readable_s49'] = dict(renderer_sha256=draw.checksum(Path(draw.__file__)),
    entry_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), width_in=7.2,
    height_in=3.1, label_size_pt=10, intended_word_width_pt=452.88,
    effective_label_size_pt=10 * 452.88 / (7.2 * 72))
provenance['output_manifest_sha256'] = draw.checksum(manifest_path)
provenance_path.write_text(json.dumps(provenance, indent=2), encoding='utf-8')
print(json.dumps(provenance['readable_s49'], indent=2))
