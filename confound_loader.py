"""
A function that is used to load confouund parameters generated by FMRIPREP.

Authors: Dr. Pierre Bellec, Francois Paugam, Hanad Sharmarke
"""
import pandas as pd
from sklearn.decomposition import PCA

motion = ["trans_x", "trans_y", "trans_z", "rot_x", "rot_y", "rot_z"]
motion_models = {
    "6params": "{}",
    "derivatives": "{}_derivative1",
    "square": "{}_power2",
    "full": "{}_derivative1_power2",
}
compcor = [
    "t_comp_cor_00",
    "t_comp_cor_01",
    "t_comp_cor_02",
    "t_comp_cor_03",
    "t_comp_cor_04",
    "t_comp_cor_05",
    "a_comp_cor_00",
    "a_comp_cor_01",
    "a_comp_cor_02",
    "a_comp_cor_03",
    "a_comp_cor_04",
    "a_comp_cor_05",
]
high_pass_filter = [
    "cosine00",
    "cosine01",
    "cosine02",
    "cosine03",
    "cosine04",
    "cosine05",
    "cosine06",
]

matter = ["csf", "white_matter"]

confound_dict = {
    "motion": motion,
    "matter": matter,
    "high_pass_filter": high_pass_filter,
    "compcor": compcor,
    "minimal": matter + high_pass_filter + motion,
}


def _pca_motion(
    confounds_out, confounds_raw, n_components=0.95, motion_model="6params"
):
    """
    Reduce the motion paramaters using PCA.

    Parameters 
        confounds_out: Pandas Dataframe

                Confounds that will be loaded
        
        confounds_raw: Pandas Dataframe

                The raw confounds from fmriprep

        n_compenents: int,float

                The number of compnents for PCA

                -if ``0 < n_components < 1``, then number of components is the amount of variance that needs to beexplained as a percentage.
                -if n_components == 0, the raw motion parameters are returned
                -if n_components >1, the number of components are returned


        motion_model: String

                Temporal and quadratic terms for head motion estimates 

                -6params: standard motion parameters (6)
                -square: standard  motion paramters + quadratic terms (12)
                -derivatives: standard motion paramters + derivatives (12)
                -full: standard standard motion paramteres + derivatives + quadratic terms + squared derivatives 


    """

    # Get columns to use based on motion model
    if motion_model != "full":
        motion_columns = list(
            set(motion + [motion_models[motion_model].format(col) for col in motion])
        )
    else:
        motion_columns = [
            motion_models[model].format(col)
            for col in motion
            for model in motion_models.keys()
        ]

    # Run PCA to reduce parameters
    motion_parameters_raw = confounds_raw[motion_columns]

    if n_components == 0:
        motion_confounds = motion_parameters_raw

    else:
        motion_parameters_raw = motion_parameters_raw.dropna()
        pca = PCA(n_components=n_components)
        confounds_pca = pca.fit_transform(motion_parameters_raw.values)
        motion_confounds = pd.DataFrame(confounds_pca)
        motion_confounds.columns = [
            "motion_pca_" + str(col + 1) for col in motion_confounds.columns
        ]

    

    confounds_out.drop(columns=motion, inplace=True)

    # Add motion parameters to confounds dataframe
    confounds_out = pd.concat((confounds_out, motion_confounds), axis=1)

    return confounds_out


def load_confounds(
    confounds_raw, strategy=["minimal"], n_components=0.95, motion_model="6params"
):
    """
    Load confounds from fmriprep

    Parameters

        confounds_raw: Pandas Dataframe
                    
                       Raw confounds from fmriprep


        strategy: A list of strings 
                    
                       The strategy used to select a subset of the confounds from fmriprep

                       -minimal: basic strategy that uses motion, high pass filter, csf and white matter paramters
                    
                       -motion: ["trans_x", "trans_y", "trans_z", "rot_x", "rot_y", "rot_z"]
                       -high_pass_filter = ["cosine00", "cosine01", ..]
                       -matter: ["csf", "white_matter"]
                       -compcor: ["t_comp_cor_00","t_comp_cor_01",..]
    """

    # Convert tsv file to pandas dataframe
    if not isinstance(confounds_raw, pd.DataFrame):
        confounds_raw = pd.read_csv(confounds_raw, delimiter="\t", encoding="utf-8")

    # Add chosen confounds based on strategy to dataframe
    confounds_out = pd.DataFrame()
    for strat in strategy:

        if strat in confound_dict.keys():

            confounds_out = pd.concat(
                (confounds_out, confounds_raw[confound_dict[strat]]), axis=1
            )
        else:
            confounds_out = pd.concat((confounds_out, confounds_raw[strat]), axis=1)

    # Throw an error if strategy has duplicate confounds
    if len(confounds_out.columns) != len(set(confounds_out.columns)):
        raise ValueError("Your strategy has duplicate confounds.")

    # Add motion parameters 
    if set(motion) & set(confounds_out.columns):
        confounds_out = _pca_motion(
            confounds_out, confounds_raw, n_components, motion_model
        )

    return confounds_out


if __name__ == "__main__":

    tsv_file = "sub-01_ses-001.tsv"

    confounds_test = load_confounds(tsv_file)
    print(confounds_test.columns)
    confounds_test.to_csv("csv_output/confounds_test.csv", index=False)
