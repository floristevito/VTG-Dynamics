import agentpy as ap
import pandas as pd
import networkx as nx
from components import *
from OD_matrix import (generate_OD)

"""
Main model block
"""

class EmtAgentsModel(ap.Model):
    """Main model that simulates electric vehicles"""
    def setup(self):
        
        # generate the manicipalities according to data prep file
        self.OD = generate_OD(self.p.g)
        self.municipalities_data = pd.read_csv('../data/gemeenten.csv').set_index('GM_CODE')
        self.municipalities = ap.AgentList(self, len(self.OD), Municipality)
        # give the right properties to every municipality according to data prep file
        for index, (key, value) in enumerate(self.OD.items()):
            self.municipalities.id[index] = key
            self.municipalities.name[index] = self.municipalities_data.loc[key, 'GM_NAAM']
            self.municipalities.OD[index] = value
            self.municipalities.inhabitants[index] = self.municipalities_data.loc[key, 'AANT_INW']
            self.municipalities.number_EVs[index] = round(self.p.percentage_ev * self.municipalities.inhabitants[index])
        
        # generate EV's 
        self.EVs = ap.AgentList(self, sum(self.municipalities.number_EVs), EV)
        index = 0 # keeps track of the EV index
        # give the right properties to every EV according to the data prep file
        for mun in self.municipalities:
            for ev in range(mun.number_EVs):
                self.EVs.home_location[index] = mun.name
                mapped_dest = mun.OD.sample(1, weights='p_flow')
                self.EVs.work_lococation_id[index] = mapped_dest['destination_id'].iloc[0]
                self.EVs.work_location_name[index] = self.municipalities_data.loc[self.EVs.work_lococation_id[index], 'GM_NAAM']
                self.EVs.commute_distance[index] = mapped_dest['distance'].iloc[0]
                index += 1
    
    def step(self):
        # move EVs
        self.EVs.step()
    
    def update(self):
        """ Record a dynamic variable. """
        self.EVs.record('energy')
