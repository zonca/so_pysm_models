import os.path

import numpy as np
import healpy as hp

import pytest
from astropy.tests.helper import assert_quantity_allclose

import pysm
import pysm.units as u

from .. import PrecomputedAlms


@pytest.fixture()
def setup(tmpdir):
    # tmpdir is a py.test feature to provide a temporary folder

    folder = tmpdir.mkdir("alms")

    np.random.seed(12)
    alm_size = hp.Alm.getsize(lmax=100)
    alms = 1j * np.random.normal(size=(3, alm_size)) << u.K_CMB
    alms += np.random.normal(size=(3, alm_size)) << u.K_CMB

    # str needed to support Python 3.5
    filename = os.path.join(str(folder), "alms.fits")
    hp.write_alm(filename, alms)
    return alms, filename


def test_precomputed_alms(setup):

    alms, filename = setup

    nside = 64
    # we assume the original `alms` are in `K_CMB`
    ref_freq = 40 * u.GHz
    test_map_K_CMB = hp.alm2map(alms, nside=nside) << u.K_CMB

    alms_K_RJ = alms.to(u.K_RJ, equivalencies=u.cmb_equivalencies(ref_freq))
    filename_K_RJ = filename.replace(".fits", "_RJ.fits")
    hp.write_alm(filename_K_RJ, alms_K_RJ)

    precomputed_alms = PrecomputedAlms(
        filename=filename_K_RJ,
        nside=nside,
        input_units="K_RJ",
        input_reference_frequency=ref_freq,
    )
    m = precomputed_alms.get_emission(23 * u.GHz)

    assert_quantity_allclose(
        m, test_map_K_CMB.to(u.K_RJ, equivalencies=u.cmb_equivalencies(23 * u.GHz))
    )

    freqs = np.array([1, 10, 100]) * u.GHz

    for freq in freqs:
        np.testing.assert_allclose(
            precomputed_alms.get_emission(freq), test_map_K_CMB.to(u.K_RJ, equivalencies=u.cmb_equivalencies(freq))
        )


def test_precomputed_alms_K_CMB(setup):

    alms, filename = setup

    nside = 64
    test_map = hp.alm2map(alms, nside=nside) << u.K_CMB
    precomputed_alms = PrecomputedAlms(
        filename=filename, nside=nside, input_units="K_CMB"
    )

    freqs = np.array([1, 10, 100]) * u.GHz

    for freq in freqs:
        np.testing.assert_allclose(
            precomputed_alms.get_emission(freq), test_map.to(u.K_RJ, equivalencies=u.cmb_equivalencies(freq))
        )
