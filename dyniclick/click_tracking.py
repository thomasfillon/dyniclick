#!/usr/bin/env python
"""        
Click tracking from click tdoas.

Usage: read
    $ ./click_tracking.py --h
"""

import os
import sys
import logging
import argparse
from argparse import RawDescriptionHelpFormatter
import textwrap
import pickle

import numpy as np
import git


NO_TRACK_ID = -1


path = os.path.dirname(os.path.abspath(__file__))


def track_clicks(clicks, amp_thres, click_interval_max, diff_max, polynomial_expectation=False):

    tracks = []

    for i, c in enumerate(clicks):

        if c[1] < amp_thres:
            continue

        if i == 0:
            tracks.append([i])
            continue

        diff_min = np.finfo(np.float32).max
        track_ind = None

        for j, track in enumerate(tracks):

            if c[0] - clicks[track[-1]][0] < click_interval_max:

                if polynomial_expectation:
                    # fit 2nd order polynomial on last 3 points
                    deg = min(len(track)-1, 2) # max degree is 2
                    last = track[-3:]
                    x = [clicks[k][0] for k in last]
                    y = [clicks[k][2] for k in last]
                    p = np.polyfit(x, y, deg)
                    # compute polynomial value at current click time
                    expected_tdoa = np.polyval(p, c[0])

                else:
                    expected_tdoa = clicks[track[-1]][2]

                diff  = np.abs(expected_tdoa - c[2])
                if diff < diff_min and diff < diff_max:
                    diff_min = diff
                    track_ind = j

        if track_ind:
            tracks[track_ind].append(i)
        else:
            tracks.append([i])

    # keep only multiple clicks tracks
    tracks =  [t for t in tracks if len(t) > 1]

    return tracks


def process(
        click_file,
        output_file,
        amp_thres,
        click_interval_max,
        diff_max
):

    data = pickle.load(open(click_file, "rb"))
    tdoa_col = data["col_names"].index("tdoa")
    clicks = data["features"][:,[0,1,tdoa_col]]

    tracks = track_clicks(clicks, amp_thres, click_interval_max, diff_max)

    # get track ind per click
    track_ind = []
    for i in range(clicks.shape[0]):
        try:
            ind = next(j for j, sublist in enumerate(tracks) if i in sublist)
        except StopIteration:
            ind = NO_TRACK_ID
        track_ind.append(ind)

    d = dict()
    # git info
    repo = git.Repo(path, search_parent_directories=True)
    d["commit"] = repo.head.object.hexsha
    d["file"] = __file__
    d["duration"] = data["duration"]
    d["config"] = {
        "click_file": click_file,
        "output_file": output_file,
        "amp_thres": amp_thres,
        "click_interval_max": click_interval_max,
        "diff_max": diff_max
    }
    d["tracks"] = np.atleast_2d(track_ind).T

    pickle.dump(d, open(output_file, 'wb'))

if __name__ == "__main__":

    parser = argparse.ArgumentParser(formatter_class=argparse.RawTextHelpFormatter,
                                     description=textwrap.dedent('''
    Click tracking.
    '''))
    parser.add_argument(
        '-v', "--verbose",
        help="Set verbose output", action="store_const", const=logging.DEBUG,
        dest="loglevel", default=logging.INFO)
    parser.add_argument("click_file", help="Click file, with click time in col 0, click amplitude in col 1 and tdoa in col tdoa_col.")
    parser.add_argument("output_file", help="Same as input, with an additional column specifying a track id, if a track is found.")
    parser.add_argument("--amp_thres", type=float, default=0.1, help="Click amplitude threshold.")
    parser.add_argument("--click_interval_max", type=float, default=0.1, help="Maximum interval between clicks before ending a track.")
    parser.add_argument("--diff_max", type=float, default=2e-5, help="Maximum difference between expection and actual value to assign a click to a track .")
    args = parser.parse_args()

    logging.getLogger().setLevel(args.loglevel)

    process(
        args.click_file,
        args.output_file,
        args.amp_thres,
        args.click_interval_max,
        args.diff_max
    )

