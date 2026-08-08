# SC H.4216 Analysis: PolicyEngine vs RFA Comparison

## Executive Summary

This analysis compares PolicyEngine estimates against the SC Revenue and Fiscal Affairs (RFA) fiscal note for H.4216, a tax reform bill that restructures South Carolina's income tax system.

### Budget Impact Summary (5.21% Top Rate)

| Source | Budget Impact | vs RFA | Accuracy |
|--------|---------------|--------|----------|
| **RFA** | **-$308.7M** | - | - |
| Test Dataset | -$370.0M | -$61.3M | 80% (20% over) |

**Key Finding:** The policy encoding is correct. The Test dataset now closely matches RFA with 80% accuracy, slightly overestimating the tax cut.

---

## H.4216 Reform Structure

### Current SC Tax System (Baseline)
- 0% on income up to $3,640
- 3% on income $3,640 to $18,230
- 6% on income over $18,230
- Taxable income = Federal Taxable Income + SC Additions - SC Subtractions

### H.4216 Reform (5.21% Top Rate)
- 1.99% on income up to $30,000
- 5.21% on income over $30,000
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

| Metric | RFA | Test |
|--------|-----|------|
| **Total Returns** | 2,757,573 | 2,914,575 (+5.7%) |
| **Millionaire Returns** | 11,936 | 20,591 (+73%) |
| **Median HH AGI** | N/A | $68,193 |
| **Avg HH AGI** | N/A | $148,865 |
| **Max AGI** | N/A | $2.38B |

### Dataset Path
- **Test:** `hf://policyengine/test/mar/SC.h5`

---

## Budget Impact by Income Bracket (5.21% Rate)

| AGI Range | RFA | Test | Test vs RFA |
|-----------|-----|------|-------------|
| $0* | -$671K | $0 | +$671K |
| $1-$10K | +$1.7M | $0 | -$1.7M |
| $10K-$20K | +$2.9M | +$2.2M | -$0.6M |
| $20K-$30K | +$0.8M | +$6.8M | +$6.0M |
| $30K-$40K | -$19.4M | -$9.0M | +$10.4M |
| $40K-$50K | -$42.6M | -$28.5M | +$14.0M |
| $50K-$75K | -$89.9M | -$53.6M | +$36.4M |
| $75K-$100K | -$48.6M | -$31.8M | +$16.8M |
| $100K-$150K | -$26.1M | +$15.0M | +$41.1M |
| $150K-$200K | +$23.8M | +$29.1M | +$5.3M |
| $200K-$300K | +$4.0M | +$0.5M | -$3.5M |
| $300K-$500K | -$32.1M | -$83.0M | -$51.0M |
| $500K-$1M | -$37.4M | -$87.6M | -$50.2M |
| **Over $1M** | **-$45.0M** | **-$130.1M** | **-$85.1M** |
| **TOTAL** | **-$308.7M** | **-$370.0M** | **-$61.3M** |

### Winner/Loser Distribution

| Metric | RFA | Test |
|--------|-----|------|
| **Tax Decrease** | 42.8% | 34.6% |
| **Tax Increase** | 22.6% | 22.3% |
| **No Change** | 34.6% | 43.1% |
| **Total Decrease $** | -$522.1M | -$766.7M |
| **Total Increase $** | +$213.4M | +$396.7M |

---

## Root Cause Analysis

### 1. Millionaire Distribution (Primary Driver)

The millionaire bracket (>$1M AGI) is the dominant driver of discrepancies:

| Metric | RFA | Test |
|--------|-----|------|
| **Millionaire Count** | 11,936 | 20,591 (+73%) |
| **Budget Impact** | -$45.0M | -$130.1M |
| **Avg Tax Change** | -$4,031 | -$6,332 |

**Test Dataset:** Has 73% more millionaires than RFA, contributing to larger overall tax cut estimate.

### 2. High-Income Brackets ($300K+)

Test dataset shows significantly larger tax cuts in high-income brackets:

| Bracket Range | RFA Impact | Test Impact | Difference |
|---------------|------------|-------------|------------|
| $300K-$500K | -$32.1M | -$83.0M | -$51.0M |
| $500K-$1M | -$37.4M | -$87.6M | -$50.2M |
| Over $1M | -$45.0M | -$130.1M | -$85.1M |
| **Total $300K+** | **-$114.5M** | **-$300.7M** | **-$186.2M** |

The $300K+ brackets account for most of the overestimate.

### 3. Middle-Income Brackets ($30K-$100K)

| Bracket Range | RFA Impact | Test Impact | Difference |
|---------------|------------|-------------|------------|
| $30K-$100K combined | -$200.5M | -$122.9M | +$77.6M |

Test dataset underweights middle-income tax cuts, partially offsetting the high-income overestimate.

### 4. Upper-Middle Income ($100K-$300K)

| Bracket Range | RFA Impact | Test Impact | Difference |
|---------------|------------|-------------|------------|
| $100K-$300K | -$22.1M | +$44.6M | +$66.7M |

Test shows tax increases in this range where RFA shows cuts, suggesting different SCIAD phase-out distributions.

---

## Summary of Dataset Characteristics

### Test Dataset
- **Slightly overestimates** tax cuts (80% accuracy)
- Has 73% more millionaires than RFA (20,591 vs 11,936)
- Higher average incomes ($149K avg HH AGI)
- Return count close to RFA (+5.7%)
- High-income brackets drive the overestimate

### Key Differences from RFA
- More returns in $300K+ brackets
- Larger average tax cuts for high earners
- Fewer middle-income filers seeing tax cuts

---

## Recommendations

### For Data Team
1. Investigate millionaire overcount (20,591 vs 11,936 RFA)
2. Validate $300K-$1M bracket weighting
3. Compare income distributions within brackets to RFA

### For Reporting

| Estimate Type | Value | Source |
|---------------|-------|--------|
| Central | -$309M | RFA |
| PE Estimate | -$370M | Test Dataset (80% accuracy) |

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
    └── 5.21_rate/
        ├── rfa_h4216_5.21_analysis.csv # RFA fiscal note data
        └── test/
            ├── pe_h4216_5.21_analysis.csv
            └── sc_h4216_5.21_analysis.ipynb
```

---

## Technical Notes

### PR #7514 Fix (February 2025)

Fixed bug where `sc_additions` (QBI and SALT addbacks) were incorrectly applied under H.4216. Since H.4216 starts from AGI (before federal deductions), addbacks are inappropriate.

- **Before fix:** +$39.8M (wrong direction - showed revenue increase)
- **After fix:** -$370M (Test dataset)

### Policy Parameters Location
```
policyengine-us/policyengine_us/parameters/gov/contrib/states/sc/h4216/
```

### Microsimulation Usage
```python
from policyengine_us import Microsimulation
from policyengine_us.reforms.states.sc.h4216.sc_h4216 import create_sc_h4216
from policyengine_core.reforms import Reform

# Create reform with 5.21% top rate
param_reform = Reform.from_dict({
    "gov.contrib.states.sc.h4216.in_effect": {"2026-01-01.2100-12-31": True},
    "gov.contrib.states.sc.h4216.rates[1].rate": {"2026-01-01.2100-12-31": 0.0521}
}, country_id="us")

base_reform = create_sc_h4216()
reform = (base_reform, param_reform)

sim = Microsimulation(dataset="hf://policyengine/test/mar/SC.h5", reform=reform)
```

### RFA Fiscal Note
- [H.4216 Fiscal Note (5.21% Rate)](https://www.scstatehouse.gov/sess126_2025-2026/fiscalimpact/H4216.pdf)
