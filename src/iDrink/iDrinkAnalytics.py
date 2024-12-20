import os, sys

import matplotlib.pyplot as plt
import matplotlib

import numpy as np
import pandas as pd
from trc import TRCData

pd.options.mode.copy_on_write = True

def smooth_timeseries(curr_trial, data, factor=4):

    freq = curr_trial.frame_rate
    smoothing_factor = freq / factor
    window = np.ones(int(smoothing_factor)) / (int(smoothing_factor))

    result = np.convolve(data, window, "same")

    return result

def use_butterworth_filter(data, cutoff, fs, order=4, normcutoff=False):
    """
    Input:
        - data: The data to be filtered
        - cutoff: The cutoff frequency of the filter
        - fs: The sampling frequency
        - order: The order of the filter

    Output:
        - filtered_data: The filtered data
    """
    from scipy.signal import butter, sosfiltfilt

    order = int(order/2)  # Order is "doubled" again by using filter 2 times

    nyquist = 0.5 * fs

    if cutoff >= nyquist:
        print(f"Warning: Cutoff frequency {cutoff} is higher than Nyquist frequency {nyquist}.")
        print("Filtering with Nyquist frequency.")
        cutoff = nyquist-1

    if normcutoff:
        cutoff = cutoff / nyquist

    sos = butter(order, cutoff, btype="low", analog=False, output="sos", fs=fs)

    filtered_data = sosfiltfilt(sos, data)


    return filtered_data

def get_measured_side(dat_mov):
    """
    Input:
        - dat_mov: pandas DataFrame with measured angles

    Output:
        - measured_side: The side that has been measured

    Find the side that has been measured. Look at elbow angles of right and left sides.
    The one with bigger range of movement is the one of the measured side.
    """

    diff_l = max(dat_mov["elbow_flex_l"]) - min(dat_mov["elbow_flex_l"])
    diff_r = max(dat_mov["elbow_flex_r"]) - min(dat_mov["elbow_flex_r"])

    if diff_l > diff_r:
        measured_side = "left"
    else:
        measured_side = "right"

    return measured_side


def get_keypoint_positions(path_file):
    """
        Returns the .trc File as pandas Dataframe
        """

    from trc import TRCData

    trc = TRCData()
    trc.load(filename=path_file)
    # trc["Body Part"][INDEX][0:X, 1:Y, 2:Z]
    # trc[timeframe][0: Timestamp, 1:Line_data][1:CHip, 1: RHip, 2: LHip]

    list_columns = ["Frame#", "Time"]
    df = pd.DataFrame(columns=list_columns)
    df["Frame#"] = trc["Frame#"]
    df["Time"] = trc["Time"]
    for component in trc["Markers"]:
        df[f"{component}_X"] = np.array(trc[component])[:, 0]
        df[f"{component}_Y"] = np.array(trc[component])[:, 1]
        df[f"{component}_Z"] = np.array(trc[component])[:, 2]

    return df


def calculate_keypoint_vel_acc(curr_trial, save_file=True):
    """
    Calculate the velocity over time of each keypoint.

    """

    opensim_marker_filtered = os.path.join(curr_trial.dir_trial, curr_trial.opensim_marker_filtered)

    trc = TRCData()
    trc.load(filename=opensim_marker_filtered)

    # trc["Body Part"][INDEX][0:X, 1:Y, 2:Z]
    # trc[timeframe][0: Timestamp, 1:Line_data][1:CHip, 1: RHip, 2: LHip]

    list_columns = ["Frame#", "Time", *trc["Markers"]]

    df_vel = pd.DataFrame(columns=list_columns)

    df_vel["Frame#"] = trc["Frame#"]
    df_vel["Time"] = trc["Time"]

    df_acc = df_vel.copy(deep=True)

    for component in trc["Markers"]:

        # Calculate gradient for each component and write it to DataFrame
        comp_array = np.array(trc[component])
        comp_array[:, ] = np.gradient(comp_array, axis=0)

        # Calculate overall gradient of all three axes - comp_array[0:X, 1:Y, 2:Z]
        grad_arr = np.sqrt((comp_array ** 2).sum(axis=1))

        # write to Dataframe
        df_vel[component] = grad_arr * 10
        df_acc[component] = np.gradient(grad_arr, axis=0)

    if save_file:
        # Save velocity data to .csv file in Analyze Results folder

        if not os.path.exists(curr_trial.dir_kin_trc):
            os.makedirs(curr_trial.dir_kin_trc)

        filepath = os.path.join(curr_trial.dir_kin_trc, f"{curr_trial.get_filename()}_keypoint_vel.csv")
        df_vel.to_csv(filepath, index=False)

        # Save acceleration data to .csv file in Analyze Results folder
        filepath = os.path.join(curr_trial.dir_kin_trc, f"{curr_trial.get_filename()}_keypoint_acc.csv")
        df_acc.to_csv(filepath, index=False)

    return df_vel, df_acc


def calculate_bodykin_vel_acc(curr_trial, save_file=True, DEBUG=False):
    """
    Uses the Output of the Body Kinematics from Pose2Sim and their first and second derivateve (gradient) to get valocity and acceleration

    Input:
        - save_file: Determines whether the files .csv files should be written.

    Output:
        - df_vel: DataFrame with Velocity data
        - df_acc: DataFrame with Acceleration data
        - .csv files written in Analyze folder
    """

    path_df_pos = curr_trial.find_file(curr_trial.dir_kin_p2s, ".csv", flag="p2s_pos")
    df_pos = pd.read_csv(path_df_pos)

    nframes = df_pos.index.to_numpy()
    try:
        time = df_pos["# times"]
        df_pos.drop(columns=["# times"], inplace=True)
    except:
        # If this .csv File ha already been changed, we have to take out "Frame#" and "Time"
        time = df_pos["Time"]
        df_pos.drop(columns=["Frame#", "Time"], inplace=True)

    df_pos.columns = sorted(set(np.char.strip(list(df_pos.columns), chars=" ")))

    df_vel = pd.DataFrame.from_dict({"Frame#": nframes,
                                     "Time": time})
    df_acc = pd.DataFrame.from_dict({"Frame#": nframes,
                                     "Time": time})

    for i in range(0, int(len(df_pos.columns)), 3):
        if DEBUG:
            print(df_pos.columns[i])
            print(df_pos.columns[i + 1])
            print(df_pos.columns[i + 2])

        vel = np.gradient(df_pos.iloc[:, [i, i + 1, i + 2]], axis=0)
        acc = np.gradient(vel, axis=0)

        vel = np.sqrt((vel ** 2).sum(axis=1))
        acc = np.sqrt((acc ** 2).sum(axis=1))
        part = df_pos.columns[i].strip(" _xyz")

        df_vel[part] = vel
        df_acc[part] = acc

    df_pos.insert(0, "Frame#", nframes)
    df_pos.insert(1, "Time", time)

    if save_file:
        # Save position ata with new column names to original location.
        df_pos.to_csv(path_df_pos, index=False)

        # Save velocity data to .csv file in Analyze Results folder
        filepath = os.path.join(curr_trial.dir_kin_p2s, f"{curr_trial.get_filename()}_Body_kin_p2s_vel.csv")
        df_vel.to_csv(filepath, index=False)

        # Save acceleration data to .csv file in Analyze Results folder
        filepath = os.path.join(curr_trial.dir_kin_p2s, f"{curr_trial.get_filename()}_Body_kin_p2s_acc.csv")
        df_acc.to_csv(filepath, index=False)

    return df_pos, df_vel, df_acc


def get_phase_timeframe(curr_trial, save_file=True):
    """
    Use a list of phases assigned to indices and a list of time stamps assigned to indices returns a list of phases with the correspoding needed time.

    Input:
        - curr_trial: The current trial

    Output:
        - df: DatFrame containing all phases, their start_Index and their end Index.
    """

    phases = curr_trial.opensim_ik["phase"]
    time = curr_trial.opensim_ik["time"]

    df = pd.DataFrame(
        columns=["phase", "phase Percentage", "needed_time", "start_time", "end_time", "start_frame", "end_frame"])

    # Setting starting conditions for first phase
    curr_phase = phases[0]
    id_start = 0
    t_start = 0
    for i in range(phases.shape[0]):
        if phases[i] != curr_phase:
            id_end = i - 1
            t_end = time.iloc[i - 1]
            passed_time = t_end - t_start
            phase_perc = round(time.iloc[-1] / passed_time, 2)
            df.loc[len(df)] = [curr_phase, phase_perc, passed_time, t_start, t_end, id_start, id_end]
            curr_phase = phases.iloc[i]
            id_start = i
            t_start = time.iloc[i]
    curr_trial.mov_phases_timeframe = df

    if save_file:
        df.to_csv(os.path.join(curr_trial.path_mov_phases_timeframe), index=False)

def get_outer_local_minima(data, peak_id_left, peak_id_right):
    """
    Calculate outer left and right local Minima between two peaks.

    Input:
        - data: Data to search the minima on.
        - peak_id_left: index of left peak
        - peak_id_right: index of right Peak

    Output:
        - List containing IDs of left and right minima
        - List containing Values of left and right minima
    """

    from scipy.signal import argrelextrema

    # Get Indices of local minima
    ID_loc_min = argrelextrema(data[peak_id_left: peak_id_right],
                               np.less, order=3)[0] + peak_id_left

    max_dist = max(data)
    l_min = data[ID_loc_min[0]]
    r_min = data[ID_loc_min[-1]]

    # Return Ids of left and right minima and their corresponding values.
    return [l_min, r_min], [ID_loc_min[0], ID_loc_min[-1]]


def get_phases_idrink(curr_trial, output_file=None, plot_plots=False):
    """
    Input:
        - curr_trial: current trial object

    Groups the Movement into 5 Phases and adds them to the recording .csv. The function can be extended to group the Movement into 7 phases.

    It either uses keypoint velocities that were calculated based on .trc files or the Body-Kinematics .sto from opensim.

    The 5 Phases are:
        - Not started
        - Reaching (Includes grasping)
        - Forward Transportation (glass to mouth)
        - Drinking
        - Back Transport (glass to table, includes release of grasp)
        - Returning (back to initial position)
        - Done

    The 7 Phases are:
        - Not started
        - Reaching
        - grasping
        - Forward Transportation (glass to mouth)
        - Drinking
        - Back Transport (glass to table)
        - release of grasp
        - Returning (back to initial position)
        - Done

    It is loosely based on the Methods used by Margit Alt Murphys publications "Three-dimensional kinematic motion analysis of a daily activity
    drinking from a glass: a pilot study" (doi:10.1186/1743-0003-3-18) and "Kinematic Analysis Using 3D Motion Capture of Drinking Task in People With
    and Without Upper-extremity Impairments" (doi:10.3791/57228)
    """

    def go_hiking(phase_list, hand_vel, phases, phase_transition_threshold, start_phase_id, curr_phase, starting_point,
                  destination, peak_id, go_left, go_up):
        """
        Input:
            - phase_list: List containing the movement Data



        Output:
            - phase_list: With added phase
            - start_phase_id: with added starting ID for current phase
            - curr_phase: Incremented curr_phase
        Walks from Valley or Peak of a graph.
        The Function finds the point at which a Threshold is passed and, saves the Id at which it happens, writes the phase
        to the curr_trial.opensim_ik DatFrame and increments the current phase.
        """

        if go_left:
            # We go left
            direction = -1
            phase_transition_threshold = phase_transition_threshold[0]
            destination_id = destination[peak_id] -1
        else:
            # We go right
            direction = 1
            phase_transition_threshold = phase_transition_threshold[1]
            destination_id = destination[peak_id] + 1

        if go_up:
            for i in range(starting_point[peak_id], destination_id, direction):
                if hand_vel[i] >= phase_transition_threshold[peak_id]:  # When the velocity has increases according to the phase threshold
                    start_phase_id[curr_phase + 1] = i  # Setting start of phase 1 - Reaching
                    phase_list.loc[curr_phase:i - 1] = phases[curr_phase]  # Writing phase 0 to DataFrame

                    curr_phase += 1
                    return phase_list, start_phase_id, curr_phase
        else:
            for i in range(starting_point[peak_id], destination_id, direction):
                if hand_vel[i] <= phase_transition_threshold[peak_id]:
                    start_phase_id[curr_phase + 1] = i  # Setting start of phase 2 - Forward Transportation
                    phase_list.loc[start_phase_id[curr_phase]:start_phase_id[curr_phase + 1] - 1] = phases[curr_phase]

                    curr_phase += 1
                    return phase_list, start_phase_id, curr_phase

    from scipy.signal import find_peaks

    if curr_trial.extended:
        phases = {
            0: "not_started",
            1: "reaching",
            2: "grasping",
            3: "forward_transportation",
            4: "drinking",
            5: "back_transport",
            6: "release_of_grasp",
            7: "returning",
            8: "done"
        }
    else:
        phases = {
            0: "not_started",
            1: "reaching",
            2: "forward_transportation",
            3: "drinking",
            4: "back_transport",
            5: "returning",
            6: "done"
        }

    side = curr_trial.measured_side[0]
    ik_out = curr_trial.opensim_ik

    """
    I added curr_trial.use_torso because the distance between the hand and the head using the OpenSim AnalyzerTool caused som issues because the distance is not properly measured.
    The Cause is most likely mixup of the X, Y, and Z axis.
    """

    curr_trial.opensim_ik["phase"] = "None"

    if curr_trial.marker_source == "trc":
        vel_hand = np.array(curr_trial.marker_vel[f"{side.upper()}Wrist"])  # .trc file
    elif curr_trial.marker_source == "p2s":
        vel_hand = np.array(curr_trial.marker_vel[f"hand_{side.lower()}"])  # p2s file
    elif curr_trial.marker_source == "anatool":
        vel_hand = np.sqrt(curr_trial.marker_vel[f"hand_{side.lower()}_X"] ** 2 + curr_trial.marker_vel[
            f"hand_{side.lower()}_Y"] ** 2 + curr_trial.marker_vel[f"hand_{side.lower()}_Z"] ** 2)

    """
    The Position between Face and the used Hand will only be used to determine the drinking phase.
    If no positional Data is given, the drinking phase will be determined based on the velocity of the hand.
    """

    if curr_trial.use_dist_handface:
        faceref = 'face'
        if curr_trial.use_torso:
            faceref = "torso"

        if curr_trial.marker_source == "trc":
            pos_hand = curr_trial.marker_pos.loc[:,
                       [f"{side.upper()}Wrist_X", f"{side.upper()}Wrist_Y", f"{side.upper()}Wrist_Z"]].rename(
                columns={f"{side.upper()}Wrist_X": "X", f"{side.upper()}Wrist_Y": "Y", f"{side.upper()}Wrist_Z": "Z"})
            pos_face = curr_trial.marker_pos.loc[:, [f"Nose_X", f"Nose_Y", f"Nose_Z"]].rename(
                columns={"Nose_X": "X", "Nose_Y": "Y", "Nose_Z": "Z"})
        elif curr_trial.marker_source == "p2s":
            if curr_trial.use_torso:
                face_ref = "torso"
            else:
                face_ref = "head"

            pos_hand = curr_trial.marker_pos.loc[:,
                       [f"hand_{side.lower()}_x", f"hand_{side.lower()}_y", f"hand_{side.lower()}_z"]].rename(
                columns={f"hand_{side.lower()}_x": "X", f"hand_{side.lower()}_y": "Y", f"hand_{side.lower()}_z": "Z"})
            pos_face = curr_trial.marker_pos.loc[:, [f"{face_ref}_x", f"{face_ref}_y", f"{face_ref}_z"]].rename(
                columns={f"{face_ref}_x": "X", f"{face_ref}_y": "Y", f"{face_ref}_z": "Z"})

        elif curr_trial.marker_source == "anatool":
            if curr_trial.use_torso:
                face_ref = "torso"
            else:
                face_ref = "head"

            pos_hand = curr_trial.marker_pos.loc[:,
                       [f"hand_{side.lower()}_X", f"hand_{side.lower()}_Y", f"hand_{side.lower()}_Z"]].rename(
                columns={f"hand_{side.lower()}_X": "X", f"hand_{side.lower()}_Y": "Y", f"hand_{side.lower()}_Z": "Z"})
            pos_face = curr_trial.marker_pos.loc[:, [f"{face_ref}_X", f"{face_ref}_Y", f"{face_ref}_Z"]].rename(
                columns={f"{face_ref}_X": "X", f"{face_ref}_Y": "Y", f"{face_ref}_Z": "Z"})

    # Smooth the velocity by a given factor
    """freq = ik_out.shape[0] / ik_out.loc[ik_out.shape[0] - 1, "time"]
    smoothing_factor = freq / curr_trial.smoothing_divisor_vel
    window = np.ones(int(smoothing_factor)) / (int(smoothing_factor))
    if curr_trial.smooth_velocity:
        vel_hand = np.convolve(vel_hand, window, "same")"""

    if curr_trial.smooth_velocity:
        vel_hand = smooth_timeseries(curr_trial, vel_hand, factor=curr_trial.smoothing_divisor_vel)
        #vel_hand = use_butterworth_filter(curr_trial, vel_hand, cutoff=curr_trial.butterworth_cutoff, fs=curr_trial.frame_rate, order=curr_trial.butterworth_order)

    # Find Peaks and Bases in vel_hand Signal
    prom_fac = 2
    while True:
        # prom = np.power(min(vel_hand) + max(vel_hand), prom_fac)
        prom = (min(vel_hand) + max(vel_hand)) / prom_fac
        # TODO: Find proper value for prom. Should find all Peaks even if Value start relatively high
        hand_vel_peaks, hand_vel_peaks_prop = find_peaks(vel_hand, prominence=prom, wlen=ik_out.shape[0] / 3)

        prom_fac += 1

        if len(hand_vel_peaks) >= 4:
            break

    if plot_plots:
        plt.plot(vel_hand)
        plt.plot(hand_vel_peaks, vel_hand[hand_vel_peaks], "x")
        plt.plot(hand_vel_peaks_prop["left_bases"], vel_hand[hand_vel_peaks_prop["left_bases"]], "x", color="red")
        plt.plot(hand_vel_peaks_prop["right_bases"], vel_hand[hand_vel_peaks_prop["right_bases"]], "x", color='green')
        plt.vlines(x=hand_vel_peaks, ymin=vel_hand[hand_vel_peaks] - hand_vel_peaks_prop["prominences"],
                   ymax=vel_hand[hand_vel_peaks], colors="green", linestyles="--")
        plt.plot(np.zeros_like(vel_hand), "--", color="gray")
        plt.close()

    phase_transition_threshold_left = vel_hand[hand_vel_peaks_prop["left_bases"]] + hand_vel_peaks_prop[
        "prominences"] * curr_trial.phase_thresh_vel
    phase_transition_threshold_right = vel_hand[hand_vel_peaks_prop["right_bases"]] + hand_vel_peaks_prop[
        "prominences"] * curr_trial.phase_thresh_vel
    phase_transition_threshold = [phase_transition_threshold_left,
                                  phase_transition_threshold_right]  # [0]: left, [1]: right

    curr_phase = 0

    # 6 IDs. if Extended: 8 IDs
    start_phase_id = np.zeros(len(phases.keys()))

    # Phase 0 always starts at 0
    # If Movement started before recording, set start of phase 1 at index 0
    start_phase_id[1] = 0

    # Start from the first peak and go left.
    # If the Velocity of the hand decreases beyond the threshold,
    # that is the starting point of Phase one - Reaching
    ik_out["phase"], start_phase_id, curr_phase = (
        go_hiking(ik_out["phase"], vel_hand, phases, phase_transition_threshold,
                  start_phase_id, curr_phase,
                  hand_vel_peaks, hand_vel_peaks_prop["left_bases"],
                  peak_id=0, go_left=True, go_up=False))

    if curr_trial.extended:
        # Start from the first peak and go right.
        # If the Velocity of the hand decreases beyond the threshold,
        # that is the starting point of Phase Two - Grasping
        ik_out["phase"], start_phase_id, curr_phase = (
            go_hiking(ik_out["phase"], vel_hand, phases, phase_transition_threshold,
                      start_phase_id, curr_phase,
                      hand_vel_peaks, hand_vel_peaks_prop["right_bases"],
                      peak_id=0, go_left=False, go_up=False))

    # Start from the second peak and go left.
    # If the Velocity of the hand decreases beyond the threshold,
    # that is the starting point of Phase two - Forward Transportation (if extended: Phase three)
    ik_out["phase"], start_phase_id, curr_phase = (
        go_hiking(ik_out["phase"], vel_hand, phases, phase_transition_threshold,
                  start_phase_id, curr_phase,
                  starting_point=hand_vel_peaks, destination=hand_vel_peaks_prop["left_bases"],
                  peak_id=1, go_left=True, go_up=False))

    if curr_trial.use_dist_handface:
        dist_hand_face = np.linalg.norm(pos_hand - pos_face, axis=1)
        if curr_trial.smooth_distance:
            """smoothing_factor = freq / curr_trial.smoothing_divisor_vel
            window = np.ones(int(smoothing_factor)) / (int(smoothing_factor))
            dist_hand_face = np.convolve(dist_hand_face, window, "same")"""
            #dist_hand_face = smooth_timeseries(curr_trial, dist_hand_face, factor=curr_trial.smoothing_divisor_vel)
            dist_hand_face = use_butterworth_filter(dist_hand_face, cutoff=curr_trial.butterworth_cutoff, fs=curr_trial.frame_rate, order=curr_trial.butterworth_order )

        max_dist = max(dist_hand_face)
        min_dist_ID = dist_hand_face.argmin()

        # Find Peaks and Bases in vel_hand Signal
        prom_fac = 2
        while True:
            # prom = np.power(min(vel_hand) + max(vel_hand), prom_fac)
            prom = (min(dist_hand_face) + max(
                dist_hand_face)) / prom_fac  # TODO: Find proper value for prom. Should find all Peaks even if Value start relatively high
            dist_hf_peaks, dist_hf_peaks_prop = find_peaks(dist_hand_face, prominence=prom, wlen=ik_out.shape[0] / 2)

            prom_fac += 1

            if len(dist_hf_peaks) >= 2:
                break

        """
        Older version, 2 outer Minima were used. THis lead to issues with the way, the local minima were calculated.
        minima, minima_idx = get_outer_local_minima(dist_hand_face, dist_hf_peaks[0], dist_hf_peaks[-1])
        dist_thresh = [minima[0] + max_dist * curr_trial.phase_thresh_pos, minima[1] + max_dist * curr_trial.phase_thresh_pos]"""

        dist_thresh = [dist_hand_face[min_dist_ID] + dist_hand_face[dist_hf_peaks[0]] * curr_trial.phase_thresh_pos,
                       dist_hand_face[min_dist_ID] + dist_hand_face[dist_hf_peaks[-1]] * curr_trial.phase_thresh_pos]

        for i in range(min_dist_ID, dist_hf_peaks[0], -1):
            if dist_hand_face[i] >= dist_thresh[0]:
                start_phase_id[curr_phase + 1] = i  # Setting start of phase 2 - Forward Transportation
                ik_out.loc[start_phase_id[curr_phase]:start_phase_id[curr_phase + 1] - 1, "phase"] = phases[curr_phase]

                curr_phase += 1
                break

        for i in range(min_dist_ID, dist_hf_peaks[-1]):
            if dist_hand_face[i] >= dist_thresh[1]:
                start_phase_id[curr_phase + 1] = i  # Setting start of phase 2 - Forward Transportation
                ik_out.loc[start_phase_id[curr_phase]:start_phase_id[curr_phase + 1] - 1, "phase"] = phases[curr_phase]
                curr_phase += 1
                break

        if plot_plots:
            plt.plot(dist_hand_face, c='b')


            if curr_trial.marker_source == "trc":
                plt.title(f"Distance of hand to {faceref}\ncalculated using 3D-keypoints", fontsize=20, weight='bold')
            elif curr_trial.marker_source == "p2s":
                plt.title(f"Distance of hand to {faceref}\ncalculated by Pose2Sim", fontsize=20, weight='bold')
            elif curr_trial.marker_source == "anatool":
                plt.title(f"Distance of hand to {faceref}\ncalculated using Opensim AnalyzerTool", fontsize=20, weight='bold')
            plt.ylabel("Distance (m)", fontsize=14)
            plt.xlabel("Frame of recording (60 fps)", fontsize=14)
            dist_range = max(dist_hand_face) - min(dist_hand_face)
            # Define a suitable step size. For example, you can divide the range by 10 to get 10 ticks.
            step = round(dist_range / 10, 2)
            # Now, use these values to set the y-ticks
            try:
                plt.yticks(np.arange(0, max(dist_hand_face), step))
            except:
                pass
            plt.plot(np.zeros_like(dist_hand_face), "--", color="gray")
            plt.savefig(os.path.join(curr_trial.dir_murphy_measures,
                                     f"{curr_trial.identifier}{curr_trial.filenename_appendix}.png"),
                        bbox_inches='tight')
            plt.close()

            print("Stop")

    else:

        # Start from the second peak and go right.
        # If the Velocity of the hand decreases beyond the threshold,
        # that is the starting point of Phase three - Drinking (if extended: Phase four)
        ik_out["phase"], start_phase_id, curr_phase = (
            go_hiking(ik_out["phase"], vel_hand, phases, phase_transition_threshold,
                      start_phase_id, curr_phase,
                      starting_point=hand_vel_peaks, destination=hand_vel_peaks_prop["right_bases"],
                      peak_id=1, go_left=False, go_up=False))

        # Start from the third peak and go left.
        # If the Velocity of the hand decreases beyond the threshold,
        # that is the starting point of Phase four - back Transportation (if extended: Phase five)
        ik_out["phase"], start_phase_id, curr_phase = (
            go_hiking(ik_out["phase"], vel_hand, phases, phase_transition_threshold,
                      start_phase_id, curr_phase,
                      starting_point=hand_vel_peaks, destination=hand_vel_peaks_prop["left_bases"],
                      peak_id=2, go_left=True, go_up=False))

    if curr_trial.extended:
        # Start from the third peak and go right.
        # If the Velocity of the hand decreases beyond the threshold,
        # that is the starting point of Phase six - Putting down Cup
        ik_out["phase"], start_phase_id, curr_phase = (
            go_hiking(ik_out["phase"], vel_hand, phases, phase_transition_threshold,
                      start_phase_id, curr_phase,
                      starting_point=hand_vel_peaks, destination=hand_vel_peaks_prop["right_bases"],
                      peak_id=2, go_left=False, go_up=False))

    # Start from the fourth peak and go left.
    # If the Velocity of the hand decreases beyond the threshold,
    # that is the starting point of Phase five - Returning (if extended: Phase seven)
    ik_out["phase"], start_phase_id, curr_phase = (
        go_hiking(ik_out["phase"], vel_hand, phases, phase_transition_threshold,
                  start_phase_id, curr_phase,
                  starting_point=hand_vel_peaks, destination=hand_vel_peaks_prop["left_bases"],
                  peak_id=3, go_left=True, go_up=False))

    # Start from the fourth peak and go right.
    # If the Velocity of the hand decreases beyond the threshold,
    # that is the starting point of Phase six - Done (if extended: Phase eight)
    ik_out["phase"], start_phase_id, curr_phase = (
        go_hiking(ik_out["phase"], vel_hand, phases, phase_transition_threshold,
                  start_phase_id, curr_phase,
                  starting_point=hand_vel_peaks, destination=hand_vel_peaks_prop["right_bases"],
                  peak_id=3, go_left=False, go_up=False))

    # Add phase six - Done (if extended: phase eight) to DataFrame.
    if start_phase_id[curr_phase] > 0:  # if startID for phase "Done" is bigger than 0, the it was set during hiking
        ik_out.loc[start_phase_id[curr_phase]:ik_out.shape[0], "phase"] = phases[curr_phase]

    if plot_plots:
        plt.plot(vel_hand, c='b')

        """plt.plot(hand_vel_peaks, vel_hand[hand_vel_peaks], "x", "")
        plt.plot(hand_vel_peaks_prop["left_bases"], vel_hand[hand_vel_peaks_prop["left_bases"]], "x")
        plt.plot(hand_vel_peaks_prop["right_bases"], vel_hand[hand_vel_peaks_prop["right_bases"]], "x")
        plt.vlines(x=hand_vel_peaks, ymin=vel_hand[hand_vel_peaks] - hand_vel_peaks_prop["prominences"],
                   ymax=vel_hand[hand_vel_peaks], colors="green", linestyles="--")"""
        appendix=''
        if curr_trial.use_dist_handface:
            appendix = f"\nand distance of hand to {faceref}"

        if curr_trial.affected:
            app_aff = "affected"
        else:
            app_aff = "unaffected"

        if curr_trial.marker_source == "trc":
            plt.title(f"Phase detection using\nendpoint velocity of 3D-keypoints{appendix}\n{app_aff}", fontsize=20, weight='bold')
        elif curr_trial.marker_source == "p2s":
            plt.title(f"Phase detection using\nendpoint velocity by Pose2Sim{appendix}\n{app_aff}", fontsize=20, weight='bold')
        elif curr_trial.marker_source == "anatool":
            plt.title(f"Phase detection using\nendpoint velocity by Opensim AnalyzerTool{appendix}\n{app_aff}", fontsize=20, weight='bold')

        plt.ylabel("Velocity (m/s)", fontsize=14)
        plt.xlabel("Frame of recording (60 fps)", fontsize=14)

        vel_range = max(vel_hand) - min(vel_hand)
        # Define a suitable step size. For example, you can divide the range by 10 to get 10 ticks.
        step = round(vel_range / 10, 2)
        # Now, use these values to set the y-ticks
        #plt.yticks(np.arange(0, max(vel_hand), step))

        colors = ['red', 'green', 'blue', 'purple', 'orange', 'cyan', 'yellow', 'deeppink', 'black']
        labels = ['not started', 'Reaching', 'Grasping', 'Forward Transportation', 'Drinking', 'Back transportation',
                  'Release of Grasp', 'Returning', 'Done']

        if start_phase_id[1] == 0:
            start_phase_id = np.delete(start_phase_id, 0)
            labels.pop(0)
            colors.remove("yellow")

        for i, phase_start in enumerate(start_phase_id):

            plt.vlines(x=phase_start, ymin=min(vel_hand), ymax=max(vel_hand), colors=colors[i % len(colors)],
                       linestyles='dashed', linewidth=2, label=labels[i % len(labels)])

        #plt.legend(loc='upper right')
        lgd = plt.legend(loc='upper center', bbox_to_anchor=(0.5, -0.15), fancybox=True, shadow=True,
                   ncol=4)  # Adjust the bbox_to_anchor values as needed

        plt.plot(np.zeros_like(vel_hand), "--", color="gray")

        if curr_trial.use_dist_handface:
            plt.savefig(os.path.join(curr_trial.dir_murphy_measures, f"{curr_trial.identifier}{app_aff}{curr_trial.filenename_appendix}_Phase_Detection.png"),
                        bbox_extra_artists=(lgd,), bbox_inches='tight')
        else:
            plt.savefig(os.path.join(curr_trial.dir_murphy_measures, f"{curr_trial.identifier}{app_aff}{curr_trial.filenename_appendix}_Phase_Detection.png"),
                        bbox_extra_artists=(lgd,), bbox_inches='tight')
        plt.close()


    if output_file is not None:
        ik_out.to_csv(output_file, index=False)

    curr_trial.opensim_ik = ik_out

def run_full_analysis(curr_trial):
    """
    This function runs all Analysis functions. It is meant to retrieve all metrics whose calculation is implemented.

    TODO: User should be able to run individual functions.

    Possible Methods:
        - Phase categorization based on marker velocity and joint angle
        - Phase categorization based on:
            - keypoint velocity (Pose2Sim) and joint angles
            - joint angle velocity (Opensim) and joint angle
            - marker velocity (Opensim) and joint angle
            - TODO: add more possible categorization methods - Maybe weighted average of all used measurements
        - TODO: add more analytics e.g., Trunk displacement, smoothness of movement, etc.
    """

    curr_trial.save_all_mov_paths()
    curr_trial.save_all_mov_data()

    if curr_trial.get_mov_data_for_analysis():
        # TODO: Delete murph06, murph18 and murph18_keypoints when get_phases_idrink is finalized
        # calculate_phases_murph06(curr_trial.opensim_ik, curr_trial.joint_vel, dat_vel_marker)
        # calculate_phases_murph18(curr_trial.opensim_ik, curr_trial.joint_vel, dat_acc_angle, dat_vel_marker, dat_acc_marker, dat_pos_marker)
        # calculate_phases_murph18_keypoints(curr_trial.opensim_ik, dat_vel_marker, dat_acc_marker, dat_pos_keypoint, curr_trial.marker_vel)

        # get_phases_idrink_old(curr_trial.opensim_ik, curr_trial.marker_vel, extended=True)

        """
        Test get_phases_idrink with different inputs and settings
        """
        get_phases_idrink(curr_trial, plot_plots=True)
        get_phase_timeframe(curr_trial)

        try:
            get_murphy_measures(curr_trial)
        except:
            import traceback
            print(traceback.format_exc())
            print(f"Murphy Measures could not be calculated.\n"
                  f"Check whether all phases could be calculated in File {curr_trial.path_ep_kin_movement_time}"
                  f"Try increasing the smoothing divisor for endpoint velocity\n")
    else:
        print("Data could not be loaded. Analysis skipped")
