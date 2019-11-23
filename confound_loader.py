"""
A function that is used to load confound parameters generated by FMRIPREP.

Authors: Dr. Pierre Bellec, Francois Paugam, Hanad Sharmarke
"""
import pandas as pd
from sklearn.decomposition import PCA

motion_6params = ["trans_x", "trans_y", "trans_z", "rot_x", "rot_y", "rot_z"]
motion_models = {
    "6params": "{}",
    "derivatives": "{}_derivative1",
    "square": "{}_power2",
    "full": "{}_derivative1_power2",
}

matter = ["csf", "white_matter"]

confound_dict = {
    "motion": ["trans", "rot"],
    "matter": ["csf", "white_matter"],
    "high_pass_filter": ["cosine"],
    "compcor": ["comp_cor"],
}
minimal = confound_dict["motion"] + confound_dict["high_pass_filter"] + confound_dict["matter"]
confound_dict["minimal"] = minimal

def confound_strat(strategy,confound_raw):
    param  = [col for col in confound_raw.columns for conf in confound_dict[strategy] if (conf in col) and "derivative" not in col and "power" not in col]
    return param

def _add_motion_model(motion_confounds, motion_model):
    """
    Add the motion model confounds to the list of motion confounds.

    Parameters
        motion_confounds: Set of strings

                Set of the motion confounds

        motion_model: string

                Name of the motion model to use
    """
    if motion_model != "full":
        motion_confounds |= {
            motion_models[motion_model].format(mot)
            for mot in set(motion_6params) & set(motion_confounds)
        }
    else:
        motion_confounds |= {
            motion_models[model].format(mot)
            for mot in set(motion_6params) & set(motion_confounds)
            for model in motion_models.keys()
        }

    return motion_confounds


def _pca_motion(
    confounds_out,
    confounds_raw,
    motion_confounds,
    n_components=0.95,
    motion_model="6params",
):
    """
    Reduce the motion paramaters using PCA.

    Parameters
        confounds_out: Pandas Dataframe

                Confounds that will be loaded

        confounds_raw: Pandas Dataframe

                The raw confounds from fmriprep

        motion_confounds: List of strings

                Names of the motion confounds to do the PCA on

        n_compenents: int,float

                The number of compnents for PCA

                -if ``0 < n_components < 1``, n_components is percentage that represents the amount of variance that needs to be explained
                -if n_components == 0, the raw motion parameters are returned
                -if n_components >1, the number of components are returned

    """

    # Run PCA to reduce parameters
    motion_parameters_raw = confounds_raw[motion_confounds]

    if n_components == 0:
        confounds_pca = motion_parameters_raw

    else:
        motion_parameters_raw = motion_parameters_raw.dropna()
        pca = PCA(n_components=n_components)
        confounds_pca = pd.DataFrame(pca.fit_transform(motion_parameters_raw.values))
        confounds_pca.columns = [
            "motion_pca_" + str(col + 1) for col in confounds_pca.columns
        ]

    # Add motion parameters to confounds dataframe
    confounds_out = pd.concat((confounds_out, confounds_pca), axis=1)

    return confounds_out


def load_confounds(
    confounds_raw, strategy=["minimal"], n_components=0.95, motion_model="6params"
):
    """
    Load confounds from fmriprep

    Parameters

        confounds_raw: Pandas Dataframe or path to tsv file

                       Raw confounds from fmriprep


        strategy: List of strings

                       The strategy used to select a subset of the confounds from fmriprep: each string can be
                       either the name of one of the following subset of confounds or the name of a confound to add.

                       -minimal: basic strategy that uses motion, high pass filter, csf and white matter parameters
                       -motion: ["trans_x", "trans_y", "trans_z", "rot_x", "rot_y", "rot_z"]
                       -high_pass_filter = ["cosine00", "cosine01", ..]
                       -matter: ["csf", "white_matter"]
                       -compcor: ["t_comp_cor_00","t_comp_cor_01",..]


        motion_model: String

                Temporal and quadratic terms for head motion estimates

                -6params: standard motion parameters (6)
                -square: standard motion paramters + quadratic terms (12)
                -derivatives: standard motion paramters + derivatives (12)
                -full: standard motion paramteres + derivatives + quadratic terms + squared derivatives (24)
    """

    # Convert tsv file to pandas dataframe
    if not isinstance(confounds_raw, pd.DataFrame):
        confounds_raw = pd.read_csv(confounds_raw, delimiter="\t", encoding="utf-8")

    # Add chosen confounds based on strategy to dataframe
    confounds_names = set()
    confounds_out = pd.DataFrame()

    for strat in strategy:
        if strat in confound_dict.keys():


            confounds_names |= set(confound_strat(strat,confounds_raw))
        else:
            confounds_names.add(strat)

    # isolate motion confounds and augment them according to the motion model
    motion_confounds = {
        confound
        for confound in confounds_names
        if confound.split("_")[0] in ["trans", "rot"]
    }
    motion_confounds = _add_motion_model(motion_confounds, motion_model)

    # load non motion confounds
    non_motion_confounds = confounds_names - motion_confounds
    confounds_out = pd.concat(
        (confounds_out, confounds_raw[list(non_motion_confounds)]), axis=1
    )

    # Apply PCA on motion confounds
    if motion_confounds:
        confounds_out = _pca_motion(
            confounds_out, confounds_raw, list(motion_confounds), n_components
        )

    return confounds_out


if __name__ == "__main__":

    tsv_file = "sub-01_ses-001.tsv"

    confounds_test = load_confounds(tsv_file, strategy = ["motion"], motion_model = "full",n_components=0)
    print(confounds_test.columns)
    confounds_test.to_csv("csv_output/confounds_test.csv", index=False)
