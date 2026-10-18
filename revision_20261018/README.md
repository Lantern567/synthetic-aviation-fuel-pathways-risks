# Sample-based airport-demand cases and input diagnostics

This directory accompanies the fixed `nexus-r1-20261018-cases` release. It provides the flight-record grouping, selected demand cases and Supplementary Figures S1-S5 used to describe the airport inputs. Model inputs, saved solutions and final cost and emissions accounts retain the values and exact source bindings in `revision_20261017/`.

The supplied flight-fuel estimation table contains 28,967 departure records for Capital and Binhai airports. Its 28,852 records with saved fuel estimates and month labels form twelve sample-based demand cases for each airport. The records are aggregated using their saved `YYYY-MM` grouping field. Each case is assigned to one model week and paired with a source weather block. Original day-precision record dates are retained separately in `case_date_composition.csv` and the row-level record files.

`case_index` is the zero-based position in the twelve-case pool. `demand_storage_label` records the identifier used by the original processing table, and `resource_source_week_label` identifies the paired weather block. The baseline uses cases 0, 1, 3 and 10 and weather blocks 1, 5, 14 and 44; the alternative uses cases 0, 3, 6 and 10 and weather blocks 1, 14, 27 and 44. Their four-model-week demand totals are 51,050,925.57290507 and 56,807,154.89541006 kg, respectively. The 52-slot legacy table is a stored case-copy mapping. The diagnostics use the twelve-case pool and its four-case selections.

The supplied table and original processing scripts are included as the input provenance. The saved case construction retains each record's existing fuel estimate and multiplicity. Records without a saved estimate remain missing. No new flight-frequency expansion, case weighting or optimization is applied by these diagnostic programs.

## Verify the saved cases

From the archive root, with Python 3.12 or later:

```bash
python -m pip install -r revision_20261018/requirements.txt
python revision_20261018/source/verify_cases.py --output work/demand_case_checks.json
```

This entry point needs neither Git nor a solver. It checks source and derived-file SHA256 values, recomposes all 24 airport-case fuel values from the supplied flight-fuel table, matches all 16 A/B model entries, verifies the eight original input-file hashes and binds eighteen unchanged summaries to the prior fixed revision manifest.

Reproduce the diagnostic figures from the same archive root:

```bash
python revision_20261018/source/build_s1.py --data-dir revision_20261018/demand_cases/plot_inputs --out work/demand_figures/figures
python revision_20261018/source/render_demand_cases.py --data-dir revision_20261018/demand_cases/derived --out work/demand_figures
```

These commands create all five figures under `work/demand_figures/figures/`; the latter also writes the plotted case and aircraft statistics under `work/demand_figures/data/`. The figure typography uses Arial where installed. The S1 input record binds the national inventory counts, 109 selected resource projects, twelve-block resource pool and eight baseline demand values to their recorded source hashes.

The original contract-generation program is retained as `source/build_contract.py`; its explicit options allow a full reconstruction against an existing checkout of commit `8b4eac762b85bcccf510cba3a61174530d48e849`. The saved-case verifier above is the standalone release check.

## Files

- `demand_cases/source_data/`: supplied flight-fuel workbook, original demand workbooks, weather pool, source summary and original-row mapping.
- `demand_cases/derived/`: case values, original-date composition, row-level records, A/B mappings and input/result preservation checks.
- `demand_cases/model_inputs/`: byte-identical selected A/B inputs.
- `demand_cases/reference_results/`: eighteen byte-identical original summaries.
- `source/original_processing/`: original grouping and extraction scripts.
- `source_map.json`: portable source paths and SHA256 bindings.
- `figures/`: standalone diagnostic figures and their plotted data.
- `SHA256SUMS.json`: this revision's payload inventory.

The scientific model, saved dispatch, accounting and physical verification programs remain in `revision_20261017/` and `archive_tools/`. Run `archive_tools/verify_revision_20261017.py` to recheck those saved solutions. The original GTL comparator retains the separate historical provenance identified there.
