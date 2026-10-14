# Synthetic aviation fuel pathway research

Code and archived results for *Infrastructure incompatibility across synthetic aviation fuel pathways risks stranding decarbonization investments* by Junteng Liao and Haoran Zhang.

## Current fixed revision archive

[Download nexus-r1-20261015](https://github.com/Lantern567/synthetic-aviation-fuel-pathways-risks/releases/tag/nexus-r1-20261015)

[Browse the fixed code and documentation](https://github.com/Lantern567/synthetic-aviation-fuel-pathways-risks/tree/nexus-r1-20261015)

The complete release ZIP contains twelve COPT 8.0.7 execution-source snapshots and configurations, selected model inputs and road-route records, complete saved dispatch data, the final 303-file manuscript data attachment, and cost/emissions and plotting sources. Each of the six electricity-dependent configurations has a baseline schedule and an alternative-week schedule with baseline production assets fixed. CTL is identified as a partial-supply diagnostic.

Download the ZIP and checksum together. After extracting the archive, run from its root directory using Python 3.12 or later:

```bash
python -m pip install -r archive_tools/requirements_verification.txt
python archive_tools/verify_archive.py --output work/integrity
python archive_tools/prepare_execution.py --workspace work/physical_checks --verify-all
python postprocess_source/verify_postprocess.py --data accompanying_data --output work/final_accounts
```

These entry points check file integrity, exact source-to-result correspondence, all twelve saved physical schedules, six fixed-production-asset pairs, and the final manuscript accounts and figure data. Verification reads saved results without launching optimization. The release README documents model preparation, required dependencies and licences, and the supplied input scope. The complete ZIP includes saved results omitted from the Git source tree.

## Historical comparison archive

[nexus-r1-20260930](https://github.com/Lantern567/synthetic-aviation-fuel-pathways-risks/releases/tag/nexus-r1-20260930), commit `d20ad94829016234eb434cfca1bd6dcd48911b78`, preserves the original thirteen model/result configurations. It provides the historical provenance for the seven retained comparators identified in the current data attachment. Its files and tag remain separate from the current fixed archive.

The manuscript is under review. Cite the fixed release tag and resolved commit. For reproduction questions or reuse permissions, contact Haoran Zhang at h.zhang@pku.edu.cn. The archive makes no new blanket licence grant.
