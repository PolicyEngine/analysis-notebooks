# Repeal State Dependent Exemptions

Reform parameter: `gov.contrib.repeal_state_dependent_exemptions.in_effect`

This reform repeals all state-level dependent exemptions, credits, and deductions that are specifically tied to the number of dependents in a tax unit. Updated formulas replace `tax_unit_size` or `exemptions_count` (which include dependents) with `head_spouse_count` (which excludes them).

## Microsimulation results

Dataset: `enhanced_cps_2024` | Period: 2024

| Metric | Value |
|---|---|
| Total state tax revenue increase | $5.87B |
| Total household net income decrease | -$5.87B |
| Benefit spending change | $0 |
| Households affected | 20.7M (14.4%) |
| States affected | 34 of 51 |

Full state-by-state results are in `state_impacts_detailed.csv`.

### Top 10 states by net income impact

| State | Net income impact | State tax revenue change | Avg change/HH | % HH affected |
|---|---|---|---|---|
| CA | -$2.43B | +$2.43B | -$163 | 23.1% |
| MI | -$479M | +$479M | -$107 | 24.7% |
| MN | -$433M | +$433M | -$165 | 29.2% |
| IL | -$350M | +$350M | -$60 | 26.9% |
| GA | -$255M | +$255M | -$52 | 20.7% |
| NY | -$245M | +$245M | -$29 | 24.0% |
| SC | -$195M | +$195M | -$82 | 13.4% |
| OH | -$157M | +$157M | -$31 | 23.4% |
| MD | -$140M | +$140M | -$56 | 21.6% |
| NJ | -$117M | +$117M | -$30 | 33.8% |

## Variables modified by the reform

### Neutralized variables (set to zero)

These are dependent-specific variables that are entirely zeroed out.

| Variable | State | Description |
|---|---|---|
| `al_dependent_exemption` | AL | Alabama dependent exemption |
| `il_dependent_exemption` | IL | Illinois dependent exemption |
| `la_dependents_exemption` | LA | Louisiana dependents exemption |
| `mn_exemptions` | MN | Minnesota exemptions (includes dependents) |
| `ms_dependents_exemption` | MS | Mississippi dependents exemption |
| `nj_dependents_exemption` | NJ | New Jersey dependents exemption |
| `ny_exemptions` | NY | New York exemptions (includes dependents) |
| `sc_dependent_exemption` | SC | South Carolina dependent exemption |
| `ut_personal_exemption` | UT | Utah personal exemption (includes dependents) |
| `nc_child_deduction` | NC | North Carolina child deduction |
| `nm_deduction_for_certain_dependents` | NM | New Mexico deduction for certain dependents |
| `mt_dependent_exemptions_person` | MT | Montana dependent exemptions per person (no effect in 2024; MT eliminated exemptions) |
| `az_dependent_tax_credit` | AZ | Arizona dependent tax credit |
| `ar_personal_credit_dependent` | AR | Arkansas personal credit for dependents |
| `id_ctc` | ID | Idaho child tax credit |
| `me_dependent_exemption_credit` | ME | Maine dependent exemption credit |

### Updated variables (formula changed to exclude dependents)

These variables originally used `tax_unit_size`, `exemptions_count`, or `tax_unit_dependents` to include dependents. The reform replaces those with `head_spouse_count` or removes the dependent component.

| Variable | State | Original pattern | Reform change |
|---|---|---|---|
| `hi_regular_exemptions` | HI | `exemptions_count` (all members) | Uses `head_spouse_count` (head + spouse only) |
| `md_total_personal_exemptions` | MD | `tax_unit_size` (all members) | Uses `head_spouse_count` |
| `mi_personal_exemptions` | MI | `exemptions_count` (all members) | Uses `head_spouse_count` + stillborn children |
| `ne_exemptions` | NE | `exemptions_count` (all members) | Uses `head_spouse_count` |
| `oh_personal_exemptions_eligible_person` | OH | Eligible if head/spouse OR dependent | Eligible only if head/spouse |
| `ok_count_exemptions` | OK | Included dependent exemptions in count | Head + spouse exemptions only |
| `ri_exemptions` | RI | `exemptions_count` (all members) | Uses `head_spouse_count` |
| `vt_personal_exemptions` | VT | Counted dependents in total | Head + spouse only |
| `va_personal_exemption_person` | VA | Applied to all members | Head + spouse only |
| `wv_personal_exemption` | WV | `tax_unit_size` (all members) | Uses `head_spouse_count` |
| `ca_exemptions` | CA | Included dependent credit count | Personal + aged/blind only |
| `ga_exemptions` | GA | `personal + dependent` exemptions | Personal exemptions only |
| `in_base_exemptions` | IN | `exemptions_count` (all members) | Uses `head_spouse_count` |
| `ks_exemptions` | KS | Included dependent amount (2024: `by_filing_status.dependent * dependents`) | Removes dependent amount; keeps base + HOH + veteran amounts |
| `ma_income_tax_exemption_threshold` | MA | Threshold included dependent count | Threshold for head/spouse only |
| `wi_base_exemption` | WI | `exemptions_count` (all members) | Uses `head_spouse_count` |
| `ia_exemption_credit` | IA | Counted dependents in exemption credit | Head/spouse + elderly/blind only |
| `de_personal_credit` | DE | `exemptions_count` (all members) | Uses `head_spouse_count` |
| `ky_family_size_tax_credit_rate` | KY | `tax_unit_size` for poverty index | Uses `head_spouse_count` for poverty index |
| `ok_child_care_child_tax_credit` | OK | Greater of 20% CDCC potential or 5% CTC | 20% of CDCC only (removes CTC component) |

## Out-of-scope variables

The following variables reference dependents but are **not** dependent exemptions. They are separate tax programs (credits, rebates, tax rate selection, EITC adjustments) and are intentionally excluded from this reform.

| Variable | State | Type | Reason excluded |
|---|---|---|---|
| `ct_child_tax_rebate` | CT | Rebate | Per-child cash rebate, not an exemption |
| `ct_property_tax_credit_eligible` | CT | Credit eligibility | Eligibility check (dependents OR elderly) |
| `il_income_tax_rebate` | IL | Rebate | Base + per-dependent rebate amount |
| `ar_low_income_tax_joint` | AR | Tax rate selection | Selects low-income tax table by dependent count |
| `az_family_tax_credit_eligible` | AZ | Credit eligibility | Income limit varies by dependent count |
| `vt_eitc` | VT | EITC adjustment | Match rate varies by child count |
| `ks_fstc` | KS | Food sales tax credit | Credit per exemption for food sales tax |
| `ma_part_b_taxable_income_exemption` | MA | Part B exemption | Includes dependent component but is a broader exemption |
| `ma_scb_total_income` | MA | Income calculation | Re-adds exemptions for Senior Circuit Breaker |
| `hi_disabled_exemptions` | HI | Disabled filer exemption | Dependent exemption only when head/spouse is disabled |
| `wi_homestead_income` | WI | Credit income | Reduces income by dependent exemption for homestead credit |

## Methodology

The analysis follows the exact same pattern as the PolicyEngine API (`budget.py` / `compare.py`):

- `sim.calc()` returns `MicroSeries` with embedded survey weights
- `.sum()` gives weighted population totals (no manual weight multiplication)
- `.count()` gives total household count (sum of weights)
- `household_tax`, `household_state_income_tax`, `household_benefits`, `household_net_income` match the API's tracked variables
- State-level groupby uses `MicroSeries.groupby(state_code).sum()` for weighted aggregation

## Files

- `repeal_state_dependent_exemptions.py` - Analysis script
- `state_impacts_detailed.csv` - Full state-by-state results
- `README.md` - This documentation
