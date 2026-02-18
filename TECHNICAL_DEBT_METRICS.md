# Technical Debt Metrics Feature

## Overview

Added comprehensive technical debt metrics to the `thothctl inventory iac` command. These metrics provide quantifiable insights into infrastructure code health and maintenance needs.

## What Was Added

### 1. Technical Debt Calculation (`inventory_service.py`)

New method `_calculate_technical_debt_metrics()` that computes:

- **Total Components**: Count of all modules in the inventory
- **Outdated Modules**: Modules with available updates
- **Outdated Providers**: Providers with available updates
- **Current Modules/Providers**: Up-to-date components
- **Breaking Changes**: Modules and providers with breaking changes
- **Debt Score**: 0-100 scale (higher = more debt)
- **Risk Level**: critical/high/medium/low
- **Recommendations**: Actionable suggestions

### 2. Debt Score Algorithm

```
Base Score = (Outdated Items / Total Items) × 100
Breaking Changes Weight = (Breaking Changes Count) × 5
Final Score = min(100, Base Score + Breaking Changes Weight)
```

**Risk Levels:**
- **Critical**: ≥70% debt score
- **High**: 50-69% debt score
- **Medium**: 30-49% debt score
- **Low**: <30% debt score

### 3. Console Output Enhancement (`iac.py`)

Added technical debt section to console summary:
- Color-coded debt score (red/yellow/cyan/green)
- Outdated modules and providers count
- Breaking changes warnings
- Risk level indicator

### 4. HTML Report Enhancement (`report_service.py`)

Added visual technical debt section with:
- Debt score card with risk-based color coding
- Outdated modules/providers cards
- Breaking changes warnings
- Recommendations panel with actionable items
- Modern card-based layout matching existing design

## Usage

The technical debt metrics are automatically calculated when using `--check-versions`:

```bash
# Basic inventory with technical debt metrics
thothctl inventory iac --check-versions

# Full analysis with compatibility checking
thothctl inventory iac --check-versions --check-schema-compatibility

# Generate all report types
thothctl inventory iac --check-versions --report-type all
```

## Example Output

### Console
```
📊 Technical Debt Metrics:
Debt Score: 45.2% (MEDIUM risk)
Outdated Modules: 12/35
Outdated Providers: 3
⚠️  Modules with Breaking Changes: 2
⚠️  Providers with Breaking Changes: 1
```

### HTML Report
- Visual cards showing debt score with color-coded risk level
- Breakdown of outdated components
- Breaking changes highlighted with warning icons
- Recommendations panel with specific action items

## Benefits

1. **Quantifiable Metrics**: Clear numbers for tracking technical debt over time
2. **Risk Assessment**: Immediate understanding of infrastructure health
3. **Prioritization**: Breaking changes highlighted for careful review
4. **Actionable**: Specific recommendations for improvement
5. **Trend Tracking**: JSON output enables historical analysis
6. **Stakeholder Communication**: Professional HTML reports for management

## Files Modified

1. `src/thothctl/services/inventory/inventory_service.py`
   - Added `_calculate_technical_debt_metrics()` method
   - Integrated calculation before report generation

2. `src/thothctl/commands/inventory/commands/iac.py`
   - Enhanced `_display_summary()` with technical debt section
   - Added color-coded console output

3. `src/thothctl/services/inventory/report_service.py`
   - Added technical debt section to HTML report generation
   - Integrated with existing modern card-based design

## Integration

The feature integrates seamlessly with existing functionality:
- Only runs when `--check-versions` is enabled
- Uses existing version check data
- Leverages compatibility analysis when available
- Appears in all report formats (console, HTML, JSON)

## Future Enhancements

Potential improvements:
- Historical trend tracking across multiple inventory runs
- Configurable debt score weights
- Custom risk level thresholds
- Integration with CI/CD for automated debt tracking
- Debt reduction planning tools
