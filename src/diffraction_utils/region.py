"""
This module defines the Region object, whose instances define regions of
interest in images.
"""

import numpy as np


class Region:
    """
    Instances of this class define regions of interest.
    """

    def __init__(self, x_start, x_end, y_start, y_end):

        # Make sure that x_end > x_start, etc.
        if x_end < x_start:
            x_start, x_end = x_end, x_start
        if y_end < y_start:
            y_start, y_end = y_end, y_start

        # These may be recorded as types other than int, but we really want
        # these to be integers so they can be used to index objects.
        self.x_start = int(x_start)
        self.x_end = int(x_end)
        self.y_start = int(y_start)
        self.y_end = int(y_end)

    @property
    def x_length(self):
        """
        Returns the length of the region in the x-direction.
        """
        return self.x_end - self.x_start

    @property
    def y_length(self):
        """
        Returns the length of the region in the y-direction.
        """
        return self.y_end - self.y_start

    @property
    def num_pixels(self):
        """
        returns the number of pixels in the region.
        """
        return self.x_length * self.y_length

    @property
    def slice(self):
        """
        Returns an object that can be used to slice numpy arrays to exactly this
        region.
        """
        if self.x_end >= 0:
            x_end = self.x_end + 1
        if self.y_end >= 0:
            y_end = self.y_end + 1
        return np.s_[self.x_start:x_end, self.y_start:y_end]

    @classmethod
    def from_dict(cls, region_dict: dict):
        """
        Instantiates a Region from a dictionary with keys in:
            ['x', 'y', 'width', 'height'].

        This is to help loading dictionarys that are generated by calling
        json.loads on the NXcollections found in I07 nexus files as of
        27/04/2022.
        """
        x_start = int(region_dict['x'])
        y_start = int(region_dict['y'])
        x_end = x_start + int(region_dict['width'])
        y_end = y_start + int(region_dict['height'])
        return cls(x_start, x_end, y_start, y_end)

    def __eq__(self, other):
        """
        Allows for equality checks to be made between instances of Region.
        """
        if not isinstance(other, Region):
            return False

        return self.x_start == other.x_start and self.x_end == other.x_end \
            and self.y_start == other.y_start and self.y_end == other.y_end

    def __str__(self):
        return f"x_start: {self.x_start}, x_end: {self.x_end}, " + \
            f"y_start: {self.y_start}, y_end: {self.y_end}."
