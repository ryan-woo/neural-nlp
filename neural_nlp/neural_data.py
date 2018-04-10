import glob
import logging
import os

import numpy as np
import pandas as pd
import re
import xarray as xr
from mkgu.assemblies import NeuroidAssembly

neural_data_dir = os.path.join(os.path.dirname(__file__), '..', 'ressources', 'neural_data')
_logger = logging.getLogger(__name__)


def load_rdms(story='Boar', roi_filter='from90to100'):
    data = []
    for filepath in glob.glob(os.path.join(
            neural_data_dir, '{}{}*.csv'.format(story + '_', roi_filter))):
        _logger.debug("Loading file {}".format(filepath))
        attributes = re.match('^.*/(?P<story>.*)_from(?P<roi_low>[0-9]+)to(?P<roi_high>[0-9]+)'
                              '(_(?P<subjects>[0-9]+)Subjects)?\.mat_r(?P<region>[0-9]+).csv', filepath)
        _data = pd.read_csv(filepath, header=None)
        num_stimuli = len(_data.columns)
        assert len(_data) % num_stimuli == 0
        num_subjects = len(_data) // num_stimuli
        _data = np.stack([_data.iloc[(subject * num_stimuli):((subject + 1) * num_stimuli)]
                          for subject in range(num_subjects)])
        _data = xr.DataArray([_data], coords={
            'timepoint_left': list(range(num_stimuli)), 'timepoint_right': list(range(num_stimuli)),
            'region': [int(attributes['region'])],
            'subject': list(range(num_subjects))},
                             dims=['region', 'subject', 'timepoint_left', 'timepoint_right'])
        stimuli_meta = lambda x: (['timepoint_left', 'timepoint_right'],
                                  np.broadcast_to(x, [num_stimuli, num_stimuli]))
        _data['story'] = stimuli_meta(attributes['story'])
        _data['roi_low'] = stimuli_meta(int(attributes['roi_low']))
        _data['roi_high'] = stimuli_meta(int(attributes['roi_high']))
        data.append(_data)
    data = xr.concat(data, 'region')

    # re-format timepoint_{left,right} to single dimension
    timepoint_dims = ['timepoint_left', 'timepoint_right']
    coords = {'timepoint': data['timepoint_left'].values}
    for name, value in data.coords.items():
        if name in timepoint_dims:
            continue
        if np.array_equal(value.dims, timepoint_dims):
            unique = np.unique(value.values)
            assert unique.size == 1
            coords[name] = 'timepoint', np.broadcast_to(unique, coords['timepoint'].shape).copy()
            # need to copy due to https://github.com/pandas-dev/pandas/issues/15860
        else:
            coords[name] = value
    dims = [dim if dim not in timepoint_dims else 'timepoint' for dim in data.dims]
    data = NeuroidAssembly(data.values, coords=coords, dims=dims)
    return data