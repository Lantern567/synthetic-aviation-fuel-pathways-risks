import argparse
import csv
import importlib.util
import os
import shutil
import sys
from pathlib import Path

from matplotlib.text import Text


def render(archive, inventory, scratch, output, hydrogen=None):
    source = archive/"revision_20261017"/"artifacts"/"workspace"/"work"/"nexus_targeted_revision"/"revision_20261007"/"figures_space_time"/"source"
    os.environ["MPLBACKEND"]="Agg"
    os.environ["MPLCONFIGDIR"]=str(scratch/"mplconfig")
    sys.path.insert(0,str(source))
    spec=importlib.util.spec_from_file_location("archived_capture_figure_template",source/"generate_appendix_docx.py")
    plot=importlib.util.module_from_spec(spec)
    sys.modules[spec.name]=plot
    spec.loader.exec_module(plot)
    target=scratch/"products"/"supply_chain_optimization"/"green_hydrogen_supply_chain_optimization"/"data"/"co2_capture_sources.csv"
    target.parent.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(inventory,target)
    output.mkdir(parents=True,exist_ok=True)
    plot.ROOT=scratch
    labels={"Share of archived CO₂ source table (%)":"Share of CO₂ source inventory (%)",
            "Aggregate weekly capture (Mt CO₂/week)":"Weekly capture ceiling (Mt CO₂/week)",
            "Weekly capture potential (Mt CO₂/week)":"Weekly capture ceiling (Mt CO₂/week)",
            "Weekly capture share":"Weekly ceiling share",
            "Unit capture cost (yuan/t CO₂)":"Unit capture cost (CNY/t CO₂)",
            "Capture cost assumption (yuan/t CO₂)":"Assumed capture cost (CNY/t CO₂)"}
    def save_figure(figure,base,*,formats,dpi,bbox_inches,pad_inches,facecolor):
        for artist in figure.findobj(Text):
            original=artist.get_text()
            revised=labels.get(original,original).replace("₂",r"$_{2}$")
            if revised!=original:artist.set_text(revised)
        if base.name=="Figure_S25":
            axis=figure.axes[0]
            ticks=axis.get_yticks()
            axis.set_yticks(ticks,[labels.get(t.get_text(),t.get_text()) for t in axis.get_yticklabels()])
            handles,titles=axis.get_legend_handles_labels()
            axis.legend(handles,titles,loc="center",bbox_to_anchor=(.5,.50),ncol=3,frameon=False,
                        columnspacing=1.05,handlelength=1.45,fontsize=6.5)
        figure.savefig(base.with_suffix(".png"),dpi=dpi,bbox_inches=bbox_inches,pad_inches=pad_inches,facecolor=facecolor)
    plot.save_publication_figure=save_figure
    if hydrogen:
        with hydrogen.open(encoding="utf-8-sig",newline="") as f:rows=list(csv.DictReader(f))
        source_root=scratch/"products/gis_energy_mapping/industrial_byproduct_hydrogen/data"
        source_root.mkdir(parents=True,exist_ok=True)
        for sector,name in (("Refinery","refinery_daily_byproduct_h2_20251027_202950.csv"),("Steel","steel_daily_byproduct_h2_20251027_202950.csv")):
            with (source_root/name).open("w",encoding="utf-8",newline="") as f:
                writer=csv.writer(f)
                writer.writerow(["province","h2_daily_tonnes"])
                writer.writerows((r["provincial_region"],r["gross_hydrogen_t_day"]) for r in rows if r["sector"]==sector)
        plot.create_byproduct_raw_summary(output/"Figure_S23.png")
    plot.create_co2_capture_raw_summary(output/"Figure_S25.png",None)
    plot.create_co2_capture_geo_maps(output/"Figure_S26.png")


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    for key in ("archive","inventory","scratch","output"):parser.add_argument("--"+key,type=Path,required=True)
    parser.add_argument("--hydrogen",type=Path)
    args=parser.parse_args()
    render(args.archive,args.inventory,args.scratch,args.output,args.hydrogen)
