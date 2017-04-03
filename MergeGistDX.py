#!/usr/bin/env python

#
# Written by M. Aldeghi
#

import re
import numpy as np
from argparse import ArgumentParser
from glob import glob


# =============
# Input Options
# =============
def parseOptions():
    parser = ArgumentParser(description='''A script to merge the small DX files
generated by GIST back into the full box volume.''')
    parser.add_argument('-f', metavar='dxfiles', dest='dxfiles',
                        help='DX files to be merged. Specify a list or use '
                             'wildcards: e.g. "gist1.dx gist2.dx gist3.dx" '
                             'or "gist*.dx".',
                        required=True, type=str, nargs='+')
    parser.add_argument('-o', metavar='outfname', dest='outfname',
                        help='Name of output DX file. Default is "merged.dx".',
                        default='merged.dx', type=str)
    args = parser.parse_args()
    return args


# ====
# Main
# ====
def main(args):

    if len(args.dxfiles) == 1:
        dxfiles = glob(args.dxfiles)
    else:
        dxfiles = args.dxfiles
    natsort(dxfiles)

    # initialise some variables
    box_origin = {}
    box_gridcounts = {'x': 0, 'y': 0, 'z': 0}
    box_spacing = 0.0
    box_ngridpoints = 0
    box_data_dict = {}
    box_data_array = []

    # --------------------------------------
    # Iterate through all files and get data
    # --------------------------------------
    for idx, dx_file in enumerate(dxfiles):
        print "Processing %s..." % dx_file
        dx = OpenDX()
        dx.read(dx_file)

        # get spacing
        # -----------
        # this will keep getting updated
        # so assumes spacing it's the same for all small boxes!
        box_spacing = dx.delta

        # Identify origin of large box
        # ----------------------------
        if idx == 0:
            box_origin = dx.origin
            box_origin['x'] += box_spacing
            box_origin['y'] += box_spacing
            box_origin['z'] += box_spacing

        # Number of grid points
        # ---------------------
        a = dx.gridcounts['x']
        b = dx.gridcounts['y']
        c = dx.gridcounts['z']
        A = a*b*2 + b*(c-2)*2 + (a-2)*(c-2)*2  # number of voxels on surface
        # remove the gridpoints on the surface from the count
        box_ngridpoints += dx.ngridpoints - A

        # Add data to dict
        # ----------------
        box_data_dict.update(dx.data_dict)

    # --------------------------------------------
    # Find number of gridpoints for each dimension
    # --------------------------------------------
    max_x = max(box_data_dict, key=lambda t: t[0])[0]
    max_y = max(box_data_dict, key=lambda t: t[1])[1]
    max_z = max(box_data_dict, key=lambda t: t[2])[2]

    min_x = min(box_data_dict, key=lambda t: t[0])[0]
    min_y = min(box_data_dict, key=lambda t: t[1])[1]
    min_z = min(box_data_dict, key=lambda t: t[2])[2]

    len_x = max_x - min_x
    len_y = max_y - min_y
    len_z = max_z - min_z

    box_gridcounts['x'] = int(round(len_x/box_spacing + 1))
    box_gridcounts['y'] = int(round(len_y/box_spacing + 1))
    box_gridcounts['z'] = int(round(len_z/box_spacing + 1))

    # a few checks just in case
    assert box_ngridpoints == len(box_data_dict)
    assert box_ngridpoints == (box_gridcounts['x'] *
                               box_gridcounts['y'] *
                               box_gridcounts['z'])
    assert box_origin['x'] == min_x
    assert box_origin['y'] == min_y
    assert box_origin['z'] == min_z

    # ----------------------------------------
    # Turn the data dict into the proper array
    # ----------------------------------------
    coord_x = np.linspace(min_x, max_x, num=box_gridcounts['x'])
    coord_y = np.linspace(min_y, max_y, num=box_gridcounts['y'])
    coord_z = np.linspace(min_z, max_z, num=box_gridcounts['z'])

    print "\nSorting the grid data..."
    for x in coord_x:
        for y in coord_y:
            for z in coord_z:
                n = box_data_dict[(round(x, 3),
                                   round(y, 3),
                                   round(z, 3))]
                box_data_array.append(n)

    assert len(box_data_array) == box_ngridpoints

    # -------------------
    # Save Merged DX file
    # -------------------
    LargeBox = OpenDX(origin=box_origin,
                      gridcounts=box_gridcounts,
                      ngridpoints=box_ngridpoints,
                      delta=box_spacing,
                      data_array=box_data_array)
    LargeBox.write(args.outfname)

    print "\nMerged File: %s" % args.outfname
    print "-----------------------------------"
    print "Grid Origin: {x:.3f} {y:.3f} {z:.3f}".format(**box_origin)
    print "N Gridpoints: %s" % box_ngridpoints
    print "Grid dimensions: {x:d} {y:d} {z:d}".format(**box_gridcounts)
    print "Grid spacing: %s\n" % box_spacing


# =====================
# Classes and Functions
# =====================
class OpenDX(object):

    def __init__(self, origin=None, gridcounts=None,
                 ngridpoints=None, delta=None, data_array=None):
        if origin is None:
            self.origin = {'x': 0., 'y': 0., 'z': 0.}
        else:
            self.origin = origin
        if gridcounts is None:
            self.gridcounts = {'x': 0, 'y': 0, 'z': 0}
        else:
            self.gridcounts = gridcounts
        if ngridpoints is None:
            self.ngridpoints = 0
        else:
            self.ngridpoints = ngridpoints
        if delta is None:
            self.delta = 0.0
        else:
            self.delta = delta
        if data_array is None:
            self.data_array = []
        else:
            self.data_array = data_array

    def read(self, dxfile):
        lines = [l for l in open(dxfile, 'r').readlines() if l.strip()]
        # Assuming first 7 lines are headers:
        header = lines[:7]
        # Data is the rest, other possible comments at the end of the file
        datapoints = [l for l in lines[7:] if is_number(l.split()[0])]

        # parse header
        for line in header:
            elem = line.split()
            if elem[0]+elem[1] == 'object1':
                self.gridcounts = {'x': int(elem[-3]),
                                   'y': int(elem[-2]),
                                   'z': int(elem[-1])}
            if elem[0]+elem[1] == 'object3':
                self.ngridpoints = int(elem[-3])
            if elem[0] == 'origin':
                self.origin = {'x': float(elem[1]),
                               'y': float(elem[2]),
                               'z': float(elem[3])}
            # NOTE: this assumes all delta are the same
            if elem[0] == 'delta':
                delta = [float(x) for x in elem[1:4] if float(x) != 0.0]
                if len(delta) == 1:
                    self.delta = delta[0]
                else:
                    exit('ERROR while reading "delta" for file %s' % dxfile)

        # read data but skip surface voxels
        # ---------------------------------

        # Put all datapoints in an array
        data_array = []
        for line in datapoints:
            elem = line.split()
            for el in elem:
                data_array.append(float(el))

        # Map datapoints in the array to their coordinates
        data_dict = {}
        c = 0
        for x in range(self.gridcounts['x']):
            for y in range(self.gridcounts['y']):
                for z in range(self.gridcounts['z']):
                    # if it is a voxel on the surface of the cuboid
                    # skip the datapoint
                    if x == 0 or x == self.gridcounts['x']-1:
                        c += 1
                        continue
                    if y == 0 or y == self.gridcounts['y']-1:
                        c += 1
                        continue
                    if z == 0 or z == self.gridcounts['z']-1:
                        c += 1
                        continue

                    loc = (round(self.origin['x'] + self.delta*x, 3),
                           round(self.origin['y'] + self.delta*y, 3),
                           round(self.origin['z'] + self.delta*z, 3),)

                    data_dict[loc] = data_array[c]
                    c += 1

        self.data_array = data_array
        self.data_dict = data_dict

        # Number of surface voxels
        a = self.gridcounts['x']
        b = self.gridcounts['y']
        c = self.gridcounts['z']
        A = a*b*2 + b*(c-2)*2 + (a-2)*(c-2)*2
        # Check that data_dict and data_array (less the surface voxels)
        # have the same number of datapoints
        assert len(self.data_array) - A == len(self.data_dict)

        # print "\n%s" % dxfile
        # print "------------------------------------------------"
        # print "Grid Origin: %s" % self.origin
        # print "N Gridpoints: %s" % self.ngridpoints
        # print "Grid dimensions: %s" % self.gridcounts
        # print "Grid spacing: %s\n" % self.delta

    def write(self, outfname):
        with open(outfname, 'w') as f:
            f.write('object 1 class gridpositions counts '
                    '{x:d} {y:d} {z:d}\n'.format(**self.gridcounts))
            f.write('origin {x:.3f} {y:.3f} {z:.3f}\n'.format(**self.origin))
            f.write('delta {0:.1f} 0 0\n'.format(self.delta))
            f.write('delta 0 {0:.1f} 0\n'.format(self.delta))
            f.write('delta 0 0 {0:.1f}\n'.format(self.delta))
            f.write('object 2 class gridconnections counts '
                    '{x:d} {y:d} {z:d}\n'.format(**self.gridcounts))
            f.write('object 3 class array type float rank 0 items '
                    '{0:d} data follows\n'.format(self.ngridpoints))

            for i, d in enumerate(self.data_array):
                f.write('{0:.4f} '.format(d))
                if (i+1.) % 3. == 0.:
                    f.write('\n')

            f.write('\n\nobject "density [A^-3]" class field\n')


def natsort(l):
    # From Ned Batchelder:
    # https://nedbatchelder.com/blog/200712/human_sorting.html
    def tryint(s):
        try:
            return int(s)
        except:
            return s

    def alphanum_key(s):
        return [tryint(c) for c in re.split('([0-9]+)', s)]

    l.sort(key=alphanum_key)


def is_number(s):
    try:
        float(s)
        return True
    except:
        return False


if __name__ == "__main__":
    args = parseOptions()
    main(args)