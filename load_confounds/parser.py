"""Flexible method to load confounds generated by fMRIprep.

Authors: load_confounds team
"""
import numpy as np
import pandas as pd
from . import confounds as cf

# Global variables listing the admissible types of noise components
all_confounds = [
    "motion",
    "high_pass",
    "wm_csf",
    "global",
    "compcor",
    "ica_aroma",
    "censoring",
]

def _check_params(confounds_raw, params):
    """Check that specified parameters can be found in the confounds."""
    not_found_params = []
    for par in params:
        if not par in confounds_raw.columns:
            not_found_params.append(par)
    if not_found_params:
        raise ConfoundNotFoundException(params=not_found_params)
    return None


def _find_confounds(confounds_raw, keywords):
    """Find confounds that contain certain keywords."""
    list_confounds = []
    not_found_keys = []
    for key in keywords:
        key_found = False
        for col in confounds_raw.columns:
            if key in col:
                list_confounds.append(col)
                key_found = True
        if not key_found:
            not_found_keys.append(key)
    if not_found_keys:
        raise ConfoundNotFoundException(keywords=not_found_keys)
    return list_confounds


def _select_compcor(compcor_cols, n_compcor, compcor_mask):
    """retain a specified number of compcor components."""
    # only select if not "auto", or less components are requested than there actually is
    if (n_compcor != "auto") and (n_compcor < len(compcor_cols)):
        compcor_cols = compcor_cols[0:n_compcor]
    return compcor_cols


def _find_compcor(confounds_json, prefix, n_compcor, compcor_mask):
    """Builds list for the number of compcor components."""
    # all possible compcor confounds, mixing different types of mask
    all_compcor = [
        comp for comp in confounds_json.keys() if f"{prefix}_comp_cor" in comp
    ]

    # loop and only retain the relevant confounds
    compcor_cols = []
    for nn in range(len(all_compcor)):
        nn_str = str(nn).zfill(2)
        compcor_col = f"{prefix}_comp_cor_{nn_str}"
        if (prefix == "t") or (
            (prefix == "a") and (confounds_json[compcor_col]["Mask"] == compcor_mask)
        ):
            compcor_cols.append(compcor_col)

    return _select_compcor(compcor_cols, n_compcor, compcor_mask)


def _find_acompcor(confounds_json, n_compcor, acompcor_combined):
    """Helper function dedicated to anat compcor."""
    if acompcor_combined:
        compcor_cols = _find_compcor(confounds_json, "a", n_compcor, "combined")
    else:
        compcor_cols = _find_compcor(confounds_json, "a", n_compcor, "WM")
        compcor_cols.extend(_find_compcor(confounds_json, "a", n_compcor, "CSF"))
    return compcor_cols


def _sanitize_confounds(confounds_raw):
    """Make sure the inputs are in the correct format."""
    # we want to support loading a single set of confounds, instead of a list
    # so we hack it
    flag_single = isinstance(confounds_raw, str) or isinstance(
        confounds_raw, pd.DataFrame
    )
    if flag_single:
        confounds_raw = [confounds_raw]

    return confounds_raw, flag_single


def _sanitize_strategy(strategy):
    """Defines the supported denoising strategies."""
    if isinstance(strategy, list):
        for conf in strategy:
            if not conf in all_confounds:
                raise ValueError(f"{conf} is not a supported type of confounds.")
    else:
        raise ValueError("strategy needs to be a list of strings")
    return strategy


def _raise_conf_not_found_error(not_found_conf, not_found_keys):
    """Consolidate a single error message across multiple missing confounds."""
    conf_str = f"parameters {not_found_conf} " if not_found_conf else ""
    and_str = "and the " if not_found_conf and not_found_keys else ""
    keys_str = f"keywords {not_found_keys} " if not_found_keys else ""
    error_msg = (
        "The "
        + conf_str
        + and_str
        + keys_str
        + "cannot be found in the available confounds. You may "
        + "want to use a different denoising strategy."
    )
    raise ValueError(error_msg)


class ConfoundNotFoundException(Exception):
    """
    Exception raised when failing to find params in the confounds.

    Parameters
    ----------
        params : list of not found params
    """

    def __init__(self, params=None, keywords=None):
        """Default values are empty lists."""
        self.params = params if params else []
        self.keywords = keywords if keywords else []


class Confounds:
    """
    Confounds from fmriprep

    Parameters
    ----------
    strategy : list of strings
        The type of noise confounds to include.
        "motion" head motion estimates.
        "high_pass" discrete cosines covering low frequencies.
        "wm_csf" confounds derived from white matter and cerebrospinal fluid.
        "global" confounds derived from the global signal.
        "ica_aroma" confounds derived from ICA-AROMA.
        "censoring" regressors for Power 2014 scrubbing approach.

    motion : string, optional
        Type of confounds extracted from head motion estimates.
        "basic" translation/rotation (6 parameters)
        "power2" translation/rotation + quadratic terms (12 parameters)
        "derivatives" translation/rotation + derivatives (12 parameters)
        "full" translation/rotation + derivatives + quadratic terms + power2d derivatives (24 parameters)

    n_motion : float
        Number of pca components to keep from head motion estimates.
        If the parameters is strictly comprised between 0 and 1, a principal component
        analysis is applied to the motion parameters, and the number of extracted
        components is set to exceed `n_motion` percent of the parameters variance.
        If the n_components = 0, then no PCA is performed.

    fd_thresh : float, optional
        Framewise displacement threshold for censoring (default = 0.2 mm)

    std_dvars_thresh : float, optional
        Standardized DVARS threshold for censoring (default = 3)

    wm_csf : string, optional
        Type of confounds extracted from masks of white matter and cerebrospinal fluids.
        "basic" the averages in each mask (2 parameters)
        "power2" averages and quadratic terms (4 parameters)
        "derivatives" averages and derivatives (4 parameters)
        "full" averages + derivatives + quadratic terms + power2d derivatives (8 parameters)

    global_signal : string, optional
        Type of confounds extracted from the global signal.
        "basic" just the global signal (1 parameter)
        "power2" global signal and quadratic term (2 parameters)
        "derivatives" global signal and derivative (2 parameters)
        "full" global signal + derivatives + quadratic terms + power2d derivatives (4 parameters)

    compcor : string, optional
        Type of confounds extracted from a component based noise correction method
        "anat" noise components calculated using anatomical compcor
        "temp" noise components calculated using temporal compcor
        "full" noise components calculated using both temporal and anatomical

    censoring : string, optional
        Type of censoring of frames with excessive motion (Power et al. 2014)
        "basic" remove time frames based on excessive FD and DVARS
        "optimized" also remove time windows which are too short after scrubbing.

    n_compcor : int or "auto", optional
        The number of noise components to be extracted.
        Default is "auto": select all components (50% variance explained by fMRIPrep defaults)

    acompcor_combined: boolean, optional
        If true, use components generated from the combined white matter and csf
        masks. Otherwise, components are generated from each mask separately and then
        concatenated.

    demean : boolean, optional
        If True, the confounds are standardized to a zero mean (over time).
        This step is critical if the confounds are regressed out of time series
        using nilearn with no or zscore standardization, but should be turned off
        with "spc" normalization.

    Attributes
    ----------
    `confounds_` : ndarray
        The confounds loaded using the specified model

    `columns_`: list of str
        The labels of the different confounds

    Notes
    -----
    The predefined strategies implemented in this class are from
    adapted from (Ciric et al. 2017). Band-pass filter is replaced
    by high-pass filter, as high frequencies have been shown to carry
    meaningful signal for connectivity analysis.

    References
    ----------
    Ciric et al., 2017 "Benchmarking of participant-level confound regression
    strategies for the control of motion artifact in studies of functional
    connectivity" Neuroimage 154: 174-87
    https://doi.org/10.1016/j.neuroimage.2017.03.020
    """

    def __init__(
        self,
        strategy=["motion", "high_pass", "wm_csf"],
        motion="full",
        n_motion=0,
        censoring="basic",
        fd_thresh=0.2,
        std_dvars_thresh=3,
        wm_csf="basic",
        global_signal="basic",
        compcor="anat",
        acompcor_combined=True,
        n_compcor="auto",
        demean=True,
    ):
        """Default parameters."""
        self.strategy = _sanitize_strategy(strategy)
        self.motion = motion
        self.n_motion = n_motion
        self.censoring = censoring
        self.fd_thresh = fd_thresh
        self.std_dvars_thresh = std_dvars_thresh
        self.wm_csf = wm_csf
        self.global_signal = global_signal
        self.compcor = compcor
        self.acompcor_combined = acompcor_combined
        self.n_compcor = n_compcor
        self.demean = demean


    def load(self, confounds_raw):
        """
        Load fMRIprep confounds

        Parameters
        ----------
        confounds_raw : path to tsv or nii file(s), optionally as a list.
            Raw confounds from fmriprep. If a nii is provided, the companion
            tsv will be automatically detected.

        Returns
        -------
        confounds :  ndarray or list of ndarray
            A reduced version of fMRIprep confounds based on selected strategy and flags.
            An intercept is automatically added to the list of confounds.
        """
        confounds_raw, flag_single = _sanitize_confounds(confounds_raw)
        confounds_out = []
        columns_out = []
        for file in confounds_raw:
            conf, col = self._load_single(file)
            confounds_out.append(conf)
            columns_out.append(col)

        # If a single input was provided,
        # send back a single output instead of a list
        if flag_single:
            confounds_out = confounds_out[0]
            columns_out = columns_out[0]

        self.confounds_ = confounds_out
        self.columns_ = columns_out
        return confounds_out

    def _load_single(self, confounds_raw):
        """Load a single confounds file from fmriprep."""
        # Convert tsv file to pandas dataframe
        confounds_raw, self.json_ = cf._confounds_to_df(confounds_raw)

        confounds = pd.DataFrame()
        not_found_conf = []
        not_found_keys = []

        for confound in self.strategy:
            try:
                loaded_confounds = getattr(self, f"_load_{confound}")(confounds_raw)
                confounds = pd.concat([confounds, loaded_confounds], axis=1)
            except ConfoundNotFoundException as exception:
                not_found_conf += exception.params
                not_found_keys += exception.keywords

        if not_found_conf or not_found_keys:
            _raise_conf_not_found_error(not_found_conf, not_found_keys)

        confounds, labels = cf._confounds_to_ndarray(confounds, self.demean)
        return confounds, labels

    def _load_motion(self, confounds_raw):
        """Load the motion regressors."""
        motion_params = cf._add_suffix(
            ["trans_x", "trans_y", "trans_z", "rot_x", "rot_y", "rot_z"], self.motion
        )
        _check_params(confounds_raw, motion_params)
        confounds_motion = confounds_raw[motion_params]

        # Optionally apply PCA reduction
        if self.n_motion > 0:
            confounds_motion = cf._pca_motion(confounds_motion, n_components=self.n_motion)
        return confounds_motion

    def _load_high_pass(self, confounds_raw):
        """Load the high pass filter regressors."""
        high_pass_params = _find_confounds(confounds_raw, ["cosine"])
        return confounds_raw[high_pass_params]

    def _load_wm_csf(self, confounds_raw):
        """Load the regressors derived from the white matter and CSF masks."""
        wm_csf_params = cf._add_suffix(["csf", "white_matter"], self.wm_csf)
        _check_params(confounds_raw, wm_csf_params)
        return confounds_raw[wm_csf_params]

    def _load_global(self, confounds_raw):
        """Load the regressors derived from the global signal."""
        global_params = cf._add_suffix(["global_signal"], self.global_signal)
        _check_params(confounds_raw, global_params)
        return confounds_raw[global_params]

    def _load_compcor(self, confounds_raw):
        """Load compcor regressors."""
        if self.compcor == "anat":
            compcor_cols = _find_acompcor(
                self.json_, self.n_compcor, self.acompcor_combined
            )

        if self.compcor == "temp":
            compcor_cols = _find_compcor(
                self.json_, "t", self.n_compcor, self.acompcor_combined
            )

        if self.compcor == "full":
            compcor_cols = _find_compcor(
                self.json_, "a", self.n_compcor, self.acompcor_combined
            )
            compcor_cols.extend(
                _find_compcor(self.json_, "t", self.n_compcor, self.acompcor_combined)
            )

        _check_params(confounds_raw, compcor_cols)
        return confounds_raw[compcor_cols]

    def _load_ica_aroma(self, confounds_raw):
        """Load the ICA-AROMA regressors."""
        ica_aroma_params = _find_confounds(confounds_raw, ["aroma"])
        return confounds_raw[ica_aroma_params]

    def _load_censoring(self, confounds_raw):
        """Perform basic censoring - Remove volumes if framewise displacement exceeds threshold"""
        """Power, Jonathan D., et al. "Steps toward optimizing motion artifact removal in functional connectivity MRI; a reply to Carp." Neuroimage 76 (2013)."""
        n_scans = len(confounds_raw)
        # Get indices of fd outliers
        fd_outliers = np.where(
            confounds_raw["framewise_displacement"] > self.fd_thresh
        )[0]
        dvars_outliers = np.where(confounds_raw["std_dvars"] > self.std_dvars_thresh)[0]
        combined_outliers = np.sort(
            np.unique(np.concatenate((fd_outliers, dvars_outliers)))
        )
        # Do optimized scrubbing if desired
        if self.censoring == "optimized":
            combined_outliers = cf._optimize_censoring(combined_outliers, n_scans)
        # Make one-hot encoded motion outlier regressors
        motion_outlier_regressors = pd.DataFrame(
            np.transpose(np.eye(n_scans)[combined_outliers]).astype(int)
        )
        column_names = [
            "motion_outlier_" + str(num)
            for num in range(np.shape(motion_outlier_regressors)[1])
        ]
        motion_outlier_regressors.columns = column_names
        return motion_outlier_regressors
