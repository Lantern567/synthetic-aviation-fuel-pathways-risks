# Synthetic aviation fuel pathway research

Code and archived results for *Infrastructure incompatibility across synthetic aviation fuel pathways risks stranding decarbonization investments* by Junteng Liao and Haoran Zhang.

## Fixed Nexus revision archive

[Download the fixed revision archive nexus-r1-20260930](https://github.com/Lantern567/synthetic-aviation-fuel-pathways-risks/releases/tag/nexus-r1-20260930)

[Browse the versioned source and documentation](https://github.com/Lantern567/synthetic-aviation-fuel-pathways-risks/tree/nexus-r1-20260930)

The release preserves the original 13 pathway results, model sources and configurations, supplementary calculation tables, Supplementary Information and a companion figure archive. The release README documents provenance, required inputs and the reproduction scope.

After extracting the release ZIP, run from its root directory with Python 3.12 or later:

```bash
python archive_tools/reproduce.py --output work/reproduced
```

This tested entry point verifies file hashes, associates outputs with solver records, checks retained temporal-index records and reproduces the archived summary tables. It does not launch optimization or certify complete physical feasibility. Eight original runs reached the 1% target MIP gap; five reached the time limit, with achieved gaps retained in the archive. The supplementary documents describe the scientific scope and limitations.

The release is a snapshot of the current revision, not a claim that all scientific validation is complete. The manuscript is under review. For citations, use the fixed tag and resolved commit rather than the moving main branch.

For reproduction questions or reuse permissions, contact Haoran Zhang at h.zhang@pku.edu.cn. The archive does not introduce a new open-source license grant.
