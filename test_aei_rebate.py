import pytest
import numpy as np
from policyengine_us import Microsimulation, CountryTaxBenefitSystem
from policyengine_core import Simulation
from aei_rebate import create_aei_reform


class TestAEIRebate:
    """Test cases for AEI rebate calculation"""
    
    @pytest.fixture
    def sim_with_reform(self):
        """Create microsimulation with AEI reform applied"""
        reform = create_aei_reform()
        return Microsimulation(
            dataset="hf://policyengine/policyengine-us-data/pooled_3_year_cps_2023.h5",
            reform=reform
        )
    
    def test_reform_adds_variable(self, sim_with_reform):
        """Test that reform successfully adds ca_aei_rebate variable"""
        assert "ca_aei_rebate" in sim_with_reform.tax_benefit_system.variables
    
    def test_full_rebate_at_150_percent_fpg(self, sim_with_reform):
        """Test household at exactly 150% FPG gets full rebate"""
        # Create test situation: household with income = 1.5 * FPG
        test_situation = {
            "households": {
                "household": {
                    "members": ["person"],
                    "state_code_str": {"2026": "CA"}
                }
            },
            "tax_units": {
                "tax_unit": {
                    "members": ["person"],
                    "adjusted_gross_income": {"2026": 24046},  # 150% of FPG
                }
            },
            "people": {
                "person": {}
            }
        }
        
        reform = create_aei_reform()
        tax_benefit_system = CountryTaxBenefitSystem(reform=reform)
        sim = Simulation(tax_benefit_system=tax_benefit_system, situation=test_situation)
        rebate = sim.calculate("ca_aei_rebate", 2026)
        fpg = sim.calculate("household_fpg", period=2026)
        
        # Should get full FPG amount
        assert rebate[0] == pytest.approx(fpg[0], rel=1e-2)
    
    def test_no_rebate_above_175_percent_fpg(self, sim_with_reform):
        """Test household above 175% FPG gets no rebate"""
        test_situation = {
            "households": {
                "household": {
                    "members": ["person"],
                    "state_code_str": {"2026": "CA"}
                }
            },
            "tax_units": {
                "tax_unit": {
                    "members": ["person"],
                    "adjusted_gross_income": {"2026": 32062},  # 200% of FPG (above 175% cutoff)
                }
            },
            "people": {
                "person": {}
            }
        }
        
        reform = create_aei_reform()
        tax_benefit_system = CountryTaxBenefitSystem(reform=reform)
        sim = Simulation(tax_benefit_system=tax_benefit_system, situation=test_situation)
        rebate = sim.calculate("ca_aei_rebate", 2026)
        
        # Should get no rebate
        assert rebate[0] == 0
    
    def test_partial_rebate_in_phaseout_range(self, sim_with_reform):
        """Test household in phase-out range gets partial rebate"""
        test_situation = {
            "households": {
                "household": {
                    "members": ["person"],
                    "state_code_str": {"2026": "CA"}
                }
            },
            "tax_units": {
                "tax_unit": {
                    "members": ["person"],
                    "adjusted_gross_income": {"2026": 26050},  # 162.5% of FPG (midpoint of phase-out)
                }
            },
            "people": {
                "person": {}
            }
        }
        
        reform = create_aei_reform()
        tax_benefit_system = CountryTaxBenefitSystem(reform=reform)
        sim = Simulation(tax_benefit_system=tax_benefit_system, situation=test_situation)
        rebate = sim.calculate("ca_aei_rebate", 2026)
        fpg = sim.calculate("household_fpg", period=2026)
        
        # Should get 50% of FPG (midpoint of phase-out)
        expected_rebate = fpg[0] * 0.5
        assert rebate[0] == pytest.approx(expected_rebate, rel=1e-2)
    
    def test_california_households_only(self, sim_with_reform):
        """Test that only California households are included in analysis"""
        ca_mask = sim_with_reform.calculate("state_code_str", map_to="household") == "CA"
        rebates = sim_with_reform.calculate("ca_aei_rebate")[ca_mask]
        
        # Should have some CA households
        assert ca_mask.sum() > 0
        # Should have some rebates
        assert (rebates > 0).sum() > 0
    
    def test_rebate_statistics_reasonable(self, sim_with_reform):
        """Test that overall rebate statistics are reasonable"""
        ca_mask = sim_with_reform.calculate("state_code_str", map_to="household") == "CA"
        rebates = sim_with_reform.calculate("ca_aei_rebate")[ca_mask]
        
        total_households = ca_mask.sum()
        households_with_rebates = (rebates > 0).sum()
        
        # Sanity checks
        assert total_households > 1e6  # At least 1M households
        assert households_with_rebates > 0  # Some households get rebates
        assert households_with_rebates < total_households  # Not all households get rebates
        assert households_with_rebates / total_households > 0.2  # At least 20% get rebates
        assert households_with_rebates / total_households < 0.5  # Less than 50% get rebates


if __name__ == "__main__":
    pytest.main([__file__])