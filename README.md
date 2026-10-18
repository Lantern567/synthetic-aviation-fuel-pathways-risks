# Synthetic aviation fuel pathway revision archive

The fixed [nexus-r1-20261018-cases release](https://github.com/Lantern567/synthetic-aviation-fuel-pathways-risks/releases/tag/nexus-r1-20261018-cases) adds the sample-based airport-demand case definitions, flight-record mappings and Supplementary Figures S1-S5 in [revision_20261018/](revision_20261018/README.md). The demand cases are paired with selected weather blocks. Their original flight dates, case indices and weather-block labels are recorded separately. All model inputs, eighteen saved solutions and final accounting records from the scientific revision below are retained unchanged.

The fixed [nexus-r1-20261017 release](https://github.com/Lantern567/synthetic-aviation-fuel-pathways-risks/releases/tag/nexus-r1-20261017) contains the scientific revision documented in [revision_20261017/](revision_20261017/README.md). It binds eighteen newly solved schedules to their exact execution sources, configurations, original summaries, complete saved dispatch and independent checks. The original direct-FT GTL comparator is preserved separately.

Start with the new saved-data verification entry point:

```bash
python -m pip install -r archive_tools/requirements_revision_20261017_verification.txt
python archive_tools/verify_revision_20261017.py --workspace work/revision_checks
```

This check requires no optimization or solver licence. The revision documentation also provides individual-case verification and exact model preparation commands. Original execution tools and reports remain identifiable separately from the current independent verification programs.

The documentation below describes the immutable `nexus-r1-20261015` release and its legacy layout. Its root checksum inventory applies to that fixed release. The new revision has its own manifest and checksum inventory under `revision_20261017/`; new archive tools are named `*_revision_20261017.py`.

## Fixed 20261015 release

This fixed archive accompanies *Infrastructure incompatibility across synthetic aviation fuel pathways risks stranding decarbonization investments* by Junteng Liao and Haoran Zhang.

Version `nexus-r1-20261015` provides the code, selected inputs and saved results for six electricity-dependent configurations evaluated with COPT 8.0.7. Each configuration has a baseline and an alternative-week schedule with baseline production assets fixed. The baseline uses weeks 1, 5, 14 and 44; the alternative uses weeks 1, 14, 27 and 44. Each set contains 224 three-hour periods. CTL is the separately identified partial-supply diagnostic.

The seven retained comparison configurations have their historical model and result provenance in [nexus-r1-20260930](https://github.com/Lantern567/synthetic-aviation-fuel-pathways-risks/releases/tag/nexus-r1-20260930), commit `d20ad94829016234eb434cfca1bd6dcd48911b78`. The accompanying data identify the source and accounting scope of every configuration used in the manuscript figures.

## Obtain the complete archive

Download `nexus-r1-20261015.zip` and its SHA256 file from the [release page](https://github.com/Lantern567/synthetic-aviation-fuel-pathways-risks/releases/tag/nexus-r1-20261015), verify the ZIP checksum and extract it. Run the commands below from the extracted archive root. The Git source tree contains the code and selected model inputs; the complete release ZIP additionally contains `validation_records/` and `accompanying_data/`.

`SHA256SUMS.json` identifies every distributed file. `provenance/run_sources.json` connects all twelve original solution summaries to their exact execution sources and configurations. `provenance/packed_inputs.json` records both the compressed and original SHA256 values of losslessly packed files. The preparation and verification commands expand these files into a new working directory.

## Recheck the saved results

Use Python 3.12 or later and install the verification requirements:

```bash
python -m pip install -r archive_tools/requirements_verification.txt
python archive_tools/verify_archive.py --output work/integrity
python archive_tools/prepare_execution.py --workspace work/physical_checks --verify-all
python postprocess_source/verify_postprocess.py --data accompanying_data --output work/final_accounts
```

These commands check distributed file hashes, source-to-result correspondence, the twelve electricity/hydrogen/fuel/transport/demand balances, the six fixed-production-asset pairs, and the final cost and inventory-emissions accounts. They read saved solutions without starting optimization or requiring a solver licence. `postprocess_source/README.md` explains the final-account and figure-data checks.

The original solver summaries are preserved byte for byte. The final manuscript accounts appear separately in `accompanying_data/`, including the GTL-BH inventory-cost account and the inventory-energy emissions ledgers. This separation keeps the solver source records identifiable and makes the reported accounts reproducible.

## Prepare a model for a new solve

```bash
python archive_tools/prepare_execution.py --workspace work/CCU_GH_FT_baseline --scenario CCU-GH-FT --label baseline
```

The command prepares the exact archived source snapshot, configuration, static data, selected electricity and airport-demand inputs, and road-route records. It prints the command for launching the archived model. Supported scenarios are `CCU-GH-FT`, `CCU-GH-MTJ`, `DAC-GH-FT`, `DAC-GH-MTJ`, `GTL-GH` and `CTL`; labels are `baseline` and `summer_fixed`. The second label also includes the archived baseline production assets.

A new solve requires the model requirements in `archive_tools/requirements_model.txt`, COPT 8.0.7 and a valid user-supplied solver licence. The recorded computations used Linux and Python 3.12.11. The archive supplies the selected inputs and road distances used for these cases. Source preprocessing and projection/design-search scripts are retained for their documented roles; upstream weather files, a full China OSM installation and solver licence files are not distributed.

## Archive contents

- `source_snapshots/`: per-run execution sources, original configurations and source summaries.
- `compute/`: model modules, preprocessing, projection and validation scripts, selected inputs and routing records.
- `validation_records/`: complete saved dispatch and facility records used by the physical checks, with large arrays losslessly compressed.
- `accompanying_data/`: the 303-file final manuscript data attachment, including figure records and accounting variants.
- `postprocess_source/`: original cost, emissions and plotting source files, reference ledgers and the final-account verification entry point.
- `archive_tools/`: archive-integrity, execution-preparation and saved-result verification commands.
- `provenance/`: source, environment, compression and validation manifests.

The physics checks cover the twelve electricity-dependent schedules. The seven historical comparators contribute their saved baseline configurations and the final stated accounting scope. Representative-week results retain the temporal assumptions specified in the Supplementary Information.

The manuscript is under review. Cite the fixed release tag and its resolved commit. This archive makes no new blanket licence grant; contact Haoran Zhang at h.zhang@pku.edu.cn for reuse permissions beyond review and reproduction.
