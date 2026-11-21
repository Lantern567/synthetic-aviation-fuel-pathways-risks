import argparse
import importlib.util
import json
import logging
import shutil
import sys
from pathlib import Path

import pandas as pd

from build_capture_input import digest


def draw(archive,correction,scratch,output):
    revision=archive/"revision_20261017"
    assets=revision/"artifacts"
    workspace=assets/"workspace"
    original=workspace/"work/nexus_targeted_revision/scientific_revision_20261017"
    spatial=original/"figures_spatial"
    template=spatial/"reproducibility_source/render_spatial.py"
    spec=importlib.util.spec_from_file_location("archived_spatial_renderer",template)
    renderer=importlib.util.module_from_spec(spec)
    sys.modules[spec.name]=renderer
    spec.loader.exec_module(renderer)
    renderer.configure_sources(workspace,None,original/"runtime/compute/project")
    logging.getLogger("fontTools.subset").setLevel(logging.WARNING)
    local=scratch/"figure_inputs"
    local.mkdir(parents=True,exist_ok=True)
    output.mkdir(parents=True,exist_ok=True)
    for f in (spatial/"network_data").iterdir():
        if f.is_file():shutil.copyfile(f,local/f.name)
    if correction:
        for path in correction.iterdir():
            if (local/path.name).is_file():shutil.copyfile(path,local/path.name)
    generated=scratch/"render"
    generated.mkdir(exist_ok=True)
    for name in renderer.REPRESENTATIVES:
        for part in (f"Main_Map_{name}.png",f"Figure_S{renderer.FIGURE_NUMBERS[name]}.png"):
            shutil.copyfile(spatial/"figures"/part,generated/part)
    shutil.copyfile(spatial/"figures/main_shared_legend.png",generated/"main_shared_legend.png")
    if correction:
        renderer.panels.RADAR_LABELS_SHORT[1]="Top-decile\nsource share"
        renderer.panels.RADAR_LABELS_SHORT[2]="Top-three\nroute share"
        renderer.panels.RADAR_LABELS_SHORT[4]="Mass flow over\n100 km"
    renderer.network_panels(local,generated)
    old_terms=renderer.publication_terms
    if correction:
        labels={"Key-node concentration (%)":"Top-decile source share (%)",
                "Key-corridor concentration (%)":"Top-three route share (%)",
                "Cross-regional logistics share (%)":"Mass flow over 100 km (%)"}
        def profile_terms(figure):
            old_terms(figure)
            for axis in figure.axes:
                axis.set_xlabel(labels.get(axis.get_xlabel(),axis.get_xlabel()))
                axis.set_ylabel(labels.get(axis.get_ylabel(),axis.get_ylabel()))
                for text in axis.texts:
                    if text.get_text() in ("(a)","(b)","(c)","(d)"):
                        text.set_x(-.022)
        renderer.publication_terms=profile_terms
    renderer.figure_s27(local,generated)
    renderer.publication_terms=old_terms
    renderer.plot_maps(local,generated,spatial/"templates",["CCU-BH-FT"])
    renderer.figure_s26(local,generated,original/"figures_temporal/temporal_data",original/"figures_temporal/inputs",revision/"final_accounts")
    renderer.compose_main(generated,spatial/"templates")
    old_joint=pd.read_csv(spatial/"network_data/scenario_integrated_metrics.csv")
    new_joint=pd.read_csv(local/"scenario_integrated_metrics.csv")
    pd.testing.assert_frame_equal(old_joint,new_joint,rtol=1e-10,atol=1e-10)
    mapping={"Figure_2":"Figure_2","Figure_S8":"Figure_S27","Figure_S35":"Figure_S26","Figure_S59":"Figure_S59"}
    for new,old in mapping.items():
        for ext in (".png",".pdf"):shutil.copyfile(generated/(old+ext),output/(new+ext))
    provenance={"renderer_sha256":digest(template),"network_metrics_sha256":digest(local/"network_metrics.csv"),
                "same_integrated_plot_data_as_base":True,"figures":{f:digest(output/(f+".png")) for f in mapping}}
    (output/"network_figure_checks.json").write_text(json.dumps(provenance,indent=2)+"\n",encoding="utf-8")


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--archive",required=True,type=Path)
    p.add_argument("--spatial-correction",type=Path)
    p.add_argument("--scratch",required=True,type=Path)
    p.add_argument("--output",required=True,type=Path)
    opts=p.parse_args()
    draw(opts.archive,opts.spatial_correction,opts.scratch,opts.output)
