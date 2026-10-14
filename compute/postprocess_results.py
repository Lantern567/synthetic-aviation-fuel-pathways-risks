import json
import hashlib
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from scipy.optimize import linear_sum_assignment
from validate_algebra import validation_passed

base = Path(__file__).resolve().parent
scenarios = ['CCU-GH-FT','CCU-GH-MTJ','DAC-GH-FT','DAC-GH-MTJ','GTL-GH','CTL']
original = pd.read_csv(base / 'original_pathway_metrics.csv').set_index('scenario')
old_sites = pd.read_csv(base / 'original_synthesis_sites.csv')
archive = (base.parents[1] / 'nexus_revision_20260929/evidence' if os.name=='nt' else Path('/home/ljt/code_project/green_methanol_for_port_transportation-main')) / 'products/supply_chain_optimization'


def carbon_total(scenario,terms):
    keys = ['saf_facility','electrolyzer_facility','methanol_to_saf','h2_production','mtj_storage','h2_storage','h2_transport','mtj_transport','co2_utilization_credit']
    if scenario=='GTL-GH':
        keys += ['ng_extraction','ng_to_methanol','ng_transport']
    else:
        keys += ['saf_synthesis_energy']
        if scenario=='CTL':
            keys += ['coal_mining','coal_transport','coal_gasification_direct','coal_gasification_energy','coal_co2_fugitive','co2_capture_energy']
        else:
            keys += ['co2_transport']
            if scenario.startswith('DAC-'):
                keys += ['dac_equipment','dac_grid_electricity']
    return sum(terms[key] for key in keys)


carbon_audit = []
for scenario in scenarios:
    data = json.loads((archive / original.loc[scenario,'source_file']).read_text(encoding='utf-8'))
    computed = carbon_total(scenario,data['carbon_emissions']['detailed'])
    reported = data['carbon_emissions']['by_stage']['total_emissions']
    assert np.isclose(computed,reported,rtol=1e-12,atol=1e-6),(scenario,computed,reported)
    carbon_audit.append({'scenario':scenario,'reported_total_kg':reported,'recomputed_total_kg':computed,'difference_kg':computed-reported})
pd.DataFrame(carbon_audit).to_csv(base / 'carbon_aggregation_check.csv',index=False)

rows,weekly_rows,new_sites,pending,leave_one_out = [],[],[],[],[]
for scenario in scenarios:
    for label in ['baseline','summer_fixed']:
        diagnostic = scenario=='CTL' and (base / 'ctl_infeasibility.json').exists()
        run_root = base.with_name(base.name+'_ctl_partial') if diagnostic else base
        out = run_root / 'runs' / scenario / label
        if (run_root / 'verified_runs' / scenario / label / 'summary.json').exists():
            out = run_root / 'verified_runs' / scenario / label
        if not (out / 'physical_validation.json').exists() or (out / 'EXPORT_IN_PROGRESS').exists():
            pending.append(f'{scenario}/{label}')
            continue
        physical = json.loads((out / 'physical_validation.json').read_text())
        if physical.get('solution_summary_sha256')!=hashlib.sha256((out / 'summary.json').read_bytes()).hexdigest():
            pending.append(f'{scenario}/{label}: physical validation for current summary')
            continue
        assert physical['passed'],(scenario,label)
        data = json.loads((out / 'summary.json').read_text())
        assert validation_passed(data['algebraic_validation']),(scenario,label,data['algebraic_validation'])
        assert data['gap']<=0.010001,(scenario,label,data['gap'])
        config = yaml.safe_load((out / 'config.yaml').read_text())
        total = carbon_total(scenario,data['carbon_expressions'])
        if 'carbon_aggregates' in data:
            assert np.isclose(total,data['carbon_aggregates']['total_emissions'],rtol=1e-12,atol=1e-6)
        energy = config['carbon_emission_parameters']['benchmarks']['saf_energy_content']
        row = {key:data[key] for key in ['scenario','label','production_kg','demand_kg','shortage_kg','demand_fulfillment_ratio','cost_per_kg_excluding_shortage','saf_capacity_kg_h','h2_capacity_kg_h','mean_utilization','worst_week_retention','gap','seconds']}
        row.update(model_variant='CTL partial-supply diagnostic; original 90% minimum is infeasible' if diagnostic else 'Retained model with corrected resource accounting and balances',objective=data['objective'],lower_bound=data['lower_bound'],objective_gap_relative_to_cost_excluding_shortage=data['objective_gap_relative_to_cost_excluding_shortage'],seconds_scope=data.get('seconds_scope','Final full-model dispatch solve only' if data['status']=='verified_decomposition_certificate' else 'Native solver elapsed time'),source_directory=str(out))
        row.update(carbon_intensity_kg_kg=total/data['production_kg'],carbon_intensity_g_mj=total/data['production_kg']/energy*1000,full_demand_served=data['demand_fulfillment_ratio']>=1-1e-8,physical_checks_passed=True,mean_capacity_premium_percent=(1/data['mean_utilization']-1)*100)
        for key in ['cost_per_kg_excluding_shortage','saf_capacity_kg_h','h2_capacity_kg_h']:
            row['original_'+key] = float(original.loc[scenario,key])
            row[key+'_change_percent'] = (row[key]/row['original_'+key]-1)*100
        rows.append(row)
        for week in data['weekly']:
            weekly_rows.append(dict(scenario=scenario,label=label,**week))
        capacity = pd.read_csv(out / 'saf_capacity.csv')
        locations = json.loads((out / 'model_parameters.json').read_text())['locations']
        capacity = capacity[capacity.value>1e-5].copy()
        capacity['latitude'] = capacity.location.map(lambda name:locations[name]['latitude'])
        capacity['longitude'] = capacity.location.map(lambda name:locations[name]['longitude'])
        sites = capacity.groupby(['latitude','longitude'],as_index=False).value.sum().rename(columns={'value':'capacity_kg_h'})
        sites['scenario'],sites['label'] = scenario,label
        new_sites.append(sites)
        row['physical_site_count'] = len(sites)
        if label=='baseline':
            for omitted in data['weekly']:
                values = [w['utilization'] for w in data['weekly'] if w['week']!=omitted['week']]
                mean,worst = float(np.mean(values)),min(values)
                leave_one_out.append({'scenario':scenario,'omitted_source_week':omitted['source_week'],'mean_utilization_percent':mean*100,'worst_week_utilization_percent':worst*100,'worst_week_retention_percent':worst/mean*100,'mean_capacity_premium_percent':(1/mean-1)*100,'additional_worst_week_premium_percent':(1/worst-1/mean)*100,'model_variant':row['model_variant'],'scope':'Static deletion of one week from optimized baseline dispatch; no rerun'})
if '--complete' in sys.argv:
    assert not pending,pending
if rows:
    pd.DataFrame(rows).to_csv(base / 'corrected_comparison.csv',index=False)
    pd.DataFrame(weekly_rows).to_csv(base / 'corrected_weekly_metrics.csv',index=False)
    pd.DataFrame(leave_one_out).to_csv(base / 'corrected_leave_one_week_out.csv',index=False)
    archived_loo = base / 'archived_leave_one_week_out.csv'
    if archived_loo.exists():
        controls = pd.read_csv(archived_loo)
        controls = controls[~controls.scenario.isin(scenarios)].copy()
        assert len(controls)==28
        controls['model_variant'] = 'Archived unaffected pathway; no new physical certification'
        controls['scope'] = 'Static deletion of one week from archived dispatch; no rerun'
        merged = pd.concat([pd.DataFrame(leave_one_out),controls],ignore_index=True)
        if '--complete' in sys.argv:
            assert len(merged)==52
        merged.to_csv(base / 'all_pathway_leave_one_week_out.csv',index=False)
    sites = pd.concat(new_sites,ignore_index=True)
    sites.to_csv(base / 'corrected_synthesis_sites.csv',index=False)
    matches = []
    for scenario in scenarios:
        target = sites[(sites.scenario==scenario)&(sites.label=='baseline')]
        if target.empty:
            continue
        for source_name in [scenario,'GTL']:
            source = old_sites[old_sites.scenario==source_name]
            assert len(source)>0,source_name
            a,b = np.radians(source[['latitude','longitude']].to_numpy()),np.radians(target[['latitude','longitude']].to_numpy())
            delta = a[:,None,:]-b[None,:,:]
            hav = np.sin(delta[:,:,0]/2)**2+np.cos(a[:,None,0])*np.cos(b[None,:,0])*np.sin(delta[:,:,1]/2)**2
            distance = 6371.0088*2*np.arcsin(np.sqrt(np.clip(hav,0,1)))
            for threshold in [1,10,25,50,100]:
                weights = np.minimum(source.capacity_kg_h.to_numpy()[:,None],target.capacity_kg_h.to_numpy()[None,:])*(distance<=threshold)
                ia,ib = linear_sum_assignment(weights,maximize=True)
                matched = float(weights[ia,ib].sum())
                matches.append({'archived_source':source_name,'corrected_target':scenario,'threshold_km':threshold,'matched_capacity_kg_h':matched,'source_share_percent':100*matched/source.capacity_kg_h.sum(),'target_share_percent':100*matched/target.capacity_kg_h.sum(),'scope':'Geographic capacity correspondence; does not establish equipment reuse'})
    pd.DataFrame(matches).to_csv(base / 'corrected_spatial_matching.csv',index=False)
(base / 'comparison_status.json').write_text(json.dumps({'validated_runs':len(rows),'pending':pending},indent=2))
print(json.dumps({'validated_runs':len(rows),'pending':pending}),flush=True)
