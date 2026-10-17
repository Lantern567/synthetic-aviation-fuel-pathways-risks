# -*- coding: utf-8 -*-
"""
Publication-ready decomposition figures for the three representative Pareto pathways.

Outputs:
- stable latest PNG/PDF files for appendix insertion
- archived copies in a timestamped session directory
- a summary JSON used by the appendix manuscript script
"""

from __future__ import annotations

import glob
import json
import logging
import shutil
import sys
from collections import OrderedDict as OD
from datetime import datetime
from pathlib import Path
from typing import Dict, List

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from cycler import cycler
from matplotlib.patches import Patch


SCRIPT_DIR = Path(__file__).resolve().parent
WORKSPACE_ROOT = SCRIPT_DIR.parent
REPO_ROOT = WORKSPACE_ROOT.parent
DEFAULT_OUTPUT_DIR = WORKSPACE_ROOT / "figures" / "redrawn"
DEFAULT_PREPARED_DIR = WORKSPACE_ROOT / "figures" / "prepared"
SCIENTIFIC_VIZ_SCRIPTS = Path.home() / ".codex" / "skills" / "scientific-visualization" / "scripts"
if SCIENTIFIC_VIZ_SCRIPTS.exists() and str(SCIENTIFIC_VIZ_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCIENTIFIC_VIZ_SCRIPTS))

try:
    from figure_export import save_publication_figure
except Exception:
    save_publication_figure = None


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


ACADEMIC_PALETTE = ["#E64B35", "#4DBBD5", "#00A087", "#3C5488", "#F39B7F", "#8491B4"]

FONT_CONFIG = {
    "label": 8.5,
    "tick": 7.0,
    "legend_text": 6.8,
    "annotation": 7.2,
    "line_width": 1.4,
}


def get_publication_rc() -> dict[str, object]:
    return {
        "font.family": "sans-serif",
        "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
        "axes.unicode_minus": False,
        "font.size": 8,
        "axes.titlesize": 8.5,
        "axes.labelsize": FONT_CONFIG["label"],
        "xtick.labelsize": FONT_CONFIG["tick"],
        "ytick.labelsize": FONT_CONFIG["tick"],
        "axes.linewidth": 0.7,
        "xtick.major.width": 0.7,
        "ytick.major.width": 0.7,
        "xtick.major.size": 3,
        "ytick.major.size": 3,
        "legend.fontsize": FONT_CONFIG["legend_text"],
        "legend.frameon": False,
        "figure.facecolor": "#FFFFFF",
        "axes.facecolor": "#FFFFFF",
        "savefig.facecolor": "#FFFFFF",
        "savefig.dpi": 300,
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
        "svg.fonttype": "none",
        "mathtext.fontset": "custom",
        "mathtext.rm": "Arial",
        "mathtext.it": "Arial:italic",
        "mathtext.bf": "Arial:bold",
        "mathtext.default": "regular",
        "axes.prop_cycle": cycler(color=ACADEMIC_PALETTE),
    }


plt.rcParams.update(get_publication_rc())


class ParetoBreakdownVisualizer:
    """Generate appendix-ready decomposition figures for three representative Pareto pathways."""

    def __init__(self, output_dir: str | Path | None = None, prepared_dir: str | Path | None = None):
        self.output_dir = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
        self.prepared_dir = Path(prepared_dir) if prepared_dir else DEFAULT_PREPARED_DIR
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.prepared_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_dir = self.output_dir / f"pareto_breakdown_{timestamp}"
        self.session_dir.mkdir(parents=True, exist_ok=True)

        logger.info("Appendix figure output directory: %s", self.session_dir)

        self.project_root = REPO_ROOT

        self.scenarios = OD(
            [
                (
                    "CTL",
                    {
                        "full_name": "Coal-to-Liquids Baseline",
                        "group": "Grey",
                        "solution_pattern": str(
                            self.project_root
                            / "products/supply_chain_optimization/coal_hydrogen_saf_optimization/results/complete_solution_*.json"
                        ),
                        "carbon_pattern": str(
                            self.project_root
                            / "products/supply_chain_optimization/coal_hydrogen_saf_optimization/results/carbon_emissions_detailed_*.json"
                        ),
                    },
                ),
                (
                    "CTL-BH",
                    {
                        "full_name": "Coal-to-Liquids with By-product H2",
                        "group": "Grey",
                        "solution_pattern": str(
                            self.project_root
                            / "products/supply_chain_optimization/coal_hydrogen_saf_optimization/results/byproduct_hydrogen/complete_solution_*.json"
                        ),
                        "carbon_pattern": str(
                            self.project_root
                            / "products/supply_chain_optimization/coal_hydrogen_saf_optimization/results/byproduct_hydrogen/carbon_emissions_detailed_*.json"
                        ),
                    },
                ),
                (
                    "CCU-BH-MTJ",
                    {
                        "full_name": "CCU with By-product H2 - MTJ",
                        "group": "Blue",
                        "solution_pattern": str(
                            self.project_root
                            / "products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/byproduct_hydrogen/two_step/complete_solution_*.json"
                        ),
                        "carbon_pattern": str(
                            self.project_root
                            / "products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/byproduct_hydrogen/two_step/carbon_emissions_detailed_*.json"
                        ),
                    },
                ),
                (
                    "CCU-BH-FT",
                    {
                        "full_name": "CCU with By-product H2 - FT",
                        "group": "Blue",
                        "solution_pattern": str(
                            self.project_root
                            / "products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/byproduct_hydrogen/one_step/complete_solution_*.json"
                        ),
                        "carbon_pattern": str(
                            self.project_root
                            / "products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/byproduct_hydrogen/one_step/carbon_emissions_detailed_*.json"
                        ),
                    },
                ),
                (
                    "DAC-BH-MTJ",
                    {
                        "full_name": "DAC with By-product H2 - MTJ",
                        "group": "Blue",
                        "solution_pattern": str(
                            self.project_root
                            / "products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/byproduct_hydrogen/two_step/complete_solution_*.json"
                        ),
                        "carbon_pattern": str(
                            self.project_root
                            / "products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/byproduct_hydrogen/two_step/carbon_emissions_detailed_*.json"
                        ),
                    },
                ),
                (
                    "DAC-BH-FT",
                    {
                        "full_name": "DAC with By-product H2 - FT",
                        "group": "Blue",
                        "solution_pattern": str(
                            self.project_root
                            / "products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/byproduct_hydrogen/one_step/complete_solution_*.json"
                        ),
                        "carbon_pattern": str(
                            self.project_root
                            / "products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/byproduct_hydrogen/one_step/carbon_emissions_detailed_*.json"
                        ),
                    },
                ),
                (
                    "GTL-BH",
                    {
                        "full_name": "GTL with By-product H2",
                        "group": "Blue",
                        "solution_pattern": str(
                            self.project_root
                            / "products/supply_chain_optimization/natural_gas_supply_chain_optimization/results/byproduct_hydrogen/byproduct_hydrogen/two_step/complete_solution_*.json"
                        ),
                        "carbon_pattern": str(
                            self.project_root
                            / "products/supply_chain_optimization/natural_gas_supply_chain_optimization/results/byproduct_hydrogen/byproduct_hydrogen/two_step/carbon_emissions_detailed_*.json"
                        ),
                    },
                ),
                (
                    "GTL-GH",
                    {
                        "full_name": "GTL-GH",
                        "group": "Blue",
                        "solution_pattern": str(
                            self.project_root
                            / "products/supply_chain_optimization/natural_gas_supply_chain_optimization/results/complete_solution_*.json"
                        ),
                        "carbon_pattern": str(
                            self.project_root
                            / "products/supply_chain_optimization/natural_gas_supply_chain_optimization/results/carbon_emissions_detailed_*.json"
                        ),
                    },
                ),
                (
                    "GTL",
                    {
                        "full_name": "GTL",
                        "group": "Blue",
                        "solution_pattern": str(
                            self.project_root
                            / "products/supply_chain_optimization/natural_gas_supply_chain_optimization/results/ft_one_step/complete_solution_*.json"
                        ),
                        "carbon_pattern": str(
                            self.project_root
                            / "products/supply_chain_optimization/natural_gas_supply_chain_optimization/results/ft_one_step/carbon_emissions_detailed_*.json"
                        ),
                    },
                ),
                (
                    "DAC-GH-MTJ",
                    {
                        "full_name": "DAC with Green H2 - MTJ",
                        "group": "Green",
                        "solution_pattern": str(
                            self.project_root
                            / "products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/two_step/complete_solution_*.json"
                        ),
                        "carbon_pattern": str(
                            self.project_root
                            / "products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/two_step/carbon_emissions_detailed_*.json"
                        ),
                    },
                ),
                (
                    "DAC-GH-FT",
                    {
                        "full_name": "DAC with Green H2 - FT",
                        "group": "Green",
                        "solution_pattern": str(
                            self.project_root
                            / "products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/one_step/complete_solution_*.json"
                        ),
                        "carbon_pattern": str(
                            self.project_root
                            / "products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/one_step/carbon_emissions_detailed_*.json"
                        ),
                    },
                ),
                (
                    "CCU-GH-MTJ",
                    {
                        "full_name": "CCU with Green H2 - MTJ",
                        "group": "Green",
                        "solution_pattern": str(
                            self.project_root
                            / "products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/two_step/complete_solution_*.json"
                        ),
                        "carbon_pattern": str(
                            self.project_root
                            / "products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/two_step/carbon_emissions_detailed_*.json"
                        ),
                    },
                ),
                (
                    "CCU-GH-FT",
                    {
                        "full_name": "CCU with Green H2 - FT",
                        "group": "Green",
                        "solution_pattern": str(
                            self.project_root
                            / "products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/one_step/complete_solution_*.json"
                        ),
                        "carbon_pattern": str(
                            self.project_root
                            / "products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/one_step/carbon_emissions_detailed_*.json"
                        ),
                    },
                ),
            ]
        )

        self.group_colors = {
            "Grey": ACADEMIC_PALETTE[5],
            "Blue": ACADEMIC_PALETTE[3],
            "Green": ACADEMIC_PALETTE[2],
        }

        self.pathway_roles = {
            "CCU-GH-FT": "Deep decarbonization",
            "GTL": "Transition case",
            "GTL-BH": "Lowest-cost frontier",
        }

        self.unified_categories = OD(
            [
                (
                    "Feedstock",
                    {
                        "short": "Feedstock",
                        "color": "#8491B4",
                        "carbon_keys": ["coal_mining", "ng_extraction"],
                        "cost_keys": ["coal_purchase_cost", "natural_gas_cost"],
                    },
                ),
                (
                    "Hydrogen System",
                    {
                        "short": "Hydrogen",
                        "color": "#4DBBD5",
                        "carbon_keys": ["h2_production", "electrolyzer_facility"],
                        "cost_keys": ["hydrogen_production_cost", "electrolyzer_investment_cost"],
                    },
                ),
                (
                    "CO2 Capture System",
                    {
                        "short": "CO2 Capture",
                        "color": "#F39B7F",
                        "carbon_keys": ["co2_capture_energy", "dac_equipment"],
                        "cost_keys": ["co2_capture_cost", "dac_capture_cost", "dac_facility_investment"],
                    },
                ),
                (
                    "Fuel Conversion",
                    {
                        "short": "Conversion",
                        "color": "#3C5488",
                        "carbon_keys": [
                            "coal_gasification_direct",
                            "coal_co2_fugitive",
                            "coal_gasification_energy",
                            "ng_to_methanol",
                            "methanol_to_saf",
                            "saf_synthesis_energy",
                            "ft_production",
                        ],
                        "cost_keys": [
                            "coal_gasification_cost",
                            "production_cost",
                            "methanol_production_cost",
                            "ft_production_cost",
                            "ft_reactor_operation_cost",
                            "ft_energy_cost",
                            "catalyst_cost",
                            "ft_catalyst_cost",
                        ],
                    },
                ),
                (
                    "Power & Utilities",
                    {
                        "short": "Power",
                        "color": "#E64B35",
                        "carbon_keys": ["dac_grid_electricity"],
                        "cost_keys": ["electricity_cost", "dac_grid_electricity_cost"],
                    },
                ),
                (
                    "Facilities & Equipment",
                    {
                        "short": "Facility",
                        "color": "#00A087",
                        "carbon_keys": ["saf_facility"],
                        "cost_keys": ["facility_investment_cost", "facility_operation_cost", "ft_reactor_investment_cost"],
                    },
                ),
                (
                    "Transport & Distribution",
                    {
                        "short": "Transport",
                        "color": "#94C7B2",
                        "carbon_keys": [
                            "coal_transport",
                            "ng_transport",
                            "h2_pipeline_transport",
                            "h2_truck_transport",
                            "h2_transport",
                            "co2_pipeline_transport",
                            "co2_truck_transport",
                            "co2_transport",
                            "mtj_transport",
                            "saf_transport",
                        ],
                        "cost_keys": [
                            "transport_operation_cost",
                            "hydrogen_transport_investment",
                            "hydrogen_transport_operation",
                            "hydrogen_pipeline_operation",
                            "ng_transport_investment",
                            "ng_transport_operation",
                            "co2_pipeline_transport_cost",
                            "co2_truck_transport_cost",
                            "saf_transport_investment",
                            "saf_transport_operation",
                        ],
                    },
                ),
                (
                    "Storage",
                    {
                        "short": "Storage",
                        "color": "#C7D4E9",
                        "carbon_keys": ["h2_storage", "mtj_storage", "saf_storage"],
                        "cost_keys": [
                            "storage_equipment_cost",
                            "storage_operation_cost",
                            "h2_storage_investment",
                            "h2_storage_operation",
                            "methanol_storage_equipment_cost",
                            "methanol_storage_investment",
                            "methanol_storage_operation",
                            "methanol_storage_operation_cost",
                            "co2_storage_investment",
                            "co2_storage_operation",
                            "final_inventory_cost",
                        ],
                    },
                ),
            ]
        )

        self.data: Dict[str, Dict] = {}
        self.selected_pareto: List[str] = []

    @staticmethod
    def _find_latest_file(pattern: str) -> Path | None:
        files = sorted(glob.glob(pattern), reverse=True)
        return Path(files[0]) if files else None

    @staticmethod
    def _safe_float(value) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    def _extract_carbon_diff(self, carbon_data: Dict) -> float:
        carbon_diff = carbon_data.get("abs_diff_vs_traditional_jet_gco2e_per_mj")
        if carbon_diff is not None:
            return self._safe_float(carbon_diff)

        traditional_jet_ci = self._safe_float(carbon_data.get("traditional_jet_ci_gco2e_per_mj", 89))
        if "carbon_intensity_mj" in carbon_data:
            return self._safe_float(carbon_data.get("carbon_intensity_mj")) - traditional_jet_ci

        return traditional_jet_ci * self._safe_float(carbon_data.get("vs_traditional_jet")) / 100.0

    def load_data(self) -> None:
        logger.info("Loading latest results for the 13 archived pathways")

        for scenario_label, config in self.scenarios.items():
            solution_path = self._find_latest_file(config["solution_pattern"])
            carbon_path = self._find_latest_file(config["carbon_pattern"])

            if solution_path is None or carbon_path is None:
                logger.warning("Skipping %s because one or more result files are missing", scenario_label)
                continue

            with solution_path.open("r", encoding="utf-8") as file:
                solution_data = json.load(file)
            with carbon_path.open("r", encoding="utf-8") as file:
                carbon_data = json.load(file)

            detailed_emissions = carbon_data.get("detailed", {})
            cost_breakdown = solution_data.get("cost_breakdown", {})

            gross_emissions = sum(max(self._safe_float(value), 0.0) for value in detailed_emissions.values())
            credit_emissions = sum(min(self._safe_float(value), 0.0) for value in detailed_emissions.values())

            record = {
                "label": scenario_label,
                "full_name": config["full_name"],
                "group": config["group"],
                "solution_path": str(solution_path),
                "carbon_path": str(carbon_path),
                "solution": solution_data,
                "carbon": carbon_data,
                "cost_breakdown": cost_breakdown,
                "detailed_emissions": detailed_emissions,
                "total_cost": self._safe_float(cost_breakdown.get("total_cost_excluding_shortage")),
                "lcoe": self._safe_float(solution_data.get("lifecycle_levelized_cost_excluding_shortage_per_kg")),
                "net_emissions": self._safe_float(carbon_data.get("by_stage", {}).get("total_emissions")),
                "gross_emissions": gross_emissions,
                "credit_emissions": credit_emissions,
                "carbon_diff": self._extract_carbon_diff(carbon_data),
            }
            self.data[scenario_label] = record

            logger.info(
                "%s | LCO-SAF = %.3f CNY/kg | delta vs jet = %.3f gCO2e/MJ",
                scenario_label,
                record["lcoe"],
                record["carbon_diff"],
            )

        logger.info("Loaded %d scenarios", len(self.data))

    @staticmethod
    def _identify_pareto_frontier(data: Dict[str, Dict]) -> List[str]:
        sorted_items = sorted(
            data.items(),
            key=lambda item: (item[1]["carbon_diff"], item[1]["lcoe"]),
        )

        pareto_labels: List[str] = []
        best_cost = float("inf")
        for label, scenario in sorted_items:
            if float(scenario["lcoe"]) < best_cost - 1e-9:
                pareto_labels.append(label)
                best_cost = float(scenario["lcoe"])
        return pareto_labels

    @staticmethod
    def _select_three_representative_pareto(pareto_labels: List[str], data: Dict[str, Dict]) -> List[str]:
        ordered = sorted(pareto_labels, key=lambda label: data[label]["carbon_diff"])
        if len(ordered) <= 3:
            return ordered

        middle_index = len(ordered) // 2
        selected = [ordered[0], ordered[middle_index], ordered[-1]]
        unique_selected: List[str] = []
        for label in selected:
            if label not in unique_selected:
                unique_selected.append(label)
        return unique_selected

    def identify_selected_pareto(self) -> None:
        pareto_labels = self._identify_pareto_frontier(self.data)
        self.selected_pareto = self._select_three_representative_pareto(pareto_labels, self.data)

        logger.info("Pareto frontier: %s", ", ".join(pareto_labels))
        logger.info("Representative appendix pathways: %s", ", ".join(self.selected_pareto))

    def _aggregate_unified_breakdown(self, source: Dict, metric_type: str, include_zero: bool = True) -> List[Dict]:
        key_field = "carbon_keys" if metric_type == "carbon" else "cost_keys"
        breakdown: List[Dict] = []

        for category_name, config in self.unified_categories.items():
            value = sum(self._safe_float(source.get(key, 0.0)) for key in config[key_field])
            value = max(value, 0.0)
            if not include_zero and value <= 0:
                continue

            breakdown.append(
                {
                    "name": category_name,
                    "short": config["short"],
                    "value": value,
                    "color": config["color"],
                }
            )

        total_value = sum(item["value"] for item in breakdown)
        for item in breakdown:
            item["pct"] = item["value"] / total_value * 100.0 if total_value > 0 else 0.0

        return breakdown

    def _build_metric_table(self, metric_type: str) -> dict:
        scenario_breakdowns: dict[str, dict[str, Dict]] = {}
        category_totals: dict[str, float] = {name: 0.0 for name in self.unified_categories}

        for scenario_label in self.selected_pareto:
            record = self.data[scenario_label]
            source = record["cost_breakdown"] if metric_type == "cost" else record["detailed_emissions"]
            breakdown = self._aggregate_unified_breakdown(source, metric_type=metric_type, include_zero=True)
            by_name = {item["name"]: item for item in breakdown}
            scenario_breakdowns[scenario_label] = by_name
            for item in breakdown:
                category_totals[item["name"]] += item["value"]

        categories = [
            name
            for name, total in sorted(category_totals.items(), key=lambda item: item[1], reverse=True)
            if total > 0
        ]

        matrix = np.array(
            [
                [scenario_breakdowns[scenario_label][category]["value"] for category in categories]
                for scenario_label in self.selected_pareto
            ],
            dtype=float,
        )

        return {
            "categories": categories,
            "matrix": matrix,
        }

    def _scenario_label(self, scenario_label: str) -> str:
        role = self.pathway_roles.get(scenario_label)
        if not role:
            return scenario_label
        return f"{scenario_label}\n{role}"

    def _scenario_card_text(self, scenario_label: str, metric_type: str) -> str:
        record = self.data[scenario_label]
        role = self.pathway_roles.get(scenario_label, "Representative frontier")

        if metric_type == "cost":
            return "\n".join(
                [
                    scenario_label,
                    role,
                    f"LCO-SAF: {record['lcoe']:.2f} CNY/kg",
                    f"Total cost: {record['total_cost'] / 1e9:.2f} bn CNY",
                ]
            )

        return "\n".join(
            [
                scenario_label,
                role,
                f"Delta vs jet: {record['carbon_diff']:+.1f} gCO2e/MJ",
                f"Net emissions: {record['net_emissions'] / 1e6:.2f} Mkg CO2e",
                f"Credits: {record['credit_emissions'] / 1e6:.2f} Mkg CO2e",
            ]
        )

    def _metric_spec(self, metric_type: str) -> dict:
        if metric_type == "cost":
            return {
                "title": "Cost composition of representative Pareto pathways",
                "subtitle": "Shared eight-category mapping across the deep-decarbonization, transition, and lowest-cost frontier cases.",
                "xlabel": "Cost contribution (billion CNY)",
                "scale": 1e9,
                "stable_stem": "pareto_cost_breakdown_appendix",
                "prepared_name": "pareto_cost_appendix.png",
                "note": None,
            }

        return {
            "title": "Positive emissions composition of representative Pareto pathways",
            "subtitle": "Stacks show positive lifecycle contributions only so that negative credit terms remain auditable as separate net annotations.",
            "xlabel": "Positive emissions contribution (million kg CO2e)",
            "scale": 1e6,
            "stable_stem": "pareto_carbon_breakdown_appendix",
            "prepared_name": "pareto_carbon_appendix.png",
            "note": None,
        }

    def _save_figure(self, fig: plt.Figure, stable_stem: str, prepared_name: str) -> dict[str, Path]:
        session_png = self.session_dir / f"{stable_stem}.png"
        session_pdf = self.session_dir / f"{stable_stem}.pdf"
        session_svg = self.session_dir / f"{stable_stem}.svg"
        if save_publication_figure is not None:
            save_publication_figure(
                fig,
                self.session_dir / stable_stem,
                formats=["png", "pdf", "svg"],
                dpi=300,
                bbox_inches="tight",
                pad_inches=0.04,
                facecolor=fig.get_facecolor(),
            )
        else:
            fig.savefig(session_png, dpi=300, bbox_inches="tight", pad_inches=0.04, facecolor=fig.get_facecolor())
            fig.savefig(session_pdf, bbox_inches="tight", pad_inches=0.04, facecolor=fig.get_facecolor())
            fig.savefig(session_svg, bbox_inches="tight", pad_inches=0.04, facecolor=fig.get_facecolor())

        stable_png = self.output_dir / f"{stable_stem}_latest.png"
        stable_pdf = self.output_dir / f"{stable_stem}_latest.pdf"
        stable_svg = self.output_dir / f"{stable_stem}_latest.svg"
        shutil.copy2(session_png, stable_png)
        shutil.copy2(session_pdf, stable_pdf)
        shutil.copy2(session_svg, stable_svg)

        prepared_png = self.prepared_dir / prepared_name
        prepared_pdf = prepared_png.with_suffix(".pdf")
        prepared_svg = prepared_png.with_suffix(".svg")
        shutil.copy2(session_png, prepared_png)
        shutil.copy2(session_pdf, prepared_pdf)
        shutil.copy2(session_svg, prepared_svg)

        logger.info("Saved figure: %s", session_png)
        return {
            "session_png": session_png,
            "session_pdf": session_pdf,
            "session_svg": session_svg,
            "stable_png": stable_png,
            "stable_pdf": stable_pdf,
            "stable_svg": stable_svg,
            "prepared_png": prepared_png,
            "prepared_pdf": prepared_pdf,
            "prepared_svg": prepared_svg,
        }

    def create_appendix_metric_figure(self, metric_type: str) -> dict[str, Path]:
        spec = self._metric_spec(metric_type)
        metric_table = self._build_metric_table(metric_type)

        categories = metric_table["categories"]
        matrix = metric_table["matrix"] / spec["scale"]
        y_positions = np.arange(len(self.selected_pareto))
        totals = matrix.sum(axis=1)

        with plt.rc_context(get_publication_rc()):
            fig = plt.figure(figsize=(7.2, 4.1), dpi=300)
            grid = fig.add_gridspec(
                1,
                2,
                width_ratios=[4.0, 1.55],
                left=0.09,
                right=0.985,
                top=0.95,
                bottom=0.21,
                wspace=0.10,
            )
            ax = fig.add_subplot(grid[0, 0])
            ax_info = fig.add_subplot(grid[0, 1])
            ax_info.axis("off")

            left = np.zeros(len(self.selected_pareto))
            for category in categories:
                values = matrix[:, categories.index(category)]
                ax.barh(
                    y_positions,
                    values,
                    left=left,
                    height=0.56,
                    color=self.unified_categories[category]["color"],
                    edgecolor="white",
                    linewidth=0.7,
                    zorder=3,
                )
                left += values

            max_total = float(totals.max()) if len(totals) else 1.0
            x_pad = max(max_total * 0.06, 0.10)
            ax.set_xlim(0, max_total + x_pad * 3.2)
            ax.set_xlabel(spec["xlabel"], labelpad=3)
            ax.set_yticks(y_positions)
            ax.set_yticklabels([self._scenario_label(label) for label in self.selected_pareto])
            ax.invert_yaxis()
            ax.xaxis.grid(True, linestyle="--", linewidth=0.7, color="#CBD5E1", alpha=0.55)
            ax.set_axisbelow(True)
            ax.spines["top"].set_visible(False)
            ax.spines["right"].set_visible(False)
            ax.spines["left"].set_color("#CBD5E1")
            ax.spines["bottom"].set_color("#CBD5E1")
            ax.tick_params(axis="y", length=0, labelsize=FONT_CONFIG["tick"])
            ax.tick_params(axis="x", labelsize=FONT_CONFIG["tick"])

            for y_value, total in zip(y_positions, totals):
                ax.text(
                    total + x_pad * 0.30,
                    y_value,
                    f"{total:.2f}",
                    va="center",
                    ha="left",
                    fontsize=FONT_CONFIG["annotation"],
                    fontweight="bold",
                    color="#0F172A",
                )

            card_y_positions = np.linspace(0.92, 0.28, len(self.selected_pareto))
            for y_anchor, scenario_label in zip(card_y_positions, self.selected_pareto):
                record = self.data[scenario_label]
                ax_info.plot(
                    [0.04, 0.04],
                    [y_anchor - 0.12, y_anchor],
                    transform=ax_info.transAxes,
                    color=self.group_colors[record["group"]],
                    linewidth=2.0,
                    solid_capstyle="round",
                )
                ax_info.text(
                    0.09,
                    y_anchor,
                    self._scenario_card_text(scenario_label, metric_type),
                    transform=ax_info.transAxes,
                    va="top",
                    ha="left",
                    fontsize=FONT_CONFIG["annotation"],
                    linespacing=1.28,
                    color="#0F172A",
                )

            handles = [Patch(facecolor=self.unified_categories[category]["color"], label=category) for category in categories]
            fig.legend(
                handles=handles,
                ncol=4,
                loc="lower center",
                bbox_to_anchor=(0.5, 0.06),
                frameon=False,
                fontsize=FONT_CONFIG["legend_text"],
                columnspacing=0.9,
                handlelength=1.2,
            )

        if spec["note"]:
            fig.text(0.09, 0.02, spec["note"], fontsize=FONT_CONFIG["annotation"], color="#64748B")

        output_paths = self._save_figure(fig, spec["stable_stem"], spec["prepared_name"])
        plt.close(fig)
        return output_paths

    def export_summary(self) -> dict[str, Path]:
        summary = []
        for rank, scenario_label in enumerate(self.selected_pareto, start=1):
            record = self.data[scenario_label]
            summary.append(
                {
                    "rank": rank,
                    "scenario": scenario_label,
                    "full_name": record["full_name"],
                    "group": record["group"],
                    "lcoe_cny_per_kg": record["lcoe"],
                    "carbon_diff_vs_jet_gco2e_per_mj": record["carbon_diff"],
                    "total_cost_cny": record["total_cost"],
                    "net_emissions_kg": record["net_emissions"],
                    "gross_emissions_kg": record["gross_emissions"],
                    "credit_emissions_kg": record["credit_emissions"],
                    "solution_path": record["solution_path"],
                    "carbon_path": record["carbon_path"],
                    "carbon_breakdown_unified": self._aggregate_unified_breakdown(
                        record["detailed_emissions"],
                        metric_type="carbon",
                        include_zero=True,
                    ),
                    "cost_breakdown_unified": self._aggregate_unified_breakdown(
                        record["cost_breakdown"],
                        metric_type="cost",
                        include_zero=True,
                    ),
                }
            )

        session_summary = self.session_dir / "pareto_breakdown_summary.json"
        with session_summary.open("w", encoding="utf-8") as file:
            json.dump(summary, file, ensure_ascii=False, indent=2)

        stable_summary = self.output_dir / "pareto_breakdown_summary_latest.json"
        prepared_summary = self.prepared_dir / "pareto_breakdown_summary_latest.json"
        shutil.copy2(session_summary, stable_summary)
        shutil.copy2(session_summary, prepared_summary)
        logger.info("Saved summary JSON: %s", session_summary)

        return {
            "session_json": session_summary,
            "stable_json": stable_summary,
            "prepared_json": prepared_summary,
        }

    def run(self) -> dict[str, Path]:
        logger.info("Generating representative Pareto appendix figures")
        self.load_data()
        if len(self.data) < 3:
            raise RuntimeError(f"Insufficient scenario results: only {len(self.data)} were loaded")

        self.identify_selected_pareto()
        if not self.selected_pareto:
            raise RuntimeError("No Pareto pathway was identified")

        cost_paths = self.create_appendix_metric_figure("cost")
        carbon_paths = self.create_appendix_metric_figure("carbon")
        summary_paths = self.export_summary()

        return {
            "cost_png": cost_paths["prepared_png"],
            "cost_pdf": cost_paths["stable_pdf"],
            "carbon_png": carbon_paths["prepared_png"],
            "carbon_pdf": carbon_paths["stable_pdf"],
            "summary_json": summary_paths["prepared_json"],
        }


def generate_appendix_pareto_assets(
    output_dir: str | Path | None = None,
    prepared_dir: str | Path | None = None,
) -> dict[str, Path]:
    visualizer = ParetoBreakdownVisualizer(output_dir=output_dir, prepared_dir=prepared_dir)
    return visualizer.run()


def main() -> None:
    assets = generate_appendix_pareto_assets()
    for name, path in assets.items():
        logger.info("%s -> %s", name, path)


if __name__ == "__main__":
    main()
