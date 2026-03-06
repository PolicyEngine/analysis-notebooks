# SC H.4216 Analysis Comparison: PolicyEngine vs RFA

## Executive Summary

**UPDATE (March 2025):** After PR #7514 fix and testing multiple datasets:

| Dataset | 5.21% Impact | vs RFA (-$309M) | 5.39% Impact | vs RFA (-$119M) |
|---------|--------------|-----------------|--------------|-----------------|
| **Production** | -$393M | 73% accuracy | -$198M | 34% accuracy |
| **Test (Mar)** | -$212M | 69% accuracy | -$93M | 78% accuracy |
| **RFA** | -$309M | - | -$119M | - |

**Key Finding:** Neither dataset consistently matches RFA. Production overestimates cuts, Test underestimates them. The core issue is baseline revenue calibration.

---

## Dataset Comparison

### Overview

| Metric | Production | Test | RFA |
|--------|------------|------|-----|
| **Tax Units** | 2,935,621 | 2,705,850 | 2,757,573 |
| **Baseline Revenue** | $6.5B | $4.0B | ~$6.4B |
| **Median HH AGI** | $43,222 | $34,927 | N/A |
| **Avg HH AGI** | $103,858 | $74,061 | N/A |
| **25th Percentile AGI** | $9,425 | $2,489 | N/A |
| **Max AGI** | $6.4M | $418.7M | N/A |

### Budget Impact Comparison

| Rate | Production | Test | RFA | Best Match |
|------|------------|------|-----|------------|
| **5.21%** | -$393M | -$212M | -$309M | Production (73%) |
| **5.39%** | -$198M | -$93M | -$119M | Test (78%) |

---

## Why Production OVERESTIMATES

Production estimates -$198M vs RFA's -$119M at 5.39% rate (**67% over**)

### 1. Higher Average Incomes
- Production median AGI: **$43,222** vs Test $34,927
- Production avg AGI: **$103,858** vs Test $74,061
- More high earners = larger tax cuts when rates drop

### 2. Higher Baseline Revenue
- Production: **$6.5B** baseline revenue
- Test: $4.0B baseline revenue
- Production has **63% more** baseline revenue than Test
- Bigger revenue base = bigger absolute cuts

### 3. More Tax Units Than RFA
- Production: 2,935,621 tax units
- RFA: 2,757,573 filers
- **+178,048 extra units** (6.5% more)
- Includes non-filers with imputed income

### 4. Fewer Low-Income Units
- Production 25th percentile: **$9,425**
- Test 25th percentile: $2,489
- Production has fewer truly low-income/zero-tax units
- More taxpayers affected by rate changes

---

## Why Test UNDERESTIMATES

Test estimates -$93M vs RFA's -$119M at 5.39% rate (**22% under**)

### 1. Lower Baseline Revenue
- Test: **$4.0B** baseline revenue
- RFA: ~$6.4B estimated baseline
- Test has **37% less** revenue than RFA
- Smaller revenue base = smaller absolute cuts

### 2. Lower Average Incomes
- Test avg AGI: **$74,061** vs Production $103,858
- Fewer high-income taxpayers paying significant taxes
- Smaller tax liabilities to cut

### 3. Extreme Outlier at Top
- Test max AGI: **$418.7M** (single household)
- Production max: $6.4M
- One extreme outlier may distort millionaire calculations
- Could skew average tax calculations

### 4. More Low-Income Units
- Test 25th percentile AGI: **$2,489**
- Production 25th percentile: $9,425
- More zero-tax units diluting the weighted averages
- More units unaffected by rate changes

---

## The Core Issue: Baseline Revenue Calibration

| Source | Baseline Revenue | vs RFA |
|--------|------------------|--------|
| **RFA** | ~$6.4B | - |
| **Production** | $6.5B | **+2%** |
| **Test** | $4.0B | **-37%** |

### What Each Dataset Gets Right/Wrong

**Production Dataset:**
- ✅ Matches RFA baseline revenue (~$6.5B)
- ❌ Wrong income distribution (too many high earners)
- ❌ Overestimates tax cuts at all rates

**Test Dataset:**
- ✅ Better return count (2.71M vs 2.76M RFA)
- ❌ Severely underestimates baseline revenue ($4B vs $6.4B)
- ❌ Underestimates tax cuts at all rates

### Ideal Dataset Would Have:
- Test's return count (~2.7M matching RFA's 2.76M filers)
- Production's baseline revenue (~$6.5B matching RFA's ~$6.4B)
- RFA's millionaire distribution (11,936 returns over $1M)

---

## Technical Details

### PR #7514 Fix (February 2025)

Fixed bug where `sc_additions` (QBI and SALT addbacks) were incorrectly applied under H.4216. Since H.4216 starts from AGI (before federal deductions), addbacks are inappropriate.

**Before fix:** +$39.8M (wrong direction)
**After fix:** -$93M to -$198M depending on dataset

### H.4216 Reform Structure

**Baseline SC Taxable Income:**
```
taxable_income = federal_taxable_income + sc_additions - sc_subtractions
```

**H.4216 SC Taxable Income:**
```
taxable_income = AGI - sc_subtractions - SCIAD
```

**Rate Structure:**
- Current: 0% up to $3,640, 3% $3,640-$18,230, 6% over $18,230
- H.4216: 1.99% up to $30,000, 5.21%/5.39% over $30,000

### SCIAD Phase-out

| Filing Status | Amount | Phase-out Start | Phase-out End |
|---------------|--------|-----------------|---------------|
| Single | $15,000 | $40,000 | $95,000 |
| MFJ | $30,000 | $80,000 | $190,000 |
| HoH | $22,500 | $60,000 | $142,500 |

---

## Recommendations

### For Data Team:
1. Investigate why Test dataset has only $4B baseline revenue vs $6.4B actual
2. Recalibrate weights to match SC tax filer distribution
3. Validate millionaire counts against IRS SOI data

### For Analysis:
1. Use Production for directional analysis (correct baseline revenue)
2. Use Test for return count validation (closer to RFA filer count)
3. Report range of estimates: -$93M to -$198M for 5.39% rate

### For Reporting:
- RFA 5.39% estimate: **-$119.1M**
- RFA 5.21% estimate: **-$309.0M**
- PE best estimates: **-$93M to -$198M** (5.39%), **-$212M to -$393M** (5.21%)
