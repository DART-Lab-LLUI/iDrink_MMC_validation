"""
We count the amount of trials in the validation trials csv and then look for each stage how many Trials were lost after
Pose2Sim and Opensim

Then we count the Trials in the outlier csv and finally report the number for each Participant and Setting (SXXX_PXX)
for analysis.

"""
import os
import sys
import glob
from os import write

from PIL.ImageOps import scale
from tqdm import tqdm
import pandas as pd
import numpy as np
import ast

sys.path.append(os.path.realpath(os.path.join(os.path.dirname(__file__), "..")))
from iDrink import iDrinkUtilities
from iDrink.iDrinkUtilities import get_title_measure_name, get_unit, get_cad, get_setting_axis_name

drive = iDrinkUtilities.get_drivepath()

root_iDrink = os.path.join(drive, 'iDrink')
root_val = os.path.join(root_iDrink, "validation_root")
root_stat = os.path.join(root_val, '04_Statistics')
root_omc = os.path.join(root_val, '03_data', 'OMC_new', 'S15133')
root_data = os.path.join(root_val, "03_data")
root_logs = os.path.join(root_val, "05_logs")

csv_val_trials = os.path.join(root_logs, 'validation_trials.csv')
df_val_trials = pd.read_csv(csv_val_trials, sep=';')

csv_settings = os.path.join(root_logs, 'validation_settings.csv')
df_settings = pd.read_csv(csv_settings, sep=';')

csv_calib_error = os.path.join(root_logs, 'calib_errors.csv')
df_calib_error = pd.read_csv(csv_calib_error, sep=';')

csv_murphy = os.path.join(root_stat, '02_categorical', 'murphy_measures.csv')
df_murphy = pd.read_csv(csv_murphy, sep=';')

df_failed_trials = None

list_identifier = sorted(df_val_trials['identifier'].tolist())

csv_failed_trials = os.path.join(root_stat, '04_failed_trials', 'failed_trials.csv')

ignore_id_p = ['P11', 'P19']
idx_s_singlecam_full = ['S017', 'S018', 'S019', 'S020', 'S021', 'S022', 'S023', 'S024', 'S025', 'S026']
idx_s_singlecam = ['S017', 'S018']
idx_s_multicam = ['S001', 'S002', 'S003', 'S004', 'S005', 'S006', 'S007', 'S008', 'S009', 'S010', 'S011', 'S012', 'S013', 'S014', 'S015', 'S016']
idx_s_multicam_reduced = ['S001', 'S002']
idx_s_reduced = idx_s_multicam_reduced + idx_s_singlecam
idx_s_full = idx_s_multicam + idx_s_singlecam

def get_calib_error(id_p, id_t, used_cams, df_error):
    """
    Get the calibration error for the given trial
    """

    calib_error = -1

    cam_str = ', '.join(used_cams)

    df_error_reduced = df_error.loc[(df_error['id_p'] == id_p) & (df_error['cam_used'] == cam_str)]

    if len(df_error_reduced) == 0:
        print(f"Calibration Error for {id_p}_{id_t} and {cam_str} not found")
        return calib_error

    calib_error = df_error_reduced['error'].values[0]

    return calib_error

def check_if_HPE_done(used_cams, id_p, id_t, hpe_model, filtered, verbose=1):
    """
    Check if the HPE was done for the given trial
    """

    filt = '02_filtered' if filtered == 'filtered' else '01_unfiltered'

    trial_int = int(id_t.split('T')[1])

    for cam in used_cams:
        if  len(used_cams) == 1: # TODO: Debug Single Cam
            files = glob.glob(os.path.join(root_val, '02_pose_estimation', filt, id_p, f'{id_p}_{cam}',
                                           hpe_model, 'single-cam', f'{id_p}_{id_t}_*.trc'))
        else:
            files = glob.glob(os.path.join(root_val, '02_pose_estimation', filt, id_p, f'{id_p}_{cam}',
                                           hpe_model, f'trial_{trial_int}_*', f'trial_{trial_int}_*.zip'))
        if len(files) == 0:
            if verbose >= 2:
                print(f"Pose Estimation for {id_p}_{id_t} not done for {cam}")
            return 0

    return 1

def check_if_pose2sim_done(id_s, id_p, id_t, verbose=1):
    """
    Check if the Pose2Sim was done for the given trial
    """

    setting = f'setting_{id_s.split("S")[1]}'

    files = glob.glob(os.path.join(root_val, '03_data', setting, id_p, id_s, f'{id_s}_{id_p}', f'{id_s}_{id_p}_{id_t}',
                                   'pose-3d', f'{id_s}_{id_p}_{id_t}_*.trc'))

    if len(files) == 0:
        if verbose >= 2:
            print(f"Pose2Sim for {id_s}_{id_p}_{id_t} not done")
        return 0

    return 1

def check_if_opensim_done(id_s, id_p, id_t, verbose=1):
    """
    Check if the OpenSim was done for the given trial
    """

    setting = f'setting_{id_s.split("S")[1]}'

    files = glob.glob(os.path.join(root_val, '03_data', setting, id_p, id_s, f'{id_s}_{id_p}', f'{id_s}_{id_p}_{id_t}',
                                   'movement_analysis', 'kin_opensim_analyzetool',  f'{id_s}_{id_p}_{id_t}_*Vec3.sto'))

    if len(files) == 0:
        if verbose >= 2:
            print(f"OpenSim for {id_s}_{id_p}_{id_t} not done")
        reason = 'Vec3.sto not found in movement_analysis\\kin_opensim_analyzetool'
        return 0, reason

    files = glob.glob(os.path.join(root_val, '03_data', setting, id_p, id_s, f'{id_s}_{id_p}', f'{id_s}_{id_p}_{id_t}',
                                   'movement_analysis', 'ik_tool',  f'{id_s}_{id_p}_{id_t}_*.csv'))

    if len(files) < 3:
        if verbose >= 2:
            print(f"OpenSim for {id_s}_{id_p}_{id_t} not done")
        reason = 'Joint velocity .csv not found in movement_analysis\\ik_tool'
        return 0, reason

    return 1, 'all_good'

def check_if_murphy_done(id_s, id_p, id_t, df_murphy, verbose=1):
    """
    Check if the Murphy Measures were done for the given trial
    """

    ts_files = glob.glob(os.path.join(root_val, '03_data', 'preprocessed_data', '01_murphy_out', f'{id_s}_{id_p}_{id_t}_*.csv'))

    if len(ts_files) == 0:
        if verbose >= 2:
            print(f"Murphy Measures for {id_s}_{id_p}_{id_t} not done")

        reason = 'time-series for measures not found in preprocessed_data\\01_murphy_out'
        return 0, reason

    df_trial_only = df_murphy.loc[(df_murphy['id_s'] == id_s) & (df_murphy['id_p'] == id_p) & (df_murphy['id_t'] == id_t)]

    if len(df_trial_only) == 0:
        if verbose >= 2:
            print(f"Murphy Measures for {id_s}_{id_p}_{id_t} not done")
        reason = 'trial not found in murphy_measures.csv'
        return 0, reason

    return 1, 'all_good'

def check_if_murphy_has_reference_data(id_s, id_p, id_t, df_murphy, verbose=1):
    """
    Check if the Murphy Measures were done for the Opensim trial
    """

    id_s_omc = 'S15133'

    ts_reference_files = glob.glob(
        os.path.join(root_val, '03_data', 'preprocessed_data', '01_murphy_out', f'{id_s_omc}_{id_p}_{id_t}_*.csv'))

    if len(ts_reference_files) == 0:
        if verbose >= 2:
            print(f"Murphy Measures for {id_s}_{id_p}_{id_t} not done")
        reason = 'time-series for OMC not found in preprocessed_data\\01_murphy_out'
        return 0, reason

    df_omc_only = df_murphy.loc[
        (df_murphy['id_s'] == id_s_omc) & (df_murphy['id_p'] == id_p) & (df_murphy['id_t'] == id_t)]

    if len(df_omc_only) == 0:
        if verbose >= 2:
            print(f"Murphy Measures for {id_s}_{id_p}_{id_t} not done")
        reason = 'OMC trial not found in murphy_measures.csv'
        return 0, reason

    return 1, 'all_good'

def get_lost_trials():

    global df_failed_trials

    columns_out = ['id_s', 'id_p', 'id_t', 'affected', 'side', 'calib_error', 'HPE', 'P2S', 'OS', 'murphy', 'murphy_omc', 'success', 'fail',
                   'failed_at', 'reason']
    df_failed_trials = pd.DataFrame(columns=columns_out)

    progbar = tqdm(total=len(list_identifier), desc='Processing')

    for identifier in list_identifier:
        progbar.set_description(f"Processing {identifier}: ")
        progbar.update(1)

        df_temp = pd.DataFrame(columns=columns_out, index=[0])

        id_s = df_val_trials.loc[df_val_trials['identifier'] == identifier, 'id_s'].values[0]
        id_p = df_val_trials.loc[df_val_trials['identifier'] == identifier, 'id_p'].values[0]
        id_t = df_val_trials.loc[df_val_trials['identifier'] == identifier, 'id_t'].values[0]

        df_temp['id_s'] = id_s
        df_temp['id_p'] = id_p
        df_temp['id_t'] = id_t
        df_temp ['affected'] = df_val_trials.loc[df_val_trials['identifier'] == identifier, 'affected'].values[0]
        df_temp['side'] = df_val_trials.loc[df_val_trials['identifier'] == identifier, 'measured_side'].values[0]

        used_cams = [f'cam{cam}' for cam in ast.literal_eval(df_val_trials.loc[df_val_trials['identifier'] == identifier, 'used_cams'].values[0])]
        pass

        hpe_model = df_settings.loc[df_settings['setting_id'] == int(id_s.split('S')[1]), 'pose_estimation'].values[0]
        filtered = df_settings.loc[df_settings['setting_id'] == int(id_s.split('S')[1]), 'filtered_2d_keypoints'].values[0]

        if len(used_cams) > 1:
            calib_error = get_calib_error(id_p, id_t, used_cams, df_calib_error)
        else:
            calib_error = -2  # -2 represents single cam

        df_temp['calib_error'] = calib_error

        HPE_success = check_if_HPE_done(used_cams, id_p, id_t, hpe_model, filtered)

        df_temp['HPE'] = HPE_success

        if not HPE_success:
            df_temp['failed_at'] = 'HPE'
            df_temp['success'] = 0
            df_temp['fail'] = 1

            df_failed_trials = pd.concat([df_failed_trials, df_temp], ignore_index=True)
            continue

        P2S_success = check_if_pose2sim_done(id_s, id_p, id_t)

        df_temp['P2S'] = P2S_success

        if not P2S_success:
            df_temp['failed_at'] = 'P2S'
            df_temp['success'] = 0
            df_temp['fail'] = 1

            df_failed_trials = pd.concat([df_failed_trials, df_temp], ignore_index=True)
            continue

        opensim_success, reason = check_if_opensim_done(id_s, id_p, id_t)

        df_temp['OS'] = opensim_success

        if not opensim_success:
            df_temp['failed_at'] = 'OS'
            df_temp['reason'] = reason
            df_temp['success'] = 0
            df_temp['fail'] = 1

            df_failed_trials = pd.concat([df_failed_trials, df_temp], ignore_index=True)
            continue



        murphy_success, reason = check_if_murphy_done(id_s, id_p, id_t, df_murphy)

        df_temp['murphy'] = murphy_success

        if not murphy_success:
            df_temp['failed_at'] = 'Murphy'
            df_temp['reason'] = reason
            df_temp['success'] = 0
            df_temp['fail'] = 1

            murphy_omc_success, _ = check_if_murphy_has_reference_data(id_s, id_p, id_t, df_murphy)
            df_temp['murphy_omc'] = murphy_omc_success

            if not murphy_omc_success:
                df_temp_reason = 'Murphy Measures for OMC and MMC not done'

            df_failed_trials = pd.concat([df_failed_trials, df_temp], ignore_index=True)
            continue

        murphy_omc_success, reason = check_if_murphy_has_reference_data(id_s, id_p, id_t, df_murphy)

        df_temp['murphy_omc'] = murphy_omc_success

        if not murphy_omc_success:
            df_temp['failed_at'] = 'Murphy OMC'
            df_temp['reason'] = reason
            df_temp['success'] = 0
            df_temp['fail'] = 1

            df_failed_trials = pd.concat([df_failed_trials, df_temp], ignore_index=True)
            continue

        if HPE_success and P2S_success and opensim_success and murphy_success and murphy_omc_success:
            df_temp['success'] = 1
            df_temp['fail'] = 0

        df_failed_trials = pd.concat([df_failed_trials, df_temp], ignore_index=True)

    progbar.close()

    os.makedirs(os.path.dirname(csv_failed_trials), exist_ok=True)
    df_failed_trials.to_csv(csv_failed_trials, sep=';', index=False)

    return df_failed_trials


def plot_lost_trials(file_app, write_html=False, write_png=True, write_svg=True, plot_success=False, showfig=False):
    """
    PLot on 2D Heatmap with id_s on y-axis and id_p on x-axis.

    Low numbers are green, high numbers are red.

    Sum is in cell.
    """
    import plotly.express as px

    global df_failed_trials

    df_failed_trials['id_s_name'] = df_failed_trials['id_s'].apply(lambda x: get_setting_axis_name(x))

    if plot_success:
        z = 'success'
        colour_scale = ['rgb(255,0,0)', 'rgb(0,255,0)']
        subdir = '01_success'
        scale_name = 'Success'
    else:
        z = 'fail'
        colour_scale = ['rgb(0,255,0)', 'rgb(255,0,0)']
        subdir = '02_fail'
        scale_name = 'Fails'

    fig = px.density_heatmap(df_failed_trials, x='id_p', y='id_s_name', z=z, text_auto=True, color_continuous_scale=colour_scale)

    fig.update_layout(title='<b>Trials failed during Pipeline<b>',
                      )

    fig.update_xaxes(title_text=f'Patients')
    fig.update_yaxes(title_text=f'Settings')
    fig.update_coloraxes(colorbar_title={'text': scale_name})

    dir_out = os.path.join(root_stat, '04_failed_trials', '02_plots', subdir)

    os.makedirs(dir_out, exist_ok=True)

    if showfig:
        fig.show()

    if write_html:
        filename = os.path.join(dir_out, f'Trials_{z}{file_app}.html')
        fig.write_html(filename)

    if write_png:
        filename = os.path.join(dir_out, f'Trials_{z}{file_app}.png')
        fig.write_image(filename, scale=5)

    if write_svg:
        filename = os.path.join(dir_out, f'Trials_{z}{file_app}.svg')
        fig.write_image(filename, scale=5)

def plot_lost_trials_by_stage(stage, file_app, write_html=False, write_png=True, write_svg=False, showfig=False):
    """
    PLot on 2D Heatmap with id_s on y-axis and id_p on x-axis.

    Low numbers are green, high numbers are red.

    Sum is in cell.
    """
    import plotly.express as px

    global df_failed_trials

    match stage:
        case 'HPE':
            title_stage = 'pose estimation'
        case 'P2S':
            title_stage = 'triangulation'
        case 'OS':
            title_stage = 'calculation of inverse kinematics'
        case 'murphy':
            title_stage = 'calculation of kinematic measures'
        case 'murphy_omc':
            title_stage = 'calculation of kinematic measures of OMC reference'
        case _:
            title_stage = 'Pipeline'


    df_temp = df_failed_trials[['id_p', 'id_s', stage]]
    df_temp[stage] = df_temp[stage].apply(lambda x: 0 if x == 1 else 1 if x == 0 else x)
    df_temp['id_s_name'] = df_temp['id_s'].apply(lambda x: get_setting_axis_name(x))

    colour_scale = ['rgb(0,255,0)', 'rgb(255,0,0)']
    subdir = '02_fail'
    scale_name = 'Fails'

    fig = px.density_heatmap(df_temp, x='id_p', y='id_s_name', z=stage, text_auto=True, color_continuous_scale=colour_scale)

    fig.update_layout(title=f'<b>Trials failed during {title_stage}<b>',
                      )

    fig.update_xaxes(title_text=f'Patients')
    fig.update_yaxes(title_text=f'Settings')
    fig.update_coloraxes(colorbar_title={'text': scale_name})

    dir_out = os.path.join(root_stat, '04_failed_trials', '02_plots', subdir)

    os.makedirs(dir_out, exist_ok=True)

    if showfig:
        fig.show()

    if write_html:
        filename = os.path.join(dir_out, f'Trials_failed_{stage}{file_app}.html')
        fig.write_html(filename)

    if write_png:
        filename = os.path.join(dir_out, f'Trials_failed_{stage}{file_app}.png')
        fig.write_image(filename, scale=5)

    if write_svg:
        filename = os.path.join(dir_out, f'Trials_failed_{stage}{file_app}.svg')
        fig.write_image(filename, scale=5)

    return fig


def plot_all_fails(stages, file_app, no_num_in_plot=False, notitle=True, write_html=False, write_png=True, write_svg=False, showfig=False):
    '''
    Creates plot with failed plots as subplots

    :param stages:
    :param write_html:
    :param write_png:
    :param showfig:
    :return:
    '''
    from plotly.subplots import make_subplots
    import plotly.graph_objects as go

    max_rows = 3
    max_cols = 2
    height = 500* max_rows
    width = 600 * max_cols

    def get_row_col(row, col):

        if col == max_cols:
            return row+1, 1
        else:
            return row, col+1

    subplot_titles = ['<b>Pipeline<b>', '<b>pose estimation<b>', '<b>triangulation<b>', '<b>inverse kinematics<b>',
                      '<b>kinematic measures<b>', '<b>kinematic measures of OMC reference<b>']
    fig = make_subplots(rows=max_rows, cols=max_cols, subplot_titles=subplot_titles,
                        horizontal_spacing=0.25, vertical_spacing=0.1)

    df_failed_trials['id_s_name'] = df_failed_trials['id_s'].apply(lambda x: get_setting_axis_name(x))

    row = 1
    col=1
    if no_num_in_plot:
        fig.add_trace(go.Histogram2d(x=df_failed_trials['id_p'], y=df_failed_trials['id_s_name'], z=df_failed_trials['fail'],
                                     histfunc='sum', coloraxis='coloraxis'), row=row, col=col)
    else:

        fig.add_trace(go.Histogram2d(x=df_failed_trials['id_p'], y=df_failed_trials['id_s_name'], z=df_failed_trials['fail'],
                                    histfunc='sum', texttemplate= "%{z}", coloraxis='coloraxis'), row=row, col=col)


    for stage in stages:
        df_temp = df_failed_trials[['id_p', 'id_s', 'id_s_name', stage]]
        df_temp[stage] = df_temp[stage].apply(lambda x: 0 if x == 1 else 1 if x == 0 else x)

        row, col = get_row_col(row, col)
        if no_num_in_plot:
            fig.add_trace(go.Histogram2d(x=df_temp['id_p'], y=df_temp['id_s_name'], z=df_temp[stage],
                                         histfunc='sum', coloraxis='coloraxis'), row=row, col=col)
        else:
            fig.add_trace(go.Histogram2d(x=df_temp['id_p'], y=df_temp['id_s_name'], z=df_temp[stage],
                                         histfunc='sum', texttemplate="%{z}", coloraxis='coloraxis'), row=row, col=col)

    colour_scale = ['rgb(0,255,0)', 'rgb(255,0,0)']
    fig.update_layout(coloraxis=dict(colorscale=colour_scale), coloraxis_colorbar=dict(title='Fails'))

    if notitle:
        fig.update_layout(width=width, height=height)
    else:
        fig.update_layout(title=dict(text='<b>Trials failed during Pipeline<b>', font=dict(size=28), automargin = False,
                                     yref='paper'),width=width, height=height)

    fig.update_annotations(font_size=16)

    fig.update_xaxes(title_text=f'Patients')
    fig.update_yaxes(title_text=f'Settings')
    fig.update_coloraxes(colorbar_title={'text': 'Fails'})

    dir_out = os.path.join(root_stat, '04_failed_trials', '02_plots', '02_fail')

    os.makedirs(dir_out, exist_ok=True)

    if showfig:
        fig.show()

    if write_html:
        filename = os.path.join(dir_out, f'Trials_failed_all{file_app}.html')
        fig.write_html(filename)

    if write_png:
        filename = os.path.join(dir_out, f'Trials_failed_all{file_app}.png')
        fig.write_image(filename, scale=5)
    if write_svg:
        filename = os.path.join(dir_out, f'Trials_failed_all{file_app}.svg')
        fig.write_image(filename, scale=5)

def plot_calib_errors():
    pass



if __name__ == '__main__':

    overwrite = False

    reduced_analysis = False
    if os.path.isfile(csv_failed_trials) and not overwrite:
        df_failed_trials = pd.read_csv(csv_failed_trials, sep=';')
    else:
        df_failed_trials = get_lost_trials()

    if reduced_analysis:
        df_failed_trials = df_failed_trials[df_failed_trials['id_s'].isin(idx_s_reduced)]
    else:
        df_failed_trials=df_failed_trials[df_failed_trials['id_s'].isin(idx_s_full)]

    count_lost_trials = df_failed_trials.groupby(['id_p', 'id_s', 'failed_at']).size().reset_index(name='count')

    stages = ['HPE', 'P2S', 'OS', 'murphy', 'murphy_omc']

    if reduced_analysis:
        file_app = '_reduced'
    else:
        file_app = ''

    plot_all_fails(stages, file_app, write_html=False, write_png=True, write_svg=True, showfig=False)

    plot_lost_trials(file_app, write_html=False, write_png=True, write_svg=True, plot_success=False, showfig=False)
    plot_lost_trials(file_app, write_html=False, write_png=True, write_svg=True, plot_success=True, showfig=False)

    for stage in stages:
        plot_lost_trials_by_stage(stage, file_app, write_html=False, write_png=True, write_svg=True, showfig=False)