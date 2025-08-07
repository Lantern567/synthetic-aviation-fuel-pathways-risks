# Execute PRP (Product Requirements Prompt)

## PRP file: $ARGUMENTS

Execute the comprehensive PRP for green methanol project feature implementation. Follow the implementation plan exactly as specified in the PRP, with validation at each step.

## Execution Process

1. **Load Context**
   - Read the entire PRP file
   - Load all referenced documentation and examples
   - Understand the domain context (green methanol, aviation fuel, energy transport)
   - Check conda environment is activated: `green_methanol_for_port_transportation`

2. **Create Implementation Plan**
   - Use TodoWrite tool to create detailed task list from PRP
   - Break down each major component into specific actionable tasks
   - Mark dependencies between tasks
   - Set up validation checkpoints

3. **Environment Preparation**
   - Verify conda environment: `conda activate green_methanol_for_port_transportation`
   - Check required dependencies are installed
   - Create necessary directories following project structure:
     ```
     module_name/
     ├── src/           # Source code
     ├── data/          # Input data files
     ├── results/       # Output results
     │   ├── tables/    # CSV/Excel outputs
     │   ├── figures/   # Visualizations
     │   └── reports/   # Analysis reports
     ├── tests/         # Test files
     ├── logs/          # Log files
     └── README.md      # Module documentation
     ```

4. **Implementation Execution**
   - Follow the exact steps outlined in the PRP
   - Implement each component following existing project patterns
   - Use established data processing patterns (pandas, numpy)
   - Follow visualization patterns (matplotlib, seaborn, pydeck)
   - Ensure proper error handling and logging
   - Generate timestamped log files in logs/ directory

5. **Validation at Each Step**
   - Run syntax checks: `python -m py_compile src/*.py`
   - Execute unit tests: `python -m pytest tests/ -v`
   - Verify data processing with sample datasets
   - Check output file generation in results/
   - Validate visualizations are generated correctly

6. **Integration Testing**
   - Test integration with existing modules
   - Verify data pipeline compatibility
   - Check performance with realistic data sizes
   - Validate memory usage and CPU utilization

7. **Documentation and Cleanup**
   - Update module README.md
   - Create usage examples
   - Document any new dependencies
   - Update main project README.md if needed
   - Generate log entry with current date in logs/

## Error Handling Strategy

If any step fails:
1. **Analyze the Error**: Check logs, error messages, stack traces
2. **Research Solution**: Use web search for specific error patterns
3. **Apply Fix**: Modify code based on research and existing patterns
4. **Validate Fix**: Re-run validation gates
5. **Continue**: Resume from next step only after validation passes

## Success Criteria (All Must Pass)

```bash
# Environment check
conda list | grep -E "(pandas|numpy|matplotlib)"

# Code syntax validation
python -m py_compile src/*.py

# Unit tests pass
python -m pytest tests/ -v --tb=short

# Integration test
python src/main_module.py --validate

# Output files generated
ls -la results/tables/
ls -la results/figures/
ls -la logs/

# Performance validation (if applicable)
python -c "import psutil; print(f'Memory: {psutil.virtual_memory().percent}%')"
```

## Completion Checklist

- [ ] All PRP requirements implemented
- [ ] Code follows existing project patterns
- [ ] Unit tests written and passing
- [ ] Integration tests passing
- [ ] Results files generated in correct locations
- [ ] Visualizations created and saved
- [ ] Documentation updated (README, logs)
- [ ] Performance validated for expected data sizes
- [ ] Error handling tested
- [ ] Code committed to git (if requested)

## Post-Implementation

1. **Generate Summary Report**
   - Create implementation summary in results/reports/
   - Document any deviations from PRP and reasons
   - Include performance metrics
   - Note any lessons learned

2. **Update Project Documentation**
   - Update main README.md with new feature
   - Add to project changelog
   - Update dependency list if needed

3. **Final Validation**
   - Run full test suite
   - Verify integration with existing workflows
   - Check resource utilization is within acceptable limits

Remember: Follow the green methanol project's established patterns and maintain compatibility with existing data processing pipelines.