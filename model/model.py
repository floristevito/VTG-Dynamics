import agentpy as ap
import pandas as pd
import networkx as nx
from components import *
from OD_matrix import (generate_OD)
import logging
import numpy as np
from timeit import default_timer as timer

"""
Main model block
"""


class EtmEVsModel(ap.Model):
    """Main model that simulates electric vehicles."""

    def setup(self):
        start = timer()
        # configure model log
        logging.basicConfig(filename='model.log', filemode='w',
                            format='%(name)s - %(levelname)s - %(message)s', level=logging.DEBUG)

        # model properties
        self.price_history = [[0] for i in range(96)]
        self.ma_price_history = []
        self.Electricity_price = pd.read_csv(
            '../data/prizes_electricity_365_days_per_15_minutes.csv')
        self.average_battery_percentage = 100
        self.total_current_power_demand = None
        self.total_VTG_capacity = None
        self.mean_charging = None
        # generate the manicipalities according to data prep file
        self.OD = generate_OD(self.p.g, self.p.m)
        self.municipalities_data = pd.read_csv(
            '../data/gemeenten.csv').set_index('GM_CODE')
        # generate all manucipality agents
        self.municipalities = ap.AgentList(self, len(self.OD), Municipality)
        # calculate percentage evs
        percentage_ev = self.p.n_evs / sum(self.municipalities_data['AANT_INW'])
        # give the right properties to every municipality according to data prep file
        for index, (key, value) in enumerate(self.OD.items()):
            self.municipalities.id[index] = key
            self.municipalities.name[index] = self.municipalities_data.loc[key, 'GM_NAAM']
            self.municipalities.OD[index] = value
            self.municipalities.inhabitants[index] = self.municipalities_data.loc[key, 'AANT_INW']
            self.municipalities.number_EVs[index] = round(
                percentage_ev * self.municipalities.inhabitants[index])
        self.weekend = False
        self.t_weekend = 480
        # correct rounding in number evs
        number_evs = sum(self.municipalities.number_EVs)
        if number_evs > self.p.n_evs:
            n = number_evs - self.p.n_evs
            for i in range(n):
                self.municipalities.random().number_EVs -= 1
        elif number_evs < self.p.n_evs:
            n = self.p.n_evs - number_evs
            for i in range(n):
                self.municipalities.random().number_EVs += 1
        self.number_evs = sum(self.municipalities.number_EVs)
        # generate EV's
        # generate EV agentlist
        self.EVs = ap.AgentList(self, 0, EV)
        index = 0  # keeps track of the EV index
        # give the right properties to every EV according to the data prep file
        for mun in self.municipalities:
            mun_start = timer()
            if mun.number_EVs > 0:
                sampled_dest = mun.OD.sample(
                        mun.number_EVs, weights='p_flow', random_state=self.p.seed, replace=True)
            for ev in range(mun.number_EVs):
                # generate ev and add to agentlist
                new_ev = EV()
                self.EVs.append(new_ev)
                # set home location
                self.EVs.home_location[index] = mun.name
                self.EVs.home_id[index] = mun.id
                # pick destination, higher p_flow gives higher chance to be picked
                mapped_dest = sampled_dest.iloc[[ev]]
                work_location_id = mapped_dest['destination_id'].iloc[0]
                self.EVs.work_location_id[index] = work_location_id
                self.EVs.work_location_name[index] = self.municipalities_data.loc[work_location_id, 'GM_NAAM']
                commute_distance = mapped_dest['distance'].iloc[0]
                self.EVs.commute_distance[index] = commute_distance
                # travel times in 15 minutes units
                self.EVs.travel_time[index] = max(1, round(
                    commute_distance/self.p.average_driving_speed))  # give at least 1 time step
                # give a enery required for trip memory
                energy_required = self.EVs.energy_rate[index] * \
                    commute_distance
                self.EVs.energy_required[index] = energy_required
                # check if maximum battery volume in model is enough to reach destination, if not, give the value needed to reach destination
                if self.model.p.h_vol < energy_required:
                    self.EVs.battery_volume[index] = energy_required
                    logging.warning(
                        'vehicle created with extended volume outside max volume range')
                # check if battery volume is enough to reach destination, if not draw triangular going down from energy required
                if self.EVs.battery_volume[index] < energy_required:
                    self.EVs.battery_volume[index] = self.random.triangular(energy_required, energy_required + 1, self.model.p.h_vol)  
                    # self.EVs.battery_volume[index] = self.random.triangular(
                    #     self.model.p.l_vol, self.model.p.m_vol, self.model.p.h_vol)
                # set current volume to final max volume
                self.EVs.current_battery_volume[index] = self.EVs.battery_volume[index] * 0.9
                # set VTG percentage
                self.EVs.allowed_VTG_percentage = self.model.p.VTG_percentage
                mun.current_EVs.append(self.EVs[index])
                index += 1
            mun_end = timer()
            logging.debug("mun {} complete, create {} evs, total {} evs created, create time {}, time now {}, evs per sec {}".\
                format(mun.name, mun.number_EVs, index + 1, round(mun_end - mun_start), \
                    round(mun_end - start), round(mun.number_EVs / (mun_end - mun_start))))
        end = timer()
        logging.info("Model init completed in {} seconds".format(end - start))
        # push some stats to log file
        logging.info('MODEL CONFIGURATION')
        logging.info('EVs in model: {}'.format(len(self.EVs)))
        logging.info('Municipalities in model: {}'.format(
            len(self.municipalities)))
        logging.info('average battery volume of EVs (kWh): {}'.format(
            np.mean(list(self.EVs.battery_volume))))
        logging.info(
            'average energy rate of EVs (kWh/km): {}'.format(np.mean(list(self.EVs.energy_rate))))

    def step(self):
        # update weekend property
        if self.t % self.t_weekend == 0:
            self.weekend = True
            self.t_weekend += 672
        if self.t % 672 == 0:
            self.weekend = False

        if self.weekend:
            logging.info("{} Weekend day".format(self.t))
        else:
            logging.info("{} it's no weekend.".format(self.t))

        # for EVs
        self.fill_history()
        self.calc_ma_price_history()
        self.EVs.step()
        self.average_battery_percentage = np.mean(
            list(self.EVs.battery_percentage))
        self.total_current_power_demand = np.sum(
            list(self.EVs.current_power_demand))
        self.total_VTG_capacity = np.sum(list(self.EVs.VTG_capacity))
        self.mean_charging = np.mean(list(self.EVs.charging))
        # debug stats
        logging.debug('time {} EVs on road:{}'.format(self.model.t, len(
            self.EVs.select(self.EVs.current_location == 'onroad'))))
        logging.debug('time {} EVs at home:{}'.format(self.model.t, len(
            self.EVs.select(self.EVs.current_location == 'home'))))
        logging.debug('time {} EVs at work:{}'.format(self.model.t, len(
            self.EVs.select(self.EVs.current_location == 'work'))))

        # for municipalities
        self.municipalities.step()

    def update(self):
        """ Record dynamic variables """
        self.record('average_battery_percentage')
        self.municipalities.record('average_battery_percentage')
        self.record('total_current_power_demand')
        self.municipalities.record('current_power_demand')
        self.record('total_VTG_capacity')
        self.municipalities.record('current_vtg_capacity')
        self.record('mean_charging')
        self.municipalities.record('current_power_demand')
        self.municipalities.record('number_EVs')

    def fill_history(self):
        '''
        Fills the memory of agents with the previous prices

        SHOULD BE DONE ON SUPERCLASS LEVEL TO SAVE DATA AND COMPUTATIONS

        '''
        index = self.t
        if self.t > len(self.Electricity_price['Electricity_price']):
            index = self.t % len(self.Electricity_price['Electricity_price'])
        self.price_history[(
            self.t % 96)-1].append(round(self.Electricity_price['Electricity_price'][self.t], 2))

    def calc_ma_price_history(self):
        '''
        From self.price_history creates avarage prices for a 24h cycle

        Could be expanded to a 4*24h cycle if wanted

        '''
        self.ma_price_history.clear()
        for i in self.price_history:
            segment = i[max(-7, -len(i)):]
            self.ma_price_history.append(round(np.mean(segment), 2))
