import lal
import lalsimulation
import numpy as np
import pytest
import torch
from astropy import units as u
import matplotlib.pyplot as plt

import ml4gw.waveforms as waveforms
from ml4gw.waveforms.conversion import (
    bilby_spins_to_lalsim,
    chirp_mass_and_mass_ratio_to_components,
)

@pytest.fixture()
def num_samples(request):
    if request.config.getoption("--benchmark"):
        return 100000
    return 100

@pytest.fixture(params=[20, 40])
def f_ref(request):
    return request.param

def test_taylor_f2(
    chirp_mass,
    mass_ratio,
    chi1,
    chi2,
    phase,
    distance,
    f_ref,
    theta_jn,
    sample_rate,
):
    mass_1, mass_2 = chirp_mass_and_mass_ratio_to_components(
        chirp_mass, mass_ratio
    )

    # compare each waveform with lalsimulation
    for i in range(len(chirp_mass)):

        # construct lalinference params
        params = dict(
            m1=mass_1[i].item() * lal.MSUN_SI,
            m2=mass_2[i].item() * lal.MSUN_SI,
            S1x=0,
            S1y=0,
            S1z=chi1[i].item(),
            S2x=0,
            S2y=0,
            S2z=chi2[i].item(),
            distance=(distance[i].item() * u.Mpc).to("m").value,
            inclination=theta_jn[i].item(),
            phiRef=phase[i].item(),
            longAscNodes=0.0,
            eccentricity=0.0,
            meanPerAno=0.0,
            deltaF=1.0 / sample_rate,
            f_min=10,
            f_ref=f_ref,
            f_max=300,
            approximant=lalsimulation.TaylorF2,
            LALpars=lal.CreateDict(),
        )
        hp_lal, hc_lal = lalsimulation.SimInspiralChooseFDWaveform(**params)

        # reconstruct frequencies generated by
        # lal and filter based on fmin and fmax
        lal_freqs = np.array(
            [
                hp_lal.f0 + ii * hp_lal.deltaF
                for ii in range(len(hp_lal.data.data))
            ]
        )

        lal_mask = (lal_freqs > params["f_min"]) & (
            lal_freqs < params["f_max"]
        )

        lal_freqs = lal_freqs[lal_mask]
        torch_freqs = torch.tensor(lal_freqs, dtype=torch.float64)

        # generate waveforms using ml4gw
        hc_ml4gw, hp_ml4gw = waveforms.TaylorF2()(
            torch_freqs,
            chirp_mass[i][None],
            mass_ratio[i][None],
            chi1[i][None],
            chi2[i][None],
            distance[i][None],
            phase[i][None],
            theta_jn[i][None],
            f_ref,
        )

        hc_ml4gw = hc_ml4gw[0]
        hp_ml4gw = hp_ml4gw[0]

        hp_lal_data = hp_lal.data.data[lal_mask]
        hc_lal_data = hc_lal.data.data[lal_mask]

        # ensure no nans
        assert not torch.any(torch.isnan(hc_ml4gw))
        assert not torch.any(torch.isnan(hp_ml4gw))

        assert np.allclose(
            1e21 * hp_lal_data.real, 1e21 * hp_ml4gw.real.numpy(), atol=1e-3
        )
        assert np.allclose(
            1e21 * hp_lal_data.imag, 1e21 * hp_ml4gw.imag.numpy(), atol=1e-3
        )
        assert np.allclose(
            1e21 * hc_lal_data.real, 1e21 * hc_ml4gw.real.numpy(), atol=1e-3
        )
        assert np.allclose(
            1e21 * hc_lal_data.imag, 1e21 * hc_ml4gw.imag.numpy(), atol=1e-3
        )

        # taylor f2 is symmetric w.r.t m1 --> m2 flip.
        # so test that the waveforms are the same when m1 and m2
        # (and corresponding chi1, chi2 are flipped)
        # are flipped this can be done by flipping mass ratio
        hc_ml4gw, hp_ml4gw = waveforms.TaylorF2()(
            torch_freqs,
            chirp_mass[i][None],
            1 / mass_ratio[i][None],
            chi2[i][None],
            chi1[i][None],
            distance[i][None],
            phase[i][None],
            theta_jn[i][None],
            f_ref,
        )

        hc_ml4gw = hc_ml4gw[0]
        hp_ml4gw = hp_ml4gw[0]

        assert np.allclose(
            1e21 * hp_lal_data.real, 1e21 * hp_ml4gw.real.numpy(), atol=1e-3
        )
        assert np.allclose(
            1e21 * hp_lal_data.imag, 1e21 * hp_ml4gw.imag.numpy(), atol=1e-3
        )
        assert np.allclose(
            1e21 * hc_lal_data.real, 1e21 * hc_ml4gw.real.numpy(), atol=1e-3
        )
        assert np.allclose(
            1e21 * hc_lal_data.imag, 1e21 * hc_ml4gw.imag.numpy(), atol=1e-3
        )


def test_phenom_d(
    chirp_mass,
    mass_ratio,
    chi1,
    chi2,
    distance,
    phase,
    theta_jn,
    sample_rate,
    f_ref,
    benchmark_storage,
    request
):
    mass_1, mass_2 = chirp_mass_and_mass_ratio_to_components(
        chirp_mass, mass_ratio
    )

    # compare each waveform with lalsimulation
    for i in range(len(chirp_mass)):

        # construct lalinference params
        params = dict(
            m1=mass_1[i].item() * lal.MSUN_SI,
            m2=mass_2[i].item() * lal.MSUN_SI,
            S1x=0,
            S1y=0,
            S1z=chi1[i].item(),
            S2x=0,
            S2y=0,
            S2z=chi2[i].item(),
            distance=(distance[i].item() * u.Mpc).to("m").value,
            inclination=theta_jn[i].item(),
            phiRef=phase[i].item(),
            longAscNodes=0.0,
            eccentricity=0.0,
            meanPerAno=0.0,
            deltaF=1.0 / sample_rate,
            f_min=10,
            f_ref=f_ref,
            f_max=300,
            approximant=lalsimulation.IMRPhenomD,
            LALpars=lal.CreateDict(),
        )
        hp_lal, hc_lal = lalsimulation.SimInspiralChooseFDWaveform(**params)

        # reconstruct frequencies generated by
        # lal and filter based on fmin and fmax
        lal_freqs = np.array(
            [
                hp_lal.f0 + ii * hp_lal.deltaF
                for ii in range(len(hp_lal.data.data))
            ]
        )

        lal_mask = (lal_freqs > params["f_min"]) & (
            lal_freqs < params["f_max"]
        )

        lal_freqs = lal_freqs[lal_mask]
        torch_freqs = torch.tensor(lal_freqs, dtype=torch.float32)

        # generate waveforms using ml4gw
        hc_ml4gw, hp_ml4gw = waveforms.IMRPhenomD()(
            torch_freqs,
            chirp_mass[i][None],
            mass_ratio[i][None],
            chi1[i][None],
            chi2[i][None],
            distance[i][None],
            phase[i][None],
            theta_jn[i][None],
            f_ref,
        )

        hc_ml4gw = hc_ml4gw[0]
        hp_ml4gw = hp_ml4gw[0]

        hp_lal_data = hp_lal.data.data[lal_mask]
        hc_lal_data = hc_lal.data.data[lal_mask]

        assert not torch.any(torch.isnan(hc_ml4gw))
        assert not torch.any(torch.isnan(hp_ml4gw))

        hp_real_abs_err = np.abs(1e21 * hp_lal_data.real - 1e21 * hp_ml4gw.real.numpy())
        hp_imag_abs_err = np.abs(1e21 * hp_lal_data.imag - 1e21 * hp_ml4gw.imag.numpy())
        hc_real_abs_err = np.abs(1e21 * hc_lal_data.real - 1e21 * hc_ml4gw.real.numpy())
        hc_imag_abs_err = np.abs(1e21 * hc_lal_data.imag - 1e21 * hc_ml4gw.imag.numpy())
        hp_real_rel_err = hp_real_abs_err / np.abs(1e21 * hp_lal_data.real)
        hp_imag_rel_err = hp_imag_abs_err / np.abs(1e21 * hp_lal_data.imag)
        hc_real_rel_err = hc_real_abs_err / np.abs(1e21 * hc_lal_data.real)
        hc_imag_rel_err = hc_imag_abs_err / np.abs(1e21 * hc_lal_data.imag)

        hp_real_rel_err[np.isinf(hp_real_rel_err)] = 0
        hp_imag_rel_err[np.isinf(hp_imag_rel_err)] = 0
        hc_real_rel_err[np.isinf(hc_real_rel_err)] = 0
        hc_imag_rel_err[np.isinf(hc_imag_rel_err)] = 0

        benchmark_storage["hp_real_abs_err"] = np.concatenate((benchmark_storage["hp_real_abs_err"], hp_real_abs_err))
        benchmark_storage["hp_real_rel_err"] = np.concatenate((benchmark_storage["hp_real_rel_err"], hp_real_rel_err))
        benchmark_storage["hp_imag_abs_err"] = np.concatenate((benchmark_storage["hp_imag_abs_err"], hp_imag_abs_err))
        benchmark_storage["hp_imag_rel_err"] = np.concatenate((benchmark_storage["hp_imag_rel_err"], hp_imag_rel_err))
        benchmark_storage["hc_real_abs_err"] = np.concatenate((benchmark_storage["hc_real_abs_err"], hc_real_abs_err))
        benchmark_storage["hc_real_rel_err"] = np.concatenate((benchmark_storage["hc_real_rel_err"], hc_real_rel_err))
        benchmark_storage["hc_imag_abs_err"] = np.concatenate((benchmark_storage["hc_imag_abs_err"], hc_imag_abs_err))
        benchmark_storage["hc_imag_rel_err"] = np.concatenate((benchmark_storage["hc_imag_rel_err"], hc_imag_rel_err))

        if (request.config.getoption("--benchmark") == False):
            assert np.allclose(
                1e21 * hp_lal_data.real, 1e21 * hp_ml4gw.real.numpy(), atol=2e-3
            )
            assert np.allclose(
                1e21 * hp_lal_data.imag, 1e21 * hp_ml4gw.imag.numpy(), atol=2e-3
            )
            assert np.allclose(
                1e21 * hc_lal_data.real, 1e21 * hc_ml4gw.real.numpy(), atol=2e-3
            )
            assert np.allclose(
                1e21 * hc_lal_data.imag, 1e21 * hc_ml4gw.imag.numpy(), atol=2e-3
            )

def test_phenom_p(
    chirp_mass,
    mass_ratio,
    distance_far,
    distance_close,
    phase,
    sample_rate,
    f_ref,
    theta_jn,
    phi_jl,
    tilt_1,
    tilt_2,
    phi_12,
    a_1,
    a_2,
):
    mass_1, mass_2 = chirp_mass_and_mass_ratio_to_components(
        chirp_mass, mass_ratio
    )
    (
        inclination,
        chi1x,
        chi1y,
        chi1z,
        chi2x,
        chi2y,
        chi2z,
    ) = bilby_spins_to_lalsim(
        theta_jn,
        phi_jl,
        tilt_1,
        tilt_2,
        phi_12,
        a_1,
        a_2,
        mass_1,
        mass_2,
        f_ref,
        phase,
    )

    tc = 0.0

    # compare each waveform with lalsimulation
    for i in range(len(chirp_mass)):

        # test far (> 400 Mpc) waveforms (O(1e-3) agreement)

        # construct lalinference params
        params = dict(
            m1=mass_1[i].item() * lal.MSUN_SI,
            m2=mass_2[i].item() * lal.MSUN_SI,
            S1x=chi1x[i].item(),
            S1y=chi1y[i].item(),
            S1z=chi1z[i].item(),
            S2x=chi2x[i].item(),
            S2y=chi2y[i].item(),
            S2z=chi2z[i].item(),
            distance=(distance_far[i].item() * u.Mpc).to("m").value,
            inclination=inclination[i].item(),
            phiRef=phase[i].item(),
            longAscNodes=0.0,
            eccentricity=0.0,
            meanPerAno=0.0,
            deltaF=1.0 / sample_rate,
            f_min=10.0,
            f_ref=f_ref,
            f_max=300,
            approximant=lalsimulation.IMRPhenomPv2,
            LALpars=lal.CreateDict(),
        )
        hp_lal, hc_lal = lalsimulation.SimInspiralChooseFDWaveform(**params)

        # reconstruct frequencies generated by
        # lal and filter based on fmin and fmax
        lal_freqs = np.array(
            [
                hp_lal.f0 + ii * hp_lal.deltaF
                for ii in range(len(hp_lal.data.data))
            ]
        )

        lal_mask = (lal_freqs > params["f_min"]) & (
            lal_freqs < params["f_max"]
        )

        lal_freqs = lal_freqs[lal_mask]
        torch_freqs = torch.tensor(lal_freqs, dtype=torch.float32)

        hc_ml4gw, hp_ml4gw = waveforms.IMRPhenomPv2()(
            torch_freqs,
            chirp_mass[i][None],
            mass_ratio[i][None],
            chi1x[i][None],
            chi1y[i][None],
            chi1z[i][None],
            chi2x[i][None],
            chi2y[i][None],
            chi2z[i][None],
            distance_far[i][None],
            phase[i][None],
            inclination[i][None],
            f_ref,
            torch.tensor([tc]),
        )

        hp_ml4gw = hp_ml4gw[0]
        hc_ml4gw = hc_ml4gw[0]

        hp_lal_data = hp_lal.data.data[lal_mask]
        hc_lal_data = hc_lal.data.data[lal_mask]

        # Only 4 of 50,000 samples failed this tolerance
        assert np.allclose(
            1e21 * hp_lal_data.real, 1e21 * hp_ml4gw.real.numpy(), atol=2e-3
        )
        assert np.allclose(
            1e21 * hp_lal_data.imag, 1e21 * hp_ml4gw.imag.numpy(), atol=2e-3
        )
        assert np.allclose(
            1e21 * hc_lal_data.real, 1e21 * hc_ml4gw.real.numpy(), atol=2e-3
        )
        assert np.allclose(
            1e21 * hc_lal_data.imag, 1e21 * hc_ml4gw.imag.numpy(), atol=2e-3
        )

        # test close (< 400 Mpc) waveforms  (O(1e-2) agreement)
        params["distance"] = (distance_close[i].item() * u.Mpc).to("m").value
        hp_lal, hc_lal = lalsimulation.SimInspiralChooseFDWaveform(**params)

        # reconstruct frequencies generated by
        # lal and filter based on fmin and fmax
        lal_freqs = np.array(
            [
                hp_lal.f0 + ii * hp_lal.deltaF
                for ii in range(len(hp_lal.data.data))
            ]
        )

        lal_mask = (lal_freqs > params["f_min"]) & (
            lal_freqs < params["f_max"]
        )

        lal_freqs = lal_freqs[lal_mask]
        torch_freqs = torch.tensor(lal_freqs, dtype=torch.float32)

        hc_ml4gw, hp_ml4gw = waveforms.IMRPhenomPv2()(
            torch_freqs,
            chirp_mass[i][None],
            mass_ratio[i][None],
            chi1x[i][None],
            chi1y[i][None],
            chi1z[i][None],
            chi2x[i][None],
            chi2y[i][None],
            chi2z[i][None],
            distance_close[i][None],
            phase[i][None],
            inclination[i][None],
            f_ref,
            torch.tensor([tc]),
        )

        hp_ml4gw = hp_ml4gw[0]
        hc_ml4gw = hc_ml4gw[0]

        hp_lal_data = hp_lal.data.data[lal_mask]
        hc_lal_data = hc_lal.data.data[lal_mask]

        assert np.allclose(
            1e21 * hp_lal_data.real, 1e21 * hp_ml4gw.real.numpy(), atol=2e-2
        )
        assert np.allclose(
            1e21 * hp_lal_data.imag, 1e21 * hp_ml4gw.imag.numpy(), atol=2e-2
        )
        assert np.allclose(
            1e21 * hc_lal_data.real, 1e21 * hc_ml4gw.real.numpy(), atol=2e-2
        )
        assert np.allclose(
            1e21 * hc_lal_data.imag, 1e21 * hc_ml4gw.imag.numpy(), atol=2e-2
        )

    # test batched outputs works as expected
    hc_ml4gw, hp_ml4gw = waveforms.IMRPhenomPv2()(
        torch_freqs,
        chirp_mass[-1][None].repeat(10),
        mass_ratio[-1][None].repeat(10),
        chi1x[-1][None].repeat(10),
        chi1y[-1][None].repeat(10),
        chi1z[-1][None].repeat(10),
        chi2x[-1][None].repeat(10),
        chi2y[-1][None].repeat(10),
        chi2z[-1][None].repeat(10),
        distance_close[-1][None].repeat(10),
        phase[-1][None].repeat(10),
        inclination[-1][None].repeat(10),
        f_ref,
        torch.tensor([tc]).repeat(10),
    )

    # check batch against lal
    assert np.allclose(
        1e21 * hp_lal_data.real, 1e21 * hp_ml4gw[0].real.numpy(), atol=2e-2
    )
    assert np.allclose(
        1e21 * hp_lal_data.imag, 1e21 * hp_ml4gw[0].imag.numpy(), atol=2e-2
    )
    assert np.allclose(
        1e21 * hc_lal_data.real, 1e21 * hc_ml4gw[0].real.numpy(), atol=2e-2
    )
    assert np.allclose(
        1e21 * hc_lal_data.imag, 1e21 * hc_ml4gw[0].imag.numpy(), atol=2e-2
    )

    # check batch against each other
    for i in range(9):
        assert np.allclose(
            1e21 * hp_ml4gw[0].real.numpy(),
            1e21 * hp_ml4gw[i + 1].real.numpy(),
            atol=1e-2,
        )
        assert np.allclose(
            1e21 * hp_ml4gw[0].imag.numpy(),
            1e21 * hp_ml4gw[i + 1].imag.numpy(),
            atol=1e-2,
        )
        assert np.allclose(
            1e21 * hc_ml4gw[0].real.numpy(),
            1e21 * hc_ml4gw[i + 1].real.numpy(),
            atol=1e-2,
        )
        assert np.allclose(
            1e21 * hc_ml4gw[0].imag.numpy(),
            1e21 * hc_ml4gw[i + 1].imag.numpy(),
            atol=1e-2,
        )
