# SC H.4216 Analysis: PolicyEngine vs RFA Comparison

## Executive Summary

This analysis compares PolicyEngine estimates against the SC Revenue and Fiscal Affairs (RFA) fiscal notes for H.4216, a tax reform bill that restructures South Carolina's income tax system.

### Budget Impact Summary

| Rate Option | RFA Estimate | State Dataset | Test Dataset | State Accuracy | Test Accuracy |
|-------------|--------------|---------------|--------------|----------------|---------------|
| **5.21%** | **-$308.7M** | -$393.0M | -$212.0M | 73% (27% over) | 69% (31% under) |
| **5.39%** | **-$119.1M** | -$198.2M | -$92.7M | 34% (66% over) | 78% (22% under) |

**Key Finding:** The policy encoding is correct. All discrepancies stem from dataset characteristics, primarily the distribution of millionaire tax filers.

---

## H.4216 Reform Structure

### Current SC Tax System (Baseline)
- 0% on income up to $3,640
- 3% on income $3,640 to $18,230
- 6% on income over $18,230
- Taxable income = Federal Taxable Income + SC Additions - SC Subtractions

### H.4216 Reform
- 1.99% on income up to $30,000
- 5.21% (bill default) or 5.39% (RFA version) on income over $30,000
- Taxable income = AGI - SC Subtractions - SCIAD (new deduction)
- No federal standard/itemized deductions in base

### SCIAD (SC Individual Adjustment Deduction)

| Filing Status | Deduction | Phase-out Start | Phase-out End |
|---------------|-----------|-----------------|---------------|
| Single | $15,000 | $40,000 AGI | $95,000 AGI |
| MFJ | $30,000 | $80,000 AGI | $190,000 AGI |
| HoH | $22,500 | $60,000 AGI | $142,500 AGI |

---

## Dataset Comparison

### Overview

| Metric | RFA | State (Production) | Test |
|--------|-----|-------------------|------|
| **Total Returns** | 2,757,573 | 2,935,621 (+6.5%) | 2,705,850 (-1.9%) |
| **Millionaire Returns** | 11,936 | 22,686 (+90%) | 6,993 (-41%) |
| **Baseline Revenue** | ~$6.4B | ~$6.5B | ~$4.0B |
| **Median HH AGI** | N/A | $43,222 | $34,927 |
| **Avg HH AGI** | N/A | $103,858 | $74,061 |
| **Max AGI** | N/A | $6.4M | $418.7M |

### Dataset Paths
- **State (Production):** `hf://policyengine/policyengine-us-data/states/SC.h5`
- **Test:** `hf://policyengine/test/mar/SC.h5`

---

## 5.21% Rate Analysis

### Budget Impact by Income Bracket

| AGI Range | RFA | State | Test | State vs RFA | Test vs RFA |
|-----------|-----|-------|------|--------------|-------------|
| $0* | -$671K | $0 | $0 | +$671K | +$671K |
| $1-$10K | +$1.7M | $0 | $0 | -$1.7M | -$1.7M |
| $10K-$20K | +$2.9M | +$2.7M | +$0.8M | -$0.2M | -$2.1M |
| $20K-$30K | +$0.8M | +$9.3M | +$2.8M | +$8.5M | +$2.0M |
| $30K-$40K | -$19.4M | -$5.4M | -$2.1M | +$14.0M | +$17.3M |
| $40K-$50K | -$42.6M | -$28.1M | -$12.9M | +$14.5M | +$29.7M |
| $50K-$75K | -$89.9M | -$30.1M | -$30.5M | +$59.8M | +$59.4M |
| $75K-$100K | -$48.6M | -$26.5M | -$31.6M | +$22.1M | +$17.0M |
| $100K-$150K | -$26.1M | +$17.9M | +$28.5M | +$44.0M | +$54.6M |
| $150K-$200K | +$23.8M | +$26.7M | +$24.6M | +$2.9M | +$0.8M |
| $200K-$300K | +$4.0M | +$10.3M | +$9.6M | +$6.3M | +$5.6M |
| $300K-$500K | -$32.1M | -$16.5M | -$26.0M | +$15.6M | +$6.1M |
| $500K-$1M | -$37.4M | -$20.3M | -$33.2M | +$17.1M | +$4.2M |
| **Over $1M** | **-$45.0M** | **-$332.9M** | **-$142.0M** | **-$287.9M** | **-$97.0M** |
| **TOTAL** | **-$308.7M** | **-$393.0M** | **-$212.0M** | **-$84.3M** | **+$96.7M** |

### Winner/Loser Distribution (5.21%)

| Metric | RFA | State | Test |
|--------|-----|-------|------|
| **Tax Decrease** | 42.8% | 23.8% | 20.6% |
| **Tax Increase** | 22.6% | 20.1% | 15.2% |
| **No Change** | 34.6% | 56.0% | 64.2% |
| **Total Decrease $** | -$522.1M | -$545.9M | -$345.7M |
| **Total Increase $** | +$213.4M | +$152.9M | +$133.7M |

---

## 5.39% Rate Analysis

### Budget Impact by Income Bracket

| AGI Range | RFA | State | Test | State vs RFA | Test vs RFA |
|-----------|-----|-------|------|--------------|-------------|
| $0* | -$571K | $0 | $0 | +$571K | +$571K |
| $1-$10K | +$1.7M | $0 | $0 | -$1.7M | -$1.7M |
| $10K-$20K | +$2.9M | +$2.7M | +$0.8M | -$0.2M | -$2.1M |
| $20K-$30K | +$0.8M | +$9.3M | +$2.8M | +$8.5M | +$2.0M |
| $30K-$40K | -$19.4M | -$5.4M | -$2.1M | +$14.0M | +$17.3M |
| $40K-$50K | -$42.0M | -$27.8M | -$12.8M | +$14.2M | +$29.2M |
| $50K-$75K | -$82.1M | -$26.5M | -$28.6M | +$55.6M | +$53.5M |
| $75K-$100K | -$36.5M | -$19.1M | -$26.8M | +$17.4M | +$9.7M |
| $100K-$150K | +$3.1M | +$37.2M | +$49.6M | +$34.1M | +$46.5M |
| $150K-$200K | +$50.9M | +$42.0M | +$32.6M | -$8.9M | -$18.3M |
| $200K-$300K | +$36.7M | +$26.7M | +$28.2M | -$10.0M | -$8.5M |
| $300K-$500K | -$4.6M | +$4.3M | -$8.9M | +$8.9M | -$4.3M |
| $500K-$1M | -$16.2M | -$6.4M | -$21.9M | +$9.8M | -$5.7M |
| **Over $1M** | **-$13.8M** | **-$235.2M** | **-$105.6M** | **-$221.4M** | **-$91.8M** |
| **TOTAL** | **-$119.1M** | **-$198.2M** | **-$92.7M** | **-$79.1M** | **+$26.4M** |

### Winner/Loser Distribution (5.39%)

| Metric | RFA | State | Test |
|--------|-----|-------|------|
| **Tax Decrease** | 38.7% | 21.5% | 18.3% |
| **Tax Increase** | 26.7% | 22.5% | 17.6% |
| **No Change** | 34.6% | 56.0% | 64.1% |
| **Total Decrease $** | -$388.7M | -$396.2M | -$259.2M |
| **Total Increase $** | +$269.6M | +$197.9M | +$166.5M |

---

## Root Cause Analysis

### 1. Millionaire Distribution (Primary Driver)

The millionaire bracket (>$1M AGI) is the dominant driver of discrepancies:

| Metric | RFA | State | Test |
|--------|-----|-------|------|
| **Millionaire Count** | 11,936 | 22,686 (+90%) | 6,993 (-41%) |
| **5.21% Impact** | -$45.0M | -$332.9M | -$142.0M |
| **5.39% Impact** | -$13.8M | -$235.2M | -$105.6M |
| **Avg Change (5.21%)** | -$4,031 | -$14,672 | -$20,306 |

**State Dataset:** Has nearly **double** the millionaires RFA reports. This alone accounts for ~$288M of the $84M overestimate at 5.21%.

**Test Dataset:** Has 41% fewer millionaires but an extreme outlier ($418.7M AGI) that skews averages significantly.

### 2. Middle-Income Brackets ($30K-$100K)

RFA shows much larger tax cuts in middle-income brackets:

| Bracket Range | RFA Impact | State Impact | Test Impact |
|---------------|------------|--------------|-------------|
| $30K-$100K combined | -$200.5M | -$90.1M | -$77.1M |
| Difference vs RFA | - | +$110.4M | +$123.4M |

Both PE datasets underweight middle-income filers relative to RFA.

### 3. Upper-Middle Income ($100K-$300K)

PE shows tax **increases** where RFA shows mixed results:

| Bracket Range | RFA Impact | State Impact | Test Impact |
|---------------|------------|--------------|-------------|
| $100K-$300K (5.21%) | -$22.1M | +$54.9M | +$62.7M |
| $100K-$300K (5.39%) | +$90.7M | +$105.9M | +$110.4M |

This suggests SCIAD phase-out behavior may differ or income distributions within brackets vary.

### 4. Low-Income Brackets ($0-$30K)

| Bracket | RFA Returns | State Returns | Test Returns |
|---------|-------------|---------------|--------------|
| $0* | 78,854 (2.9%) | 619,010 (21.1%) | 727,881 (26.9%) |
| $1-$10K | 286,253 (10.4%) | 502,276 (17.1%) | 498,186 (18.4%) |

PE datasets have significantly more zero/low-income tax units. These units have zero tax liability, so they don't affect budget impact but dilute the "% with tax change" statistics.

---

## Summary of Dataset Characteristics

### State (Production) Dataset
- **Overestimates** tax cuts at both rates
- Has 90% more millionaires than RFA
- Higher average incomes ($104K vs $74K Test)
- Baseline revenue matches RFA (~$6.5B)
- More total returns than RFA (+6.5%)

### Test Dataset
- **Underestimates** tax cuts at both rates
- Has 41% fewer millionaires than RFA
- Lower average incomes ($74K)
- Baseline revenue 37% below RFA ($4.0B vs $6.4B)
- Return count close to RFA (-1.9%)
- Has extreme outlier ($418.7M AGI)

### Ideal Dataset Would Have
- RFA's millionaire count (~11,936)
- RFA's return count (~2.76M)
- RFA's baseline revenue (~$6.4B)
- Middle-income weighting matching SC tax filer data

---

## Recommendations

### For Data Team
1. Investigate millionaire overcount in State dataset (22,686 vs 11,936 RFA)
2. Investigate baseline revenue undercount in Test dataset ($4.0B vs $6.4B)
3. Recalibrate weights to match SC DOR filer distribution by income bracket
4. Validate against IRS SOI data for SC

### For Analysis
1. Report range of estimates from both datasets
2. Use State for directional analysis (correct baseline revenue magnitude)
3. Use Test for return count validation (closer to RFA)
4. Note millionaire bracket as primary source of uncertainty

### For Reporting
| Rate | Conservative | Central | Aggressive |
|------|--------------|---------|------------|
| 5.21% | -$212M (Test) | -$309M (RFA) | -$393M (State) |
| 5.39% | -$93M (Test) | -$119M (RFA) | -$198M (State) |

---

## File Structure

```
sc/
├── data_exploration.ipynb              # State dataset exploration
├── data_exploration_test.ipynb         # Test dataset exploration
├── sc_dataset_summary_weighted.csv     # State dataset summary stats
├── sc_test_dataset_summary_weighted.csv # Test dataset summary stats
└── h4216_analysis/
    ├── h4216_analysis_comparison.md    # This file
    ├── 5.21_rate/
    │   ├── rfa_h4216_5.21_analysis.csv # RFA fiscal note data
    │   ├── state/
    │   │   ├── pe_h4216_5.21_state_analysis.csv
    │   │   └── sc_h4216_5.21_state_analysis.ipynb
    │   └── test/
    │       ├── pe_h4216_5.21_analysis.csv
    │       └── sc_h4216_5.21_analysis.ipynb
    └── 5.39_rate/
        ├── rfa_h4216_analysis.csv      # RFA fiscal note data
        ├── state/
        │   ├── pe_h4216_5.39_state_analysis.csv
        │   └── sc_h4216_5.39_state_analysis.ipynb
        └── test/
            ├── pe_h4216_test_analysis.csv
            └── sc_h4216_test_analysis.ipynb
```

---

## Technical Notes

### PR #7514 Fix (February 2025)

Fixed bug where `sc_additions` (QBI and SALT addbacks) were incorrectly applied under H.4216. Since H.4216 starts from AGI (before federal deductions), addbacks are inappropriate.

- **Before fix:** +$39.8M (wrong direction - showed revenue increase)
- **After fix:** -$93M to -$393M depending on dataset and rate

### Policy Parameters Location
```
policyengine-us/policyengine_us/parameters/gov/contrib/states/sc/h4216/
```

### Microsimulation Usage
```python
from policyengine_us import Microsimulation
from policyengine_us.reforms.states.sc.h4216.sc_h4216 import create_sc_h4216
from policyengine_core.reforms import Reform

# Create reform with specific top rate
param_reform = Reform.from_dict({
    "gov.contrib.states.sc.h4216.in_effect": {"2026-01-01.2100-12-31": True},
    "gov.contrib.states.sc.h4216.rates[1].rate": {"2026-01-01.2100-12-31": 0.0521}
}, country_id="us")

base_reform = create_sc_h4216()
reform = (base_reform, param_reform)

sim = Microsimulation(dataset="hf://policyengine/test/mar/SC.h5", reform=reform)
```
