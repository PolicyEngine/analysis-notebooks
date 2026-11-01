# FISC Act marriage bonus

Richard Reeves asked PolicyEngine to rerun FISC reform 76612 with the 20 percent marriage bonus at zero, so that the difference gives the bonus's marginal cost, and to show who receives it. This folder holds that analysis. Every number is static and comes from a microsimulation run for that scenario.

## Result

The bonus costs $34.3 billion in 2026 and $334.5 billion over 2026-2035, the sum of ten calendar years in nominal dollars with no discounting.

| Year | Full FISC | FISC with the bonus at zero | Bonus |
|---|---|---|---|
| 2026 | -$145.31B | -$111.03B | -$34.28B |
| 2027 | -$138.23B | -$104.00B | -$34.23B |
| 2028 | -$136.27B | -$102.07B | -$34.20B |
| 2029 | -$128.23B | -$94.26B | -$33.97B |
| 2030 | -$125.77B | -$92.10B | -$33.67B |
| 2031 | -$118.67B | -$85.16B | -$33.50B |
| 2032 | -$115.23B | -$82.00B | -$33.23B |
| 2033 | -$107.71B | -$74.89B | -$32.82B |
| 2034 | -$104.18B | -$71.69B | -$32.49B |
| 2035 | -$96.06B | -$64.00B | -$32.06B |
| 2026-2035 | -$1,215.65B | -$881.19B | -$334.45B |

Each column shows the change in government revenue against current law, which equals the budget impact because the model moves no benefit spending when the credit changes. The bonus column subtracts the second column from the first. A direct comparison of policy 76612 over policy 99021 agrees: -$334.4522769B over ten years.

The figure depends on the data file. The same model and reform put the 2026 bonus at $25.3 billion on the file behind the March 2025 analysis, $29.6 billion on a resample of the 2024 CPS and $34.3 billion on the current dataset, and joint filers hold 54, 69 and 72 percent of base amounts in those files. Those three runs measure sensitivity to the file and set no uncertainty range. [Three data files](#three-data-files) sets out the comparison.

### Who receives it, 2026

These rows rank households on current-law household net income, the app's standard decile.

| Decile | Bonus | Share of the bonus | Households receiving | Mean per household | Percent of income |
|---|---|---|---|---|---|
| 1 | $1.44B | 4.2% | 8.4% | $85 | 0.32% |
| 2 | $3.20B | 9.3% | 16.1% | $231 | 0.49% |
| 3 | $4.02B | 11.7% | 20.0% | $320 | 0.52% |
| 4 | $4.45B | 13.0% | 22.5% | $352 | 0.46% |
| 5 | $4.05B | 11.8% | 23.1% | $328 | 0.35% |
| 6 | $4.24B | 12.4% | 24.9% | $357 | 0.31% |
| 7 | $5.03B | 14.7% | 30.3% | $444 | 0.31% |
| 8 | $4.21B | 12.3% | 29.0% | $392 | 0.22% |
| 9 | $2.89B | 8.4% | 18.9% | $269 | 0.11% |
| 10 | $0.74B | 2.2% | 4.5% | $66 | 0.01% |

The bonus reaches 24.0 million tax units and 23.9 million of 124.6 million households, and a receiving tax unit gets $1,429 on average.

These rows move with the data file. The bottom five deciles receive 50.1 percent of the bonus in the current dataset, 39.4 percent in the CPS and 36.2 percent in the March 2025 file, and the top three receive 22.9, 30.4 and 38.0 percent. `results/deciles_by_data_file_2026.csv` holds the decile rows for all three files.

Ranking on income adjusted for household size moves larger families down the distribution, so the bonus looks more concentrated at the bottom. On that ranking the bottom five deciles receive 61.9 percent of it and the top three 14.0 percent, against 50.1 percent and 22.9 percent above. `results/deciles_by_component_2026.csv` holds both rankings.

Two things shape these rows. Joint filers make up 38 percent of tax units with a child in decile 1 and 91 percent in decile 10. And the limits bite at each end. At 20 percent of joint filers' base amounts, the bonus would cost $40.9 billion. The phase-out removes $5.2 billion of that, nearly all of it in deciles 9 and 10, and the AGI cap removes $1.4 billion, mostly in decile 1.

| Decile | Joint share of tax units with a child | Statutory bonus | Lost to the phase-out | Lost to the AGI cap | Bonus paid |
|---|---|---|---|---|---|
| 1 | 38% | $2.28B | $0.00B | $0.84B | $1.44B |
| 2 | 42% | $3.37B | $0.00B | $0.17B | $3.20B |
| 3 | 59% | $4.22B | $0.00B | $0.20B | $4.02B |
| 4 | 70% | $4.54B | $0.00B | $0.09B | $4.45B |
| 5 | 70% | $4.08B | $0.00B | $0.02B | $4.05B |
| 6 | 76% | $4.26B | $0.00B | $0.02B | $4.24B |
| 7 | 84% | $5.04B | $0.00B | $0.01B | $5.03B |
| 8 | 85% | $4.23B | $0.00B | $0.02B | $4.21B |
| 9 | 87% | $4.61B | $1.72B | $0.00B | $2.89B |
| 10 | 91% | $4.21B | $3.47B | $0.00B | $0.74B |

The negative-income group adds $0.06 billion of statutory bonus, all of it lost to the cap.

### Is the bonus regressive?

No. Reeves suspected the bonus was "the most regressive piece of the design", and that suspicion does not hold on any of the three data files. A narrower version holds on all three: the bonus reaches the bottom of the distribution less than the rest of the credit does. How far it reaches depends on the file. The rows below use the current dataset, and [Three data files](#three-data-files) shows the other two.

- The bonus narrows inequality. It lowers the Gini of household net income from 0.47012 to 0.46941 and the Gini of equivalised income across people from 0.44545 to 0.44393.
- It cuts poverty from 11.68 percent to 11.31 percent and child poverty from 12.36 percent to 11.45 percent.
- As a percent of income it rises from 0.32 percent in decile 1 to 0.52 percent in decile 3, then falls to 0.01 percent in decile 10.
- Its concentration coefficient is +0.066 on household income and -0.184 on equivalised income. Both fall far below the 0.475 and 0.457 Ginis of those incomes, which marks a progressive transfer.
- Its dollars peak in the middle of the distribution: $42 per person in decile 1, $129 in decile 4, $146 in decile 7 and $21 in decile 10.
- The rest of the credit scores -0.075 and -0.288 and the newborn add-on -0.035 and -0.227, so both reach the bottom harder on either ranking. The bottom five deciles receive 61.3 percent of the rest of the credit, 62.2 percent of the add-on and 50.1 percent of the bonus.

The Gini change per dollar in the table below compares the bonus and the add-on less cleanly: the add-on lowers household Gini more per billion, and the bonus lowers equivalised Gini slightly more. The two pieces that raise inequality are the repeal of the child tax credit and the AGI cap. The cap raises it most per dollar and falls hardest on decile 1, which loses $219 per household, or 0.78 percent of income.

| Provision | Net cost | Gini without it | Gini with it | Gini change per $B | Equivalised Gini change per $B | Child poverty without it | Child poverty with it |
|---|---|---|---|---|---|---|---|
| Child tax credit repeal | -$133.21B | 0.47462 | 0.47773 | +0.000023 | +0.000042 | 18.02% | 23.06% |
| Credit without the bonus | $244.24B | 0.47773 | 0.47012 | -0.000031 | -0.000053 | 23.06% | 12.36% |
| Marriage bonus | $34.28B | 0.47012 | 0.46941 | -0.000021 | -0.000044 | 12.36% | 11.45% |
| Newborn add-on | $8.87B | 0.46963 | 0.46941 | -0.000025 | -0.000043 | 11.76% | 11.45% |
| Income phase-out | -$37.59B | 0.47018 | 0.46941 | -0.000021 | -0.000022 | 11.44% | 11.45% |
| AGI cap | -$8.75B | 0.46889 | 0.46942 | +0.000060 | +0.000088 | 10.77% | 11.45% |
| Full FISC | $145.31B | 0.47462 | 0.46941 | -0.000036 | -0.000062 | 18.02% | 11.45% |

The repeal and the credit add in sequence from current law. The other rows remove one provision from full FISC. The equivalised column and the AGI cap row come from the local runs, and the rest from the API. The reform floors the cap at zero, so no parameter lifts it at zero or negative AGI, and `run.py` removes it at every AGI for that row. API policy 99024 lifts the cap above zero AGI only, which costs $4.32 billion of the $8.75 billion. `results/provisions_2026.csv` keeps that row as `agi_cap_above_zero_agi`. `results/provisions_2026.csv` holds the decile detail, and each of its rows ranks deciles on income without that provision. `results/gini_by_provision_2026.csv` and `results/component_summary_2026.csv` hold the two Gini measures and each piece's concentration on both rankings.

The child tax credit that FISC repeals scores +0.084 on household income and -0.118 on equivalised income, so the bonus reaches the bottom harder than the child tax credit does on both rankings.

### Against the $30 billion estimate

Reeves's back-of-envelope figure, "arithmetic on the married share", came to about $30 billion a year. The model's $34.3 billion exceeds it by $4.3 billion, or 14 percent. At 20 percent, $30 billion implies a $150 billion married base. In the model joint filers hold $204.5 billion of base amount, 72 percent of $284.3 billion, before the limits apply, and $170.3 billion of credit once they apply, 70 percent of $244.3 billion. Twenty percent of the first gives the $40.9 billion statutory bonus, and the limits take that to $34.3 billion. On the March 2025 data, joint filers hold $153.1 billion of base amount, which sits close to the implied $150 billion and gives a $30.6 billion statutory bonus. The CPS resample gives a $29.6 billion bonus after the limits. `results/versus_reeves_estimate.csv` and `results/data_comparison_2026.csv` hold these lines. We do not know the inputs behind the $30 billion, so this analysis makes no claim about where the figures part.

### Against the March 2025 estimate

`fisc_act_10_year_impact.csv` shows an income tax change of -$193.14B for 2026, -$190.00B for 2035 and -$1,947.53B over ten years. Today's figures come to -$145.30B, -$96.27B and -$1,217.40B. A rerun of the March 2025 stack reproduces both checked years to within a dollar, and this ladder walks 2026 from one estimate to the other:

| Rung | Full FISC, income tax | Step | What the step changes |
|---|---|---|---|
| March 2025 model, data and law | -$193.14B | | |
| Today's model, March 2025 data, March 2025 child tax credit | -$200.16B | -$7.02B | Model code and law apart from the child tax credit |
| Today's model, March 2025 data, today's child tax credit | -$124.06B | +$76.09B | The baseline child tax credit |
| Today's model, today's data, today's child tax credit | -$145.30B | -$21.23B | The dataset |

The baseline accounts for the largest step. The March 2025 model carried a $1,000 child tax credit in 2026 and today's carries $2,200, so repealing it recovers more: in full FISC on the March 2025 data, the repeal offsets $34.3 billion of the credit under the old baseline and $110.4 billion under the new one. The first step mixes code changes with the rest of the 2025 law. The joint standard deduction for 2026, for example, stands at $16,600 in the March 2025 model and $32,200 today.

The order of the last two steps matters because they interact by $12.10 billion. Taking the dataset first makes it a -$33.33B step and the baseline a +$88.19B step. `results/march_2025_step_orders.csv` holds both orders. The ladder walks one path through 2026 and does not extend to the decade. Its first step runs only on the March 2025 data with the March 2025 child tax credit, and we did not run the March 2025 model on today's data, so the interactions of that step with the other two stay unmeasured.

The bonus moves differently, because no change in the child tax credit reaches it.

| | March 2025 stack | Today's model, March 2025 data | Today's model, today's data |
|---|---|---|---|
| Bonus, 2026 | $24.44B | $25.35B | $34.29B |
| Bonus, 2035 | $24.02B | | $32.06B |

The dataset supplies $8.94 billion of the $9.85 billion rise in 2026. Both files hold about the same base amount, $283.0 billion and $284.3 billion, and they split it differently.

### Three data files

The same model and reform ran on three files. Each ranks households within its own file.

| 2026 | March 2025 data | CPS resample | Current dataset | Census Bureau, 2023 |
|---|---|---|---|---|
| Children under 18 | 76.0M | 69.6M | 77.9M | 72.3M |
| Share of children in joint tax units | 53.9% | 68.6% | 71.6% | 66.7% with married parents |
| Joint tax units | 71.8M | 70.2M | 86.0M | 63.9M married couples |
| Joint tax units with a child | 25.1M | 25.6M | 28.9M | 24.0M married couples with own children |
| Base amount | $283.0B | $255.9B | $284.3B | |
| Joint share of base amount | 54.1% | 68.9% | 71.9% | |
| Statutory bonus | $30.6B | $35.3B | $40.9B | |
| Bonus paid | $25.3B | $29.6B | $34.3B | |
| Bottom five deciles' share of the bonus | 36.2% | 39.4% | 50.1% | |
| Top three deciles' share of the bonus | 38.0% | 30.4% | 22.9% | |
| Bottom five deciles' share of the rest of the credit | 48.4% | 50.8% | 61.3% | |
| Gini without the bonus | 0.53462 | 0.44640 | 0.47012 | |
| Gini with the bonus | 0.53425 | 0.44611 | 0.46942 | |
| Bonus concentration, household income | +0.262 | +0.257 | +0.066 | |
| Rest of the credit, household income | +0.124 | +0.135 | -0.075 | |
| Bonus concentration, equivalised income | -0.027 | -0.091 | -0.184 | |
| Rest of the credit, equivalised income | -0.126 | -0.193 | -0.288 | |

The Census column describes living arrangements in 2023, and the other columns count tax units in 2026. [Table C3](https://www.census.gov/data/tables/2023/demo/families/cps-2023.html) counts children living with married parents, and table FG3 counts opposite-sex married couple family groups. Tax units follow filing and dependency: a married grandparent who claims a child counts as a joint tax unit with a child, and the model files every married couple in a tax unit jointly. So the Census column gives context and tests no file.

The share of children in joint tax units runs above the Census share on the current dataset, close to it on the CPS resample and well below it on the March 2025 file. [PolicyEngine/microcosm#880](https://github.com/PolicyEngine/microcosm/issues/880) runs one piece of code over several files and counts married couples with a child under 18: 29.7 million on the current dataset, 25.8 million on the raw 2024 ASEC and 20.8 million on an older enhanced CPS, against 22.7 million in BLS data for 2025. [#1212](https://github.com/PolicyEngine/microcosm/issues/1212) and [#1070](https://github.com/PolicyEngine/microcosm/issues/1070) track its marital status and child counts. No source here counts joint filers with children on every file, so we report no corrected figure. Each figure comes from a full run on a real file.

Across the three files, the bonus narrows the Gini, its concentration falls below the Gini of income on both rankings, and the rest of the credit reaches the bottom more than it does. The share reaching the bottom half and the concentration on household income move a lot. Bonus dollars peak in decile 7 in the current dataset, decile 8 in the CPS resample and decile 9 in the March 2025 file, and dollars per person peak in the same deciles.

The CPS file comes from `policyengine_us_data`'s `CPS_2024`, which builds on the Census Bureau's 2024 ASEC and then resamples it. It draws households with replacement in proportion to their Census weights, and it saves each household's weight as a count of its draws, so the file holds 20,657 distinct households from 27,881 draws. Redrawing that sample 200 times from the saved households gives a standard deviation of $0.46 billion in the bonus and 0.7 percentage points in the bottom five deciles' share, and `results/cps_sampling_spread_2026.csv` holds the spread. The bonus on each other file sits at least nine of those standard deviations away. These runs cover 2026 only.

Today's model refuses the March 2025 file as it stands, because the file saves an SPM threshold that the model computes for itself. `run.py` copies the file without that column, and income tax does not read it. The model then ignores 16 more columns. The March 2025 model read `medicare_part_b_premiums` as part of health insurance premiums and several reported benefit amounts, and neither model reads the three retirement distribution columns or `is_widowed`.

## Method

**Reform.** Policy 76612 sets `gov.contrib.congress.golden.fisc_act.in_effect`. Policy 99021 adds `family_income_supplement.marriage_bonus_rate` at zero and changes nothing else. Policy 2 is current law.

**Bill and model.** H.R. 1308 Sec. 2(d)(2) raises the monthly payment by 20 percent for a married pregnant woman or a beneficiary married to a qualified caregiver of an eligible child. Sec. 2(d)(3) then cuts the payment, not below zero, by $16.67 a month for each whole $1,000 of AGI above $125,000, or $250,000 for spouses filing jointly, and Sec. 2(d)(4) caps it at a twelfth of the combined AGI of the beneficiary and spouse. Sec. 3 repeals the child tax credit. `policyengine_us/reforms/congress/golden/fisc_act.py` applies these steps in this order to an annual credit, and it reads the phase-out as a smooth 20 cents per dollar of AGI. The bill's steps come to $200.04 a year per whole $1,000. On these runs they would add $112.4 million to the credit and $15.3 million to the bonus. Every estimate here reruns reform 76612, so it uses the smooth phase-out. The test suite checks 54 household cases, including incomes between the $1,000 steps, against a closed form of the model's annual reading, and `analysis.stepped_credit` states the bill's steps.

**What the number answers.** It answers "what does FISC cost less with this provision removed?", because the bonus exists only inside the credit and enters before the phase-out and cap. The credit difference equals the income tax difference to within a fraction of a cent for every tax unit.

**Baseline.** Current law in policyengine-us 2.2.1, which carries the 2025 reconciliation law's child tax credit of $2,200 in 2026.

**Deciles.** `household_income_decile` ranks households on household net income with no size adjustment, and each decile holds about a tenth of people. These tables rank every component on current-law income so that the rows compare. Percent of income divides by current-law household net income. Households with negative net income take their own row, which receives $9 of the bonus.

**Gini.** The API's Gini matches household net income across households, with no equivalisation and with negative incomes left in, to within 0.00001 in all six scenarios that `summarize.py` compares. The second measure takes equivalised household net income across people, with negative incomes at zero.

**Concentration.** Each coefficient keeps one unit throughout, and tied incomes share a midrank. On household income it ranks households on household net income, weights them by household weight and counts household dollars. On equivalised income it ranks people on equivalised household net income, weights them by people and divides each household's dollars by the square root of its size. The 0.475 and 0.457 benchmarks use those same units with negative incomes left in, so the second differs from the equivalised Gini above, 0.453 at current law, which sets them to zero.

**Poverty.** The API reports poverty rates for every provision but the AGI cap, whose rates come from local person arrays. The model's `in_poverty` tests SPM unit net income against the SPM threshold, and `summarize.py` rebuilds each person's flag from those two arrays.

| Number | Path |
|---|---|
| Budget by year, poverty, household Gini, provision comparison | Production API, `results/api/` |
| Decile dollars, shares, receipt, percent of income | Local microsimulation |
| Equivalised Gini, concentration, joint shares, limits | Local microsimulation |
| AGI cap row of the provision table | Local microsimulation, `fisc_no_agi_cap` |
| Three data files | Local runs of today's bundle on each file |
| March 2025 comparison | Local rerun of the March 2025 stack, and local runs of today's bundle on the March 2025 data |

The local runs and the API use the same bundle. Local and API reform differences match to the dollar in every scenario compared: both put the bonus at $34.285367915B of income tax in 2026 and $32.064156757B in 2035, and the newborn, phase-out and above-zero AGI cap variants match at $8.8704B, -$37.5928B and -$4.3196B. Local income tax levels sit a constant $0.33 billion below the API's in all three core scenarios, and local net income sits $0.51 billion above it. Household counts, weights and child tax credit totals match exactly, so those do not explain the gap, and we have not traced its cause. It moves decile means by at most $1.72, in deciles 7 to 10. Local and API poverty rates for children and working-age adults match to 15 digits. The local rate for people 65 and over runs 0.0086 points above the API's, cause also untraced, which lifts the all-ages rate by 0.0015 points.

## Versions

- policyengine 6.11.1, which pins policyengine-us 2.2.1 and policyengine-core 3.33.3
- Dataset `hf://policyengine/populace-us/populace_us_2024.h5@populace-us-2024-spm-20260915`, sha256 `6496cc4393d4d3c6574f76eca231de5898c803b9067645591fd5c4d3e65aee84`
- `results/provenance.json` records the full bundle of the local runs, and each file in `results/api/` records the bundle of its API run
- The March 2025 stack runs policyengine-us 1.211.0 and policyengine-core 3.16.3 on `enhanced_cps_2024.h5` at Hugging Face revision 0611cbeda3, and `march_2025.py` records how to build it
- The CPS runs use `cps_2024.h5` from `policyengine/policyengine-us-data` at Hugging Face revision 21280dca59, sha256 `16b8cdbdc2c83d102fedb0f557d6de0a28344df4dacedb7ce95b587deef84fbc`

## Invariants

`summarize.py` raises before writing `results/invariants.json` if any of these fails:

- Decile rows sum to the aggregate.
- Restoring the bonus to 20 percent reproduces the full reform exactly.
- A rerun with the same versions gives identical arrays.
- No unmarried tax unit receives the bonus, and no bonus falls below zero.
- With the bonus at zero, no credit exceeds its base amount.
- Every tax unit's credit equals the closed form of the model's annual reading at 20 percent and at zero.
- In the bonus and AGI cap comparisons, every tax unit's income tax moves with its credit to within a dollar.
- In those comparisons, every household's net income moves by its change in benefits less its change in tax.
- Each household's credit equals the sum of its tax units' credits, rebuilt through person links.
- The bonus measured by income tax and by net income each sit within 0.1 percent of the bonus measured by the credit.
- The `fisc_no_agi_cap` credit equals the uncapped formula at every AGI, and that run pays credit at zero and negative AGI.
- Local and API results agree on the bonus in 2026 and 2035, the decile means, the Gini, and the poverty rates, within the tolerances `summarize.py` states.
- Every saved array and every table cell holds a finite number, apart from cells left blank on purpose, and saved equivalised income equals net income over the square root of household size.
- Each household's net income moves by its rebuilt credit less its rebuilt state income tax, to within a dollar. State income tax moves only for tax units whose credit moves, and its total matches the API's.
- With the AGI cap and without it, each person's poverty flag matches their SPM unit's income and threshold, the thresholds match, and each household's SPM income moves with its net income. Nobody enters poverty when the cap goes, someone leaves it, and the rates fall at or below the API's partial removal.
- Between 2026 and 2035 every record keeps its ages, joint status, base amount and household size, and every weight grows by one factor.
- On each of the three data files, the bonus lowers the Gini, concentrates below income and reaches the bottom less than the rest of the credit, on both rankings.
- No unmarried tax unit receives the bonus in 2035.
- The March 2025 rerun reproduces the published CSV in 2026 and 2035.

`test_analysis.py` states the formula and table properties for all inputs with Hypothesis. `test_summarize.py` confirms that the checks fail on runs that break them, including offsetting tax errors, net income with no tax or benefit behind it, a household bonus that misses its tax units, state tax with no credit behind it, poverty flags that their incomes do not explain, a saved NaN, and a file that breaks the regressivity answer. It also confirms that the decile rows sum to the aggregate.

## Caveats

- The estimates hold earnings, marriage, fertility and filing behaviour fixed. They say nothing about whether the bonus would change who marries.
- The model reads "married" as filing jointly, so a married couple filing separately gets no bonus, and neither does an unmarried couple raising a child together.
- The bill pays monthly on application to the Social Security Administration. The model pays an annual credit to every eligible tax unit, with no take-up rate.
- The bill tests AGI from the most recently ended taxable year, and the model tests the current year.
- The bill counts citizen, national or permanent resident children. The model has no such test, so it pays for some children the bill excludes.
- The bill requires that a child has provided no more than half of their own support, and that the caregiver lives with the child and supports the child economically. The model tests the child's age and tax dependency, and it looks for an adult head or spouse.
- The bill pays the bonus to a beneficiary married to a qualified caregiver of the child. The model pays it to every joint filer with an eligible child.
- The bill's cap combines the AGI of the beneficiary and spouse. The model uses tax unit AGI, including for couples filing separately.
- The bill creates a payment from the Social Security Administration and says nothing about means-tested benefits. The model treats the payment as a refundable income tax credit and moves no benefit, so these runs do not show whether the payment would change benefits.
- We have not put a dollar figure on any of these substitutions.
- The model pays $8,000 for a child under 1: $4,800 for twelve months at $400, and $3,200 for four months at $800 as a stand-in for pregnancy. The bill pays $800 a month once a pregnancy has lasted at least 20 weeks and starts the child's payment after the month of birth. The model has no separate count of pregnancies.
- The bill takes effect at least a year after enactment. These runs apply it to all of 2026.
- The current dataset calibrates a pool of CPS ASEC records to 2024 targets, and the model uprates incomes and scales weights to reach later years. From 2026 to 2035 every record keeps its ages, family structure, filing status and base amount, and every weight grows by 3.35 percent, so the decade holds no cohort aging and no change in family structure.
- The bonus and its distribution depend on how many parents file jointly, and the three data files put that share of base amounts at 54, 69 and 72 percent. The 2026 estimate moves by $9 billion across them, and the bottom five deciles' share by 14 percentage points. The spread measures sensitivity to the file and sets no uncertainty range.
- The ten-year figures and the poverty rates come from the current dataset alone.

## Reproduce

```bash
uv run --python 3.13 --with 'policyengine[models]==6.11.1' --with pytest --with hypothesis pytest us/congress/fisc_marriage_bonus -n 0
```

```bash
uv run us/congress/fisc_marriage_bonus/fetch_api.py us/congress/fisc_marriage_bonus/results/api
```

```bash
uv run us/congress/fisc_marriage_bonus/run.py fisc 2026 --out work
```

```bash
uv run us/congress/fisc_marriage_bonus/run.py fisc_no_agi_cap 2026 --out detail --detail
```

```bash
uv run us/congress/fisc_marriage_bonus/run.py fisc 2026 --out detail --detail
```

```bash
uv run us/congress/fisc_marriage_bonus/run.py fisc 2026 --dataset cps_2024.h5 --out cps --people
```

`run.py` takes one scenario and one year and holds about 14 GB of memory for about five minutes. `analysis.SCENARIOS` lists the scenarios, and the runs need 2026 for all of them and 2035 for `baseline`, `fisc` and `fisc_no_bonus`. `fisc_agi_cap_at_zero_only` matches API policy 99024, and `fisc_no_agi_cap` removes the cap at every AGI. The detail folder needs `fisc`, `fisc_no_bonus` and `fisc_no_agi_cap` for 2026 with `--detail`, which saves the poverty and state tax arrays beside each run. A rerun of `fisc_no_bonus` into a second folder supplies the determinism check. `march_2025.py` documents the older environment it needs, and it writes `baseline`, `fisc` and `fisc_no_bonus` for 2026 and 2035 into the March folder. The last rungs run `baseline_march_2025_ctc`, `baseline`, `fisc` and `fisc_no_bonus` for 2026 with `run.py --dataset enhanced_cps_2024.h5 --out ecps`, and `fisc` there also takes `--people`. The CPS folder needs `baseline`, `fisc --people` and `fisc_no_bonus` for 2026. Today's SPM code refuses both older files, so `--people` saves ages and weights without poverty. Then:

```bash
uv run --python 3.13 --with 'policyengine[models]==6.11.1' python us/congress/fisc_marriage_bonus/summarize.py --work work --rerun rerun --march march --ecps ecps --cps cps --detail detail
```
