"""
Minnesota CTC Reform

This module defines a reform that modifies Minnesota's Child Tax Credit (CWFC):
- Sets the CTC amount to $2,000 per child (up from $1,750)
- Sets the main phase-out rate to 20% (up from 12%)
- Leaves the other phase-out rate (ctc_ineligible_with_qualifying_older_children) unchanged at 9%
"""

from policyengine_core.reforms import Reform


def create_mn_ctc_reform():
    """
    Create a reform that:
    - Sets MN CTC amount to $2,000
    - Sets the main phase-out rate to 20%
    """
    reform = Reform.from_dict(
        {
            # Set CTC amount to $2,000 per child
            "gov.states.mn.tax.income.credits.cwfc.ctc.amount": {
                "2025-01-01.2100-12-31": 2000
            },
            # Set main phase-out rate to 20%
            "gov.states.mn.tax.income.credits.cwfc.phase_out.rate.main": {
                "2025-01-01.2100-12-31": 0.20
            },
        },
        country_id="us",
    )
    return reform


# For direct use in notebooks
mn_ctc_reform = create_mn_ctc_reform()
