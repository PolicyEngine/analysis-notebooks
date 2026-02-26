# SC H.4216 Analysis Comparison: PolicyEngine vs RFA

## Summary

| Metric | RFA | PolicyEngine | Difference |
|--------|-----|--------------|------------|
| **General Fund Impact** | **-$119.1M** | **+$39.8M** | **+$158.9M** |
| Total Returns | 2,757,573 | 2,935,621 | +178,048 |
| Tax Decrease % | 38.7% | 20.0% | -18.7pp |
| Tax Increase % | 26.7% | 24.0% | -2.7pp |
| No Change % | 34.6% | 56.0% | +21.4pp |

## Top 5 Discrepancies by Income Bracket

| AGI Range | RFA Impact | PE Impact | Difference |
|-----------|------------|-----------|------------|
| Over $1,000,000 | -$13.8M | -$115.3M | -$101.5M |
| $50,001-$75,000 | -$82.1M | -$23.3M | +$58.9M |
| $100,001-$150,000 | +$3.1M | +$53.4M | +$50.3M |
| $300,001-$500,000 | -$4.6M | +$40.6M | +$45.3M |
| $500,001-$1,000,000 | -$16.2M | +$18.7M | +$34.9M |

## Key Differences Explaining the $159M Gap

### 1. Upper-Middle Income ($100k-$500k): PE Shows Much Larger Tax Increases

| Bracket | RFA Avg Change | PE Avg Change | Direction |
|---------|----------------|---------------|-----------|
| $100k-$150k | +$11 | +$284 | Both increase, PE 25x larger |
| $150k-$200k | +$355 | +$727 | Both increase, PE 2x larger |
| $300k-$500k | **-$82** | **+$1,099** | RFA: decrease, PE: increase |
| $500k-$1M | **-$631** | **+$1,129** | RFA: decrease, PE: increase |

**This is the primary driver of the difference.** PolicyEngine shows significant tax INCREASES in the $100k-$500k range where RFA shows small increases or even decreases.

### 2. Middle Income ($30k-$100k): PE Shows Smaller Tax Cuts

| Bracket | RFA Avg Change | PE Avg Change |
|---------|----------------|---------------|
| $30k-$40k | -$72 | -$23 |
| $40k-$50k | -$179 | -$135 |
| $50k-$75k | -$202 | -$77 |
| $75k-$100k | -$146 | -$71 |

RFA shows 2-3x larger tax cuts in these brackets.

### 3. Over $1M: PE Shows Much Larger Tax Cuts

| Metric | RFA | PE |
|--------|-----|-----|
| Avg Change | -$1,154 | -$5,082 |
| Total Impact | -$13.8M | -$115.3M |

PE shows 4-8x larger tax cuts for millionaires, but with more returns (22,686 vs 11,936).

### 4. Low Income ($0-$30k): Different Tax Bases

RFA shows existing tax liability for low-income filers ($50, $3, $16, $107 avg), while PE shows $0 for most low-income brackets. This suggests:
- Different baseline calculations
- Different treatment of non-filers
- CPS data may underrepresent low-income tax filers

## Likely Causes

### 1. Implementation Details (from PR #7494)

**Baseline SC Taxable Income:**
```python
taxable_income = federal_taxable_income + sc_additions - sc_subtractions
```
Where `federal_taxable_income` = AGI - standard/itemized deduction - QBI deduction

**H.4216 SC Taxable Income:**
```python
taxable_income = AGI + sc_additions - sc_subtractions - SCIAD
```
Where SCIAD phases out from $40k-$190k AGI (varies by filing status)

**Key Insight**: The reform switches from using federal taxable income (after federal deductions) to using AGI minus SCIAD. For taxpayers who itemize large deductions or have QBI deductions, this could result in HIGHER taxable income under H.4216.

### 2. SCIAD Phase-out Creates Winners and Losers

| Filing Status | SCIAD Amount | Phase-out Start | Phase-out End |
|---------------|--------------|-----------------|---------------|
| Single | $15,000 | $40,000 | $95,000 |
| MFJ | $30,000 | $80,000 | $190,000 |
| HoH | $22,500 | $60,000 | $142,500 |

For taxpayers above phase-out thresholds with SCIAD = $0:
- If their federal deduction was > $0, they lose that deduction entirely
- This explains why PE shows large tax INCREASES for $100k-$500k brackets

### 3. Baseline Tax Differences
PE baseline avg tax ($2,220) is lower than RFA ($2,321), suggesting different starting points for current law calculations.

### 4. Data Source Differences
- **RFA**: SC Department of Revenue 2024 tax returns (95% sample, inflated to 100%)
- **PE**: CPS-based synthetic data for South Carolina

Tax return data captures actual filers with precise income/deduction information. CPS-based data may:
- Over/underrepresent certain income groups
- Miss nuances in itemized vs standard deduction usage
- Have different filing status distributions

### 5. Federal Deduction Treatment
H.4216 eliminates federal standard/itemized deductions. The impact depends heavily on:
- Current deduction amounts by income level
- How many taxpayers itemize vs take standard deduction
- QBI deduction amounts (not replaced by SCIAD)

RFA has actual deduction data; PE estimates from CPS.

## Net Effect

The $159M difference primarily comes from:
1. **+$140M**: PE shows larger tax increases in $100k-$500k brackets
2. **+$59M**: PE shows smaller tax cuts in $30k-$100k brackets
3. **-$102M**: PE shows larger tax cuts for over $1M bracket
4. **+$60M**: Various other bracket differences

**Bottom line**: PolicyEngine's model shows the SCIAD phase-out creating more tax increases for upper-middle income taxpayers than RFA estimates, which more than offsets the tax cuts elsewhere.
