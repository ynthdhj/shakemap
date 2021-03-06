#!/usr/bin/env python
import os
import os.path

import matplotlib
matplotlib.use('Agg')

import pytest

from shakemap.utils.config import get_config_paths
from shakemap.coremods.model import ModelModule
from shakemap.coremods.assemble import AssembleModule
from shakemap.coremods.xtestplot import TestPlot
from shakemap.coremods.xtestplot_spectra import TestPlotSpectra

########################################################################
# Test the nullgmpe and the dummy correlation function as well as
# the two xtestplot functions
########################################################################


def test_validation():

    installpath, datapath = get_config_paths()
    try:
        #
        # Test xtestplot on validation event 0006
        #
        assemble = AssembleModule('validation_test_0006')
        assemble.execute()
        model = ModelModule('validation_test_0006')
        model.execute()
        plot = TestPlot('validation_test_0006')
        plot.execute()

        #
        # Test xtestplot_spectra on validation event 0007
        #
        assemble = AssembleModule('validation_test_0007')
        assemble.execute()
        model = ModelModule('validation_test_0007')
        model.execute()
        plot = TestPlotSpectra('validation_test_0007')
        plot.execute()
    finally:
        data_file = os.path.join(datapath, 'validation_test_0006', 'current',
                                 'shake_data.hdf')
        if os.path.isfile(data_file):
            os.remove(data_file)
        res_file = os.path.join(datapath, 'validation_test_0006', 'current',
                                'products', 'shake_results.hdf')
        if os.path.isfile(res_file):
            os.remove(res_file)
        data_file = os.path.join(datapath, 'validation_test_0007', 'current',
                                 'shake_data.hdf')
        if os.path.isfile(data_file):
            os.remove(data_file)
        res_file = os.path.join(datapath, 'validation_test_0007', 'current',
                                'products', 'shake_results.hdf')
        if os.path.isfile(res_file):
            os.remove(res_file)


if __name__ == '__main__':
    os.environ['CALLED_FROM_PYTEST'] = 'True'
    test_validation()
