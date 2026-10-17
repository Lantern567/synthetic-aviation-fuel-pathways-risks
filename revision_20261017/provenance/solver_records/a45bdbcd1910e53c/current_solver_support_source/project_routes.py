from pathlib import Path
import argparse
import gc
import hashlib
import json
import re
import time

import coptpy as cp
import numpy as np
from scipy import sparse


PERIODS, WEEK_PERIODS, WEEKS, SCALE = 224, 56, 4, 1e6


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def name_hash(names):
    return hashlib.sha256("\n".join(names).encode()).hexdigest()


def max_or_zero(values):
    return float(np.max(values, initial=0))


def resource_activation_cuts(matrix, names, row_names, lower, upper, rhs, types, old_to_new, projected_columns):
    csr, lookup = matrix.tocsr(), {name: i for i, name in enumerate(names)}
    adjacency = {}

    def activation_neighbours(column):
        if column not in adjacency:
            neighbours = []
            for position in range(matrix.indptr[column], matrix.indptr[column + 1]):
                row = matrix.indices[position]
                if matrix.data[position] <= 0 or rhs[row] != 0:
                    continue
                start, end = csr.indptr[row:row + 2]
                columns, values = csr.indices[start:end], csr.data[start:end]
                negative = columns[values < 0]
                if len(negative) == 1 and (lower[columns] >= 0).all():
                    neighbours.append(int(negative[0]))
            adjacency[column] = neighbours
        return adjacency[column]

    rr, cc, vv, witnesses = [], [], [], []
    for row, name in enumerate(row_names):
        if not name.startswith("electricity_balance_") or not 0 < rhs[row] < cp.COPT.INFINITY:
            continue
        start, end = csr.indptr[row:row + 2]
        columns, coefficients = csr.indices[start:end], csr.data[start:end]
        if not (coefficients >= 0).all() or not (lower[columns] >= 0).all():
            continue
        for column, coefficient in zip(columns, coefficients):
            variable_name = names[column]
            if variable_name.startswith("h2_prod_"):
                build_name = "electrolyzer_facility_" + variable_name.removeprefix("h2_prod_").rsplit("_", 1)[0]
            elif variable_name.startswith("prod_"):
                build_name = "facility_" + variable_name.removeprefix("prod_").rsplit("_", 1)[0]
            else:
                continue
            if build_name not in lookup or coefficient <= 0:
                continue
            built = lookup[build_name]
            if types[built] == cp.COPT.CONTINUOUS or lower[built] < 0 or upper[built] > 1:
                raise ValueError(f"Resource activation needs a binary facility: {build_name}")
            links = activation_neighbours(int(column))
            if built not in links and not any(built in activation_neighbours(link) for link in links):
                raise ValueError(f"Cannot prove facility activation through original capacity rows: {variable_name}/{build_name}")
            if old_to_new[column] < 0 or old_to_new[built] < 0:
                raise ValueError("Resource cuts unexpectedly depend on projected route flows")
            number = len(witnesses)
            rr.extend([number, number]); cc.extend([old_to_new[column], old_to_new[built]])
            vv.extend([1.0, -float(rhs[row] / coefficient)])
            witnesses.append({"resource_row": name, "production_variable": variable_name, "binary_variable": build_name,
                              "maximum_kg_per_period": float(rhs[row] / coefficient)})
    cuts = sparse.coo_matrix((vv, (rr, cc)), shape=(len(witnesses), projected_columns)).tocsc()
    return cuts, witnesses


def family_mapping(kind, names, row_names, matrix, cost, lower, upper):
    lookup, rows = {name: i for i, name in enumerate(names)}, {name: i for i, name in enumerate(row_names)}
    co2 = kind == "co2"
    prefix = "co2_pipe_" if co2 else "h2_pipeline_transport_"
    flow_prefix = f"corrected_{kind}_flow_"
    weekly = [i for i, name in enumerate(names) if name.startswith(prefix)]
    flow = [i for i, name in enumerate(names) if name.startswith(flow_prefix)]
    if not weekly or len(flow) != len(weekly) * PERIODS:
        raise ValueError(f"Unexpected {kind} weekly/period route variable counts: {len(weekly)}/{len(flow)}")
    sources = [name.removeprefix("dac_co2_").removesuffix("_h0") for name in names if name.startswith("dac_co2_") and name.endswith("_h0")] if co2 else [name.removeprefix("h2_prod_").removesuffix("_0") for name in names if name.startswith("h2_prod_") and name.endswith("_0")]
    if not sources or len(sources) != len(set(sources)):
        raise ValueError(f"Missing or duplicate {kind} source node names")
    routes = []
    for i in weekly:
        route = names[i].removeprefix(prefix).removesuffix("_week")
        matches = [source for source in sources if route.startswith(source + "_")]
        if len(matches) != 1:
            raise ValueError(f"Ambiguous {kind} route source: {names[i]} / {matches}")
        source = matches[0]
        destination = route[len(source) + 1:]
        if not destination or (co2 and source == destination):
            raise ValueError(f"Invalid {kind} route: {names[i]}")
        routes.append((source, destination))
    if len(set(routes)) != len(routes):
        raise ValueError(f"Duplicate {kind} route names")
    route_by_weekly = {column: route for column, route in zip(weekly, routes)}
    if co2:
        csr = matrix.tocsr()
        route_id_to_weekly = {}
        weekly_set = set(weekly)
        for route_id in range(len(weekly)):
            row = rows[f"corrected_co2_contract_{route_id}_w0"]
            matching = [int(column) for column in csr.indices[csr.indptr[row]:csr.indptr[row + 1]] if column in weekly_set]
            if len(matching) != 1:
                raise ValueError(f"CO2 contract does not uniquely identify weekly route {route_id}: {matching}")
            route_id_to_weekly[route_id] = matching[0]
        if len(set(route_id_to_weekly.values())) != len(weekly):
            raise ValueError("CO2 numbered contracts do not cover each weekly route once")
        numbered_routes = [route_by_weekly[route_id_to_weekly[i]] for i in range(len(weekly))]
        # MPS会将原始地名中的空格规范成下划线，使用真实合同约束恢复原路线编号。
        weekly = [route_id_to_weekly[i] for i in range(len(weekly))]
        routes = numbered_routes
        flow = sorted(flow, key=lambda column: tuple(map(int, re.fullmatch(r"corrected_co2_flow_(\d+)_p(\d+)", names[column]).groups())))
        expected_flow_names = [f"corrected_co2_flow_{route_id}_p{period}" for route_id in range(len(routes)) for period in range(PERIODS)]
    else:
        flow = sorted(flow, key=lambda column: int(names[column].removeprefix(flow_prefix)))
        expected_flow_names = [f"corrected_h2_flow_{i}" for i in range(len(routes) * PERIODS)]
    if [names[i] for i in flow] != expected_flow_names:
        raise ValueError(f"Incomplete ordered {kind} flow identifiers")
    flow = np.asarray(flow, dtype=int)
    weekly = np.asarray(weekly, dtype=int)
    if not np.equal(cost[flow], 0).all() or not np.equal(lower[flow], 0).all() or (upper[flow] < 0).any():
        raise ValueError(f"{kind} projected variables must be zero-cost nonnegative flows")
    balance_rows, contract_rows = [], []
    for route_id, (source, destination) in enumerate(routes):
        balance_source = f"corrected_co2_balance_{source}_p" if co2 else f"corrected_h2_balance_{source}_"
        balance_destination = f"corrected_co2_balance_{destination}_p" if co2 else f"corrected_h2_balance_{destination}_"
        balance_rows.extend((rows[balance_source + str(period)], rows[balance_destination + str(period)]) for period in range(PERIODS))
        contract_rows.extend(rows[f"corrected_co2_contract_{route_id}_w{period // WEEK_PERIODS}"] if co2 else rows[f"h2_weekly_flow_{source}_{destination}_{period // WEEK_PERIODS}"] for period in range(PERIODS))
    balances = np.asarray(balance_rows, dtype=int)
    expected_rows = np.column_stack([balances, contract_rows])
    expected_coefficients = np.tile([1.0, -1.0, 1.0], (len(flow), 1))
    order = np.argsort(expected_rows, axis=1)
    actual = matrix[:, flow].tocsc()
    actual.eliminate_zeros()
    self_route = np.repeat([source == destination for source, destination in routes], PERIODS)
    routed = actual[:, ~self_route].tocsc()
    if not np.equal(np.diff(routed.indptr), 3).all():
        raise ValueError(f"{kind} period flows occur outside two node balances and one weekly contract")
    if not np.array_equal(routed.indices.reshape(-1, 3), np.take_along_axis(expected_rows, order, axis=1)[~self_route]):
        raise ValueError(f"{kind} flow incidence differs from parsed route/source/period")
    if not np.allclose(routed.data.reshape(-1, 3), np.take_along_axis(expected_coefficients, order, axis=1)[~self_route], rtol=0, atol=1e-12):
        raise ValueError(f"{kind} flow coefficients are not lossless signed incidences")
    if self_route.any():
        local = actual[:, self_route].tocsc()
        if not np.equal(np.diff(local.indptr), 1).all() or not np.array_equal(local.indices, np.asarray(contract_rows)[self_route]) or not np.equal(local.data, 1).all():
            raise ValueError(f"{kind} same-node flows do not cancel exactly in original node balances")
    removed_rows = np.unique(contract_rows)
    if len(removed_rows) != WEEKS * len(routes):
        raise ValueError(f"Incomplete {kind} route weekly contracts")
    csr = matrix[removed_rows, :].tocsr()
    if not np.equal(np.diff(csr.indptr), WEEK_PERIODS + 1).all():
        raise ValueError(f"Unexpected extra variables in {kind} contract equations")
    weekly_row_activity = matrix[removed_rows, :][:, weekly].tocsc()
    if not np.equal(np.diff(weekly_row_activity.indptr), WEEKS).all() or not np.equal(weekly_row_activity.data, -1).all():
        raise ValueError(f"{kind} weekly contract coefficient differs from minus one in each week")
    return {"kind": kind, "flow": flow, "weekly": weekly, "routes": routes, "balance_rows": balances,
            "contract_rows": removed_rows, "upper": upper[flow].reshape(-1, PERIODS)}


def export_projection(source, output):
    started = time.time()
    environment = cp.Envr()
    original = environment.createModel("source_physical_model")
    original.read(str(source))
    if float(original.getObjective().getConstant()) != 0:
        raise ValueError("Projected objective requires a zero original objective constant")
    variables, constraints = original.getVars(), original.getConstrs()
    names, row_names = [var.getName() for var in variables], [row.getName() for row in constraints]
    if len(names) != len(set(names)) or len(row_names) != len(set(row_names)):
        raise ValueError("Original MPS has duplicate row or column names")
    matrix = original.getA().tocsc()
    cost = np.asarray(original.getInfo(cp.COPT.Info.Obj, variables))
    lower, upper = [np.asarray(original.getInfo(field, variables)) for field in [cp.COPT.Info.LB, cp.COPT.Info.UB]]
    lhs, rhs = [np.asarray(original.getInfo(field, constraints)) for field in [cp.COPT.Info.LB, cp.COPT.Info.UB]]
    types = np.asarray([var.getType() for var in variables])
    families = [family_mapping(kind, names, row_names, matrix, cost, lower, upper) for kind in ["h2", "co2"]]
    eliminated = np.concatenate([family["flow"] for family in families])
    removed_rows = np.concatenate([family["contract_rows"] for family in families])
    keep, keep_rows = np.setdiff1d(np.arange(len(names)), eliminated), np.setdiff1d(np.arange(len(row_names)), removed_rows)
    if np.abs(lhs[removed_rows]).max(initial=0) or np.abs(rhs[removed_rows]).max(initial=0):
        raise ValueError("Projected weekly contract rows are not zero-right-hand-side equalities")
    old_to_new, row_to_new = np.full(len(names), -1, dtype=int), np.full(len(row_names), -1, dtype=int)
    old_to_new[keep], row_to_new[keep_rows] = np.arange(len(keep)), np.arange(len(keep_rows))
    extra_lower, extra_upper, aggregate_names = [], [], []
    total = len(keep)
    for family in families:
        sources = sorted({source for source, destination in family["routes"]})
        destinations = sorted({destination for source, destination in family["routes"]})
        family["sources"], family["destinations"] = sources, destinations
        family["source_ids"] = np.asarray([sources.index(source) for source, destination in family["routes"]])
        family["destination_ids"] = np.asarray([destinations.index(destination) for source, destination in family["routes"]])
        for role, nodes, route_nodes in [("out", sources, family["source_ids"]), ("in", destinations, family["destination_ids"])]:
            count = len(nodes) * PERIODS
            family[role] = np.arange(total, total + count).reshape(len(nodes), PERIODS)
            aggregate = np.zeros((len(nodes), PERIODS))
            np.add.at(aggregate, route_nodes, family["upper"])
            extra_upper.extend(np.minimum(aggregate.ravel(), cp.COPT.INFINITY))
            extra_lower.extend(np.zeros(count))
            aggregate_names.extend(f"projection_{family['kind']}_{role}_{node}_p{period}" for node in nodes for period in range(PERIODS))
            total += count
    rr, cc, vv = [], [], []
    for family in families:
        row_lookup = {name: i for i, name in enumerate(row_names)}
        for role, nodes, sign in [("out", family["sources"], 1), ("in", family["destinations"], -1)]:
            for node_id, node in enumerate(nodes):
                for period in range(PERIODS):
                    balance = f"corrected_co2_balance_{node}_p{period}" if family["kind"] == "co2" else f"corrected_h2_balance_{node}_{period}"
                    rr.append(row_to_new[row_lookup[balance]])
                    cc.append(family[role][node_id, period] - len(keep))
                    vv.append(sign)
    extra = sparse.coo_matrix((vv, (rr, cc)), shape=(len(keep_rows), total - len(keep))).tocsc()
    projected = sparse.hstack([matrix[keep_rows, :][:, keep], extra], format="csc")
    rr, cc, vv, new_row_names = [], [], [], []
    for family in families:
        for week in range(WEEKS):
            for role, nodes, route_node_ids in [("out", family["sources"], family["source_ids"]), ("in", family["destinations"], family["destination_ids"])]:
                for node_id, node in enumerate(nodes):
                    row = len(new_row_names)
                    new_row_names.append(f"projection_{family['kind']}_{role}_{node}_w{week}")
                    periods = family[role][node_id, week * WEEK_PERIODS:(week + 1) * WEEK_PERIODS]
                    rr.extend([row] * len(periods)); cc.extend(periods); vv.extend(np.ones(len(periods)))
                    selected = family["weekly"][route_node_ids == node_id]
                    rr.extend([row] * len(selected)); cc.extend(old_to_new[selected]); vv.extend(-np.ones(len(selected)))
        for period in range(PERIODS):
            row = len(new_row_names)
            new_row_names.append(f"projection_{family['kind']}_same_period_{period}")
            for role, sign in [("out", 1), ("in", -1)]:
                columns = family[role][:, period]
                rr.extend([row] * len(columns)); cc.extend(columns); vv.extend(np.full(len(columns), sign))
    additional = sparse.coo_matrix((vv, (rr, cc)), shape=(len(new_row_names), total)).tocsc()
    cuts, cut_witnesses = resource_activation_cuts(matrix, names, row_names, lower, upper, rhs, types, old_to_new, total)
    projected = sparse.vstack([projected, additional, cuts], format="csc")
    output.mkdir(parents=True, exist_ok=True)
    sparse.save_npz(output / "master_matrix.npz", projected)
    np.savez_compressed(output / "master_data.npz", c=np.r_[cost[keep] / SCALE, np.zeros(total - len(keep))],
                        lhs=np.r_[lhs[keep_rows], np.zeros(len(new_row_names)), np.full(cuts.shape[0], -cp.COPT.INFINITY)],
                        rhs=np.r_[rhs[keep_rows], np.zeros(len(new_row_names) + cuts.shape[0])],
                        lb=np.r_[lower[keep], extra_lower], ub=np.r_[upper[keep], extra_upper],
                        vtype=np.r_[types[keep], np.full(total - len(keep), cp.COPT.CONTINUOUS)])
    np.savez_compressed(output / "original_mapping.npz", keep=keep, removed_rows=removed_rows,
                        **{f"{family['kind']}_flows": family["flow"] for family in families})
    meta = {"schema_version": 1, "source_mps": str(source), "source_sha256": digest(source),
            "column_name_sha256": name_hash(names), "original_rows": len(row_names), "original_columns": len(names),
            "projected_rows": projected.shape[0], "projected_columns": projected.shape[1],
            "retained_original_columns": len(keep), "objective_scale": SCALE, "original_objective_constant": 0.0, "seconds": time.time() - started,
            "mps_derived_resource_activation_cuts": cuts.shape[0],
            "global_bound_method": "LP relaxation of necessary node-period/weekly aggregate conditions for both H2 and CO2; original integer design variables relaxed only for the LP lower bound.",
            "structural_checks": {"projected_flows_have_zero_objective": True, "flow_incidence_exactly_verified_against_original_mps": True,
                                  "all_unprojected_original_constraints_retained": True, "source_capture_and_inventory_constraints_retained": True},
            "families": {family["kind"]: {"routes": len(family["routes"]), "sources": len(family["sources"]), "destinations": len(family["destinations"]),
                                                   "removed_zero_cost_period_variables": len(family["flow"]), "removed_contract_rows": len(family["contract_rows"])} for family in families}}
    meta["projection_files_sha256"] = {name: digest(output / name) for name in ["master_matrix.npz", "master_data.npz", "original_mapping.npz"]}
    write_json(output / "resource_activation_cuts.json", cut_witnesses)
    write_json(output / "projection.json", meta)
    print("DUAL_PROJECTION_EXPORTED", json.dumps(meta), flush=True)
    del variables, constraints, original, environment
    gc.collect()
    return meta


def configure(model, seconds, threads, log):
    for name, value in {"LpMethod": 2, "Threads": threads, "Crossover": 1, "TimeLimit": seconds, "FeasTol": 1e-7, "DualTol": 1e-7}.items():
        model.setParam(name, value)
    model.setLogFile(str(log))


def solve_projection(output, seconds, threads, threshold, reuse_root=False):
    meta = read_json(output / "projection.json")
    for name, expected in meta["projection_files_sha256"].items():
        if digest(output / name) != expected:
            raise ValueError(f"Projection file bytes changed: {name}")
    data = np.load(output / "master_data.npz")
    matrix = sparse.load_npz(output / "master_matrix.npz")
    environment = cp.Envr()
    master = environment.createModel("dual_routing_projection_lp")
    master.loadMatrix(data["c"], matrix, data["lhs"], data["rhs"], data["lb"], data["ub"], data["vtype"].tolist())
    if reuse_root:
        status = read_json(output / "root_lp_status.json")
        if status["source_sha256"] != meta["source_sha256"] or status["column_name_sha256"] != meta["column_name_sha256"]:
            raise ValueError("Saved root lower-bound certificate identifies another original MPS")
        root_values = np.load(output / "root_lp_values.npz")["values"]
        if len(root_values) != len(data["c"]):
            raise ValueError("Saved root solution differs from projected column order")
    else:
        configure(master, seconds, threads, output / "root_lp.log")
        master.solveLP()
        status = {"status": master.status, "has_solution": bool(master.getAttr("HasSol")), "seconds": master.getAttr("SolvingTime"),
                  "source_sha256": meta["source_sha256"], "column_name_sha256": meta["column_name_sha256"]}
        if status["has_solution"]:
            status["objective"] = float(master.ObjVal * SCALE)
            root_values = np.asarray(master.getValues())
            np.savez_compressed(output / "root_lp_values.npz", values=root_values)
        write_json(output / "root_lp_status.json", status)
    if status["status"] != cp.COPT.OPTIMAL or status["has_solution"] is not True:
        raise RuntimeError(f"Projection LP has not certified its global lower bound: {status}")
    lower_bound = float(status["objective"])
    fixed = master.clone()
    configure(fixed, seconds, threads, output / "rounded_lp.log")
    variables = fixed.getVars()
    integer_indices = np.flatnonzero(data["vtype"] != cp.COPT.CONTINUOUS)
    if not np.all(data["lb"][integer_indices] >= 0) or not np.all(data["ub"][integer_indices] <= 1):
        raise ValueError("Design rounding currently requires binary original variables")
    rounded = (root_values[integer_indices] > threshold).astype(float)
    fixed.setInfo(cp.COPT.Info.LB, [variables[int(i)] for i in integer_indices], rounded.tolist())
    fixed.setInfo(cp.COPT.Info.UB, [variables[int(i)] for i in integer_indices], rounded.tolist())
    fixed.solveLP()
    rounded_status = {"status": fixed.status, "has_solution": bool(fixed.getAttr("HasSol")), "seconds": fixed.getAttr("SolvingTime"),
                      "lower_bound": lower_bound, "binary_rounding_threshold": threshold,
                      "source_sha256": meta["source_sha256"], "column_name_sha256": meta["column_name_sha256"],
                      "bound_source": str(output / "root_lp_status.json"), "global_bound_method": meta["global_bound_method"]}
    write_json(output / "rounded_lp_status.json", rounded_status)
    if fixed.status != cp.COPT.OPTIMAL:
        raise RuntimeError(f"Rounded projected design lacks an optimal dispatch: {rounded_status}")
    candidate = np.asarray(fixed.getValues())
    original_keep = np.load(output / "original_mapping.npz")["keep"]
    proposed = np.zeros(meta["original_columns"])
    proposed[original_keep] = candidate[:len(original_keep)]
    rounded_status["objective"] = float(fixed.ObjVal * SCALE)
    np.savez_compressed(output / "rounded_lp_values.npz", values=candidate)
    np.savez_compressed(output / "candidate_0.npz", values=proposed)
    write_json(output / "rounded_lp_status.json", rounded_status)
    write_json(output / "candidate_0.json", rounded_status)
    print("DUAL_PROJECTION_CANDIDATE", json.dumps(rounded_status), flush=True)
    del variables, fixed, master, environment
    gc.collect()
    return rounded_status


def repair_full_model(source, output, seconds, threads):
    meta = read_json(output / "candidate_0.json")
    if digest(source) != meta["source_sha256"]:
        raise ValueError("Candidate source MPS bytes differ")
    environment = cp.Envr()
    model = environment.createModel("full_original_h2_co2_dispatch")
    model.read(str(source))
    if float(model.getObjective().getConstant()) != 0:
        raise ValueError("Candidate lower bound cannot be used with a nonzero objective constant")
    variables, rows = model.getVars(), model.getConstrs()
    names = [var.getName() for var in variables]
    if name_hash(names) != meta["column_name_sha256"]:
        raise ValueError("Candidate original variable ordering differs")
    proposal = np.load(output / "candidate_0.npz")["values"]
    lower, upper = [np.asarray(model.getInfo(field, variables)) for field in [cp.COPT.Info.LB, cp.COPT.Info.UB]]
    types = np.asarray([var.getType() for var in variables])
    fixed_indices = [i for i, name in enumerate(names) if types[i] != cp.COPT.CONTINUOUS or name.startswith("h2_pipeline_transport_") or name.startswith("co2_pipe_")]
    model.setInfo(cp.COPT.Info.LB, [variables[i] for i in fixed_indices], proposal[fixed_indices].tolist())
    model.setInfo(cp.COPT.Info.UB, [variables[i] for i in fixed_indices], proposal[fixed_indices].tolist())
    model.setObjective(model.getObjective() / SCALE)
    configure(model, seconds, threads, output / "repair_full.log")
    model.solveLP()
    status = {"status": model.status, "has_solution": bool(model.getAttr("HasSol")), "seconds": model.getAttr("SolvingTime"),
              "source_sha256": meta["source_sha256"], "column_name_sha256": meta["column_name_sha256"],
              "fixed_integer_count": int(np.sum(types != cp.COPT.CONTINUOUS)),
              "fixed_h2_weekly_contract_count": sum(name.startswith("h2_pipeline_transport_") for name in names),
              "fixed_co2_weekly_contract_count": sum(name.startswith("co2_pipe_") for name in names)}
    write_json(output / "repair_status_0.json", status)
    if not status["has_solution"]:
        raise RuntimeError(f"Full original MPS dispatch is not feasible under candidate design/contracts: {status}")
    values = np.asarray(model.getValues())
    lhs, rhs = [np.asarray(model.getInfo(field, rows)) for field in [cp.COPT.Info.LB, cp.COPT.Info.UB]]
    activity = model.getA() @ values
    integers = np.flatnonzero(types != cp.COPT.CONTINUOUS)
    status.update(objective=float(model.ObjVal * SCALE), lower_bound=meta["lower_bound"],
                  max_constraint_residual=max_or_zero(np.maximum(lhs - activity, activity - rhs)),
                  max_bound_residual=max_or_zero(np.maximum(lower - values, values - upper)),
                  max_integer_violation=max_or_zero(np.abs(values[integers] - np.rint(values[integers]))),
                  max_fixed_candidate_difference=max_or_zero(np.abs(values[fixed_indices] - proposal[fixed_indices])),
                  bound_source=meta["bound_source"], global_bound_method=meta["global_bound_method"],
                  method="Full original MPS dispatch with all design integers and H2/CO2 weekly contracts fixed; every original row and original bound independently evaluated.")
    if status["objective"] <= 0 or status["lower_bound"] > status["objective"] + 1e-3:
        raise ValueError(f"Invalid global lower bound or objective: {status}")
    status["gap"] = max(0, (status["objective"] - status["lower_bound"]) / abs(status["objective"]))
    status["physically_feasible_algebraically"] = (status["max_constraint_residual"] <= 1e-3 and status["max_bound_residual"] <= 1e-5
                                                    and status["max_integer_violation"] <= 1e-6 and status["max_fixed_candidate_difference"] <= 1e-5)
    status["relative_gap_tolerance"] = .01
    status["passed"] = status["physically_feasible_algebraically"] and status["gap"] <= .01
    np.savez_compressed(output / "repaired_values_0.npz", values=values)
    write_json(output / "repair_status_0.json", status)
    if status["passed"]:
        np.savez_compressed(output / "values.npz", values=values)
        write_json(output / "certificate.json", status)
    print("DUAL_PROJECTION_FULL_REPAIR", json.dumps(status), flush=True)
    if not status["passed"]:
        raise RuntimeError(f"Full original MPS candidate has not met feasibility and one-percent global gap: {status}")
    return status


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--stage", choices=["export", "lp", "round", "repair", "all"], default="all")
    parser.add_argument("--lp-time", type=float, default=900)
    parser.add_argument("--repair-time", type=float, default=1200)
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--round-threshold", type=float, default=.001)
    args = parser.parse_args()
    source, output = args.source.resolve(), args.out.resolve()
    if source.parent == output or source.parent in output.parents:
        raise ValueError("Projection output must be outside the original run directory")
    if args.stage in ["export", "all"]:
        if (output / "projection.json").exists():
            raise FileExistsError(f"Choose a new projection probe directory: {output}")
        export_projection(source, output)
    if args.stage in ["lp", "all"]:
        solve_projection(output, args.lp_time, args.threads, args.round_threshold)
    if args.stage == "round":
        solve_projection(output, args.lp_time, args.threads, args.round_threshold, reuse_root=True)
    if args.stage in ["repair", "all"]:
        repair_full_model(source, output, args.repair_time, args.threads)


if __name__ == "__main__":
    main()
