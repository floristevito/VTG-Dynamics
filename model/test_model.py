import pytest
from model import EtmEVsModel


@pytest.fixture
def example_params():
    return {
        'steps': 10,
        'g': 0.000076,
        'm': 3,
        'percentage_ev': 0.0000029 * 0.2,# 0.0000029 * 0.2,0.00003
        'VTG_percentage': 0.15,
        'charging_speed_min': 20,
        'charging_speed_max': 60,
        'l_dep': 20,
        'm_dep': 23,
        'h_dep': 44,
        'offset_dep': 2,
        'l_dwell': 12,
        'm_dwell': 28,
        'h_dwell': 36,
        'offset_dwell': 3,
        'average_driving_speed': 10,
        'l_vol': 16.7,
        'm_vol': 59.6,
        'h_vol': 107.8,
        'l_energy': 0.104,
        'm_energy': 0.192,
        'h_energy': 0.281,
        'p_smart': 1,
        'seed': 4,
    }

def test_number_agents(example_params):
    example_model = EtmEVsModel(example_params)
    example_model.setup() 
    agents_start = len(example_model.EVs)
    example_model.run()
    agents_end = len(example_model.EVs)
    assert agents_start == agents_end

def test_power_demand(example_params):
    example_model = EtmEVsModel(example_params)
    example_model.setup()
    example_model.run()
    power_demands = [] 
    for i in example_model.municipalities:
        power_demands.append(i.current_power_demand)
    assert min(power_demands) >= 0 

def test_min_drive_range_agents(example_params):
    example_model = EtmEVsModel(example_params)
    example_model.setup() 
    ranges = []
    for i in example_model.EVs:
        range = i.battery_volume / i.energy_rate 
        ranges.append(range)
    assert min(ranges) > 50

def test_max_drive_range_agents(example_params):
    example_model = EtmEVsModel(example_params)
    example_model.setup() 
    ranges = []
    for i in example_model.EVs:
        range = i.battery_volume / i.energy_rate 
        ranges.append(range)
    assert max(ranges) < 1000