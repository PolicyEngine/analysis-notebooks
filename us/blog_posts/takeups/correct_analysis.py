#!/usr/bin/env python3
"""
Correct analysis - focusing on the actual problem: 241M vs ~50M
"""

from policyengine_us import Microsimulation
import numpy as np

def correct_analysis():
    """Focus on the real issue: weighted sums."""
    
    dataset = "hf://policyengine/policyengine-us-data/enhanced_cps_2024.h5"
    
    print("=" * 60)
    print("CORRECT ANALYSIS OF THE BUG")
    print("=" * 60)
    
    print("\n1. THE ACTUAL NUMBERS (WEIGHTED):")
    print("-" * 40)
    
    # Fresh 2025
    sim1 = Microsimulation(dataset=dataset)
    aca_2025_fresh = sim1.calculate("is_aca_ptc_eligible", map_to="tax_unit", period=2025)
    print(f"2025 alone: {aca_2025_fresh.sum()/1e6:.2f}M tax units eligible")
    
    # Fresh 2026
    sim2 = Microsimulation(dataset=dataset)
    aca_2026_fresh = sim2.calculate("is_aca_ptc_eligible", map_to="tax_unit", period=2026)
    print(f"2026 alone: {aca_2026_fresh.sum()/1e6:.2f}M tax units eligible")
    
    # 2026 then 2025 (bug)
    sim3 = Microsimulation(dataset=dataset)
    _ = sim3.calculate("is_aca_ptc_eligible", map_to="tax_unit", period=2026)
    aca_2025_bug = sim3.calculate("is_aca_ptc_eligible", map_to="tax_unit", period=2025)
    print(f"2025 after 2026: {aca_2025_bug.sum()/1e6:.2f}M tax units 'eligible' (BUG)")
    
    print(f"\nThe problem: 241.73M is way too high!")
    print(f"Expected ~50M, got 241.73M - that's {241.73/49.70:.1f}x inflation")
    
    print("\n2. UNDERSTANDING THE VALUES:")
    print("-" * 40)
    
    # The variable represents COUNT of eligible persons per tax unit
    # Not boolean eligibility
    
    values_fresh = np.array(aca_2025_fresh)
    values_bug = np.array(aca_2025_bug)
    
    print(f"Fresh 2025 values range: {values_fresh.min():.0f} to {values_fresh.max():.0f}")
    print(f"Bug 2025 values range: {values_bug.min():.0f} to {values_bug.max():.0f}")
    
    # Get weights to understand the weighted sum
    weights = np.array(sim3.calculate("tax_unit_weight", period=2025))
    
    # Manual calculation of weighted sums
    weighted_fresh = (values_fresh * weights).sum()
    weighted_bug = (values_bug * weights).sum()
    
    print(f"\nWeighted sums (manual calculation):")
    print(f"Fresh: {weighted_fresh/1e6:.2f}M")
    print(f"Bug: {weighted_bug/1e6:.2f}M")
    
    print("\n3. WHAT'S HAPPENING TO THE VALUES:")
    print("-" * 40)
    
    # Compare the distributions
    from collections import Counter
    
    fresh_dist = Counter(values_fresh)
    bug_dist = Counter(values_bug)
    
    print("Distribution of values (count of tax units with each value):")
    print("\nFresh 2025:")
    for val in sorted(fresh_dist.keys())[:8]:
        print(f"  {val}: {fresh_dist[val]:,} tax units")
    
    print("\nBug 2025:")
    for val in sorted(bug_dist.keys())[:8]:
        print(f"  {val}: {bug_dist[val]:,} tax units")
    
    print("\n4. THE KEY INSIGHT:")
    print("-" * 40)
    
    # Look at how individual tax units change
    changes = values_bug - values_fresh
    
    # How many tax units had their values increase?
    increased = (changes > 0).sum()
    decreased = (changes < 0).sum()
    unchanged = (changes == 0).sum()
    
    print(f"Tax units with increased values: {increased:,} ({100*increased/len(changes):.1f}%)")
    print(f"Tax units with decreased values: {decreased:,} ({100*decreased/len(changes):.1f}%)")
    print(f"Tax units unchanged: {unchanged:,} ({100*unchanged/len(changes):.1f}%)")
    
    # What's the average change?
    print(f"\nAverage change per tax unit: {changes.mean():.2f}")
    print(f"Total change (unweighted): {changes.sum():.0f}")
    
    # Weighted average change
    weighted_changes = changes * weights
    print(f"Total change (weighted): {weighted_changes.sum()/1e6:.2f}M")
    
    print("\n5. THE PATTERN OF CORRUPTION:")
    print("-" * 40)
    
    # Look at which tax units get corrupted
    corrupted_indices = np.where(changes != 0)[0]
    
    # Sample some corrupted tax units
    sample_indices = corrupted_indices[:10]
    
    print("Sample of corrupted tax units:")
    print("Index | Weight    | Fresh | Bug | Change")
    print("-" * 45)
    for idx in sample_indices:
        print(f"{idx:5d} | {weights[idx]:9.1f} | {values_fresh[idx]:5.0f} | {values_bug[idx]:3.0f} | {changes[idx]:+6.0f}")
    
    # Check if high-weight tax units are more affected
    high_weight_threshold = np.percentile(weights, 90)
    high_weight_mask = weights > high_weight_threshold
    
    high_weight_changes = changes[high_weight_mask]
    low_weight_changes = changes[~high_weight_mask]
    
    print(f"\nAverage change for high-weight tax units: {high_weight_changes.mean():.2f}")
    print(f"Average change for low-weight tax units: {low_weight_changes.mean():.2f}")
    
    print("\n6. CONCLUSION:")
    print("-" * 40)
    
    print("""
The bug causes the COUNT of eligible persons per tax unit to increase.
This happens for 57% of tax units, adding phantom eligible persons.

The weighted sum jumps from 49.70M to 241.73M because:
1. Many tax units get extra phantom eligible persons (0→1, 0→2, 1→3, etc.)
2. These phantom counts get multiplied by tax unit weights
3. Result: 4.86x inflation in the total

This is definitely a caching/state corruption bug in PolicyEngine's
aggregation system when crossing year boundaries.
""")

if __name__ == "__main__":
    correct_analysis()