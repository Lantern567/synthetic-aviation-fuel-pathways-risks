import json

import coptpy as cp
import numpy as np
import pandas as pd


def validation_passed(report):
    return (report['max_constraint_absolute_residual']<=1e-3
            and report['max_variable_bound_violation']<=1e-5
            and report['max_integer_violation']<=1e-6
            and report['electricity_violations_over_1e_5_mwh']==0)


def validate(model,out,provided_values=None):
    variables = model.getVars()
    constraints = model.getConstrs()
    values = np.asarray(model.getValues() if provided_values is None else provided_values)
    lower = np.asarray(model.getInfo(cp.COPT.Info.LB,variables))
    upper = np.asarray(model.getInfo(cp.COPT.Info.UB,variables))
    bound = np.maximum(np.maximum(lower-values,values-upper),0)
    integrality = max((abs(value-round(value)) for var,value in zip(variables,values) if var.getType()!=cp.COPT.CONTINUOUS),default=0)
    pd.DataFrame({'variable':[var.getName() for var in variables],'value':values,'lb':lower,'ub':upper}).to_csv(out / 'variables.csv',index=False)
    activity = model.getA()@values
    lhs = np.asarray(model.getInfo(cp.COPT.Info.LB,constraints))
    rhs = np.asarray(model.getInfo(cp.COPT.Info.UB,constraints))
    violation = np.maximum(np.maximum(lhs-activity,activity-rhs),0)
    scale = np.maximum.reduce([np.ones(len(activity)),np.abs(activity),np.where(np.abs(lhs)<1e29,np.abs(lhs),0),np.where(np.abs(rhs)<1e29,np.abs(rhs),0)])
    table = pd.DataFrame({'name':[row.getName() for row in constraints],'activity':activity,'lb':lhs,'ub':rhs,'violation':violation,'relative_violation':violation/scale})
    table.nlargest(30,'violation').to_csv(out / 'largest_constraint_residuals.csv',index=False)
    electricity = table[table.name.str.startswith(('electricity_balance_','dac_joint_electricity_','dac_grid_scope_','dac_grid_balance_','mtj_electricity_balance_'))]
    electricity.to_csv(out / 'electricity_constraint_residuals.csv',index=False)
    report = {'constraints_checked':len(table),'variables_checked':len(values),
              'max_constraint_absolute_residual':float(violation.max()),'max_constraint_relative_residual':float((violation/scale).max()),
              'max_variable_bound_violation':float(bound.max()),'max_integer_violation':float(integrality),
              'electricity_constraints_checked':len(electricity),'max_electricity_violation_mwh':float(electricity.violation.max()),
              'electricity_violations_over_1e_5_mwh':int((electricity.violation>1e-5).sum()),
              'scope':'Every exported linear constraint, variable bound and integer decision; input provenance and physical balance are checked separately'}
    report['passed'] = validation_passed(report)
    (out / 'validation.json').write_text(json.dumps(report,indent=2))
    assert report['passed'],report
    return report
