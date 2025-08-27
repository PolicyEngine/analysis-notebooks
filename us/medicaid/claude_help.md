

## Using Your Old Outputs as Ground Truth

**Recreate key statistics and compare:**
- Total ACA enrollment (you noted ~2M drop - that's a red flag)
- Income distribution of enrollees 
- Average subsidy amounts by income level
- Count of people near the subsidy cliff (138-400% FPL)

**Reverse-engineer expected values:**
- If effects were in deciles 4-6 before, calculate what income range that implied
- Check if those income ranges in the new data still contain the population that should be affected by the cliff
- The subsidy cliff at 400% FPL should hit people around $50-60k (single) or $100-120k (family of 4) - verify which decile that falls into now

## Critical Checks Without Old Data

**Sanity check the new results:**
```python
# Check income percentiles to see if decile 9 makes sense
print(df.groupby('income_decile')['income'].describe())
print(f"400% FPL for single: {fpl_single * 4}")
print(f"400% FPL for family of 4: {fpl_family4 * 4}")

# Verify ACA enrollment totals
print(f"Total ACA enrollees: {df[df['aca_enrolled']==1]['weight'].sum()}")
# Compare to known ~14-15 million marketplace enrollment
```

**Look for data/code misalignment:**
- Variable name changes (income vs magi vs adjusted_income)
- Changes in categorical coding (0/1 vs 1/2 for enrollment)
- Unit changes (annual vs monthly income)
- Weight scaling issues (person weights in thousands vs ones)

## Most Likely Culprits

Given your symptoms, check these first:

1. **Income definition changed** - The decile shift suggests income might be calculated differently (e.g., excluding certain sources, or using post-tax instead of pre-tax)

2. **Weight rescaling** - A 2M drop in enrollment could be a simple weight scaling issue

3. **Sample universe** - The data team might have restricted to a different population (e.g., only tax filers, or excluded dependents)

4. **Decile calculation scope** - Are you calculating deciles over the full population or just ACA-eligible? This could drastically shift which incomes fall in decile 9

Would it help if I wrote some diagnostic code to check these specific issues? Also, what specific outputs did you document from your previous run - do you have things like mean income by decile, or counts of people at different FPL thresholds?