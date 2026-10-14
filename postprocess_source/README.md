# Inventory accounting and figure sources

This folder records the inventory cost and electricity-emission processing used by the current Nexus revision. `original_source/` contains 26 byte-preserved source files: three cost-processing scripts, seven emissions-processing scripts, and sixteen plotting dependencies. `source_manifest.json` identifies each source and reference ledger by SHA-256.

The scientific inputs and final results are in the revision's `Accompanying_Data/` directory. Its `SHA256.json` covers the delivered files. The twelve COPT schedules have original run summaries, configurations, model parameters and 24 SAF/hydrogen inventory CSV files. The thirteen baseline pathway records combine six COPT configurations with seven retained archived comparators. The separate result-version mapping identifies these origins.

| Pathway | Cost (CNY/kg of actual fuel output) | Supply-chain emissions (g CO2e/MJ) | Demand served |
| --- | ---: | ---: | ---: |
| GTL-BH | 5.290539354389216 | 87.34169131743451 | 100% |
| GTL | 6.501554612497708 | 56.94035770298387 | 100% |
| CCU-GH-FT | 26.063813275934226 | 19.43638790367873 | 43.841300164492225% |

The table uses `figure_data/normalized_pathway_records/*_complete_solution.json` and `*_carbon_emissions.json`. `accounting_reference/pathway_summary.csv` is the final Figure 1 source summary; `accounting_reference/carbon_categories.csv` is the corresponding positive-emission category table. Emission values retain the manuscript's production-and-supply-chain accounting boundary, including its capture attribution and excluding combustion. Demand served is reported separately from unit cost.

## Portable verification

Use Python 3.12 and the tested dependencies:

```sh
python -m pip install -r requirements-verification.txt
python verify_postprocess.py --data ../accompanying_data --output verification_output
```

Set `--data` to the actual `Accompanying_Data` directory if the archive uses a different layout. The command checks source and data hashes, executes the unmodified `all_site_inventory.py` on copied real inventory/run/configuration records, and calls the original `update_carbon.corrected()` and learning/category functions. It checks 12 inventory accounts, all 13 baseline cost/carbon ledgers, 143 learning-projection rows and 104 positive-emission category rows. It also checks the retained GTL-BH design and dispatch against the source record. `verification_report.json` gives the results; `original_inventory_execution.txt` retains the inventory calculation output. This command performs accounting verification and does not invoke an optimization solver.

SAF stock in kilograms is converted to tonnes for its configured kWh/(tonne day) energy coefficient. Hydrogen uses its kWh/(kg day) coefficient. Each saved stock state uses the three-hour duration divided by 24 hours/day. The 12 electricity-dependent schedules include all saved supply and receiving stock locations. The archived byproduct-hydrogen comparators use their saved SAF ledger and source-location hydrogen ledger; receiving-location hydrogen trajectories are not inferred. GTL retains its zero SAF storage-emission term. The reference ledger distinguishes these scopes explicitly.

GTL-BH inventory operating costs use the saved design and dispatch, half of each site's peak stock as the average-stock proxy, and 672 represented hours. `accounting_reference/source_GTL-BH_complete_solution.json` and the final normalized record retain both the source ledger/solve objective and the reported cost account. GTL's inventory operating charge remains zero.

## Source execution layout

The original processing and rendering scripts retain their author-workspace relative paths and Windows font references. They are provenance snapshots; the portable command above is the tested entry point for the delivered accounts. Running the original full figure pipelines additionally requires their documented pre-accounting input stage, figure templates and directory layout; see `dependency_map.json`. The published current data alone should not be used as an input to reapply the inventory adjustments.

The renderer dependencies include NumPy, pandas, matplotlib, Pillow, PyMuPDF, PyYAML, python-docx, openpyxl, Cartopy, frykit, shapely and pyproj. The original Windows rendering used Times New Roman. Fonts, matplotlib versions and rasterization can affect pixel-identical output. The final category and learning tables supplied with the revision identify the plotted values independently of rendering.

`verification_reference/verified_accounts.json` records a successful run against the current delivered data on 2026-10-15. It verifies the accounting and figure tables within the stated scopes; it does not substitute for the separate optimization or archived-comparator validation records.
