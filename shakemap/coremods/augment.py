"""
Reads shake_data.hdf from the event's current directory and adds local
configs, data, etc., then writes a new shake_data.hdf.
"""

# stdlib imports
import os.path
import glob
import datetime
import shutil

# third party imports
from configobj import ConfigObj

# local imports
from .base import CoreModule
from shakelib.utils.containers import ShakeMapInputContainer
from shakemap.utils.config import get_config_paths, get_custom_validator,\
    config_error, check_config, get_configspec


class AugmentModule(CoreModule):
    """
    augment -- Incorporate additional content into the shake_data.hdf input
                     file.
    """

    command_name = 'augment'

    def execute(self):
        """
        Augment a ShakeMap input data file with local configs, data, rupture,
        etc. The version history will only be incremented if the originator
        differs from the originator in the previous line of the history.

        Raises:
            NotADirectoryError: When the event data directory does not
                exist.
            FileNotFoundError: When the the event's event.xml file does
                not exist.
            RuntimeError: When there are problems parsing the configuration.
            ValidateError: When there are configuration items missing or mis-
                configured.
        """

        install_path, data_path = get_config_paths()
        datadir = os.path.join(data_path, self._eventid, 'current')
        if not os.path.isdir(datadir):
            raise NotADirectoryError('%s is not a valid directory.' % datadir)

        hdf_file = os.path.join(datadir, 'shake_data.hdf')
        if not os.path.isfile(hdf_file):
            raise FileNotFoundError('%s does not exist. Use assemble.' %
                                    hdf_file)
        shake_data = ShakeMapInputContainer.load(hdf_file)

        #
        # Clear away results from previous runs
        #
        products_path = os.path.join(datadir, 'products')
        if os.path.isdir(products_path):
            shutil.rmtree(products_path, ignore_errors=True)

        #
        # Get the config from the HDF file and merge in the local configs
        #
        spec_file = get_configspec()
        validator = get_custom_validator()
        shake_config = shake_data.getConfig()
        shake_config = ConfigObj(shake_config, configspec=spec_file)

        modules_file = os.path.join(install_path, 'config', 'modules.conf')
        if os.path.isfile(modules_file):
            self.logger.info('Found a modules file.')
            modules = ConfigObj(modules_file, configspec=spec_file)
            shake_config.merge(modules)
        gmpe_file = os.path.join(install_path, 'config', 'gmpe_sets.conf')
        if os.path.isfile(gmpe_file):
            self.logger.info('Found a gmpe file.')
            gmpe_sets = ConfigObj(gmpe_file, configspec=spec_file)
            shake_config.merge(gmpe_sets)
        config_file = os.path.join(install_path, 'config', 'model.conf')
        if os.path.isfile(config_file):
            self.logger.info('Found a global config file.')
            global_config = ConfigObj(config_file, configspec=spec_file)
            shake_config.merge(global_config)
        #
        # this is the event specific model.conf (may not be present)
        # prefer model.conf to model_zc.conf
        #
        event_config_file = os.path.join(datadir, 'model.conf')
        event_config_zc_file = os.path.join(datadir, 'model_zc.conf')
        if os.path.isfile(event_config_file):
            self.logger.info('Found an event specific model.conf file.')
            event_config = ConfigObj(event_config_file,
                                     configspec=spec_file)
            shake_config.merge(event_config)
        elif os.path.isfile(event_config_zc_file):
            self.logger.info('Found an event specific model_zc file.')
            event_config = ConfigObj(event_config_zc_file,
                                     configspec=spec_file)
            shake_config.merge(event_config)
        #
        # Validate the resulting config
        #
        results = shake_config.validate(validator)
        if not results or isinstance(results, dict):
            config_error(shake_config, results)
        check_config(shake_config, self.logger)
        #
        # The vs30 file may have macros in it
        #
        vs30file = shake_config['data']['vs30file']
        if vs30file:
            vs30file = vs30file.replace('<INSTALL_DIR>', install_path)
            vs30file = vs30file.replace('<DATA_DIR>', data_path)
            vs30file = vs30file.replace('<EVENT_ID>', self._eventid)
            if not os.path.isfile(vs30file):
                raise FileNotFoundError('vs30 file "%s" is not a '
                                        'valid file' % vs30file)
            shake_config['data']['vs30file'] = vs30file
        #
        # If there is a prediction_location->file file, then we need
        # to expand any macros
        #
        if 'file' in shake_config['interp']['prediction_location']:
            loc_file = shake_config['interp']['prediction_location']['file']
            if loc_file and loc_file != 'None':      # 'None' is a string here
                loc_file = loc_file.replace('<INSTALL_DIR>', install_path)
                loc_file = loc_file.replace('<DATA_DIR>', data_path)
                loc_file = loc_file.replace('<EVENT_ID>', self._eventid)
                if not os.path.isfile(loc_file):
                    raise FileNotFoundError('prediction file "%s" is not a '
                                            'valid file' % loc_file)
                shake_config['interp']['prediction_location']['file'] = loc_file
        #
        # Put the updated config back into shake_data.hdf`
        #
        config = shake_config.dict()
        shake_data.setConfig(config)
        #
        # Look for additional data files and update the stationlist if found
        #
        datafiles = glob.glob(os.path.join(datadir, '*_dat.xml'))
        if os.path.isfile(os.path.join(datadir, 'stationlist.xml')):
            datafiles.append(os.path.join(datadir, 'stationlist.xml'))
        if datafiles:
            self.logger.info('Found additional data files...')
            shake_data.addStationData(datafiles)
        #
        # Look for a rupture file and replace the existing one if found
        #
        rupturefiles = glob.glob(os.path.join(datadir, '*_fault.txt'))
        eventxml = os.path.join(datadir, 'event.xml')
        rupturefile = None
        if len(rupturefiles):
            rupturefile = rupturefiles[0]
        if not os.path.isfile(eventxml):
            eventxml = None
        if rupturefile is not None or eventxml is not None:
            self.logger.info('Updating rupture/origin information.')
            shake_data.updateRupture(
                eventxml=eventxml, rupturefile=rupturefile)

        #
        # Sort out the version history. We're working with an existing
        # HDF file, so: if we are the originator, just update the timestamp,
        # otherwise add a new line.
        #
        timestamp = datetime.datetime.utcnow().strftime('%FT%TZ')
        originator = config['system']['source_network']

        history = shake_data.getVersionHistory()
        if history['history'][-1][1] == originator:
            history['history'][-1][0] = timestamp
        else:
            version = int(history['history'][-1][2]) + 1
            new_line = [timestamp, originator, version]
            history['history'].append(new_line)
        shake_data.setVersionHistory(history)

        shake_data.close()
