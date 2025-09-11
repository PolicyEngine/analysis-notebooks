#!/usr/bin/env python3
"""
Examine how rating areas are assigned to tax units in the datasets
"""

from policyengine_us import Microsimulation
import pandas as pd
import numpy as np

print("Loading datasets...")
print("=" * 70)

# Load both datasets
old_baseline = Microsimulation(dataset="/Users/daphnehansell/Documents/GitHub/analysis-notebooks/us/medicaid/enhanced_cps_2024.h5")
new_baseline = Microsimulation(dataset="hf://policyengine/policyengine-us-data/enhanced_cps_2024.h5")

year = 2026

print("\nEXAMINING RATING AREA ASSIGNMENTS")
print("=" * 70)

# Get rating areas for tax units
print("\n1. Getting rating area data...")
old_rating_area = old_baseline.calculate("slcsp_rating_area", map_to="household", period=year)
new_rating_area = new_baseline.calculate("slcsp_rating_area", map_to="household", period=year)

# Get state codes as strings
old_states = old_baseline.calculate("state_code_str", map_to="household", period=year)
new_states = new_baseline.calculate("state_code_str", map_to="household", period=year)

# Get counties
old_county = old_baseline.calculate("county_str", map_to="household", period=year)
new_county = new_baseline.calculate("county_str", map_to="household", period=year)

# Get weights
weights = old_rating_area.weights

# Create DataFrames for analysis
old_df = pd.DataFrame({
    'state': old_states,
    'county': old_county,
    'rating_area': old_rating_area,
    'weight': weights
})

new_df = pd.DataFrame({
    'state': new_states,
    'county': new_county,
    'rating_area': new_rating_area,
    'weight': weights
})

print("\n2. RATING AREA DISTRIBUTION:")
print("-" * 40)

# Overall distribution
print("Old dataset rating areas:")
print(old_df['rating_area'].value_counts().head(10))
print(f"\nTotal unique rating areas: {old_df['rating_area'].nunique()}")

print("\nNew dataset rating areas:")
print(new_df['rating_area'].value_counts().head(10))
print(f"\nTotal unique rating areas: {new_df['rating_area'].nunique()}")

print("\n3. CHECKING IF ALL UNITS IN A STATE HAVE SAME RATING AREA:")
print("-" * 40)

# Check a few key states
test_states = ['AL', 'CA', 'FL', 'NY', 'TX']
state_names = ['Alabama', 'California', 'Florida', 'New York', 'Texas']

for state_code, state_name in zip(test_states, state_names):
    old_state_df = old_df[old_df['state'] == state_code]
    new_state_df = new_df[new_df['state'] == state_code]
    
    old_unique_areas = old_state_df['rating_area'].nunique()
    new_unique_areas = new_state_df['rating_area'].nunique()
    
    print(f"\n{state_name} (code {state_code}):")
    print(f"  Old dataset: {old_unique_areas} unique rating area(s)")
    if old_unique_areas <= 5:
        print(f"    Areas: {sorted(old_state_df['rating_area'].unique())}")
    print(f"  New dataset: {new_unique_areas} unique rating area(s)")
    if new_unique_areas <= 5:
        print(f"    Areas: {sorted(new_state_df['rating_area'].unique())}")

print("\n4. COUNTY ASSIGNMENTS BY STATE:")
print("-" * 40)

# Check what counties are assigned
for state_code, state_name in zip(test_states[:3], state_names[:3]):
    old_state_df = old_df[old_df['state'] == state_code]
    new_state_df = new_df[new_df['state'] == state_code]
    
    old_counties = old_state_df['county'].value_counts().head(3)
    new_counties = new_state_df['county'].value_counts().head(3)
    
    print(f"\n{state_name}:")
    print("  Old dataset top counties:")
    for county, count in old_counties.items():
        print(f"    {county}: {count} households")
    print("  New dataset top counties:")
    for county, count in new_counties.items():
        print(f"    {county}: {count} households")

print("\n5. RATING AREA VS COUNTY RELATIONSHIP:")
print("-" * 40)

# Check if rating area 1 dominates (the default)
old_area1_pct = (old_df['rating_area'] == 1).mean() * 100
new_area1_pct = (new_df['rating_area'] == 1).mean() * 100

print(f"Percentage of households with rating area = 1:")
print(f"  Old dataset: {old_area1_pct:.1f}%")
print(f"  New dataset: {new_area1_pct:.1f}%")

# Check weighted percentages
old_area1_weighted = ((old_df['rating_area'] == 1) * old_df['weight']).sum() / old_df['weight'].sum() * 100
new_area1_weighted = ((new_df['rating_area'] == 1) * new_df['weight']).sum() / new_df['weight'].sum() * 100

print(f"\nWeighted percentage with rating area = 1:")
print(f"  Old dataset: {old_area1_weighted:.1f}%")
print(f"  New dataset: {new_area1_weighted:.1f}%")

# Sample some specific households to see their assignments
print("\n6. SAMPLE HOUSEHOLD ASSIGNMENTS (first 10):")
print("-" * 40)
print("\nOld dataset:")
print(old_df[['state', 'county', 'rating_area']].head(10))
print("\nNew dataset:")
print(new_df[['state', 'county', 'rating_area']].head(10))

# Check if counties are truly the first alphabetically
print("\n7. VERIFYING ALPHABETICAL COUNTY ASSIGNMENT:")
print("-" * 40)

for state_code, state_name in zip(test_states[:2], state_names[:2]):
    old_state_df = old_df[old_df['state'] == state_code]
    most_common_county = old_state_df['county'].mode()[0] if len(old_state_df) > 0 else "N/A"
    print(f"\n{state_name}: Most common county = '{most_common_county}'")
    print(f"  (Should be first alphabetically in the state)")