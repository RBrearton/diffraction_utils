"""
This module contains:

Parsing functions used to extract information from experimental files.

Classes used to help make parsing more modular. These include the NexusBase
class and its children.
"""

# We've gotta access the _value attribute on some NXobjects.
# pylint: disable=protected-access


import json
import os
from typing import List
from abc import abstractmethod


import nexusformat.nexus.tree as nx
from nexusformat.nexus import nxload
import numpy as np


from .region import Region
from .debug import debug
from .data_file import DataFileBase


class NexusBase(DataFileBase):
    """
    This class contains *mostly* beamline agnostic nexus parsing convenience
    stuff. It's worth noting that this class still makes a series of assumptions
    about how data is laid out in a nexus file that can be broken. Instead of
    striving for some impossible perfection, this class is practical in its
    assumptions of how data is laid out in a .nxs file, and will raise if an
    assumption is violated. All instrument-specific assumptions that one must
    inevitably make to extract truly meaningful information from a nexus file
    are made in children of this class.

    Attrs:
        file_path:
            The local path to the file on the local filesystem.
        nxfile:
            The object produced by loading the file at file_path with nxload.
    """

    def __init__(self, local_path: str):
        super().__init__(local_path)
        self.nxfile = nxload(local_path)

    @property
    def src_path(self):
        """
        The name of this nexus file, as it was recorded when the nexus file was
        written.
        """
        return self.nxfile.file_name

    @property
    def detector(self):
        """
        Returns the NXdetector instance stored in this NexusFile.

        Raises:
            ValueError if more than one NXdetector is found.
        """
        det, = self.instrument.NXdetector
        return det

    @property
    def instrument(self):
        """
        Returns the NXinstrument instanced stored in this NexusFile.

        Raises:
            ValueError if more than one NXinstrument is found.
        """
        instrument, = self.entry.NXinstrument
        return instrument

    @property
    def entry(self) -> nx.NXentry:
        """
        Returns this nexusfile's entry.

        Raises:
            ValueError if more than one entry is found.
        """
        entry, = self.nxfile.NXentry
        return entry

    @property
    def default_signal(self) -> np.ndarray:
        """
        The numpy array of intensities pointed to by the signal attribute in the
        nexus file.
        """
        return self.default_nxdata[self.default_signal_name].nxdata

    @property
    def default_axis(self) -> np.ndarray:
        """
        Returns the nxdata associated with the default axis.
        """
        return self.default_nxdata[self.default_axis_name].nxdata

    @property
    def default_signal_name(self):
        """
        Returns the name of the default signal.
        """
        return self.default_nxdata.signal

    @property
    def default_axis_name(self) -> str:
        """
        Returns the name of the default axis.
        """
        return self.entry[self.entry.default].axes

    @property
    def default_nxdata_name(self):
        """
        Returns the name of the default nxdata.
        """
        return self.entry.default

    @property
    def default_nxdata(self) -> np.ndarray:
        """
        Returns the default NXdata.
        """
        return self.entry[self.default_nxdata_name]

    # A hack to tell pylint that this class is still meant to be abstract.
    @property
    @abstractmethod
    def default_axis_type(self) -> str:
        return super().default_axis_type()


class I07Nexus(NexusBase):
    """
    This class extends NexusBase with methods useful for scraping information
    from nexus files produced at the I07 beamline at Diamond.
    """
    excalibur_detector_2021 = "excroi"
    excalibur_04_2022 = "exr"

    @property
    def local_data_path(self) -> str:
        """
        The local path to the data (.h5) file. Note that this isn't in the
        NexusBase class because it need not be reasonably expected to point at a
        .h5 file.

        Raises:
            FileNotFoundError if the data file cant be found.
        """
        file = _try_to_find_files(
            [self._src_data_path], [self.local_path])[0]
        return file

    @property
    def detector_name(self) -> str:
        """
        Returns the name of the detector that we're using. Because life sucks,
        this is a function of time.
        """
        if "excroi" in self.entry:
            return I07Nexus.excalibur_detector_2021
        if "exr" in self.entry:
            return I07Nexus.excalibur_04_2022
        # Couldn't recognise the detector.
        raise NotImplementedError()

    @property
    def default_axis_name(self) -> str:
        """
        Returns the name of the default axis.
        """
        return self.entry[self.entry.default].axes

    @property
    def default_axis_type(self) -> str:
        """
        Returns the type of our default axis, either being 'q', 'th' or 'tth'.
        """
        if self.default_axis_name == 'qdcd':
            return 'q'
        if self.default_axis_name == 'diff1delta':
            return 'tth'

    def _get_ith_region(self, i: int):
        """
        Returns the ith region of interest found in the .nxs file.

        Args:
            i:
                The region of interest number to return. This number should
                match the ROI name as found in the .nxs file (generally not 0
                indexed).

        Returns:
            The ith region of interest found in the .nxs file.
        """
        x_1 = self.detector[self._get_region_bounds_key(i, 'x_1')][0]
        x_2 = self.detector[self._get_region_bounds_key(i, 'Width')][0] + x_1
        y_1 = self.detector[self._get_region_bounds_key(i, 'y_1')][0]
        y_2 = self.detector[self._get_region_bounds_key(i, 'Height')][0] + y_1
        return Region(x_1, x_2, y_1, y_2)

    @property
    def signal_regions(self) -> List[Region]:
        """
        Returns a list of region objects that define the location of the signal.
        Currently there is nothing better to do than assume that this is a list
        of length 1.
        """
        if self.detector_name == I07Nexus.excalibur_detector_2021:
            return [self._get_ith_region(i=1)]
        if self.detector_name == I07Nexus.excalibur_04_2022:
            # Make sure our code executes for bytes and strings.
            try:
                json_str = self.instrument[
                    "ex_rois/excalibur_ROIs"]._value.decode("utf-8")
            except AttributeError:
                json_str = self.instrument[
                    "ex_rois/excalibur_ROIs"]._value
            # This is badly formatted and cant be loaded by the json lib. We
            # need to make a series of modifications.
            json_str = json_str.replace('u', '')
            json_str = json_str.replace("'", '"')
            json_str = json_str.replace('x', '"x"')
            json_str = json_str.replace('y', '"y"')
            json_str = json_str.replace('width', '"width"')
            json_str = json_str.replace('height', '"height"')
            json_str = json_str.replace('angle', '"angle"')

            roi_dict = json.loads(json_str)
            return [Region.from_dict(roi_dict['Region_1'])]

        raise NotImplementedError()

    @property
    def background_regions(self) -> List[Region]:
        """
        Returns a list of region objects that define the location of background.
        Currently we just ignore the zeroth region and call the rest of them
        background regions.
        """
        if self.detector_name == I07Nexus.excalibur_detector_2021:
            return [self._get_ith_region(i)
                    for i in range(2, self._number_of_regions+1)]
        if self.detector_name == I07Nexus.excalibur_04_2022:
            # Make sure our code executes for bytes and strings.
            try:
                json_str = self.instrument[
                    "ex_rois/excalibur_ROIs"]._value.decode("utf-8")
            except AttributeError:
                json_str = self.instrument[
                    "ex_rois/excalibur_ROIs"]._value
            # This is badly formatted and cant be loaded by the json lib. We
            # need to make a series of modifications.
            json_str = json_str.replace('u', '')
            json_str = json_str.replace("'", '"')
            json_str = json_str.replace('x', '"x"')
            json_str = json_str.replace('y', '"y"')
            json_str = json_str.replace('width', '"width"')
            json_str = json_str.replace('height', '"height"')
            json_str = json_str.replace('angle', '"angle"')

            roi_dict = json.loads(json_str)
            bkg_roi_list = list(roi_dict.values())[1:]
            return [Region.from_dict(x) for x in bkg_roi_list]

        raise NotImplementedError()

    @property
    def probe_energy(self):
        """
        Returns the energy of the probe particle parsed from this NexusFile.
        """
        return float(self.instrument.dcm1energy.value)

    @property
    def transmission(self):
        """
        Proportional to the fraction of probe particles allowed by an attenuator
        to strike the sample.
        """
        return float(self.instrument.filterset.transmission)

    @property
    def detector_distance(self):
        """
        Returns the distance between sample and detector.
        """
        return float(self.instrument.diff1detdist.value)

    @property
    def _src_data_path(self):
        """
        Returns the raw path to the data file. This is useless if you aren't on
        site, but used by islatu to guess where you've stored the data file
        locally.
        """
        # This is far from ideal; there currently seems to be no standard way
        # to refer to point at information stored outside of the nexus file.
        # If you're a human, it's easy enough to find, but with code this is
        # a pretty rubbish task. Here I just grab the first .h5 file I find
        # and run with it.
        found_h5_files = []

        def recurse_over_nxgroups(nx_object, found_h5_files):
            """
            Recursively looks for nxgroups in nx_object that, when cast to a
            string, end in .h5.
            """
            for key in nx_object:
                new_obj = nx_object[key]
                if str(new_obj).endswith(".h5"):
                    found_h5_files.append(str(new_obj))
                if isinstance(new_obj, nx.NXgroup):
                    recurse_over_nxgroups(new_obj, found_h5_files)

        recurse_over_nxgroups(self.nxfile, found_h5_files)

        return found_h5_files[0]

    @property
    def _region_keys(self) -> List[str]:
        """
        Parses all of the detector's dictionary keys and returns all keys
        relating to regions of interest.
        """
        return [key for key in self.detector.keys() if key.startswith("Region")]

    @property
    def _number_of_regions(self) -> int:
        """
        Returns the number of regions of interest described by this nexus file.
        This *assumes* that the region keys take the form f'region_{an_int}'.
        """
        split_keys = [key.split('_') for key in self._region_keys]

        return max([int(split_key[1]) for split_key in split_keys])

    def _get_region_bounds_key(self, region_no: int, kind: str) -> List[str]:
        """
        Returns the detector key relating to the bounds of the region of
        interest corresponding to region_no.

        Args:
            region_no:
                An integer corresponding the the particular region of interest
                we're interested in generating a key for.
            kind:
                The kind of region bounds keys we're interested in. This can
                take the values:
                    'x_1', 'width', 'y_1', 'height'
                where '1' can be replaced with 'start' and with/without caps on
                first letter of width/height.

        Raises:
            ValueError if 'kind' argument is not one of the above.

        Returns:
            A list of region bounds keys that is ordered by region number.
        """
        # Note that the x, y swapping is a quirk of the nexus standard, and is
        # related to which axis on the detector varies most rapidly in memory.
        if kind in ('x_1', 'x_start'):
            insert = 'X'
        elif kind in ('width', 'Width'):
            insert = 'Width'
        elif kind in ('y_1', 'y_start'):
            insert = 'Y'
        elif kind in ('height', 'Height'):
            insert = 'Height'
        else:
            raise ValueError(
                "Didn't recognise 'kind' argument.")

        return f"Region_{region_no}_{insert}"


class I10Nexus(NexusBase):
    """
    This class extends NexusBase with methods useful for scraping information
    from nexus files produced at the I10 beamline at Diamond.
    """


def _try_to_find_files(filenames: List[str],
                       additional_search_paths: List[str]):
    """
    Check that data files exist if the file parsed by parser pointed to a
    separate file containing intensity information. If the intensity data
    file could not be found in its original location, check a series of
    probable locations for the data file. If the data file is found in one
    of these locations, update file's entry in self.data.

    Returns:
        :py:attr:`list` of :py:attr:`str`:
            List of the corrected, actual paths to the files.
    """
    found_files = []

    # If we had only one file, make a list out of it.
    if not hasattr(filenames, "__iter__"):
        filenames = [filenames]

    cwd = os.getcwd()
    start_dirs = [
        cwd,  # maybe file is stored near the current working dir
        # To search additional directories, add them in here manually.
    ]
    start_dirs.extend(additional_search_paths)

    local_start_directories = [x.replace('\\', '/') for x in start_dirs]
    num_start_directories = len(local_start_directories)

    # Now extend the additional search paths.
    for i in range(num_start_directories):
        search_path = local_start_directories[i]
        split_srch_path = search_path.split('/')
        for j in range(len(split_srch_path)):
            extra_path_list = split_srch_path[:-(j+1)]
            extra_path = '/'.join(extra_path_list)
            local_start_directories.append(extra_path)

    # This line allows for a loading bar to show as we check the file.
    for i, _ in enumerate(filenames):
        # Better to be safe... Note: windows is happy with / even though it
        # defaults to \
        filenames[i] = str(filenames[i]).replace('\\', '/')

        # Maybe we can see the file in its original storage location?
        if os.path.isfile(filenames[i]):
            found_files.append(filenames[i])
            continue

        # If not, maybe it's stored locally? If the file was stored at
        # location /a1/a2/.../aN/file originally, for a local directory LD,
        # check locations LD/aj/aj+1/.../aN for all j<N and all LD's of
        # interest. This algorithm is a generalization of Andrew McCluskey's
        # original approach.

        # now generate a list of all directories that we'd like to check
        candidate_paths = []
        split_file_path = str(filenames[i]).split('/')
        for j in range(len(split_file_path)):
            local_guess = '/'.join(split_file_path[j:])
            for start_dir in local_start_directories:
                candidate_paths.append(
                    os.path.join(start_dir, local_guess))

        # Iterate over each of the candidate paths to see if any of them contain
        # the data file we're looking for.
        found_file = False
        for candidate_path in candidate_paths:
            if os.path.isfile(candidate_path):
                # File found - add the correct file location to found_files
                found_files.append(candidate_path)
                found_file = not found_file
                debug.log("Data file found at " + candidate_path + ".")
                break

        # If we didn't find the file, tell the user.
        if not found_file:
            raise FileNotFoundError(
                "The data file with the name " + filenames[i] + " could "
                "not be found. The following paths were searched:\n" +
                "\n".join(candidate_paths)
            )
    return found_files
