import numpy as np
import healpy as hp

try:
    from pixell import curvedsky, enmap
except:
    pass

import pysm
from pysm import units as u


class PrecomputedAlms(pysm.Model):
    def __init__(
        self,
        filename,
        input_units="uK_CMB",
        input_reference_frequency=None,
        nside=None,
        target_shape=None,
        target_wcs=None,
        precompute_output_map=True,
        has_polarization=True,
        map_dist=None,
    ):
        """Generic component based on Precomputed Alms

        Load a set of Alms from a FITS file and generate maps at the requested
        resolution and frequency assuming the CMB black body spectrum.
        A single set of Alms is used for all frequencies requested by PySM,
        consider that PySM expects the output of components to be in uK_RJ.

        See more details at https://so-pysm-models.readthedocs.io/en/latest/so_pysm_models/models.html

        Parameters
        ----------
        filename : string
            Path to the input Alms in FITS format
        input_units : string
            Input unit strings as defined by pysm.convert_units, e.g. K_CMB, uK_RJ, MJysr
        input_reference_frequency: float
            If input units are K_RJ or Jysr, the reference frequency
        nside : int
            HEALPix NSIDE of the output maps
        precompute_output_map : bool
            If True (default), Alms are transformed into a map in the constructor,
            if False, the object only stores the Alms and generate the map at each
            call of the signal method, this is useful to generate maps convolved
            with different beams
        has_polarization : bool
            whether or not to simulate also polarization maps
            Default: True
        """

        super().__init__(nside=nside, map_dist=map_dist)
        self.shape = target_shape
        self.wcs = target_wcs
        self.filename = filename
        self.input_units = u.Unit(input_units)
        self.has_polarization = has_polarization

        alm = np.complex128(
            hp.read_alm(self.filename, hdu=(1, 2, 3) if self.has_polarization else 1)
        )

        self.equivalencies = (
            None
            if input_reference_frequency is None
            else u.cmb_equivalencies(input_reference_frequency)
        )
        if precompute_output_map:
            self.output_map = self.compute_output_map(alm)

        else:
            self.alm = alm

    def compute_output_map(self, alm):

        if self.nside is None:
            assert (self.shape is not None) and (self.wcs is not None)
            n_comp = 3 if self.has_polarization else 1
            output_map = enmap.empty((n_comp,) + self.shape[-2:], self.wcs)
            curvedsky.alm2map(alm, output_map, spin=[0, 2], verbose=True)
        elif self.nside is not None:
            output_map = hp.alm2map(alm, self.nside)
        else:
            raise ValueError("You must specify either nside or both of shape and wcs")
        return (output_map << self.input_units).to(
            u.uK_CMB, equivalencies=self.equivalencies
        )

    @u.quantity_input
    def get_emission(
        self, freqs: u.GHz, fwhm: [u.arcmin, None] = None, weights=None
    ) -> u.uK_RJ:
        """Return map in uK_RJ at given frequency or array of frequencies

        Parameters
        ----------
        freqs : list or ndarray
            Frequency or frequencies in GHz at which compute the signal
        fwhm : float (optional)
            Smooth the input alms before computing the signal, this can only be used
            if the class was initialized with `precompute_output_map` to False.
        output_units : str
            Output units, as defined in `pysm.convert_units`, by default this is
            "uK_RJ" as expected by PySM.

        Returns
        -------
        output_maps : ndarray
            Output maps array with the shape (num_freqs, 1 or 3 (I or IQU), npix)
        """

        try:
            nfreqs = len(freqs)
        except TypeError:
            nfreqs = 1
            freqs = freqs.reshape((1,))

        try:
            output_map = self.output_map
        except AttributeError:
            if fwhm is None:
                alm = self.alm
            else:
                alm = hp.smoothalm(
                    self.alm, fwhm=fwhm.to_value(u.radian), pol=True, inplace=False
                )

            output_map = self.compute_output_map(alm)

        convert_to_uK_RJ = (np.ones(len(freqs), dtype=np.double) * u.uK_CMB).to_value(
            u.uK_RJ, equivalencies=u.cmb_equivalencies(freqs)
        )

        if nfreqs == 1:
            scaling_factor = convert_to_uK_RJ[0]
        else:
            scaling_factor = np.trapz(convert_to_uK_RJ * weights, x=freqs.value)

        return output_map.value * scaling_factor << u.uK_RJ
