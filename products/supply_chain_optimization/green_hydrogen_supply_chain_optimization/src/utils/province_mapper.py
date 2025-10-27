"""Utility helpers to enrich CO? capture source records with province metadata.

The CSV generated for CO? capture sources is assembled from multiple GIS datasets.
A subset of the records might miss the human readable province column because the
original GIS exports use non-standard field names.  To keep the optimisation
pipeline robust we provide a lightweight mapper that rehydrates the province
information from the raw GIS dumps before the model consumes the data.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable, Optional

import pandas as pd

# Keys that should be present in the GIS configuration definition.
_REQUIRED_CONFIG_FIELDS: Iterable[str] = (
    "file_name",
    "name_col",
    "lat_col",
    "lon_col",
    "province_col",
)


def _project_root() -> Path:
    """Return the absolute path to the repository root."""

    return Path(__file__).resolve().parents[5]


def _gis_dir() -> Path:
    """Location of the scraped GIS data used for back-filling provinces."""

    return (
        _project_root()
        / "products"
        / "gis_energy_mapping"
        / "gis_data_scraper"
        / "scraped_gis_data"
    )


# Minimal configuration describing how to extract match keys for each facility type.
_GIS_DATA_SPECS: Dict[str, Dict[str, str]] = {
    "coal_power": {
        "file_name": "coal_power_plants.csv",
        "name_col": "Plant_name",
        "lat_col": "Latitude",
        "lon_col": "Longitude",
        "province_col": "Subnational_unit__province__sta",
    },
    "gas_power": {
        "file_name": "gas_power_plants.csv",
        "name_col": "Name",
        "lat_col": "Lat",
        "lon_col": "Long",
        "province_col": "Province",
    },
    "oil_refinery": {
        "file_name": "oil_refineries.csv",
        "name_col": "Name",
        "lat_col": "Lat",
        "lon_col": "Long",
        "province_col": "Province",
    },
}

# Cache to avoid re-reading the GIS CSV multiple times during a single run.
_PROVINCE_LOOKUP_CACHE: Dict[str, Dict[str, str]] = {}


def _build_match_key(series: pd.Series) -> pd.Series:
    """Create a deterministic match key from name and coordinates."""

    name = series.iloc[:, 0].astype(str).str.strip()
    lat = pd.to_numeric(series.iloc[:, 1], errors="coerce").round(6)
    lon = pd.to_numeric(series.iloc[:, 2], errors="coerce").round(6)
    return name + "_" + lat.astype(str) + "_" + lon.astype(str)


def _load_province_map(facility_type: str) -> Dict[str, str]:
    """Load the GIS province lookup for a single facility type."""

    if facility_type in _PROVINCE_LOOKUP_CACHE:
        return _PROVINCE_LOOKUP_CACHE[facility_type]

    spec = _GIS_DATA_SPECS.get(facility_type)
    if not spec:
        _PROVINCE_LOOKUP_CACHE[facility_type] = {}
        return {}

    missing_fields = [field for field in _REQUIRED_CONFIG_FIELDS if field not in spec]
    if missing_fields:
        raise ValueError(
            f"GIS specification for '{facility_type}' is missing keys: {missing_fields}"
        )

    dataset_path = _gis_dir() / spec["file_name"]
    if not dataset_path.exists():
        _PROVINCE_LOOKUP_CACHE[facility_type] = {}
        return {}

    required_columns = [
        spec["name_col"],
        spec["lat_col"],
        spec["lon_col"],
        spec["province_col"],
    ]

    data = pd.read_csv(dataset_path, encoding="utf-8-sig")

    for column in required_columns:
        if column not in data.columns:
            _PROVINCE_LOOKUP_CACHE[facility_type] = {}
            return {}

    # Drop rows where coordinates are missing ¨C matching would fail anyway.
    data = data.dropna(subset=[spec["lat_col"], spec["lon_col"]])

    # Prepare the match key used for lookups.
    match_input = data[[spec["name_col"], spec["lat_col"], spec["lon_col"]]]
    data["match_key"] = _build_match_key(match_input)

    province_map = (
        data[["match_key", spec["province_col"]]]
        .dropna(subset=[spec["province_col"]])
        .assign(**{spec["province_col"]: lambda df: df[spec["province_col"]].astype(str).str.strip()})
        .set_index("match_key")[spec["province_col"]]
        .to_dict()
    )

    _PROVINCE_LOOKUP_CACHE[facility_type] = province_map
    return province_map


def enrich_province_info(df: pd.DataFrame, logger: Optional[object] = None) -> pd.DataFrame:
    """Return a copy of *df* with missing province values filled using GIS lookups."""

    if df.empty:
        return df

    working_df = df.copy()
    if "province" not in working_df.columns:
        working_df["province"] = "Unknown"

    # Normalise province strings before attempting a lookup.
    working_df["province"] = (
        working_df["province"].fillna("Unknown").replace({"": "Unknown"}).astype(str).str.strip()
    )

    # We only touch rows where the province is still unknown.
    unknown_mask = working_df["province"].isin({"", "Unknown", "nan", "NaN"})
    if not unknown_mask.any():
        return working_df

    # Provide a lightweight shim for logging without hard dependency.
    def _log(level: str, message: str) -> None:
        if logger is None:
            return
        log_method = getattr(logger, level, None)
        if callable(log_method):
            log_method(message)

    _log("info", f"Backfilling province for {int(unknown_mask.sum())} CO? sources")

    for facility_type, spec in _GIS_DATA_SPECS.items():
        type_mask = (working_df["facility_type"] == facility_type) & unknown_mask
        if not type_mask.any():
            continue

        province_map = _load_province_map(facility_type)
        if not province_map:
            _log(
                "warning",
                f"Province lookup for facility type '{facility_type}' is unavailable; remaining rows stay Unknown",
            )
            continue

        match_input = working_df.loc[
            type_mask, ["location_name", "latitude", "longitude"]
        ].copy()
        match_input["match_key"] = _build_match_key(match_input)

        working_df.loc[type_mask, "province"] = match_input["match_key"].map(province_map).fillna(
            working_df.loc[type_mask, "province"]
        )

        still_unknown = (working_df.loc[type_mask, "province"] == "Unknown").sum()
        _log(
            "info",
            "Facility type '%s': resolved %d records, %d still unknown" % (
                facility_type,
                type_mask.sum() - still_unknown,
                still_unknown,
            ),
        )

        # Update the unknown mask so further types do not reprocess resolved rows.
        unknown_mask = working_df["province"].isin({"", "Unknown", "nan", "NaN"})

    return working_df
