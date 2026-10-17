from collections import defaultdict

import coptpy as cp
import numpy as np
import pandas as pd


class CorrectedModelMixin:
    def _create_variables(self):
        super()._create_variables()
        if self.scenario != 'GTL-GH':
            return
        assert 24 % self.hours_per_period == 0
        self.ng_periods_per_day = 24 // self.hours_per_period
        assert self.total_hours % self.ng_periods_per_day == 0
        self.ng_days = self.total_hours // self.ng_periods_per_day
        self.ng_transport_by_technology_vars = {}
        self.ng_route_distances = {}
        for technology in ['pipeline_direct_conversion','lng_to_hplant_conversion']:
            allowed = self.config['transport_modes'][self.technologies[technology]['transport_mode']]['suitable_sources']
            for source in self.ng_locations+self.lng_terminal_locations:
                info = self.locations[source]
                if info['type'] not in allowed:
                    continue
                for destination in self.non_lng_mtj_locations[technology]:
                    self.ng_route_distances[source,destination] = self._calculate_location_distance(source,destination)
                    for day in range(self.ng_days):
                        key = source,destination,day
                        if key not in self.ng_transport_vars:
                            self.ng_transport_vars[key] = self.model.addVar(lb=0,name=f'ng_transport_{source}_{destination}_day_{day}')
                        self.ng_transport_by_technology_vars[source,destination,technology,day] = self.model.addVar(lb=0,name=f'ng_tech_{source}_{destination}_{technology}_day_{day}')

    def _create_cost_expressions(self):
        super()._create_cost_expressions()
        if self.scenario != 'GTL-GH':
            return
        rate,years = self.economic_params['discount_rate'],self.economic_params['project_lifespan']
        pv = years if rate == 0 else (1-(1+rate)**(-years))/rate
        expression = cp.quicksum(var*(4.52e-4*self.ng_route_distances[source,destination]+0.927) for (source,destination,day),var in self.ng_transport_vars.items())*52/self.time_horizon_weeks*pv
        change = expression-self.cost_expressions['ng_transport_operation']
        self.cost_expressions['ng_transport_operation'] = expression
        self.cost_aggregates['total_operation_cost'] += change
        self.cost_aggregates['total_cost_excluding_shortage'] += change

    def _create_carbon_emission_expressions(self):
        super()._create_carbon_emission_expressions()
        if self.scenario != 'GTL-GH':
            return
        extraction = self.carbon_params['raw_materials']['ng_extraction_intensity']
        # 配置中的罐车碳强度按每100公里给定，运输距离使用公里。
        truck = self.carbon_params['transportation']['ng_truck_intensity']/100
        raw = cp.quicksum(var*self.technologies[tech]['ng_consumption_ratio']*extraction for (loc,tech,t),var in self.production_vars.items())
        transport = cp.quicksum(var*self.ng_route_distances[source,destination]*truck for (source,destination,day),var in self.ng_transport_vars.items())
        raw_change = raw-self.carbon_expressions['ng_extraction']
        transport_change = transport-self.carbon_expressions['ng_transport']
        self.carbon_expressions['ng_extraction'] = raw
        self.carbon_expressions['ng_transport'] = transport
        self.carbon_aggregates['raw_material_emissions'] += raw_change
        self.carbon_aggregates['transport_emissions'] += transport_change
        self.carbon_aggregates['total_emissions'] += raw_change+transport_change
        self.carbon_aggregates['annual_emissions'] += (raw_change+transport_change)*52/self.time_horizon_weeks

    def _add_natural_gas_transport_constraints(self):
        if self.scenario != 'GTL-GH':
            return super()._add_natural_gas_transport_constraints()
        allocated,incoming = defaultdict(list),defaultdict(list)
        for (source,destination,tech,day),var in self.ng_transport_by_technology_vars.items():
            allocated[source,destination,day].append(var)
            incoming[destination,tech,day].append(var)
        truck = self.config['transport_constraints']['ng_truck_transport']
        self.ng_truck_daily_limit = truck['max_trucks_per_day']*truck['truck_capacity_m3']
        for key,var in self.ng_transport_vars.items():
            source,destination,day = key
            self.model.addConstr(var==cp.quicksum(allocated[key]),name=f'ng_allocation_{source}_{destination}_{day}')
            self.model.addConstr(var<=self.ng_truck_daily_limit,name=f'ng_daily_truck_capacity_{source}_{destination}_{day}')
        for tech in ['pipeline_direct_conversion','lng_to_hplant_conversion']:
            for destination in self.non_lng_mtj_locations[tech]:
                for day in range(self.ng_days):
                    periods = range(day*self.ng_periods_per_day,(day+1)*self.ng_periods_per_day)
                    demand = cp.quicksum(self.production_vars[destination,tech,t]*self.technologies[tech]['ng_consumption_ratio'] for t in periods)
                    self.model.addConstr(cp.quicksum(incoming[destination,tech,day])==demand,name=f'ng_daily_balance_{destination}_{tech}_{day}')
        self._add_lng_terminal_daily_capacity_constraints()

    def _add_lng_terminal_daily_capacity_constraints(self):
        if self.scenario != 'GTL-GH':
            return super()._add_lng_terminal_daily_capacity_constraints()
        outbound = defaultdict(list)
        for (source,destination,day),var in self.ng_transport_vars.items():
            outbound[source,day].append(var)
        self.ng_daily_capacities = {}
        for location in self.lng_terminal_locations:
            info = self.locations[location]
            capacity = float(self.lng_terminals[info['original_terminal_id']]['effective_daily_capacity_m3_per_day'])
            assert capacity>0,(location,info)
            self.ng_daily_capacities[location] = capacity
            for day in range(self.ng_days):
                periods = range(day*self.ng_periods_per_day,(day+1)*self.ng_periods_per_day)
                direct = cp.quicksum(self.production_vars[location,tech,t]*self.technologies[tech]['ng_consumption_ratio'] for tech in self.technologies for t in periods if (location,tech,t) in self.production_vars)
                self.model.addConstr(direct+cp.quicksum(outbound[location,day])<=capacity,name=f'ng_lng_daily_capacity_{location}_{day}')

    def _add_valid_inequalities(self):
        if self.scenario=='CTL' and self.diagnostic_scope.get('allow_ctl_shortage',False):
            return
        return super()._add_valid_inequalities()

    def _process_renewable_data(self, renewable_data):
        for name,rows in renewable_data.groupby('plant_name',sort=False):
            rows = rows.sort_values('period')
            assert np.array_equal(rows.period.to_numpy(),np.arange(self.total_hours)),name
            first = rows.iloc[0]
            self.locations[name] = {'type':first['type'],'latitude':float(first.latitude),'longitude':float(first.longitude),'capacity_mw':float(first.capacity_mw),'hourly_generation':rows.power_output_mw.to_list()}
        self._add_airports_to_locations()
        if self.scenario == 'GTL-GH':
            self._add_lng_terminals_to_locations()
            self._add_ng_pipelines_to_locations()

    def _process_airport_data(self, airport_data):
        frame = pd.read_csv(self.corrected_input / 'airport_input.csv')
        self.airports = {}
        for name, group in frame.groupby('departure_airport_name', sort=False):
            group = group.sort_values('week_number')
            demand = group.weekly_total_fuel_kg_total.to_numpy(dtype=float)
            self.airports[name] = {
                'latitude': float(group.departure_airport_latitude.iloc[0]),
                'longitude': float(group.departure_airport_longitude.iloc[0]),
                'weekly_demand_series': demand.tolist(),
                'avg_weekly_demand_kg': float(demand.mean()),
                'max_weekly_demand_kg': float(demand.max()),
                'total_annual_demand_kg': float(demand.sum()*13),
            }

    def build_model(self):
        self.solver_environment = cp.Envr()
        self.model = self.solver_environment.createModel(self.scenario)
        for name, value in {'TimeLimit':14400,'Threads':16,'LpMethod':2,'RelGap':0.001,'FeasTol':1e-7,'IntTol':1e-7}.items():
            self.model.setParam(name,value)
        if self.initial_solution_mode:
            for name,value in {'TimeLimit':1800,'Threads':8,'LpMethod':1}.items():
                self.model.setParam(name,value)
        self._create_variables()
        self._create_cost_expressions()
        self._create_constraints()
        self._add_joint_electricity_constraints()
        self._create_objective()

    def _add_renewable_power_constraints(self, location, hour):
        return

    def _add_hydrogen_production_constraints(self):
        maximum = self.config['capacity_limits']['electrolyzer_max_capacity_kg_per_hour']
        for location, capacity in self.electrolyzer_capacity_vars.items():
            assert self.locations[location]['type'] in ('solar_plant','wind_farm'), location
            self.model.addConstr(capacity <= maximum*self.electrolyzer_facility_vars[location],name=f'electrolyzer_capacity_{location}')
            for t in range(self.total_hours):
                self.model.addConstr(self.hydrogen_production_vars[location,t] <= capacity*self.hours_per_period,name=f'h2_production_capacity_{location}_{t}')

    def _add_dac_energy_constraints(self, energy_kwh_per_ton_co2, methanol_locations):
        # DAC变量在基础变量创建过程中生成，联合电力约束在全部变量创建后添加。
        self.corrected_dac_kwh_per_kg = float(energy_kwh_per_ton_co2)/1000

    def _add_joint_electricity_constraints(self):
        self.electricity_parameters = []
        saf_terms = defaultdict(list)
        for (location, technology, t), var in self.production_vars.items():
            saf_terms[location,t].append(var)
        for location, info in self.locations.items():
            renewable = info['type'] in ('solar_plant','wind_farm')
            if renewable:
                power = np.asarray(info['hourly_generation'],dtype=float)
                assert len(power) == self.total_hours and np.isfinite(power).all() and (power >= 0).all()
            for t in range(self.total_hours):
                h2 = self.hydrogen_production_vars.get((location,t),0)
                h2_energy = h2*self.costs['electrolysis_power_consumption']/1000
                saf = cp.quicksum(saf_terms[location,t])
                if self.scenario == 'GTL-GH':
                    intensity = float(self.config.get('carbon_intensity',{}).get('production_process',{}).get('mtj_process_energy',4500))/1000
                    if (location,t) in self.mtj_renewable_electricity_vars:
                        used = self.mtj_renewable_electricity_vars[location,t]
                        grid = self.mtj_grid_electricity_vars[location,t]
                        self.model.addConstr(used+grid == saf*intensity/1000,name=f'mtj_electricity_balance_{location}_{t}')
                        self.model.addConstr(h2_energy+used <= power[t]*self.hours_per_period,name=f'electricity_balance_{location}_{t}')
                        built = cp.quicksum(var for (loc,tech),var in self.facility_vars.items() if loc==location)
                        self.model.addConstr(used<=power[t]*self.hours_per_period*built,name=f'mtj_build_power_{location}_{t}')
                elif renewable:
                    intensity = 7.6
                    saf_energy = saf*intensity/1000
                    available = power[t]*self.hours_per_period
                    self.model.addConstr(h2_energy+saf_energy <= available,name=f'electricity_balance_{location}_{t}')
                if self.scenario.startswith('DAC-') and (location,t) in self.dac_co2_supply:
                    dac_energy = self.dac_co2_supply[location,t]*self.corrected_dac_kwh_per_kg/1000
                    grid = self.dac_grid_electricity_vars[location,t]/1000
                    self.model.addConstr(grid <= dac_energy,name=f'dac_grid_scope_{location}_{t}')
                    if renewable:
                        self.model.addConstr(h2_energy+saf*7.6/1000+dac_energy <= power[t]*self.hours_per_period+grid,name=f'dac_joint_electricity_{location}_{t}')
                    else:
                        self.model.addConstr(dac_energy == grid,name=f'dac_grid_balance_{location}_{t}')
        if self.scenario == 'GTL-GH':
            imported = {destination for source,destination in self.hydrogen_pipeline_transport_vars}
            for location,info in self.locations.items():
                if info['type'] not in ('solar_plant','wind_farm') or location in imported:
                    continue
                energy = sum(info['hourly_generation'])*self.hours_per_period
                builds = []
                consumption = []
                for (loc,tech),built in self.facility_vars.items():
                    if loc!=location:
                        continue
                    ratio = self.technologies[tech]['h2_consumption_ratio']*self.costs['electrolysis_power_consumption']/1000
                    embodied = cp.quicksum(self.production_vars[loc,tech,t]*ratio for t in range(self.total_hours))
                    self.model.addConstr(embodied<=energy*built,name=f'local_hydrogen_build_{loc}_{tech}')
                    builds.append(built)
                    consumption.append(embodied)
                mtj_energy = cp.quicksum(self.mtj_renewable_electricity_vars[location,t] for t in range(self.total_hours))
                self.model.addConstr(cp.quicksum(consumption)+mtj_energy<=energy*cp.quicksum(builds),name=f'joint_local_build_energy_{location}')
        self.electricity_scope = 'Hydrogen uses renewable electricity only; co-located synthesis shares the same pool; DAC grid purchases cover DAC only; nonrenewable synthesis retains grid supply.'

    def _add_hydrogen_balance_constraints(self):
        self.hydrogen_period_flow_vars = {}
        incoming, outgoing = defaultdict(list), defaultdict(list)
        limit = float(self.config['capacity_limits'].get('hydrogen_pipeline_max_daily_capacity_kg',50000))*self.hours_per_period/24
        profiles = {}
        if self.initial_solution_mode:
            for source in self.hydrogen_locations:
                power = np.asarray(self.locations[source]['hourly_generation']).reshape(self.time_horizon_weeks,self.periods_per_week)
                totals = power.sum(axis=1,keepdims=True)
                profiles[source] = np.divide(power,totals,out=np.zeros_like(power),where=totals>0).ravel()
        for (source,destination), weekly in self.hydrogen_pipeline_transport_vars.items():
            for t in range(self.total_hours):
                if self.initial_solution_mode:
                    var = weekly*profiles[source][t]
                else:
                    var = self.model.addVar(lb=0,ub=limit,name=f'corrected_h2_flow_{len(self.hydrogen_period_flow_vars)}')
                self.hydrogen_period_flow_vars[source,destination,t] = var
                outgoing[source,t].append(var)
                incoming[destination,t].append(var)
            for week in range(self.time_horizon_weeks):
                self.model.addConstr(cp.quicksum(self.hydrogen_period_flow_vars[source,destination,t] for t in range(week*self.periods_per_week,(week+1)*self.periods_per_week)) == weekly,name=f'h2_weekly_flow_{source}_{destination}_{week}')
            if self.initial_solution_mode:
                self.model.addConstr(weekly*float(profiles[source].max())<=limit,name=f'initial_profile_flow_cap_{source}_{destination}')
        production = defaultdict(list)
        for (location,technology,t),var in self.production_vars.items():
            production[location,t].append(var*self.technologies[technology]['h2_consumption_ratio'])
        for location in self.locations:
            if (location,0) not in self.hydrogen_storage_vars:
                assert not any(key[0] == location for key in incoming), location
                continue
            self.model.addConstr(self.hydrogen_storage_vars[location,0] == 0,name=f'corrected_h2_initial_{location}')
            for t in range(self.total_hours):
                self.model.addConstr(self.hydrogen_storage_vars[location,t+1] == self.hydrogen_storage_vars[location,t] + self.hydrogen_production_vars.get((location,t),0) + cp.quicksum(incoming[location,t]) - cp.quicksum(outgoing[location,t]) - cp.quicksum(production[location,t]),name=f'corrected_h2_balance_{location}_{t}')
