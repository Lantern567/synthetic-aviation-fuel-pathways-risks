# Create PRP (Product Requirements Prompt)

## Feature file: $ARGUMENTS

Generate a complete PRP for green methanol project feature implementation with thorough research. Ensure context is passed to the AI agent to enable self-validation and iterative refinement. Read the feature file first to understand what needs to be created, how the examples provided help, and any other considerations.

The AI agent only gets the context you are appending to the PRP and training data. Assume the AI agent has access to the codebase and the same knowledge cutoff as you, so it's important that your research findings are included or referenced in the PRP. The Agent has Websearch capabilities, so pass URLs to documentation and examples.

## Research Process

1. **Codebase Analysis**
   - Search for similar features/patterns in the codebase
   - Identify files to reference in PRP (air_port_data_process/, gis_data_scraper/, natural_gas_supply_chain_optimization/, etc.)
   - Note existing conventions to follow (pandas, numpy, pytest patterns)
   - Check test patterns for validation approach
   - Look for existing data processing pipelines and visualization patterns

2. **Project-Specific Context**
   - Green methanol transportation and port logistics domain knowledge
   - Aviation fuel calculation patterns (pyBADA, BADA3)
   - GIS data processing and visualization patterns
   - Natural gas supply chain optimization methods
   - Energy infrastructure data handling

3. **External Research**
   - Search for similar features/patterns online
   - Library documentation (pandas, numpy, matplotlib, gurobi, etc.)
   - Implementation examples (GitHub/StackOverflow/blogs)
   - Best practices and common pitfalls for scientific computing
   - Domain-specific resources (aviation fuel, energy transport, GIS)

4. **User Clarification** (if needed)
   - Specific patterns to mirror from existing modules?
   - Integration requirements with existing data pipelines?
   - Performance requirements for large datasets?

## PRP Generation

Using PRPs/templates/prp_base.md as template:

### Critical Context to Include
- **Documentation**: URLs with specific sections
- **Code Examples**: Real snippets from existing modules
- **Data Patterns**: How the project handles CSV, Excel, GeoJSON files
- **Visualization Patterns**: matplotlib, seaborn, pydeck usage patterns
- **Testing Patterns**: pytest structure and test data handling
- **Domain Knowledge**: Green methanol, aviation fuel, energy transport specifics
- **Gotchas**: Library quirks, version issues, conda environment specifics

### Implementation Blueprint
- Start with pseudocode showing approach
- Reference real files from air_port_data_process/, gis_data_scraper/, etc.
- Include data validation and error handling strategy
- Consider performance for large datasets
- List tasks to be completed to fulfill the PRP in the order they should be completed
- Include visualization and results output requirements

### Validation Gates (Must be Executable)
```bash
# Environment check
conda activate green_methanol_for_port_transportation

# Syntax/Style check (if available)
python -m py_compile src/*.py

# Unit Tests
python -m pytest tests/ -v

# Integration test with sample data
python src/main_module.py --test-mode

# Results validation
ls -la results/tables/ results/figures/
```

### Project-Specific Considerations
- Ensure compatibility with existing conda environment
- Follow established file structure (src/, data/, results/, tests/, logs/)
- Use existing data formats (CSV, Excel, GeoJSON)
- Generate appropriate log files with timestamps
- Update README.md after implementation
- Consider CPU/GPU resource utilization as specified in CLAUDE.md

*** CRITICAL AFTER YOU ARE DONE RESEARCHING AND EXPLORING THE CODEBASE BEFORE YOU START WRITING THE PRP ***

*** ULTRATHINK ABOUT THE PRP AND PLAN YOUR APPROACH THEN START WRITING THE PRP ***

## Output
Save as: `PRPs/{feature-name}.md`

## Quality Checklist
- [ ] All necessary context included
- [ ] Validation gates are executable by AI
- [ ] References existing project patterns
- [ ] Clear implementation path following project structure
- [ ] Error handling and data validation documented
- [ ] Performance considerations for scientific computing workloads
- [ ] Domain knowledge included (green methanol, aviation, energy)
- [ ] Integration points with existing modules identified

Score the PRP on a scale of 1-10 (confidence level to succeed in one-pass implementation using Claude Code)

Remember: The goal is one-pass implementation success through comprehensive context specific to the green methanol transportation project.