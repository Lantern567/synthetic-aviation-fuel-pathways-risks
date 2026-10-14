import gc
import hashlib
import json
import sys
import time
from pathlib import Path

import coptpy as cp
import numpy as np
import pandas as pd
import yaml
from scipy import sparse

base = Path(__file__).resolve().parent
scenario,label = sys.argv[1:3]
out = base / 'decomposed_runs' / scenario / label
out.mkdir(parents=True,exist_ok=True)
started = time.time()
environment = cp.Envr()
original = environment.createModel('original_constraints')
source = base / 'runs' / scenario / label / 'model.mps.gz'
original.read(str(source))
variables,rows = original.getVars(),original.getConstrs()
names = [v.getName() for v in variables]
column_name_hash = hashlib.sha256('\n'.join(names).encode()).hexdigest()
row_names = [r.getName() for r in rows]
assert len(set(names))==len(names)
matrix = original.getA()
cost = np.asarray(original.getInfo(cp.COPT.Info.Obj,variables))
lower = np.asarray(original.getInfo(cp.COPT.Info.LB,variables))
upper = np.asarray(original.getInfo(cp.COPT.Info.UB,variables))
lhs = np.asarray(original.getInfo(cp.COPT.Info.LB,rows))
rhs = np.asarray(original.getInfo(cp.COPT.Info.UB,rows))
types = np.asarray([v.getType() for v in variables])
flow_indices = np.asarray([i for i,name in enumerate(names) if name.startswith('corrected_h2_flow_')])
flow_indices = flow_indices[np.argsort([int(names[i].rsplit('_',1)[1]) for i in flow_indices])]
weekly_indices = np.asarray([i for i,name in enumerate(names) if name.startswith('h2_pipeline_transport_')])
assert len(flow_indices)==224*len(weekly_indices)
assert np.all(cost[flow_indices]==0)
flow_limit = float(upper[flow_indices[0]])
assert np.all(upper[flow_indices]==flow_limit) and np.all(lower[flow_indices]==0)
sources = sorted([name.removeprefix('h2_prod_').removesuffix('_0') for name in names if name.startswith('h2_prod_') and name.endswith('_0')],key=len,reverse=True)
routes = []
for index in weekly_indices:
    name = names[index].removeprefix('h2_pipeline_transport_').removesuffix('_week')
    matches = [source for source in sources if name.startswith(source+'_')]
    assert len(matches)==1,(name,matches)
    routes.append((matches[0],name[len(matches[0])+1:]))
sources = sorted(set(a for a,b in routes))
destinations = sorted(set(b for a,b in routes))
source_id,destination_id = {n:i for i,n in enumerate(sources)},{n:i for i,n in enumerate(destinations)}
source_index = np.asarray([source_id[a] for a,b in routes])
destination_index = np.asarray([destination_id[b] for a,b in routes])
retained = np.ones(len(names),dtype=bool)
retained[flow_indices] = False
keep = np.flatnonzero(retained)
old_to_new = np.full(len(names),-1,dtype=int)
old_to_new[keep] = np.arange(len(keep))
weekly_master = old_to_new[weekly_indices]
keep_rows = np.asarray([not name.startswith('h2_weekly_flow_') for name in row_names])
remaining_rows = np.flatnonzero(keep_rows)
row_lookup = {row_names[i]:j for j,i in enumerate(remaining_rows)}
ns,nd,nr = len(sources),len(destinations),len(routes)
nbase = len(keep)
nout,nin = ns*224,nd*224
out_index = np.arange(nbase,nbase+nout).reshape(ns,224)
in_index = np.arange(nbase+nout,nbase+nout+nin).reshape(nd,224)
rr,cc,vv = [],[],[]
for nodes,indices,sign in [(sources,out_index,1),(destinations,in_index,-1)]:
    for i,name in enumerate(nodes):
        for t in range(224):
            rr.append(row_lookup[f'corrected_h2_balance_{name}_{t}'])
            cc.append(indices[i,t]-nbase)
            vv.append(sign)
extra = sparse.coo_matrix((vv,(rr,cc)),shape=(len(remaining_rows),nout+nin)).tocsc()
master_matrix = sparse.hstack([matrix[remaining_rows,:][:,keep],extra],format='csc')
rr,cc,vv = [],[],[]
for week in range(4):
    for node_index,indices,route_node,offset in [(i,out_index[i],source_index,0) for i in range(ns)]+[(i,in_index[i],destination_index,ns) for i in range(nd)]:
        row = week*(ns+nd)+offset+node_index
        for t in range(week*56,(week+1)*56):
            rr.append(row); cc.append(indices[t]); vv.append(1)
        for route in np.flatnonzero(route_node==node_index):
            rr.append(row); cc.append(weekly_master[route]); vv.append(-1)
extra = sparse.coo_matrix((vv,(rr,cc)),shape=(4*(ns+nd),nbase+nout+nin)).tocsc()
master_matrix = sparse.vstack([master_matrix,extra],format='csc')
timing_columns = np.r_[out_index.ravel(),in_index.ravel()]
timing_rows = np.r_[np.tile(np.arange(224),ns),np.tile(np.arange(224),nd)]
timing_values = np.r_[np.ones(nout),-np.ones(nin)]
timing = sparse.coo_matrix((timing_values,(timing_rows,timing_columns)),shape=(224,nbase+nout+nin)).tocsc()
master_matrix = sparse.vstack([master_matrix,timing],format='csc')
strong_rows,strong_columns,strong_values = [],[],[]
lookup = {names[index]:i for i,index in enumerate(keep)}
inputs = base / 'inputs' / ('baseline' if label=='baseline' else 'summer')
config = yaml.safe_load((base / 'runs' / scenario / label / 'config.yaml').read_text())
h2_intensity = float(config['cost_parameters']['electrolysis']['electrolysis_power_consumption'])
strong_count = 0
for record in pd.read_csv(inputs / 'renewable_periods.csv').itertuples():
    location = record.plant_name.replace(' ','_')
    t = record.period
    combinations = [(f'h2_prod_{location}_{t}',f'electrolyzer_facility_{location}',record.power_output_mw*3000/h2_intensity)]
    if scenario!='GTL-GH':
        combinations.extend((f'prod_{location}_{tech}_{t}',f'facility_{location}_{tech}',record.power_output_mw*3000/7.6) for tech,info in config['technologies'].items() if isinstance(info,dict) and 'h2_consumption_ratio' in info)
    for production_name,build_name,maximum in combinations:
        assert production_name in lookup and build_name in lookup,(production_name,build_name)
        strong_rows.extend([strong_count,strong_count])
        strong_columns.extend([lookup[production_name],lookup[build_name]])
        strong_values.extend([1,-maximum])
        strong_count += 1
strong = sparse.coo_matrix((strong_values,(strong_rows,strong_columns)),shape=(strong_count,nbase+nout+nin)).tocsc()
master_matrix = sparse.vstack([master_matrix,strong],format='csc')
master_lhs = np.r_[lhs[remaining_rows],np.zeros(4*(ns+nd)+224),np.full(strong_count,-cp.COPT.INFINITY)]
master_rhs = np.r_[rhs[remaining_rows],np.zeros(4*(ns+nd)+224+strong_count)]
master = environment.createModel('routing_projection')
aggregate_upper = np.concatenate([np.repeat(np.bincount(source_index,minlength=ns)*flow_limit,224),np.repeat(np.bincount(destination_index,minlength=nd)*flow_limit,224)])
sparse.save_npz(out / 'master_matrix.npz',master_matrix)
np.savez_compressed(out / 'master_data.npz',c=np.r_[cost[keep]*1e-6,np.zeros(nout+nin)],lhs=master_lhs,rhs=master_rhs,lb=np.r_[lower[keep],np.zeros(nout+nin)],ub=np.r_[upper[keep],aggregate_upper],vtype=np.r_[types[keep],np.full(nout+nin,cp.COPT.CONTINUOUS)])
if '--export-only' in sys.argv:
    print('PROJECTION_EXPORTED',flush=True)
    sys.exit(0)
master.loadMatrix(np.r_[cost[keep]*1e-6,np.zeros(nout+nin)],master_matrix,master_lhs,master_rhs,np.r_[lower[keep],np.zeros(nout+nin)],np.r_[upper[keep],aggregate_upper],np.r_[types[keep],np.full(nout+nin,cp.COPT.CONTINUOUS)].tolist())
master_vars = master.getVars()
seed = base / 'solver_probes' / scenario / 'seed_fixed/values.npz'
if seed.exists():
    values = np.load(seed)['values']
    assert len(values)==len(names)
    flows = values[flow_indices].reshape(nr,224)
    initial_out,initial_in = np.zeros((ns,224)),np.zeros((nd,224))
    np.add.at(initial_out,source_index,flows)
    np.add.at(initial_in,destination_index,flows)
    initial = np.r_[values[keep],initial_out.ravel(),initial_in.ravel()]
    residual = master_matrix@initial
    assert np.maximum(np.maximum(master_lhs-residual,residual-master_rhs),0).max()<1e-3
    master.setMipStart(master_vars,initial.tolist())
    master.loadMipStart()
if (out / 'rounded_lp_values.npz').exists() and '--reuse-rounded' in sys.argv:
    rounded_initial = np.load(out / 'rounded_lp_values.npz')['values']
    assert len(rounded_initial)==len(master_vars)
    residual = master_matrix@rounded_initial
    assert np.maximum(np.maximum(master_lhs-residual,residual-master_rhs),0).max()<1e-3
    master.setMipStart(master_vars,rounded_initial.tolist())
    master.loadMipStart()
if (out / 'certificate.json').exists():
    previous = json.loads((out / 'certificate.json').read_text())
    assert previous['max_constraint_residual']<=1e-3 and previous['max_bound_residual']<=1e-5 and previous['max_integer_violation']<=1e-6
    previous_values = np.load(out / 'values.npz')['values']
    previous_flows = previous_values[flow_indices].reshape(nr,224)
    previous_out,previous_in = np.zeros((ns,224)),np.zeros((nd,224))
    np.add.at(previous_out,source_index,previous_flows)
    np.add.at(previous_in,destination_index,previous_flows)
    previous_start = np.r_[previous_values[keep],previous_out.ravel(),previous_in.ravel()]
    residual = master_matrix@previous_start
    assert np.maximum(np.maximum(master_lhs-residual,residual-master_rhs),0).max()<1e-3
    master.setMipStart(master_vars,previous_start.tolist())
    master.loadMipStart()
for name,value in {'TimeLimit':3600,'Threads':8,'LpMethod':2,'Crossover':0,'RelGap':0.0001,'FeasTol':1e-8,'IntTol':1e-8,'RootCutRounds':0,'HeurLevel':1}.items():
    master.setParam(name,value)
rounding = '--round' in sys.argv
master.setLogFile(str(out / ('round_master.log' if rounding else 'master.log')))
existing_cuts = sorted(out.glob('cut_*.npz'))
for path in existing_cuts:
    cut = np.load(path)
    expression = cp.quicksum(float(c)*master_vars[int(i)] for i,c in zip(cut['indices'],cut['coefficients']) if c!=0)
    master.addConstr(expression<=float(cut['rhs']),name=path.stem)
print('PROJECTION_READY',scenario,master.getAttr('Rows'),master.getAttr('Cols'),flush=True)
# 保存原始矩阵用于验证每个重构解；不删除任何原始物理限制。
del original,variables,rows
gc.collect()
history = json.loads((out / 'history.json').read_text()) if (out / 'history.json').exists() else []
start_iteration = max((int(path.stem.split('_')[1]) for path in existing_cuts),default=-1)+1
for iteration in range(start_iteration,start_iteration+50):
    if rounding:
        if iteration==0 and (out / 'rounded_lp_status.json').exists() and '--reuse-rounded' in sys.argv:
            candidate = np.load(out / 'rounded_lp_values.npz')['values']
            rounded_status = json.loads((out / 'rounded_lp_status.json').read_text())
            master_objective,master_bound = rounded_status['objective'],rounded_status['lower_bound']
        else:
            master.solveLP()
            assert master.status==cp.COPT.OPTIMAL,master.status
            master_bound = float(master.ObjVal*1e6)
            fixed = master.clone()
            fixed.setParam('Crossover',1)
            fixed.setParam('FeasTol',1e-9)
            fixed.setLogFile(str(out / f'round_fixed_{iteration}.log'))
            fixed_vars = fixed.getVars()
            integers = np.flatnonzero(types[keep]!=cp.COPT.CONTINUOUS)
            rounded = (np.asarray(master.getValues())[integers]>1e-7).astype(float)
            fixed.setInfo(cp.COPT.Info.LB,[fixed_vars[int(i)] for i in integers],rounded.tolist())
            fixed.setInfo(cp.COPT.Info.UB,[fixed_vars[int(i)] for i in integers],rounded.tolist())
            fixed.solveLP()
            assert fixed.status==cp.COPT.OPTIMAL,('Rounded design',fixed.status)
            candidate = np.asarray(fixed.getValues())
            master_objective = float(fixed.ObjVal*1e6)
            del fixed_vars,fixed
    else:
        master.solve()
        assert master.getAttr('HasSol'),master.status
        candidate = np.asarray(master.getValues())
        master_objective = float(master.ObjVal*1e6)
        master_bound = float(master.getAttr('ObjBound')*1e6)
    print('MASTER_CANDIDATE',iteration,master_objective,master_bound,flush=True)
    proposed = np.zeros(len(names))
    proposed[keep] = candidate[:nbase]
    np.savez_compressed(out / f'candidate_{iteration}.npz',values=proposed)
    (out / f'candidate_{iteration}.json').write_text(json.dumps({'objective':master_objective,'lower_bound':master_bound,'column_name_sha256':column_name_hash,'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest()},indent=2))
    q = candidate[weekly_master]
    outbound,inbound = candidate[out_index],candidate[in_index]
    full_flows = np.zeros((nr,224))
    cuts,slacks = 0,[]
    for week in range(4):
        active = np.flatnonzero(q>1e-8)
        n = len(active)
        count = n+56*(ns+nd)
        col = np.arange(n*56).reshape(n,56)
        route_rows = np.repeat(np.arange(n),56)
        source_rows = n+(source_index[active,None]*56+np.arange(56)).ravel()
        destination_rows = n+ns*56+(destination_index[active,None]*56+np.arange(56)).ravel()
        a = sparse.coo_matrix((np.ones(n*56*3),(np.r_[route_rows,source_rows,destination_rows],np.tile(col.ravel(),3))),shape=(count,n*56)).tocsc()
        a = sparse.hstack([a,sparse.eye(count),-sparse.eye(count)],format='csc')
        b = np.r_[q[active],outbound[:,week*56:(week+1)*56].ravel(),inbound[:,week*56:(week+1)*56].ravel()]
        sub = environment.createModel(f'week_{week}')
        sub.loadMatrix(np.r_[np.zeros(n*56),np.ones(2*count)],a,b,b,np.zeros(n*56+2*count),np.r_[np.full(n*56,flow_limit),np.full(2*count,cp.COPT.INFINITY)])
        for name,value in {'Threads':4,'LpMethod':1,'FeasTol':1e-9,'DualTol':1e-9,'TimeLimit':600,'Logging':0}.items():
            sub.setParam(name,value)
        sub.solveLP()
        assert sub.status==cp.COPT.OPTIMAL,('transport feasibility solve',sub.status)
        slack = float(sub.ObjVal)
        slacks.append(slack)
        if slack<=1e-4:
            full_flows[active,week*56:(week+1)*56] = np.asarray(sub.getValues()[:n*56]).reshape(n,56)
        else:
            dual = np.asarray(sub.getDuals())
            yout = dual[n:n+ns*56].reshape(ns,56)
            yin = dual[n+ns*56:].reshape(nd,56)
            yq = -(yout[source_index]+yin[destination_index]).max(axis=1)
            yq[active] = dual[:n]
            limit = flow_limit*np.maximum(yq[:,None]+yout[source_index]+yin[destination_index],0).sum()
            indices = np.r_[weekly_master,out_index[:,week*56:(week+1)*56].ravel(),in_index[:,week*56:(week+1)*56].ravel()]
            coefficients = np.r_[yq,yout.ravel(),yin.ravel()]
            assert coefficients@candidate[indices]-limit>slack-1e-3,(slack,coefficients@candidate[indices]-limit)
            if seed.exists():
                assert coefficients@initial[indices]<=limit+1e-3,('Cut excludes independently feasible starting solution',iteration,week)
            np.savez_compressed(out / f'cut_{iteration}_{week}.npz',indices=indices,coefficients=coefficients,rhs=limit)
            expression = cp.quicksum(float(c)*master_vars[int(i)] for i,c in zip(indices,coefficients) if c!=0)
            master.addConstr(expression<=float(limit),name=f'transport_feasibility_{iteration}_{week}')
            cuts += 1
        del sub
    record = {'iteration':iteration,'master_objective':master_objective,'bound':master_bound,'slack_kg':slacks,'cuts':cuts,'seconds':time.time()-started}
    history.append(record)
    (out / 'history.json').write_text(json.dumps(history,indent=2))
    print('PROJECTION_ITERATION',json.dumps(record),flush=True)
    if cuts:
        continue
    full = np.zeros(len(names))
    full[keep] = candidate[:nbase]
    full[flow_indices] = full_flows.ravel()
    activity = matrix@full
    violation = np.maximum(np.maximum(lhs-activity,activity-rhs),0)
    bound_violation = np.maximum(np.maximum(lower-full,full-upper),0)
    integer_violation = np.abs(full[types!=cp.COPT.CONTINUOUS]-np.rint(full[types!=cp.COPT.CONTINUOUS]))
    objective = float(cost@full)
    lower_bound = master_bound
    gap = max(0,(objective-lower_bound)/abs(objective))
    report = dict(scenario=scenario,label=label,objective=objective,lower_bound=lower_bound,gap=gap,max_constraint_residual=float(violation.max()),max_bound_residual=float(bound_violation.max()),max_integer_violation=float(integer_violation.max()),seconds=time.time()-started,iterations=iteration+1,method='Projected routing master with exact three-hour route feasibility subproblems and valid dual feasibility cuts',source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),column_name_sha256=column_name_hash)
    report['passed'] = report['max_constraint_residual']<=1e-3 and report['max_bound_residual']<=1e-5 and report['max_integer_violation']<=1e-6 and gap<=0.001001
    np.savez_compressed(out / 'values.npz',values=full)
    (out / 'certificate.json').write_text(json.dumps(report,indent=2))
    if rounding and report['max_constraint_residual']<=1e-3 and report['max_bound_residual']<=1e-5 and report['max_integer_violation']<=1e-6 and gap>0.001001:
        master.setMipStart(master_vars,candidate.tolist())
        master.loadMipStart()
        rounding = False
        print('INTEGER_REFINEMENT',gap,flush=True)
        continue
    assert report['passed'],report
    print('PROJECTION_COMPLETE',json.dumps(report),flush=True)
    break
else:
    raise RuntimeError('Transport decomposition exceeded iteration limit')
del master_vars,master
del environment
