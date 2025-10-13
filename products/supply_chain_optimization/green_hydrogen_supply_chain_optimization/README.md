# Green Hydrogen Supply Chain Optimization

## Project Overview

This project implements a **Mixed Integer Linear Programming (MILP)** model for optimizing the supply chain of Sustainable Aviation Fuel (SAF) production using green hydrogen and CO₂ capture through a two-step process:

**Process**: Green H₂ + CO₂ → Methanol → SAF (E-CRM + MTJ)

### Key Features

- **Green Hydrogen Production**: Electrolysis powered by renewable energy (wind/solar)
- **CO₂ Capture**: Integration with industrial CO₂ capture sources (coal/gas power plants, oil refineries)
- **Two-Step Chemical Process**:
  - Step 1: H₂ + CO₂ → Methanol (E-CRM electro-chemical reduction)
  - Step 2: Methanol → SAF (MTJ methanol-to-jet conversion)
- **Multi-Modal Transport**: Pipeline and truck transport for both H₂ and CO₂
- **Time-Scale Matching**: Weekly CO₂ supply vs hourly production scheduling
- **Carbon Emission Tracking**: Full lifecycle carbon intensity calculation
- **Gurobi Optimization**: Large-scale MILP solver for supply chain optimization

### Technology Stack

- **Optimization**: Gurobi 11.0+ (MILP solver)
- **Data Processing**: pandas, numpy
- **Geospatial**: GraphHopper routing engine, OSM data
- **Visualization**: matplotlib, pydeck
- **Configuration**: YAML-based parameter management

## Project Structure

```
green_hydrogen_supply_chain_optimization/
├── src/                                    # Source code
│   ├── core/                              # Core optimization model
│   │   ├── __init__.py
│   │   └── green_hydrogen_optimization_model.py  # Main optimizer class
│   │
│   ├── co2/                               # CO₂ capture and emission modules
│   │   ├── __init__.py
│   │   ├── co2_capture_calculator.py     # CO₂ capture quantity calculation
│   │   └── co2_emission_calculator.py    # Lifecycle carbon emission calculation
│   │
│   ├── hydrogen/                          # Hydrogen processing modules
│   │   ├── __init__.py
│   │   ├── hydrogen_clustering_optimizer.py
│   │   ├── hydrogen_pipeline_distance_calculator.py
│   │   └── hydrogen_transport_visualizer.py
│   │
│   ├── routing/                           # Route planning modules
│   │   ├── __init__.py
│   │   ├── graphhopper_routing_engine.py
│   │   ├── osm_routing_engine.py
│   │   └── pipeline_coordinate_integrator.py
│   │
│   ├── cache/                             # Cache management
│   │   └── data_cache_manager.py
│   │
│   ├── visualization/                     # Visualization tools
│   │   ├── transport_route_visualizer.py
│   │   └── method_comparison_visualizer.py
│   │
│   ├── utils/                             # Utility functions
│   │   └── direct_capacity_preprocessor.py
│   │
│   └── sensitivity_analysis/              # Sensitivity analysis
│       └── fast_sensitivity_analyzer.py
│
├── data/                                  # Data files
│   ├── co2_capture_sources.csv           # CO₂ capture source data (generated)
│   └── china-latest.osm.pbf              # OSM map data (download required)
│
├── results/                               # Output results
│   ├── tables/                           # Result tables (CSV)
│   ├── figures/                          # Visualizations (PNG, HTML)
│   ├── reports/                          # Analysis reports
│   └── logs/                             # Execution logs
│
├── tests/                                 # Unit tests
│   └── test_phase7_methods.py
│
├── README.md                              # This file
└── requirements.txt                       # Python dependencies
```

## Installation

### 1. Prerequisites

- Python 3.12+
- Conda (recommended) or virtualenv
- Gurobi 11.0+ with valid license
- (Optional) GraphHopper server for routing

### 2. Environment Setup

```bash
# Create conda environment
conda create -n green_h2_saf python=3.12
conda activate green_h2_saf

# Install dependencies
pip install -r requirements.txt

# Install Gurobi (if not already installed)
conda install -c gurobi gurobi

# Activate Gurobi license
grbgetkey YOUR_LICENSE_KEY
```

### 3. Data Preparation

**CO₂ Capture Source Data:**
- GIS data files required in: `products/gis_energy_mapping/gis_data_scraper/scraped_gis_data/`
  - `coal_power_plants.csv`
  - `gas_power_plants.csv`
  - `oil_refineries.csv`

**Airport Data:**
- Excel file with airport demand data
- Path configured in: `shared/data/GreenHydrogenSupplyChainOptimizer_config.yaml`

**Renewable Energy Data:**
- Wind and solar generation data (hourly)
- Path configured in config file

**OSM Map Data (Optional):**
```bash
# Download China OSM data for GraphHopper routing
wget https://download.geofabrik.de/asia/china-latest.osm.pbf -P data/
```

## Configuration

The optimizer is configured through `shared/data/GreenHydrogenSupplyChainOptimizer_config.yaml`.

### Key Configuration Sections

**Basic Parameters:**
```yaml
basic_parameters:
  time_horizon_weeks: 1              # Optimization time horizon
  hours_per_week: 168                # Hours per week (7*24)
  use_graphhopper_routing: true      # Enable GraphHopper routing
  max_transport_distance_km: 1000.0  # Max transport distance
```

**CO₂ Parameters:**
```yaml
co2_parameters:
  capture_sources:
    coal_power_capture_rate: 0.85    # Coal plant capture rate
    lng_power_capture_rate: 0.90     # LNG plant capture rate
    oil_refinery_capture_rate: 0.80  # Refinery capture rate

  transport:
    pipeline_transport_cost_function:
      function_type: piecewise_linear
      data_points:                   # [distance(km), cost(yuan/ton/100km)]
        - [25, 12.0]
        - [50, 8.5]
        - [100, 5.0]
        # ... more points
```

**Technology Parameters:**
```yaml
technologies:
  methanol_mtj_two_step:
    h2_consumption_ratio: 0.20       # kg H₂/kg SAF
    co2_consumption_ratio: 3.5       # kg CO₂/kg SAF
    methanol_intermediate_ratio: 1.3 # kg methanol/kg SAF
    efficiency: 0.70                 # Overall efficiency
```

## Usage

### Basic Usage

```python
from core import GreenHydrogenSupplyChainOptimizer
import pandas as pd

# 1. Initialize optimizer
optimizer = GreenHydrogenSupplyChainOptimizer(
    time_horizon_weeks=1,
    use_graphhopper_routing=False  # Set to True if GraphHopper is available
)

# 2. Load data
renewable_data = pd.read_csv('renewable_energy_data.csv')  # Your renewable data
airport_excel_path = 'path/to/airport_data.xlsx'

optimizer.load_data_from_excel(
    airport_excel_path=airport_excel_path,
    renewable_data=renewable_data
)

# 3. Run optimization
optimizer.optimize()

# 4. Get results
results = optimizer.get_optimization_results()
print(f"Total cost: {results['total_cost']:,.2f} yuan")
print(f"SAF production: {results['total_saf_production']:,.2f} kg")
```

### Advanced Usage with Custom Parameters

```python
# Override config parameters
optimizer = GreenHydrogenSupplyChainOptimizer(
    time_horizon_weeks=4,
    use_graphhopper_routing=True,
    solver_time_limit=3600,  # 1 hour time limit
    solver_mip_gap=0.01      # 1% optimality gap
)

# Access specific results
co2_supply = optimizer.get_co2_supply_plan()
h2_transport = optimizer.get_hydrogen_transport_plan()
methanol_production = optimizer.get_methanol_production_schedule()
```

## Model Formulation

### Decision Variables

**Production Variables:**
- `methanol_production[j,t]`: Methanol production at location j, hour t (kg/h)
- `saf_production[j,tech,t]`: SAF production at location j using technology tech, hour t (kg/h)

**Transport Variables:**
- `co2_pipeline_transport[c,j,w]`: CO₂ pipeline transport from source c to location j, week w (kg)
- `co2_truck_transport[c,j,w]`: CO₂ truck transport (kg)
- `h2_pipeline_transport[i,j,t]`: H₂ pipeline transport (kg)
- `h2_truck_transport[i,j,t]`: H₂ truck transport (kg)

**Inventory Variables:**
- `methanol_inventory[j,t]`: Methanol inventory at location j, hour t (kg)
- `co2_inventory[j,t]`: CO₂ inventory for time-scale matching (kg)
- `saf_inventory[k,t]`: SAF inventory at airport k (kg)

**Facility Variables:**
- `facility_build[j,tech]`: Binary decision to build facility at location j

### Constraints

1. **CO₂ Supply Balance** (weekly)
2. **Methanol Production** (H₂ + CO₂ → Methanol, hourly)
3. **SAF Production** (Methanol → SAF, hourly)
4. **Methanol Inventory Balance** (hourly)
5. **CO₂ Inventory Balance** (time-scale matching, hourly)
6. **H₂ Supply Balance** (hourly)
7. **SAF Demand Satisfaction** (airport demand, weekly)
8. **Transport Capacity Limits**
9. **Facility Capacity Limits**

### Objective Function

Minimize total cost:
```
Total Cost =
  + H₂ Production Cost
  + CO₂ Capture Cost
  + CO₂ Transport Cost (pipeline + truck)
  + H₂ Transport Cost (pipeline + truck)
  + Methanol Production Cost
  + Methanol Storage Cost
  + SAF Production Cost
  + SAF Transport Cost
  + Facility Investment Cost
  + Shortage Penalty
```

## Output Files

The optimizer generates the following output files in `results/` directory:

**Tables (CSV):**
- `optimization_summary_{timestamp}.csv`: Overall optimization results
- `facility_decisions_{timestamp}.csv`: Facility location decisions
- `co2_supply_plan_{timestamp}.csv`: CO₂ supply schedule
- `hydrogen_supply_plan_{timestamp}.csv`: H₂ supply schedule
- `saf_production_plan_{timestamp}.csv`: SAF production schedule
- `carbon_emission_report_{timestamp}.csv`: Carbon emission analysis

**Figures (PNG/HTML):**
- Transport route visualizations
- Cost breakdown charts
- Carbon emission comparisons

## Development

### Running Tests

```bash
# Run Phase 6 constraint tests
python test_phase6_constraints.py

# Run Phase 7 integration tests
python test_phase7_small.py
```

### Code Structure

- **Modularity**: Each module has a single responsibility
- **Type Hints**: All functions use type annotations
- **Documentation**: Comprehensive docstrings for all public methods
- **Logging**: Detailed logging for debugging and monitoring

### Development Status

**Completed Phases (Phase 0-6):**
- ✓ Phase 0-5: CO₂ module, configuration, carbon emission calculator
- ✓ Phase 6: Core model refactoring (decision variables, constraints, objective function)

**Current Phase (Phase 7-8):**
- ✓ Phase 7: Integration testing (basic validation completed)
- ⏳ Phase 8: Documentation (in progress)

## Troubleshooting

### Common Issues

**1. Gurobi License Error**
```
GurobiError: HostID mismatch
```
Solution: Activate Gurobi license with `grbgetkey YOUR_LICENSE_KEY`

**2. Module Import Error**
```
ModuleNotFoundError: No module named 'core'
```
Solution: Ensure Python path includes the `src/` directory

**3. GraphHopper Connection Error**
```
ConnectionError: GraphHopper service not available
```
Solution: Either start GraphHopper server or set `use_graphhopper_routing: false` in config

**4. Data File Not Found**
```
FileNotFoundError: co2_capture_sources.csv
```
Solution: Run CO₂ capture calculator first to generate the data file

### Performance Optimization

- **Reduce Time Horizon**: Start with 1 week for testing
- **Disable GraphHopper**: Set `use_graphhopper_routing: false` for faster testing
- **Adjust Solver Parameters**: Increase `MIPGap` for faster solve (lower accuracy)
- **Use Clustering**: Enable plant clustering to reduce decision variables

## References

### Technical Documentation

- [PRD v2.0](../../../docs/绿氢供应链优化产品需求文档_PRD_v2.0.md): Product Requirements Document
- [Configuration Guide](../../../shared/data/GreenHydrogenSupplyChainOptimizer_config.yaml): Full configuration reference
- [Gurobi Documentation](https://www.gurobi.com/documentation/): Optimization solver reference

### Academic Background

- **E-CRM Technology**: Electro-chemical CO₂ reduction to methanol
- **MTJ Technology**: Methanol-to-jet fuel conversion (Haldor Topsoe)
- **CCS Technology**: Carbon capture and storage (Global CCS Institute)
- **Green Hydrogen**: IEA Hydrogen Report 2024, IRENA Green Hydrogen Cost 2024

## License

[Specify your license here]

## Authors

- Project Team: Green Methanol for Port Transportation Research Group
- AI Assistant: Claude Code (Anthropic)

## Version History

- **v2.0.0** (2025-10-14): Green hydrogen + CO₂ two-step process implementation
  - Migrated from natural gas-based to green hydrogen-based supply chain
  - Added CO₂ capture module
  - Added carbon emission calculator
  - Refactored core optimization model
  - Updated configuration and documentation

- **v1.0.0** (2025-09-XX): Initial natural gas-based implementation

## Contact

For questions, issues, or contributions, please contact:
[Your contact information]

---

**Last Updated**: 2025-10-14
**Status**: Production Ready (Phase 6 Complete, Testing in Progress)
