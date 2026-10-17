import json
from pathlib import Path

import frykit.plot as fplt
import numpy as np
from scipy.optimize import brentq, least_squares

here = Path(__file__).resolve().parent
reg = json.loads((here / 'templates/archive_registration.json').read_text())
coordinates = np.array([[116.5846, 40.0801], [117.3462, 39.1244]])
points = fplt.CN_AZIMUTHAL_EQUIDISTANT.transform_points(fplt.PLATE_CARREE, coordinates[:, 0], coordinates[:, 1])
pixels = np.column_stack([points[:, 0] * reg['scale_x'] + reg['offset_x'], points[:, 1] * reg['scale_y'] + reg['offset_y']])
ticks = reg['independent_tick_checks']
lon_ticks = np.array([record['detected_tick_x'] for record in ticks if 'longitude' in record])
lat_ticks = np.array([record['detected_tick_y'] for record in ticks if 'latitude' in record])
x0, y0, x1, y1 = reg['frame']


def residual(parameters):
    scale, xshift, yshift = parameters
    longitude = fplt.PLATE_CARREE.transform_points(fplt.CN_AZIMUTHAL_EQUIDISTANT,
        (lon_ticks - xshift) / scale, np.full(4, (yshift - y1) / scale))[:, 0]
    latitude = fplt.PLATE_CARREE.transform_points(fplt.CN_AZIMUTHAL_EQUIDISTANT,
        np.full(5, (x0 - xshift) / scale), (yshift - lat_ticks) / scale)[:, 1]
    return np.r_[(longitude - [114, 116, 118, 120]) * 344, (latitude - np.arange(38, 43)) * 426]


solution = least_squares(residual, [reg['scale_x'], reg['offset_x'], reg['offset_y']], x_scale='jac')
scale, shift_x, shift_y = solution.x
calibrated = np.column_stack([points[:, 0] * scale + shift_x, -points[:, 1] * scale + shift_y])
centroids = np.array([[entry['x'], entry['y']] for entry in reg['airports']])
errors = np.linalg.norm(calibrated - centroids, axis=1)
current_ticks = []
for record in ticks:
    if 'latitude' in record:
        expected = brentq(lambda pixel: fplt.PLATE_CARREE.transform_point(
            (x0 - shift_x) / scale, (shift_y - pixel) / scale, fplt.CN_AZIMUTHAL_EQUIDISTANT)[1] - record['latitude'], 0, 2300)
        current_ticks.append(dict(latitude=record['latitude'], expected_pixel_y=expected, detected_tick_y=record['detected_tick_y']))
    else:
        expected = brentq(lambda pixel: fplt.PLATE_CARREE.transform_point(
            (pixel - shift_x) / scale, (shift_y - y1) / scale, fplt.CN_AZIMUTHAL_EQUIDISTANT)[0] - record['longitude'], 100, 3000)
        current_ticks.append(dict(longitude=record['longitude'], expected_pixel_x=expected, detected_tick_x=record['detected_tick_x']))
result = dict(reg, scale_x=scale, scale_y=-scale, offset_x=shift_x, offset_y=shift_y,
              independent_tick_checks=current_ticks,
              max_tick_error_pixels=float(abs(residual(solution.x)).max()),
              airport_centroid_residual_pixels=errors.tolist(),
              calibration_basis='Nine labelled original map-frame ticks; two original airport centroids independently checked',
              runtime_projection=str(fplt.CN_AZIMUTHAL_EQUIDISTANT),
              runtime_source_projection=str(fplt.PLATE_CARREE))
print(json.dumps(result, indent=2))
assert result['max_tick_error_pixels'] < 4
assert errors.max() < 5, errors
(here / 'templates/current_archive_registration.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
