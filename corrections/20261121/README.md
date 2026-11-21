# Industrial CO₂ supply and network results for the Nexus study

This directory supplies the coal-unit inputs, industrial CO₂ contracts and network indicators used in the publication version. The original model matrices, costs, energy inputs, routing graph and operating schedules are available from the [fixed study archive](https://github.com/Lantern567/synthetic-aviation-fuel-pathways-risks/releases/tag/nexus-r1-20261018-cases-full), commit `e24a85cf9a131e45be6808ace2e3b7cb140cdac9`.

The modelled weekly ceiling for each operating coal unit equals its nameplate capacity in MW multiplied by 168 hours, the archived capacity factor of 0.53, an emission factor of 0.95 t CO₂/MWh and a capture rate of 0.85. The 3,146 units sum to 81.723757 Mt/week. Gas power and refineries contribute 3.316920 and 6.742157 Mt/week, respectively. The four Yangliuqing units each use 300 MW as listed by the North China Energy Regulatory Bureau for the 2023–2024 heating season. These quantities are model inputs. [Regulatory table, page 18](https://hbj.nea.gov.cn/xxgk/fdzdgknr/scxxgk/202403/P020240318557794789706.pdf#page=18)

## Dispatch and accounting

The industrial point-source model screens 31 records within 100 km of central Beijing. Six configurations use these records. All 16 regional coal ceilings decrease and the other 15 ceilings are unchanged. Capacities do not change the regional coordinates or candidate links. The configured maximum cluster count also exceeds the number of regional sources. This restriction of the published feasible set preserves its verified global objective lower bounds.

Five published schedules satisfy all 31 revised ceilings. For the CCU-BH-FT baseline, a linear assignment first minimizes the tonnes transferred between previously selected units at the same location. It preserves each receiving site's supply, route length and price. Equal-tonnage alternatives prioritize the larger original contract. The resulting weekly reassignment is 7,431.621542 tonnes from Yangliuqing source record 12 to record 13 on the existing 54.655850 km connection to Tianjin Iron and Steel. Their resulting weekly allocations are 21,569.940000 and 20,071.726016 tonnes, respectively.

HiGHS 1.16.0 independently solved the complete economic dispatch with the selected integer design and weekly contracts fixed, following the study's dispatch protocol. The retained solution is feasible in the unrestricted corrected model and its objective is within 0.9772% of a valid global lower bound. All 241,974 full-model rows, 1,546,263 variables and integer decisions were checked. The reported gap applies to the objective including shortage penalties. The cost and carbon ledgers give 9.69 CNY/kg and 271.063 g CO₂e/MJ at full baseline demand coverage.

In Table S18 the three largest routes carry 55.83% of mass flow, and the largest source record contributes 34.65%. The geographic synthesis-site matching, hourly operation and supplied fuel quantities use the same validated schedules. Figure 2 and Figures S8, S25, S26 and S59 use the corrected input or route data.

## Read the distributed files

- `data/input/coal_unit_inputs.csv` identifies all coal units and their applied nameplates and capacity factors. `data/input/co2_capture_sources.csv` contains the complete model input. `capture_input_checks.json` provides hashes, national totals and the regional correspondence.
- `data/runs/<scenario>/<set>/capture_dispatch_certificate.json` records every regional source check and the objective certificate. The CCU-BH-FT baseline also includes its complete revised primal vector, route contracts and independently checked cost and carbon ledgers.
- `data/spatial/` contains the updated transport and network records in the study's figure-input formats.

## Reproduce the checks

Extract the complete fixed study archive. Python 3.12, NumPy, SciPy, pandas, PyYAML and HiGHS 1.16.0 are used by the numerical scripts. From this directory, run the following verification on the distributed data. Replace `STUDY_ARCHIVE` with the path containing `revision_20261017`.

```sh
python check_revision.py --archive STUDY_ARCHIVE --data data
```

`build_capture_input.py` reconstructs the inputs from the original GIS coal-unit snapshot, the industrial capture inventory and the CCU-BH-FT configuration. The original GIS files reside in `revision_20261017/sources/b6da4acdaf34504e/shared_project/products/`. The case configuration resides in `revision_20261017/saved_results/CCU-BH-FT/baseline/config.yaml`.

```sh
python build_capture_input.py --raw-coal RAW_COAL_CSV_GZ --old-inventory ARCHIVED_CO2_CSV --configuration CASE_YAML --output REBUILT/input
python verify_dispatch.py --archive STUDY_ARCHIVE --limits REBUILT/input/capture_input_checks.json --output REBUILT/runs --scratch SCRATCH
python verify_accounts.py --archive STUDY_ARCHIVE --data REBUILT --scratch SCRATCH/accounts
python update_spatial.py --archive STUDY_ARCHIVE --published SPATIAL_FIGURE_INPUTS --contracts REBUILT/runs/CCU-BH-FT/baseline/ccu_co2_transport_accounting.csv --certificate REBUILT/runs/CCU-BH-FT/baseline/capture_dispatch_certificate.json --output REBUILT/spatial
python check_revision.py --archive STUDY_ARCHIVE --data REBUILT
```

`SPATIAL_FIGURE_INPUTS` is the archive's `revision_20261017/artifacts/workspace/work/nexus_targeted_revision/scientific_revision_20261017/figures_spatial/network_data` directory. For figure generation, also install the figure dependencies distributed with the original archive.

```sh
python plot_capture.py --archive STUDY_ARCHIVE --inventory REBUILT/input/co2_capture_sources.csv --scratch SCRATCH/national --output FIGURES
python plot_network.py --archive STUDY_ARCHIVE --spatial-correction REBUILT/spatial --scratch SCRATCH/network --output FIGURES
```

To build an industrial CO₂ model from its prepared execution source, use the archive's `prepare_revision_20261017.py` and replace the prepared runtime's `project/products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/data/co2_capture_sources.csv` with the corrected file before model construction. For the archived full-matrix method, `verify_dispatch.py` applies the equivalent source bounds directly and validates the primal vector and global bound.
