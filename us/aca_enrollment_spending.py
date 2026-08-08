from policyengine_us import Microsimulation
import pandas as pd

YEAR = 2025

STATES = [
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "DC", "FL",
    "GA", "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME",
    "MD", "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH",
    "NJ", "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI",
    "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI",
]

results = []

for state in STATES:
    print(f"Processing {state}...")
    try:
        sim = Microsimulation(
            dataset=f"hf://policyengine/policyengine-us-data/states/{state}.h5"
        )
        aca_ptc = sim.calc("aca_ptc", period=YEAR, map_to="person")
        enrolled = (aca_ptc > 0).sum()
        spending = aca_ptc.sum()
        results.append({
            "state": state,
            "aca_enrollment": enrolled,
            "aca_spending": spending,
        })
        print(f"  {state}: {enrolled:,.0f} enrolled, ${spending:,.0f} spending")
    except Exception as e:
        print(f"  ERROR for {state}: {e}")
        # CA workaround: set in_la=False to avoid LA county rating area bug
        if state == "CA":
            import numpy as np
            print(f"  Retrying {state} with in_la workaround...")
            sim = Microsimulation(
                dataset=f"hf://policyengine/policyengine-us-data/states/{state}.h5"
            )
            household = sim.populations['household']
            sim.set_input('in_la', YEAR, np.zeros(household.count, dtype=bool))
            aca_ptc = sim.calc("aca_ptc", period=YEAR, map_to="person")
            enrolled = (aca_ptc > 0).sum()
            spending = aca_ptc.sum()
            results.append({
                "state": state,
                "aca_enrollment": enrolled,
                "aca_spending": spending,
            })
            print(f"  {state}: {enrolled:,.0f} enrolled, ${spending:,.0f} spending")
        else:
            results.append({
                "state": state,
                "aca_enrollment": None,
                "aca_spending": None,
            })

# National
print("\nProcessing national...")
sim_national = Microsimulation()
aca_ptc_national = sim_national.calc("aca_ptc", period=YEAR, map_to="person")
national_enrolled = (aca_ptc_national > 0).sum()
national_spending = aca_ptc_national.sum()
results.append({
    "state": "US (National)",
    "aca_enrollment": national_enrolled,
    "aca_spending": national_spending,
})

df = pd.DataFrame(results)
df["aca_spending_billions"] = df["aca_spending"] / 1e9
df = df.sort_values("aca_enrollment", ascending=False)

print("\n" + "=" * 70)
print("ACA Enrollment and Spending by State")
print("=" * 70)
print(df.to_string(index=False, float_format=lambda x: f"{x:,.0f}"))

df.to_csv(f"us/aca_enrollment_spending_by_state_{YEAR}.csv", index=False)
print("\nSaved to us/aca_enrollment_spending_by_state.csv")
