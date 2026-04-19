# Infrastructure incompatibility across synthetic aviation fuel pathways risks stranding decarbonization investments

> Code, data pipeline, and MILP optimization framework accompanying the manuscript
> **"Infrastructure incompatibility across synthetic aviation fuel pathways risks stranding decarbonization investments"**
> Liao, J. & Zhang, H.\*, School of Urban Planning and Design, Peking University, Shenzhen

---

## Overview

This repository hosts the end-to-end code, data-processing scripts, and optimization models used to test whether different synthetic aviation fuel (SAF) pathways share a compatible infrastructure regime, or whether pathway switching actually constitutes an **industrial regime reconstruction**.

We compile full life-cycle techno-economic parameters for **13 carbon–hydrogen–route combinations** and couple them to full-year hourly renewable-power output series reduced through a representative-week procedure. A **three-layer (production–transport–consumption) multi-commodity flow MILP** is then solved for each pathway, jointly optimizing facility siting, capacity planning, inventory scheduling and demand fulfilment on a 3-hour / weekly temporal grid. The resulting Pareto frontier reveals **two discrete industrial regime shifts** — in cost, spatial configuration, and temporal-operational structure — rather than a continuous substitution curve, which is the core empirical finding of the paper.

## Key findings reproduced by this repository

1. **Cost–emission frontier (triple discontinuity).** The marginal cost increment in the deep-decarbonization segment is **9.5×** that of the near-term segment, while the absolute emission-reduction gain is only **0.74×** as large.
2. **Spatial non-inheritability.** The 4-node demand-driven closed-loop network of GTL and the 120-node resource-driven distributed network of CCU-GH-FT exhibit **near-zero overlap**, admitting no gradual transition.
3. **Temporal-operational divergence.** GTL is dominated by rare slow-recovery events (robustness penalty **47.70 %**), whereas CCU-GH-FT is dominated by structural underutilization (chronic penalty **94.20 %**) — two categorically distinct and non-transferable operational challenges.

## Repository layout

> Note: the paper's code and data pipeline live on the active work branch
> **`两步法改一步法（只改配置的模式）`**. This `main` branch hosts the top-level README and archival documents only.

The main analysis modules (on the work branch) are organised in a product-based layout:

```
products/
├── supply_chain_optimization/
│   ├── coal_hydrogen_saf_optimization/             # CTL / CTL-BH pathways
│   ├── natural_gas_supply_chain_optimization/      # GTL / GTL-GH / GTL-BH pathways
│   ├── green_hydrogen_supply_chain_optimization/   # CCU-GH-FT / CCU-GH-MTJ pathways
│   ├── dac_hydrogen_saf_supply_chain_optimization/ # DAC-GH-* / DAC-BH-* pathways
│   ├── sensitivity_analysis/                       # 215-run Gurobi sensitivity sweep (Figs. S20–S24)
│   ├── learning_curves/                            # Wright's-Law 2026–2036 projections (Figs. S36–S48)
│   └── visualization/                              # Figures 1–4 and Figs. S25–S63
├── aviation_fuel_analysis/                         # Airport fuel demand (Figs. S2–S5)
└── gis_energy_mapping/                             # Industrial H₂ / CO₂ and renewables maps (Figs. S6–S17)
appendix_saf_workspace/                             # Manuscript, appendix, supplementary info, figure scripts
```

## Manuscript ↔ code map

| Manuscript element | Code entry point |
| --- | --- |
| Unified 13-scenario MILP | `products/supply_chain_optimization/*/src/core/*_optimization_model.py` |
| Representative-week data | `products/aviation_fuel_analysis/` + `products/gis_energy_mapping/` |
| Sensitivity sweep (Figs. S20–S24) | `products/supply_chain_optimization/sensitivity_analysis/sensitivity_runner.py` |
| Learning-curve trajectories (Figs. S36–S48) | `products/supply_chain_optimization/learning_curves/` |
| Figure 1–3 visualization | `products/supply_chain_optimization/visualization/` |
| Appendix DOCX / figures | `appendix_saf_workspace/scripts/generate_appendix_docx.py` |

## Data and model inputs

Model inputs cover four categories: feedstock and energy supply data, spatial network data, techno-economic parameters, and airport demand data. A consistent accounting boundary is applied across all 13 pathways; pathway-specific parameters are switched through scenario indicator variables so the same MILP framework produces all pathway-level optima. Full parameter tables and data provenance are documented in the **Supplementary Information** of the manuscript.

External data that cannot be redistributed (proprietary techno-economic parameters, raw flight-level data, and `china-latest.osm.pbf`) are excluded from the repository; their sources are listed in the manuscript's data-availability statement.

## Software and environment

- Python 3.12+
- [Gurobi](https://www.gurobi.com/) (commercial solver) — tested with academic license
- `pandas`, `numpy`, `matplotlib`, `seaborn`, `pydeck`, `frykit` (maps), `python-docx`
- Conda environment used during development: `green_methanol_for_port_transportation`

```bash
conda activate green_methanol_for_port_transportation
# run a single-pathway optimization (example: GTL baseline)
python products/supply_chain_optimization/natural_gas_supply_chain_optimization/src/natural_gas_optimization_model.py
# run the 215-instance sensitivity sweep
python products/supply_chain_optimization/sensitivity_analysis/sensitivity_runner.py
```

## Citation

If you use this code or data pipeline, please cite:

```bibtex
@article{Liao2026_SAF_infrastructure_incompatibility,
  title   = {Infrastructure incompatibility across synthetic aviation fuel pathways risks stranding decarbonization investments},
  author  = {Liao, Junteng and Zhang, Haoran},
  year    = {2026},
  note    = {Manuscript under review}
}
```

## License and contact

Academic and research use. For collaboration or reproduction support, please contact the corresponding author
**Haoran Zhang · h.zhang@pku.edu.cn**.

---

Legacy READMEs from earlier iterations of this repository (BADA aviation carbon calculator, GraphHopper tooling, green-methanol port-transport case study) are preserved under `docs/legacy/` for provenance and are no longer actively maintained.
