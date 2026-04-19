# Data Sources

> Provenance and scope of every dataset used by the 13-pathway SAF supply-chain model.
> Mirrors the data pipeline documented in **Appendix S1** of the manuscript
> *"Infrastructure incompatibility across synthetic aviation fuel pathways risks stranding decarbonization investments"*.

All raw data remain external to this repository because of size, licensing, or redistribution constraints. This document lets you rebuild the model-ready inputs from their original sources and cross-check the numbers quoted in the main text and appendix.

Quick link back: the cross-dataset table is **Table S1**, the preprocessing flow is **Figure S18**, and the compression overview is **Figure S1**.

---

## 1. Cross-dataset overview (Appendix §1.1, Table S1)

| Dataset block | Raw source & scope | Model-ready representation | Role in optimization |
| --- | --- | --- | --- |
| Airport SAF demand | 2024 domestic flight schedule processed flight-by-flight with a pyBADA-based fuel model | 8 airport-week records (Beijing + Tianjin × 4 representative weeks) | Weekly SAF demand at airport nodes |
| Renewable electricity | China-wide wind and solar plant inventories + hourly output profiles (MERRA-2-based reconstruction) | 1,798 wind plants + 1,908 solar plants × 672 modeled hours | Limits green-H₂ production and defines the renewable spatial opportunity |
| Industrial by-product H₂ | Refinery and steel-plant geocoded inventories with daily H₂ estimates | 180 refinery sites + 211 steel-sector sites | Upper bound for by-product hydrogen pathways |
| Industrial / atmospheric CO₂ | Industrial capture-source metadata + CCUS reference projects + DAC siting rules | 3,445 industrial capture-source records + DAC candidate locations | Upper bounds for CCU; siting for DAC pathways |
| Transport network | Existing pipeline GIS + province-level gas/electricity price tables + OSM road graph | 436 pipeline polylines + 30 provincial price surfaces | Candidate logistics arcs + route-specific transport / energy costs |
| Techno-economic parameters | Scenario-specific YAML configs + harmonized literature inputs | Route-specific cost, emissions, efficiency, lifetime, policy parameters | Objective coefficients + ex-post emissions accounting |

The temporal reduction documented in Figure S1 converts **52 calendar weeks → 4 representative weeks**, **2,912 three-hour periods → 224 retained periods**, and **8,736 annual hours → 672 modeled hours**.

---

## 2. Airport aviation-fuel demand (Appendix §1.2)

- **Raw source**: 2024 domestic flight schedule (Chinese civil aviation). One row per flight, with operating airport, aircraft type, and route-distance context.
- **Processing tool**: flight-level [pyBADA](https://github.com/eurocontrol-bada/pybada)-based fuel-consumption model (EUROCONTROL BADA3/4 coefficients) applied to every scheduled flight to estimate fuel use at the flight level; aggregated to airport–week totals.
- **Demand scope** (current archived instance): Beijing + Tianjin airports; the 4 retained weeks hold 39.55 Mkg for Beijing and 11.50 Mkg for Tianjin.
- **Representative-week mapping** (Table S2): new weeks 1–4 ↔ original calendar weeks **1, 5, 14, 44** of 2024.
- **Candidate pool**: full-year 52 weeks → 12-week screening pool → 4 retained weeks. Coverage across low/medium/high demand positions is documented in Figures S4–S5.
- **Reproduction entry points**: `products/aviation_fuel_analysis/` (flight schedule preprocessing + pyBADA wrapper); `appendix_saf_workspace/scripts/fig_s7b_demand_aircraft.py` (demand descriptors Fig S3).

The raw flight schedule file is **not** redistributed here. Where to obtain: civil-aviation authority releases for 2024, or commercial flight-schedule providers. We cite the source by provider rather than by proprietary filename.

---

## 3. Renewable electricity (Appendix §1.3)

- **Wind stack**: 7,988 raw plant-level rows → **1,798 operating plants** in the hourly reconstruction with 181.47 GW installed capacity and 84.99 TWh of simulated annual generation. Median annual full-load hours ≈ **5,073 h**.
- **Solar stack**: 13,265 raw plant-level rows → **1,908 operating plants** in the hourly reconstruction with 64.35 GW installed capacity and 37.51 TWh simulated generation. Median annual full-load hours ≈ **3,118 h**.
- **Meteorological drivers**: MERRA-2 (NASA GES DISC, reanalysis product for solar irradiance and wind speed) combined with plant coordinates, hub-height adjustment, and turbine power-conversion curves for wind; plant coordinates linked to radiation fields for solar.
- **Plant inventories**: consolidated from public operating-plant records (see Figure S8 maps).
- **Temporal reduction**: full annual hourly output → 12-week candidate pool → 4 retained weeks (weeks 1, 2, 4, 11 of the 12-week pool remapped to the final 4-week horizon; Figure S9 panel d).

Raw MERRA-2 data and plant inventories are large (tens of GB). Obtain MERRA-2 from [NASA GES DISC](https://disc.gsfc.nasa.gov/datasets?project=MERRA-2). Plant inventory fields used: coordinates, installed capacity, commissioning year, operating status.

---

## 4. Industrial by-product hydrogen (Appendix §1.4)

- **Refinery H₂**: 180 sites across 27 provinces, aggregate **1,412.56 t H₂ / day**.
- **Steel-sector H₂**: 211 sites across 28 provinces, aggregate **150,549.3 t H₂ / day** (order-of-magnitude larger than refineries).
- Both layers enter as **availability upper bounds**, not forced supply — the optimization may draw less when cost-optimal.
- **Scripts & maps**: Figure S11 (summary statistics) and Figure S12 (national maps). Reproduction: `products/gis_energy_mapping/industrial_byproduct_hydrogen/`.

Raw site-level geocoded inventories are compiled from public facility registries and published industry surveys. Where the repository expected a data file, the path is kept but the file is excluded from Git via `.gitignore`.

---

## 5. Industrial CO₂ and DAC carbon supply (Appendix §1.4)

- **Industrial point-source CO₂**: 3,445 records across 34 provinces. Weekly capture potential: **179.3 Mt/week (coal power)**, **3.3 Mt/week (gas power)**, **6.7 Mt/week (oil refinery)**. Median unit capture cost: **150 / 180 / 120 yuan per t CO₂** respectively.
- **CCUS reference projects**: 21 records retained as metadata beside the optimization instance (not used as forced demand).
- **DAC**: generated procedurally per scenario; siting candidates attached to renewable- or industrial-node anchors depending on scenario config.
- **Maps & summaries**: Figures S13–S14.

Source tables are assembled from public CCUS project registries (Global CCS Institute, IEA CCUS database, and peer-reviewed plant-level surveys). DAC cost trajectories tied to learning-curve references listed in §7 below.

---

## 6. Transport network & energy prices (Appendix §1.5)

- **Pipeline GIS**: 436 polylines (317 operating + 44 planned), cumulative length **116,204 km** across records with explicit length metadata; median segment length **130.1 km**. Used to construct candidate arcs — **not** assumed as an already-built future network.
- **Road routing**: OpenStreetMap-derived road graph, served via [GraphHopper](https://github.com/graphhopper/graphhopper) at `localhost:8989` with a 168 h cache expiry. Shortest-path truck distances replace straight-line distances for all truck arcs.
- **Candidate-arc distance screen**: 1,000 km.
- **Pipeline connector graph**: k = 10 nearest connectors, Johnson algorithm.
- **Province-level energy prices** (after excluding nationwide aggregate rows): gas **1.41–3.61 yuan per 10k m³**; electricity **0.377–0.617 yuan per kWh**.
- **China OSM file**: `china-latest.osm.pbf` (~1 GB) not redistributed. Download from [Geofabrik](https://download.geofabrik.de/asia/china.html) and place under the expected `data/` subfolder of each optimization module (see `products/supply_chain_optimization/*/data/`).

---

## 7. Techno-economic parameters & learning-curve inputs (Appendix §1.1, §2.5–2.8)

- Per-pathway techno-economic parameters (CAPEX, OPEX, efficiency, lifetime, policy credits, emission factors) live in per-scenario YAML configs inside `products/supply_chain_optimization/<pathway>/configs/`.
- Parameter harmonization and literature provenance: see Appendix Tables S8–S9.
- Wright's-Law 2026–2036 learning-curve projections for coal-CCS, gas-CCS, refinery-CCS, FT synthesis, electrolyzers, and DAC are generated by `products/supply_chain_optimization/learning_curves/generate_lcoe_projection.py`. The **upstream learning-curve literature PDFs** (~86 MB) are excluded from Git; the written survey in `learning_curves/LEARNING_CURVE_SURVEY.md` + `learning_curve_literature_summary.md` lists every referenced study so you can pull them yourself.

---

## 8. Spatial preprocessing & clustering (Appendix §1.6)

- DBSCAN clustering of renewable/by-product-H₂/CO₂ source layers, with **eps = 60 km, min_samples = 2**. Archived runs retained:
  - Renewables: 24 clusters + 13 direct-connection points
  - By-product H₂: 12 clusters + 23 noise points
  - Point-source CO₂: similar treatment, clusters kept per source type
- Cluster-center selection balances intra-cluster travel with existing-pipeline access (pipeline weight 0.3, shared-pipeline discount 0.65).
- Candidate logistics arcs = business node ↔ 10 nearest pipeline nodes (precomputed super-graph) + shortest-path road arcs for trucks.
- **Preprocessing workflow diagram**: `appendix_saf_workspace/Figure_S18_preprocessing_workflow.drawio` (source) and Figure S18 in the appendix.

---

## 9. What is actually under version control vs. excluded

**Tracked in this repository** (code only):
- Optimization models, constraint builders, sensitivity sweep, learning-curve generator, visualization scripts, appendix figure scripts.
- Small per-pathway YAML configs (once promoted out of `data/`).

**Excluded by `.gitignore`**:
- All raw datasets (`*.xlsx`, `*.csv`, `*.pbf`, `*.nc`).
- Reference literature PDFs under `learning_curves/references/` (~86 MB).
- Appendix figure outputs and caches (~1.2 GB figures + 553 MB word backups).
- Solver logs, monitoring snapshots, and per-run result dumps.

If you want to reproduce a specific figure or table, the manuscript and this document together tell you where every input comes from; run the relevant script after placing the matching raw files under `data/`.
