#!/usr/bin/env python3
"""
Test numpy.bincount behavior to understand the bug.
"""

import numpy as np

def test_bincount():
    """Test how numpy.bincount works with weights and minlength."""
    
    print("=" * 60)
    print("TESTING NUMPY.BINCOUNT BEHAVIOR")
    print("=" * 60)
    
    # The bug appears to be in the sum() method line 148:
    # return numpy.bincount(self.members_entity_id, weights=array)
    
    # This should aggregate person values to tax units
    # But something goes wrong with minlength
    
    print("\n1. BASIC BINCOUNT TEST:")
    print("-" * 40)
    
    # Simulate person to tax unit mapping
    # 10 persons belonging to 5 tax units
    members_entity_id = np.array([0, 0, 1, 1, 2, 2, 3, 3, 4, 4])
    
    # Boolean eligibility array (0 or 1)
    eligibility = np.array([1, 0, 1, 1, 0, 0, 1, 0, 0, 1])
    
    # Using bincount to sum by tax unit
    result = np.bincount(members_entity_id, weights=eligibility)
    
    print(f"Person to tax unit mapping: {members_entity_id}")
    print(f"Person eligibility: {eligibility}")
    print(f"Tax unit sums: {result}")
    print("Expected: [1, 2, 0, 1, 1] - counts of eligible persons per tax unit")
    
    print("\n2. TESTING MINLENGTH PARAMETER:")
    print("-" * 40)
    
    # What if minlength is wrong?
    result_short = np.bincount(members_entity_id, weights=eligibility, minlength=3)
    result_long = np.bincount(members_entity_id, weights=eligibility, minlength=10)
    
    print(f"With minlength=3: {result_short}")
    print(f"With minlength=10: {result_long}")
    
    print("\n3. TESTING THE BUG SCENARIO:")
    print("-" * 40)
    
    # What if members_entity_id gets corrupted?
    # Or if the weights array is wrong size?
    
    # Scenario 1: Wrong entity IDs
    corrupted_ids = np.array([0, 0, 1, 1, 2, 2, 3, 3, 4, 4, 0, 0])  # Extra 0s added
    
    try:
        result_corrupted = np.bincount(corrupted_ids[:10], weights=eligibility)
        print(f"Normal result: {result_corrupted}")
    except:
        print("Error with normal weights")
    
    # But what if we accidentally use wrong weights?
    if len(corrupted_ids) == 12 and len(eligibility) == 10:
        # This would error
        print("Mismatch in array sizes would cause error")
    
    print("\n4. TESTING ACCUMULATION BUG:")
    print("-" * 40)
    
    # What if bincount is called multiple times and accumulates?
    # This could happen if the result array isn't reset
    
    result1 = np.bincount(members_entity_id, weights=eligibility)
    print(f"First calculation: {result1}")
    
    # If this gets added to existing values instead of replacing:
    result2 = result1 + np.bincount(members_entity_id, weights=eligibility)
    print(f"If accumulated (bug): {result2}")
    
    print("\n5. THE LIKELY BUG - CACHED ARRAYS:")
    print("-" * 40)
    
    # The bug might be that when calculating 2025 after 2026,
    # the members_entity_id or the result array is cached/corrupted
    
    # Simulate 2026 calculation
    members_2026 = np.array([0, 0, 1, 1, 2, 2, 3, 3, 4, 4])
    elig_2026 = np.array([0, 0, 1, 0, 0, 0, 1, 0, 0, 0])
    result_2026 = np.bincount(members_2026, weights=elig_2026)
    print(f"2026 result: {result_2026}")
    
    # Now 2025 with different eligibility
    elig_2025 = np.array([1, 0, 1, 1, 0, 0, 1, 0, 0, 1])
    result_2025_correct = np.bincount(members_2026, weights=elig_2025)
    print(f"2025 correct: {result_2025_correct}")
    
    # But what if the previous result isn't cleared?
    # Or if bincount is called with wrong parameters?
    
    # Hypothesis: The bug might be in the minlength parameter
    # Line 145 uses minlength=self.count
    # But line 148 doesn't specify minlength
    
    print("\n6. MINLENGTH BUG REPRODUCTION:")
    print("-" * 40)
    
    # If self.count changes between years...
    count_2026 = 5
    count_2025 = 5  # Should be same
    
    # But what if count gets corrupted to be larger?
    count_corrupted = 10
    
    result_normal = np.bincount(members_entity_id, weights=eligibility, minlength=count_2025)
    result_bug = np.bincount(members_entity_id, weights=eligibility, minlength=count_corrupted)
    
    print(f"Normal (minlength=5): {result_normal}")
    print(f"Bug (minlength=10): {result_bug}")
    print("Extra zeros don't cause the inflation we see...")
    
    print("\n7. THE REAL ISSUE - ARRAY REUSE?")
    print("-" * 40)
    
    # What if the array being passed as weights is wrong?
    # Or if members_entity_id is wrong?
    
    # This would cause the massive inflation we see
    wrong_weights = np.array([2, 2, 1, 1, 0, 1, 0, 0, 1, 0])  # Values > 1
    result_inflated = np.bincount(members_entity_id, weights=wrong_weights)
    
    print(f"With inflated weights: {result_inflated}")
    print("This matches what we see - values of 2, 3, etc. instead of just 0, 1")

if __name__ == "__main__":
    test_bincount()