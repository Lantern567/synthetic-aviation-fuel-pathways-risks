# Synthetic aviation fuel pathway revision archive

This repository snapshot preserves the original results and supporting materials for the current Nexus revision of *Infrastructure incompatibility across synthetic aviation fuel pathways risks stranding decarbonization investments* by Junteng Liao and Haoran Zhang.

**Version:** `nexus-r1-20260930`  
**Status:** revision snapshot  
**Release:** [Current revision archive](https://github.com/Lantern567/synthetic-aviation-fuel-pathways-risks/releases/tag/nexus-r1-20260930)

The adopted outputs are the 13 archived Gurobi runs dated 1 February 2026. The release provides computational provenance, source files, archived outputs, supplementary documents and a tested entry point for checking the archive and reproducing its summary tables. It does not certify complete physical feasibility or constitute an independently validated reoptimization.

## Contents

| Directory or file | Purpose |
| --- | --- |
| `model_source/` | Scientific Python source and configurations preserved from the source snapshot |
| `archived_outputs/` | Original pathway solutions, schedules and associated analysis outputs |
| `supplementary_data/` | Solver records, temporal indices and supplementary calculation tables |
| `documents/` | Supplementary Information, supplementary figure archive and solver summary |
| `archive_tools/reproduce.py` | Archive checks and reproduction of the 13-pathway summary |
| `provenance/` | Source and result indices, checks and observed environment inventory |
| `archive_metadata.json` | Version, provenance and validation scope |
| `SHA256SUMS.json` | File integrity manifest |

## Reproduce the archived summary

Use Python 3.12 or later. This entry point uses the Python standard library and does not require a solver license.

```bash
python archive_tools/reproduce.py --output work/reproduced
```

The command verifies file hashes, associates each of the 13 solutions with its solver record, checks the retained temporal-index records, and writes `pathway_summary.csv`, `solver_records.csv` and `archive_checks.json`. It does not launch optimization or establish energy and material balance feasibility. Its check results apply only to the named archive and indexing tests.

The historical runs used Gurobi 12.0.3 with a target relative MIP gap of 1%. Eight reached that tolerance. Five stopped at the time limit; their achieved gaps, including 27.2950% for GTL-GH, are retained in the solver table. A time-limited incumbent must be interpreted with its reported bound.

## Source and environment

The scientific model and configuration files under `model_source/` retain their internal directory structure and are associated with [commit 35d257c](https://github.com/Lantern567/synthetic-aviation-fuel-pathways-risks/commit/35d257cdb51b597ab7a099dcc5ad26ea10eb6664). The temporal plotting module uses the pathway labels corresponding to its source folders. Additional server cache helpers are included. File-level hashes and comparison with the source commit are recorded in `provenance/model_source_index.json` and `provenance/source_commit_comparison.json`.

`environment-summary.yml` defines the environment required by the summary entry point. `provenance/server_packages_observed_20260930.json` records packages observed on the research server on 30 September 2026; it is not a contemporaneous lockfile for the February runs.

The historical optimizer sources retain their original server paths and external service assumptions. Running them requires the corresponding inputs, GIS and routing services, path configuration and an independently obtained Gurobi license. The archive-summary command above is the tested portable entry point for this release. Full optimization has not been rerun as part of preparing this snapshot.

## Interpretation of the archived results

The study compares 13 retained pathways for Beijing–Tianjin airport demand using four representative weeks and a three-hour production grid. The manuscript examines differences in cost structure, facility siting and utilization requirements. Geographic correspondence, equipment reuse and operational performance are separate measures. The archived comparative findings are conditional on the model, input and carbon-accounting assumptions described in the supplementary documents.

The release retains the original result values. The validation summary covers solver provenance and temporal indexing and must not be cited as a certificate that all model or engineering checks passed. Refer to the Supplementary Information for the reported scope and limitations.

## Data availability

The release contains the archived optimization outputs and supplementary summary data. Upstream raw flight records, the full raw renewable-resource archive and the OSM country extract are not bundled here. Their roles and data sources are described in the Supplementary Information. This snapshot should not be described as a self-contained raw-data-to-optimization reproduction package.

## Citation

Cite the manuscript and the fixed release tag `nexus-r1-20260930`, together with the resolved commit identifier. `CITATION.cff` supplies the archive metadata. The manuscript is under review; the snapshot does not imply journal acceptance.

## Contact and permissions

For reproduction questions or reuse permissions, contact the corresponding author, Haoran Zhang, at h.zhang@pku.edu.cn. No new open-source license grant is asserted by this archival release; third-party data and software retain their respective terms.
