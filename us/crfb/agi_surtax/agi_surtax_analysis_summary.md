# CRFB AGI Surtax Reform - Analysis Summary

## Reform Parameters

**Single Filers:**
- 1% surtax on AGI above $100,000
- 2% surtax on AGI above $1,000,000

**Joint Filers:**
- 1% surtax on AGI above $200,000
- 2% surtax on AGI above $1,000,000

**Note:** This analysis covers both the basic AGI surtax and the expanded base option (which adds retirement contributions, HSA, tax-exempt income, etc.)

---

## 10-Year Revenue Estimate (2026-2035)

| Year | Revenue (Billions) |
|------|-------------------|
| 2026 | $64.72 |
| 2027 | $68.62 |
| 2028 | $72.74 |
| 2029 | $77.51 |
| 2030 | $82.99 |
| 2031 | $88.99 |
| 2032 | $95.46 |
| 2033 | $102.23 |
| 2034 | $109.78 |
| 2035 | $117.70 |
| **Total** | **$880.74** |

---

## Comparison with Other Estimates

| Source | Reform | 10-Year Estimate | Budget Window | Publication Date |
|--------|--------|------------------|---------------|------------------|
| [**PolicyEngine Microsim**](https://github.com/PolicyEngine/policyengine-us/pull/7230) | 1% on $100k/$200k, 2% on $1M | **$881B** | 2026-2035 | Jan 2026 |
| **PolicyEngine Microsim** | 1% on $100k/$200k, 2% on $1M (expanded base) | **$1,027B** | 2026-2035 | Jan 2026 |
| **PolicyEngine Microsim** | 2% on $100k/$200k (flat) | **$1,423B** | 2026-2035 | Jan 2026 |
| [**CBO Option 46a**](https://www.cbo.gov/budget-options/60938) (JCT) | 1% on $20k/$40k (flat) | $1,440B | 2025-2034 | Dec 2024 |
| [**CBO Option 46b**](https://www.cbo.gov/budget-options/60938) (JCT) | 2% on $100k/$200k (flat) | $1,051B | 2025-2034 | Dec 2024 |
| [**Tax Foundation**](https://taxfoundation.org/blog/millionaires-surtax/) | 10% on $1M/$2M | $716B | 2020-2029 | Jul 2023 |

---

## Expanded Base Option

The surtax can optionally be applied to an expanded income base that includes income sources typically excluded from AGI.

### 10-Year Revenue with Expanded Base (2026-2035)

| Year | Basic AGI | Expanded Base | Difference |
|------|-----------|---------------|------------|
| 2026 | $64.72B | $76.81B | +$12.09B |
| 2027 | $68.62B | $81.25B | +$12.63B |
| 2028 | $72.74B | $85.67B | +$12.93B |
| 2029 | $77.51B | $91.08B | +$13.57B |
| 2030 | $82.99B | $97.18B | +$14.19B |
| 2031 | $88.99B | $103.80B | +$14.81B |
| 2032 | $95.46B | $110.89B | +$15.43B |
| 2033 | $102.23B | $118.33B | +$16.10B |
| 2034 | $109.78B | $126.65B | +$16.87B |
| 2035 | $117.70B | $135.49B | +$17.79B |
| **Total** | **$880.74B** | **$1,027.15B** | **+$146.41B** |

### What the Expanded Base Adds

| Income Source | 2026 Microsim Total | Status |
|---------------|---------------------|--------|
| Traditional 401(k) contributions | $286B | ✅ Working |
| Tax-exempt Social Security | $864B | ✅ Working |
| Employer health insurance premiums | $528B | ✅ Working |
| Tax-exempt interest income | $109B | ✅ Working |
| Health Savings Account (ALD) | $4.5B | ✅ Working |
| Traditional IRA contributions | $2.4B | ✅ Working |
| Traditional 403(b) contributions | $0 | ⚠️ No data in CPS |
| Student loan interest (ALD) | $0 | ⚠️ Bug in eligibility check |
| Foreign earned income exclusion | $0 | ⚠️ Very few claimants |

**Notes:**
- ~$1.8T in additional income is captured by the expanded base (mostly 401k, Social Security, health insurance)
- 3 variables have no microsimulation data but work for individual household calculations
- The `student_loan_interest_ald` has a known bug (incorrectly requires American Opportunity Credit eligibility)

---

## Back-of-Envelope Validation

**Key IRS SOI data points (2022):**
- ~800k returns with AGI > $1M
- Top 1% (AGI > $663k) earned ~$3.3T
- Top 5% (AGI > $262k) earned ~$5.7T
- Total US AGI: ~$14.8T

**Rough calculation:**

1. **2% bracket (>$1M):** ~$1.5-2T in AGI above $1M threshold × 2% = ~$30-40B

2. **1% bracket ($100k/$200k to $1M):** ~$3-4T in AGI in this range × 1% = ~$30-40B

3. **Total estimate:** ~$60-80B/year

The 2026 microsim result of **$65B is within this range**.

---

## Analysis Notes

**Why PolicyEngine estimate ($881B) is lower than CBO's 2% option ($1,051B):**

1. **Different rate structure:**
   - CBO: flat 2% on ALL AGI above $100k/$200k
   - CRFB: 1% on $100k-$1M, then 2% only on AGI above $1M

2. **Lower effective rate:** The CRFB reform only applies 2% to millionaire income; income between $100k-$1M is taxed at just 1%

3. **Behavioral responses:** CBO estimates from JCT may incorporate different behavioral assumptions

**Implication:** The CRFB tiered structure raises ~$170B less than a flat 2% surtax because it taxes the $100k-$1M bracket at half the rate.

---

## Sources

- [CBO - Options for Reducing the Deficit: 2025 to 2034](https://www.cbo.gov/system/files/2024-12/60557-budget-options.pdf) (Dec 2024)
- [CBO Budget Option 60938 - AGI Surtax](https://www.cbo.gov/budget-options/60938)
- [Tax Foundation - Millionaire's Surtax](https://taxfoundation.org/blog/millionaires-surtax/) (Jul 2023)
- [CRFB - CBO's Revenue Options](https://www.crfb.org/blogs/cbos-revenue-savings-options)
- [IRS SOI - Individual Tables by AGI](https://www.irs.gov/statistics/soi-tax-stats-individual-statistical-tables-by-size-of-adjusted-gross-income)
- [Tax Foundation - Federal Income Tax Data 2025](https://taxfoundation.org/data/all/federal/latest-federal-income-tax-data-2025/)
