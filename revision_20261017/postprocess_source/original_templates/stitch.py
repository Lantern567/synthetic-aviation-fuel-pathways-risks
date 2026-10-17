import base64
import importlib.util
import json
from pathlib import Path

from PIL import Image, ImageOps

HERE = Path(__file__).resolve().parent
FIGURES = HERE/'figures'


def flatten_white(path):
    image = Image.open(path).convert('RGBA')
    background = Image.new('RGB',image.size,'white')
    background.paste(image,mask=image.getchannel('A'))
    return background


def stitch_white(area_png, cost_png, carbon_png, out_png):
    area = flatten_white(area_png)
    right_width = int(area.width*.56)
    donut_height = area.height//2
    composite = Image.new('RGB',(area.width+right_width,area.height),'white')
    composite.paste(area,(0,0))
    for index,source in enumerate([cost_png,carbon_png]):
        donut = ImageOps.contain(flatten_white(source),(right_width,donut_height),Image.Resampling.LANCZOS)
        composite.paste(donut,(area.width+(right_width-donut.width)//2,index*donut_height+(donut_height-donut.height)//2))
    composite.save(out_png,dpi=(300,300))
    composite.save(out_png.with_suffix('.pdf'),'PDF',resolution=300)
    encoded = base64.b64encode(out_png.read_bytes()).decode('ascii')
    width,height = composite.size
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="{width/300*25.4:.2f}mm" height="{height/300*25.4:.2f}mm" viewBox="0 0 {width} {height}"><image width="{width}" height="{height}" href="data:image/png;base64,{encoded}"/></svg>'
    out_png.with_suffix('.svg').write_text(svg,encoding='utf-8')


def main():
    source = HERE.parents[1]/'corrected_runs_20261006/project/products/supply_chain_optimization/visualization/pareto_three_breakdown_visualization.py'
    spec = importlib.util.spec_from_file_location('original_polar',source)
    polar = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(polar)
    scenarios = json.loads((HERE/'adapted_data/manifest.json').read_text(encoding='utf-8'))
    for scenario in scenarios:
        carbon = json.loads((HERE/f'adapted_data/{scenario}_carbon_emissions.json').read_text(encoding='utf-8'))
        values = polar._aggregate(carbon['detailed'],'carbon_keys')
        polar.draw_donut(values,'Carbon\nShare',FIGURES/f'{scenario}_carbon.png')
        stitch_white(FIGURES/f'{scenario}_polar.png',FIGURES/f'{scenario}_cost.png',FIGURES/f'{scenario}_carbon.png',FIGURES/f'{scenario}_composite.png')
    print('WHITE COMPOSITES',len(scenarios))


if __name__=='__main__':
    main()
