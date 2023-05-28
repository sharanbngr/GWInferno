import jax.numpy as jnp
import numpy as np

from ..distributions import powerlaw_pdf
from ..interpolation import BSpline
from ..interpolation import LogXBSpline
from .gwpopulation.gwpopulation import PowerlawRedshiftModel


class PowerlawBasisSplinePrimaryPowerlawRatio(object):
    def __init__(self, nknots, m1pe, m1inj, mmin=3, m2min=3, mmax=100, k=4, basis=BSpline, **kwargs):
        """
        __init__ _summary_

        Args:
            nknots (int): Number of knots used to create the B-Spline.
            m1pe (_type_): m1's parameter estimation.
            m1inj (_type_): m1's injection.
            mmin (int, optional): Minimum primary mass distribution cutoff. Defaults to 3.
            m2min (int, optional): _description_. Defaults to 3.
            mmax (int, optional): Maximum primary mass distribution cutoff. Defaults to 100.
            k (int, optional): _description_. Defaults to 4.
            basis (_type_, optional): _description_. Defaults to BSpline.
        """
        self.m2min = m2min
        self.nknots = nknots
        self.mmin = mmin
        self.mmax = mmax
        self.ms = jnp.linspace(mmin, mmax, 1000)
        self.nknots = nknots
        interior_knots = np.linspace(np.log(mmin), np.log(mmax), nknots - k + 2)
        dx = interior_knots[1] - interior_knots[0]
        knots = np.concatenate(
            [
                np.log(mmin) - dx * np.arange(1, k)[::-1],
                interior_knots,
                np.log(mmax) + dx * np.arange(1, k),
            ]
        )
        self.knots = knots
        self.interpolator = basis(nknots, knots=knots, interior_knots=interior_knots, xrange=(np.log(mmin), np.log(mmax)), k=4, **kwargs)
        self.pe_design_matrix = jnp.array(self.interpolator.bases(np.log(m1pe)))
        self.inj_design_matrix = jnp.array(self.interpolator.bases(np.log(m1inj)))
        self.dmats = [self.inj_design_matrix, self.pe_design_matrix]
        self.norm_design_matrix = jnp.array(self.interpolator.bases(np.log(self.ms)))

    def smoothing(self, ms, mmin, delta_m):
        sm = ms - mmin
        smoothing_region = jnp.greater(sm, 0) & jnp.less(sm, delta_m)
        window = jnp.where(
            smoothing_region,
            1.0 / (jnp.exp(delta_m / sm + delta_m / (sm - delta_m)) + 1.0),
            1,
        )
        window = jnp.where(jnp.isinf(window) | jnp.isnan(window), 1, window)
        return jnp.where(jnp.less_equal(ms, mmin), 0, window)

    def p_m1(self, m1, alpha, mmin, mmax, cs):
        p_m = powerlaw_pdf(m1, alpha=-alpha, low=mmin, high=mmax)
        ndim = len(m1.shape)
        perturbation = jnp.exp(self.interpolator.project(self.dmats[ndim - 1], cs))
        norm = self.norm_p_m1(alpha=alpha, mmin=mmin, mmax=mmax, cs=cs)
        return p_m * perturbation / norm

    def norm_p_m1(self, alpha, mmin, mmax, cs):
        p_m = powerlaw_pdf(self.ms, alpha=-alpha, low=mmin, high=mmax)
        perturbation = jnp.exp(self.interpolator.project(self.norm_design_matrix, cs))
        return jnp.trapz(y=p_m * perturbation, x=self.ms)

    def p_q(self, q, m1, beta):
        p_q = powerlaw_pdf(q, alpha=beta, low=self.m2min / m1, high=1)
        return p_q

    def __call__(self, m1, q, **kwargs):
        beta = kwargs.pop("beta")
        p_m1 = self.p_m1(m1, **kwargs)
        p_q = self.p_q(q, m1, beta=beta)
        return p_m1 * p_q


class PowerlawBasisSplinePrimaryRatio(object):
    def __init__(self, nknots, qknots, m1pe, qpe, m1inj, qinj, mmin=2, mmax=100, k=4):
        self.nknots = nknots
        self.mmin = mmin
        self.mmax = mmax
        self.ms = jnp.linspace(mmin, mmax, 1000)
        self.qs = jnp.linspace(mmin / mmax, 1, 500)
        self.nknots = nknots
        self.qknots = qknots
        self.mm, self.qq = jnp.meshgrid(self.ms, self.qs)
        interior_knots = np.linspace(np.log(mmin), np.log(mmax), nknots - k + 2)
        dx = interior_knots[1] - interior_knots[0]
        knots = np.concatenate(
            [
                np.log(mmin) - dx * np.arange(1, k)[::-1],
                interior_knots,
                np.log(mmax) + dx * np.arange(1, k),
            ]
        )
        self.knots = knots
        interior_qknots = np.linspace(0, 1, qknots - k + 2)
        dxq = interior_qknots[1] - interior_qknots[0]
        knotsq = np.concatenate(
            [
                -dxq * np.arange(1, k)[::-1],
                interior_qknots,
                1 + dxq * np.arange(1, k),
            ]
        )
        self.knotsq = knotsq

        self.interpolator = BSpline(
            nknots,
            knots=knots,
            interior_knots=interior_knots,
            xrange=(np.log(mmin), np.log(mmax)),
            k=4,
        )
        self.pe_design_matrix = jnp.array(self.interpolator.bases(np.log(m1pe)))
        self.inj_design_matrix = jnp.array(self.interpolator.bases(np.log(m1inj)))
        self.dmats = [self.inj_design_matrix, self.pe_design_matrix]
        self.qinterpolator = BSpline(
            qknots,
            knots=knotsq,
            interior_knots=interior_qknots,
            xrange=(0, 1),
            k=4,
        )
        self.qpe_design_matrix = jnp.array(self.qinterpolator.bases(qpe))
        self.qinj_design_matrix = jnp.array(self.qinterpolator.bases(qinj))
        self.qdmats = [self.qinj_design_matrix, self.qpe_design_matrix]
        self.qshapes = [(self.qknots, 1), (self.qknots, 1, 1)]
        self.norm_design_matrix = jnp.array(self.interpolator.bases(np.log(self.mm)))
        self.qnorm_design_matrix = jnp.array(self.qinterpolator.bases(self.qq))

    def p_m1(self, m1, alpha, mmin, mmax, cs):
        p_m = powerlaw_pdf(m1, alpha=-alpha, low=mmin, high=mmax)
        ndim = len(m1.shape)
        perturbation = jnp.exp(self.interpolator.project(self.dmats[ndim - 1], cs))
        return p_m * perturbation

    def norm_pm1q(self, alpha, mmin, mmax, cs, beta, vs):
        p_m = powerlaw_pdf(self.mm, alpha=-alpha, low=mmin, high=mmax)
        perturbation = jnp.exp(self.interpolator.project(self.norm_design_matrix, cs))
        p_q = powerlaw_pdf(self.qq, alpha=beta, low=mmin / self.mm, high=1)
        qperturbation = jnp.exp(self.qinterpolator.project(self.qnorm_design_matrix, vs))
        p_mq = p_m * perturbation * p_q * qperturbation
        return jnp.trapz(jnp.trapz(p_mq, self.qs, axis=0), self.ms)

    def p_q(self, q, m1, beta, mmin, vs):
        p_q = powerlaw_pdf(q, alpha=beta, low=mmin / m1, high=1)
        ndim = len(q.shape)
        perturbation = jnp.exp(self.qinterpolator.project(self.qdmats[ndim - 1], vs))
        return p_q * perturbation

    def __call__(self, m1, q, **kwargs):
        beta = kwargs.pop("beta")
        mmin = kwargs.pop("mmin", self.mmin)
        vs = kwargs.pop("vs")
        p_m1 = self.p_m1(m1, mmin=mmin, **kwargs)
        p_q = self.p_q(q, m1, beta=beta, mmin=mmin, vs=vs)
        norm = self.norm_pm1q(beta=beta, mmin=mmin, vs=vs, **kwargs)
        return p_m1 * p_q / norm


class PowerlawSplineRedshiftModel(PowerlawRedshiftModel):
    def __init__(self, nknots, z_pe, z_inj, basis=LogXBSpline):
        super().__init__(z_pe=z_pe, z_inj=z_inj)
        self.nknots = nknots
        self.interpolator = basis(nknots, xrange=(self.zmin, self.zmax), k=4, normalize=False)
        self.pe_design_matrix = jnp.array(self.interpolator.bases(z_pe))
        self.inj_design_matrix = jnp.array(self.interpolator.bases(z_inj))
        self.dmats = [self.inj_design_matrix, self.pe_design_matrix]
        self.norm_design_matrix = jnp.array(self.interpolator.bases(self.zs))

    def normalization(self, lamb, cs):
        pz = self.dVdc_ * jnp.power(1.0 + self.zs, lamb - 1)
        pz *= jnp.exp(self.interpolator.project(self.norm_design_matrix, cs))
        return jnp.trapz(pz, self.zs)

    def prob(self, z, dVdc, lamb, cs):
        ndim = len(z.shape)
        return dVdc * jnp.power(1.0 + z, lamb - 1.0) * jnp.exp(self.interpolator.project(self.dmats[ndim - 1], cs))

    def __call__(self, z, lamb, cs):
        ndim = len(z.shape)
        dVdc = self.dVdcs[ndim - 1]
        return jnp.where(
            jnp.less_equal(z, self.zmax),
            self.prob(z, dVdc, lamb, cs) / self.normalization(lamb, cs),
            0,
        )