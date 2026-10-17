# Scientific revision: saved solutions, exact sources and accounts

This directory records twelve newly solved baseline configurations and six fixed-production-asset alternate-week schedules. `revision_manifest.json` binds all eighteen accepted solutions to their execution sources, selected inputs and final accounts. The original direct-FT GTL comparator is preserved separately and is not counted as a new solve.

Each run contains its exact executed model and runtime sources, original YAML configuration, unchanged solver summary, facility and dispatch tables, solver certificate, and saved independent validation reports. The final inventory-energy and carbon accounts are stored separately. Summary files in `source_snapshots/` and the expanded `saved_results/` reproduce the local calculation records byte for byte. Large tables use lossless gzip compression; both compressed and original hashes are recorded.

The CCU/DAC conversion blocks use a common route-level model input of 7.6 kWh per kilogram of final fuel for FT and MTJ. Final synthesis emissions apply this same physical and cost coefficient. Hydrogen supply and DAC capture electricity are accounted separately.

`sources/` contains the complete shared project dependencies and the five actual execution directories, including selected electricity, industrial-hydrogen and airport inputs and cached road routes. SQLite route databases are captured with SQLite online backup and checked for database integrity. Solver licence files and the environment-specific licence launcher are excluded.

## Verify saved results

Use Python 3.12 or later and install the verification requirements from the repository root:

```bash
python -m pip install -r archive_tools/requirements_revision_20261017_verification.txt
python archive_tools/verify_revision_20261017.py --workspace work/revision_integrity --integrity-only
python archive_tools/verify_revision_20261017.py --workspace work/revision_saved_checks
```

The complete check expands the actual saved records, independently recalculates physical balances, transport and inventory costs, and final cost and emissions accounts, and compares the six pairs of fixed production assets. It performs no optimization and needs no solver licence. An individual case can be checked with `--scenario CCU-GH-FT --label baseline`.

The saved verification record identifies the scientific data manifest and the final distribution integrity separately. Original case-check reports, their input hashes, the fixed-asset comparisons and the solver-proof checks remain available under `provenance/`.

The current independent verification programs are recorded in `verification_source/source_manifest.json`. These programs are distinct from the original execution-time validation tools retained in the source snapshots and runtime bundles. The manifest retains hashes of the original saved validation reports; the verification workspace records the current tool hashes and newly generated reports. Scientific model sources and original solver summaries remain unchanged when a verification program is updated.

The saved solver records include projected matrices, actual root-LP primal values and optimal statuses, candidate and repair records, and full-model certificates. The checks recalculate their objective values, feasibility residuals and accepted relative gaps. Integer-design partition cases additionally retain their complete original MPS and all partition nodes and leaf records; the pure-data verifier checks the exhaustive domain coverage and original-objective correspondence. Independent dual vectors were not saved. An archive-restored CCU-GH-FT model was also constructed with COPT; after matching variable and constraint names, its full coefficient matrix, bounds, variable types and objective coefficients were identical to the original model. No optimization is run by these verification commands.

## Prepare an exact model

```bash
python archive_tools/prepare_revision_20261017.py --workspace work/revision_CCU_GH_FT --scenario CCU-GH-FT --label baseline
```

This command expands the shared dependencies, actual inputs and route caches, restores the exact per-run execution sources and configuration, and prints commands for constructing the model or starting a new solve. The `summer_fixed` label also restores the actual baseline production assets. The preparation manifest lists the source hashes and any shared-source versions replaced by the exact run snapshot.

Model construction or a new solve requires COPT 8.0.7, the model requirements and a user-supplied licence. The recorded environment is included in the runtime source manifest. No new solve is needed to inspect or validate the archived results.

## Rebuild the cost and carbon figures

```bash
python -m pip install -r archive_tools/requirements_revision_20261017_figures.txt
python archive_tools/prepare_figures_revision_20261017.py --workspace work/revision_figures --render
```

This command restores the eighteen raw records and final accounts, checks their provenance, rebuilds fixed-design sensitivities and learning tables, and renders Figure 1, Figures S20–S25, S28–S29 and S36–S48. It uses byte-identical original figure templates through the archived wrapper. Install Times New Roman for matching typography. S20 uses actual natural-gas consumption, S21 uses source-specific industrial-hydrogen conditioning capacity and capital costs, and S23 uses actual captured CO₂. These coefficient comparisons retain production assets, dispatch, output and service levels. Figure 1 and S25 use direct supply-chain carbon intensities and the nondominated envelope of the thirteen actual baseline points.

The PV-input preparation and resource, spatial and temporal figure sources and their complete selected inputs are retained under `artifacts/`. To restore them with the original file hierarchy, add `--supporting-artifacts` to the preparation command. Add `--render-supporting` to rebuild these inputs and figures. The preparation report records the mapping from original input roots to the new working directories and all rebuilding commands. Resource-map typography uses Matplotlib 3.10.7; its dedicated requirements are in `requirements_revision_20261017_resource_figures.txt`, and `--resource-python` can select that Python environment. The other final figures record Matplotlib 3.11.2. Original source hashes, inherited templates, selected genuine upstream resource files, prepared figure data, final outputs and verification records are listed in `artifacts/source_manifest.json`. Generated previews and environment caches are excluded.

## Data organization

- `source_snapshots/`: exact per-run model, runtime and configuration snapshots, with unchanged summaries.
- `saved_results/`: original solver exports and validation reports, with large arrays compressed.
- `final_accounts/`: final manuscript cost and emissions records and their source hashes.
- `verification_source/`: current independent saved-data checks and final-account processor.
- `sources/`: full shared project dependencies, five actual runtimes, selected inputs and route caches.
- `postprocess_source/` and `figure_data/`: figure preparation and rendering sources and their actual input contracts.
- `artifacts/`: PV-input preparation, resource/spatial/temporal figure sources, selected original inputs, final data contracts and figure verification records.
- `preserved_GTL/`: original direct-FT GTL reference and retained learning assumptions.
- `provenance/`: original solver proofs, full MPS for integer-partition cases, model-construction equivalence records and collection sources.
- `SHA256SUMS.json`: distributed-file inventory for this revision directory.

The immutable 20260930 and 20261015 releases and their legacy source files retain their original provenance. This directory records the scientific revision.
