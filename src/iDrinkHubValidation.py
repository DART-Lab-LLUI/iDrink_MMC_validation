import glob
import os
import sys
import time
import re
from tqdm import tqdm

import argparse
import pandas as pd

from iDrink import iDrinkTrial, iDrinkPoseEstimation

from Pose2Sim import Pose2Sim

"""
This File is the starting Point of the iDrink Validation.


It creates all trial objects and then runs the pipeline for each trial and setting.

The pipeline is as follows:

- Pose Estimation
- Pose2Sim
- Opensim
- iDrink Analytics --> Calculation of Murphy Measures

The possible settings are:

- 29 different Camera Setups
- 2 Calibration Methods
- 3 HPE Methods (Openpose, MMPose and Pose2Sim Pose Estimation)
- 2 sets of 2D Keypoints (filtered and unfiltered)
- 4 ways to calculate the Murphy Measures (Analyzer only, Analyzer and keypoints, Opensim Invkin Tool and Analyzer, and Opensim invkin Tool and keypoints)

In Total we have 29 * 2 * 3 * 2 * 4 = 1392 different settings

When creating the trial objects, a csv file is created, which contains all the settings for each trial.
"""

""" The Folder Structure is as explained on this table: https://miro.com/app/board/uXjVKzgWI8c=/"""

# Command-line interface definition 6112qg
parser = argparse.ArgumentParser(description='Extract marker locations from C3D files and save in TRC format.')
parser.add_argument('--mode', metavar='m', default=None,
                    help='"pose_estimation", "pose2sim", "opensim", "murphy_measures", "statistics", or "full"')
parser.add_argument('--poseback', metavar='hpe', type=str, default='mmpose',
                    help='Method for Pose Estimation: "openpose", "mmpose", "pose2sim"')
parser.add_argument('--trial_id', metavar='t_id', type=str, default=None,
                    help='Trial ID if only one single trial should be processed')
parser.add_argument('--patient_id', metavar='p_id', type=str, default=None,
                    help='Patient ID if only one single patient should be processed')
parser.add_argument('--verbose', metavar='v', type=int, default=1,
                    help='Verbosity level: 0, 1, 2 default: 0')
parser.add_argument('--DEBUG', action='store_true', default=False,
                    help='Debug mode')

root_MMC = r"C:\iDrink\Test_folder_structures"  # Root directory of all MMC-Data --> Videos and Openpose json files
root_OMC = r"C:\iDrink\OMC_data_newStruct"  # Root directory of all OMC-Data --> trc of trials.
root_val = r"C:\iDrink\validation_root"  # Root directory of all iDrink Data for the validation --> Contains all the files necessary for Pose2Sim and Opensim and their Output.
root_data = os.path.join(root_val, "03_data")  # Root directory of all iDrink Data for the validation --> Contains all the files necessary for Pose2Sim and Opensim and their Output.
default_dir = os.path.join(root_val, "01_default_files")  # Default Files for the iDrink Validation
df_settings = pd.read_csv(os.path.join(root_val, "validation_settings.csv"), sep=';')

def run_full_pipeline(trial_list, mode):
    """
    Runs the pipeline for the given trial list.

    :param trial_list:
    :return:
    """
    for trial in trial_list:
        print(f"Running Pipeline for {trial.identifier}")
        # Pose Estimation
        if mode == "pose_estimation":
            print("Running Pose Estimation")

def create_trial_objects():
    """
    TODO: Script writes a csv file, that contains information of which steps are done for which trial and setting.

    Creates the trial Objects that will be use in the following Pipelines.

    Depending on the mode, different files will be used to create the objects.

    Cases:
    Pose Estimation: Uses only the video_files
    Pose2Sim: Uses the json files created by Pose estimation. If the folder structure for the Pose2Sim execution is not yet build, the files will be copied into the right structure.
    Opensim: Uses the trc files created by Pose2Sim.
    Murphy Measures: Uses the Opensim files.
    statistics: Checks for all files and creates a csv file with the results.
    full: uses video_files as Pose Estimation does.


    :param:
    :return trial_list: List of Trial Objects
    """
    def trials_from_video():
        """
        Creates the trial objects for the Pose Estimation Pipeline.

        :return:
        """
        if sys.gettrace() is not None:  # If Debugger is in Use, limit settings to first 10
            n_settings = 10
        else:
            n_settings = df_settings["setting_id"].max()

        trials_df = pd.DataFrame(
            columns=["setting_id", "patient_id", "trial_id", "identifier", "affected", "side", "cam_setting",
                     "cams_used", "videos_used", "session_dir", "participant_dir", "trial_dir", "dir_calib"])
        if args.verbose >= 1:
            progress_bar = tqdm(total=n_settings, desc="Creating Trial-DataFrame", unit="Setting")

        if args.mode == "pose_estimation":
            n_settings = 1

        for setting_id in range(1, n_settings+1):
            id_s = f"S{setting_id:03d}"  # get Setting ID for use as Session ID in the Pipeline
            cam_setting = df_settings.loc[df_settings["setting_id"] == setting_id, "cam_setting"].values[0]
            # Check whether Cam is used for Setting
            cams_tuple = eval(df_settings.loc[df_settings["setting_id"] == setting_id, "cams"].values[ 0])  # Get the tuple of cams for the setting


            # Create Setting folder if not yet done
            dir_setting = os.path.join(root_data, f"setting_{setting_id}")
            if not os.path.exists(dir_setting):
                os.makedirs(dir_setting, exist_ok=True)

            for p in os.listdir(root_MMC):
                p_dir = os.path.join(root_MMC, p)
                # Get the patient_id
                id_p = re.search(r'(P\d+)', p_dir).group(1)  # # get Participant ID for use in the Pipeline

                part_dir = os.path.join(dir_setting, id_p)
                if not os.path.exists(part_dir):
                    os.makedirs(part_dir, exist_ok=True)
                dir_session = os.path.join(part_dir, id_s)
                if not os.path.exists(dir_session):
                    os.makedirs(dir_session, exist_ok=True)
                dir_calib = os.path.join(part_dir, f"{id_s}_Calibration")
                if not os.path.exists(dir_calib):
                    os.makedirs(dir_calib, exist_ok=True)
                part_dir = os.path.join(dir_session, f"{id_s}_{id_p}")
                if not os.path.exists(part_dir):
                    os.makedirs(part_dir, exist_ok=True)

                # Make sure, we only iterate over videos, that correspond to the correct camera
                if args.mode == "pose_estimation":  # If mode is pose estimation, use all present cam_folders
                    pattern = r'0-9'
                else:  # use only cams that are in setting
                    pattern = "".join([f"{i}" for i in cams_tuple])

                pattern = re.compile(f'cam[{pattern}]*').pattern
                cam_folders = glob.glob(os.path.join(p_dir, "01_measurement", "04_Video", "03_Cut", "drinking", pattern))

                # Get all video files of patient
                video_files = []
                for cam_folder in cam_folders:
                    video_files.extend(glob.glob(os.path.join(cam_folder, "**", "*.mp4"), recursive=True))

                for video_file in video_files:
                    # Extract trial ID and format it
                    trial_number = int(re.search(r'trial_\d+', video_file).group(0).split('_')[1])
                    id_t = f'T{trial_number:03d}'
                    identifier = f"{id_s}_{id_p}_{id_t}"
                    if args.verbose >=2:
                        print("Creating: ", identifier)

                    trial_dir = os.path.join(part_dir, identifier)
                    if not os.path.exists(trial_dir):
                        os.makedirs(trial_dir, exist_ok=True)



                    if identifier not in trials_df["identifier"].values:
                        # Add new row to dataframe only containing the trial_id
                        identifier = f"{id_s}_{id_p}_{id_t}"
                        new_row = pd.Series({"setting_id": id_s, "patient_id": id_p,"trial_id": id_t, "identifier": identifier, "cams_used": "", "videos_used": ""})
                        trials_df = pd.concat([trials_df, new_row.to_frame().T], ignore_index=True)

                    try:
                        affected = re.search(r'unaffected', video_file).group(0)
                    except:
                        affected = 'affected'

                    side = re.search(r'R|L', video_file).group(0)
                    cam = re.search(r'(cam\d+)', video_file).group(0)


                    if len(trials_df.loc[trials_df["identifier"] == identifier, "cams_used"].values[0]) == 0:
                        trials_df.loc[trials_df["identifier"] == identifier, "cams_used"] = str(re.search(r'\d+', cam).group())
                        trials_df.loc[trials_df["identifier"] == identifier, "videos_used"] = str(video_file)
                    else:
                        trials_df.loc[trials_df["identifier"] == identifier, "cams_used"] = (
                                trials_df.loc[trials_df["identifier"] == identifier, "cams_used"] +
                                ", " + str(re.search(r'\d+', cam).group()))
                        trials_df.loc[trials_df["identifier"] == identifier, "videos_used"] = (
                                trials_df.loc[trials_df["identifier"] == identifier, "videos_used"] +
                                ", " + str(video_file))


                    trials_df.loc[trials_df["identifier"] == identifier, "affected"] = affected
                    trials_df.loc[trials_df["identifier"] == identifier, "side"] = side
                    trials_df.loc[trials_df["identifier"] == identifier, "cam_setting"] = cam_setting

                    trials_df.loc[trials_df["identifier"] == identifier, "session_dir"] = dir_session
                    trials_df.loc[trials_df["identifier"] == identifier, "participant_dir"] = part_dir
                    trials_df.loc[trials_df["identifier"] == identifier, "trial_dir"] = trial_dir
                    trials_df.loc[trials_df["identifier"] == identifier, "dir_calib"] = dir_calib

            if args.verbose >= 1:
                progress_bar.update(1)

        if args.verbose >= 1:
            progress_bar.close()

        if args.verbose >= 1:
            progress_bar = tqdm(total=trials_df["identifier"].shape[0], desc="Creating Trial Objects:",
                                unit="Trial")

        trial_list = []
        for identifier in trials_df["identifier"]:

            if args.verbose >= 2:
                print(f"Setting and Videos for {identifier} are: ", trials_df.loc[trials_df["identifier"] == identifier, "setting_id"].values[0] , trials_df.loc[trials_df["identifier"] == identifier, "videos_used"].values[0])

            # get list from strings of videos and cams
            videos = trials_df.loc[trials_df["identifier"] == identifier, "videos_used"].values[0].split(", ")
            cams = trials_df.loc[trials_df["identifier"] == identifier, "cams_used"].values[0].split(", ")
            affected = trials_df.loc[trials_df["identifier"] == identifier, "affected"].values[0]  # get Participant ID for use in the Pipeline
            side = trials_df.loc[trials_df["identifier"] == identifier, "side"].values[0]  # get Participant ID for use in the Pipeline

            id_s = trials_df.loc[trials_df["identifier"] == identifier, "setting_id"].values[0] # get Setting ID for use as Session ID in the Pipeline
            id_p = trials_df.loc[trials_df["identifier"] == identifier, "patient_id"].values[0]  # get Participant ID for use in the Pipeline
            id_t = trials_df.loc[trials_df["identifier"] == identifier, "trial_id"].values[0]  # get Trial ID for use in the Pipeline

            s_dir = trials_df.loc[trials_df["identifier"] == identifier, "session_dir"].values[0]  # get Session Directory for use in the Pipeline
            p_dir = trials_df.loc[trials_df["identifier"] == identifier, "participant_dir"].values[0]  # get Participant Directory for use in the Pipeline
            t_dir = trials_df.loc[trials_df["identifier"] == identifier, "trial_dir"].values[0]  # get Trial Directory for use in the Pipeline

            # Create the trial object
            trial = iDrinkTrial.Trial(identifier=identifier, id_s=id_s, id_p=id_p, id_t=id_t,
                                      dir_root=root_data, dir_default=default_dir,
                                      dir_trial=t_dir, dir_participant=p_dir, dir_session=s_dir,
                                      affected=affected, measured_side=side,
                                      video_files=videos, used_cams=cams,
                                      used_framework=args.poseback, pose_model="Coco17_UpperBody")
            trial.create_trial()
            trial.load_configuration()

            trial.config_dict["pose"]["videos"] = videos
            trial.config_dict["pose"]["cams"] = cams

            trial.config_dict.get("project").update({"project_dir": trial.dir_trial})
            trial.config_dict['pose']['pose_framework'] = trial.used_framework
            trial.config_dict['pose']['pose_model'] = trial.pose_model

            trial.save_condiguration()

            trial_list.append(trial)

            if args.verbose >= 1:
                progress_bar.update(1)
        if args.verbose >= 1:
            progress_bar.close()

        # Run the pipeline
        return trial_list

    def trials_from_json():
        pass

    def trials_from_p2s():
        pass

    def trials_from_opensim():
        pass

    def trials_from_murphy():
        pass

    def trials_from_csv():
        pass

    match args.mode:
        case "pose_estimation":
            print("creating trial objects for Pose Estimation")
            trial_list = trials_from_video()
            return trial_list


        case "pose2sim":
            print("creating trial objects for Pose2Sim")
            from Pose2Sim import Pose2Sim


        case "opensim":
            print("creating trial objects for Opensim")

        case "murphy_measures":
            print("creating trial objects for Murphy Measures")

        case "statistics":
            print("creating trial objects for Statistics")

        case "full":
            print("creating trial objects for Full Pipeline")
        case _:
            print("No Mode was given. Please specify a mode.")
            sys.exit(1)



    # Get all video files
    video_files = glob.glob(os.path.join(root_MMC, "**", "*.mp4"), recursive=True)
    # Get all json files
    json_files = glob.glob(os.path.join(root_MMC, "**", "*.json"), recursive=True)
    # Get all trc files
    trc_files = glob.glob(os.path.join(root_OMC, "**", "*.trc"), recursive=True)

    """# Create the trial objects
    for video_file in video_files:
        # Get the trial_id
        trial_id = os.path.basename(video_file).split("_")[0]

        # Get the patient_id
        patient_id = os.path.basename(os.path.dirname(video_file))

        # Get the json file
        json_file = [j for j in json_files if trial_id in j and patient_id in j]

        # Get the trc file
        trc_file = [t for t in trc_files if trial_id in t and patient_id in t]

        # Create the trial object
        trial = Trial(trial_id, patient_id, video_file, json_file, trc_file)

        # Run the pipeline
        trial.run_pipeline(mode)"""



def run_mode():
    """
    Runs the pipeline for given mode.

    :param:
    :return:
    """
    # First create list of trials to iterate through
    trial_list = create_trial_objects()

    match args.mode:
        case "pose_estimation":  # Runs only the Pose Estimation
            print("Pose Estimaton Method: ", args.poseback)

            match args.poseback:
                case "openpose":
                    print("Running Openpose")
                    #trial_list = create_trial_objects(mode)
                    raise NotImplementedError("Openpose is not yet implemented")


                case "mmpose":
                    print("Pose Estimation mode: MMPose starting.")
                    for trial in trial_list:
                        if args.verbose >= 1:
                            print(f"starting Pose Estimation for: {trial.identifier}")

                        iDrinkPoseEstimation.validation_pose_estimation_2d(trial, root_val, writevideofiles=True,
                                                                           filter_2d=False, DEBUG=False)

                        # TODO: Implement kp filtering by using the existing 2d keypoints
                        """iDrinkPoseEstimation.validation_pose_estimation_2d(curr_trial, root_data, writevideofiles=False,
                                                                           filter_2d=True, DEBUG=False)"""

                case "pose2sim":
                    print("Pose Estimation mode: Pose2Sim starting.")
                    for trial in trial_list:
                        # Change the config_dict so that the correct pose model is used

                        if trial.pose_model == "Coco17_UpperBody":
                            trial.config_dict['pose']['pose_model'] = 'COCO_17'
                        Pose2Sim.poseEstimation(trial.config_dict)

                        trial.config_dict['pose']['pose_model'] = trial.pose_model




                case _:  # If no mode is given
                    print("Invalid Mode was given. Please specify a valid mode.")
                    sys.exit(1)


        case "pose2sim":  # Runs only the Pose2Sim
            print("Johann, take this out")

        case "opensim":  # Runs only Opensim
            print("Johann, take this out")

        case "murphy_measures":  # runs only the calculation of murphy measures
            print("Johann, take this out")

        case "statistics":  # runs only the statistic script
            print("Johann, take this out")

        case "full":  # runs the full pipeline
            print("Johann, take this out")

        case _:  # If no mode is given
            raise ValueError("Invalid Mode was given. Please specify a valid mode.")
            sys.exit(1)



if __name__ == '__main__':
    # Parse command line arguments
    args = parser.parse_args()

    if args.DEBUG or sys.gettrace() is not None:
        print("Debug Mode is activated\n"
              "Starting debugging script.")
        args.mode = 'pose_estimation'
        args.poseback = 'mmpose'





    if args.mode is not None:
        print("Starting with Mode: ", args.mode)
        run_mode()
    else:
        print("No Mode was given. Please specify a mode.")
        sys.exit(1)