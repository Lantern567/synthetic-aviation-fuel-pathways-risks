# PRP: {FEATURE_NAME}

## Overview
{Brief description of what this feature does and why it's needed}

## Context and Background

### Domain Knowledge
- **Green Methanol Transportation**: {specific domain context}
- **Aviation Fuel Systems**: {relevant aviation fuel knowledge}
- **Energy Infrastructure**: {energy systems background}
- **Port Logistics**: {port and transportation context}

### Codebase Context
- **Related Modules**: {list existing modules this integrates with}
- **Data Sources**: {input data formats and sources}
- **Output Requirements**: {expected output formats and locations}
- **Performance Requirements**: {speed, memory, resource considerations}

## Technical Requirements

### Functional Requirements
1. {Primary functionality requirement 1}
2. {Primary functionality requirement 2}
3. {Data processing requirement}
4. {Visualization/output requirement}

### Non-Functional Requirements
- **Performance**: {specific performance targets}
- **Scalability**: {data volume handling requirements}
- **Reliability**: {error handling and robustness needs}
- **Maintainability**: {code organization and documentation standards}

## Architecture and Design

### Module Structure
```
{module_name}/
├── src/                    # Source code
│   ├── main_processor.py   # Main processing logic
│   ├── data_loader.py      # Data input handling
│   ├── calculators.py      # Core calculation functions
│   └── visualizers.py      # Visualization components
├── data/                   # Input data files
├── results/                # Output directory
│   ├── tables/            # CSV/Excel outputs
│   ├── figures/           # Generated plots
│   └── reports/           # Analysis reports
├── tests/                  # Test files
├── logs/                   # Log files
└── README.md              # Module documentation
```

### Data Flow
1. **Input**: {describe input data sources and formats}
2. **Processing**: {describe data transformation steps}
3. **Calculation**: {describe core computation logic}
4. **Output**: {describe result generation and saving}

### Integration Points
- **Existing Modules**: {how it connects with air_port_data_process/, gis_data_scraper/, etc.}
- **Data Dependencies**: {what data it needs from other modules}
- **Shared Utilities**: {common functions or patterns to reuse}

## Implementation Details

### Core Algorithms
{Detailed description of algorithms to implement, with references to existing patterns}

### Data Processing Pipeline
```python
# Pseudocode showing the processing flow
def main_processing_pipeline(input_data):
    # 1. Data validation and cleaning
    validated_data = validate_input(input_data)
    
    # 2. Core calculations
    results = perform_calculations(validated_data)
    
    # 3. Result processing
    processed_results = process_results(results)
    
    # 4. Output generation
    save_outputs(processed_results)
    
    return processed_results
```

### Key Functions to Implement
1. **{function_name_1}**: {description and signature}
2. **{function_name_2}**: {description and signature}
3. **{function_name_3}**: {description and signature}

## Dependencies and Libraries

### Required Libraries
- **Core**: pandas, numpy
- **Calculation**: {specific calculation libraries}
- **Visualization**: matplotlib, seaborn
- **Optional**: {optional dependencies}

### Environment Setup
```bash
conda activate green_methanol_for_port_transportation
pip install {any_new_dependencies}
```

## Testing Strategy

### Unit Tests
- Test all calculation functions with known inputs/outputs
- Test data validation and error handling
- Test edge cases and boundary conditions

### Integration Tests
- Test complete data pipeline with sample data
- Test integration with existing modules
- Test file I/O operations

### Test Data
- Use samples from existing project data
- Create synthetic test cases for edge conditions
- Ensure tests run quickly (< 30 seconds total)

## Validation Gates

### Code Quality
```bash
# Syntax validation
python -m py_compile src/*.py

# Style check (if available)
flake8 src/ || echo "Style check not available, manual review needed"
```

### Functionality Tests
```bash
# Unit tests
python -m pytest tests/ -v

# Integration test with sample data
python src/main_processor.py --test-mode

# Verify outputs
ls -la results/tables/
ls -la results/figures/
```

### Performance Validation
```bash
# Memory usage check
python -c "import psutil; print(f'Available memory: {psutil.virtual_memory().available/1024/1024/1024:.1f} GB')"

# Processing time for typical dataset
time python src/main_processor.py --benchmark
```

## Documentation Requirements

### Code Documentation
- Docstrings for all functions and classes
- Type hints for function parameters and returns
- Inline comments for complex logic

### Module Documentation
- Update module README.md with usage examples
- Document data input/output formats
- Include performance benchmarks and limitations

### Project Integration
- Update main project README.md
- Add entry to project changelog
- Document any new dependencies

## Success Criteria

### Functional Success
- [ ] All required calculations implemented and tested
- [ ] Data pipeline processes sample data without errors
- [ ] Output files generated in correct format and location
- [ ] Integration with existing modules works properly

### Quality Success
- [ ] All tests pass (unit and integration)
- [ ] Code follows project patterns from examples/
- [ ] Performance meets requirements (process 10K records < 60 seconds)
- [ ] Error handling covers anticipated failure modes

### Documentation Success
- [ ] All functions have proper docstrings
- [ ] Module README.md is complete and accurate
- [ ] Usage examples work as documented
- [ ] Integration instructions are clear

## Implementation Tasks

### Phase 1: Core Structure
1. Create module directory structure
2. Set up basic data loading functions
3. Implement core calculation logic
4. Write unit tests for calculations

### Phase 2: Integration
1. Integrate with existing data sources
2. Implement visualization components
3. Add error handling and logging
4. Create integration tests

### Phase 3: Validation and Documentation
1. Run full test suite and fix issues
2. Performance testing and optimization
3. Complete documentation
4. Update project README and logs

## Risk Mitigation

### Technical Risks
- **Large Dataset Performance**: Use chunked processing, implement caching
- **Memory Usage**: Monitor memory consumption, use generators for large files
- **Calculation Accuracy**: Validate against known benchmarks, use established libraries

### Integration Risks
- **Data Format Changes**: Implement flexible data parsing with validation
- **Dependency Conflicts**: Pin specific versions, test in clean environment
- **API Changes**: Use stable APIs, implement graceful degradation

## Resources and References

### Documentation Links
- {Link to relevant API documentation}
- {Link to calculation methodology papers}
- {Link to existing module documentation}

### Code References
- {Path to similar implementations in codebase}
- {Reference to examples/ directory patterns}
- {External code examples or tutorials}

### Domain Resources
- {Domain-specific resources for green methanol}
- {Aviation industry standards or data sources}
- {Energy sector guidelines or references}

## Confidence Score: {X}/10

{Explanation of confidence level and any remaining uncertainties}

---

**Generated**: {timestamp}
**Context Engineering Version**: Green Methanol Project v1.0
**Estimated Implementation Time**: {X} hours