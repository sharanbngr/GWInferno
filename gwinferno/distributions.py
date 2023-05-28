import jax.numpy as jnp
from jax.scipy.special import erf
from jax.scipy.special import gammaln

"""
=============================================
This file contains some functions copied from https://github.com/ColmTalbot/gwpopulation re-implemented with jax.numpy
=============================================
"""


def log_logistic_unit(x, x0):
    """
    log_logistic_unit soft truncate a distribution with the log logistic unit

    Args:
        x (array_like): input array to truncate
        x0 (float): value of array we want to apply a soft truncation to

    Returns:
        array_like: input array with the soft truncation at x0 applied
    """
    diff = x - x0
    return jnp.where(
        jnp.greater(diff, 0),
        -jnp.log1p(jnp.exp(-4 * diff)),
        4 * diff - jnp.log1p(jnp.exp(4 * diff)),
    )


def logistic_unit(x, x0, sgn=1, sc=4):
    """
    logistic_unit soft truncate a distribution with the logistic unit

    Args:
        x (array_like): input array to truncate
        x0 (float): value of array we want to apply a soft truncation to
        sgn (int, optional): Which side do we truncate on (1 for right, -1 for left). Defaults to 1.
        sc (int, optional): scale of truncation, where higher values is sharper. Defaults to 4.

    Returns:
        array_like: input array with the soft truncation at x0 applied
    """
    return 1.0 / (1.0 + jnp.exp(sgn * sc * (x - x0)))


def powerlaw_logit_pdf(xx, alpha, high, fall_off):
    """
    powerlaw_logit_pdf pdf of high mass soft truncation powerlaw:
        $$ p(x) \propto x^{\alpha}\Theta(x-x_\mathrm{min})\Theta(x_\mathrm{max}-x) $$

    Args:
        xx (array_like): points to evaluate pdf at
        alpha (float): power law index
        high (float): high end truncation bound
        fall_off (float): scale of logistic unit to truncate distribution

    Returns:
        array_like: pdf evaluated at xx
    """
    prob = jnp.power(xx, alpha) * logistic_unit(xx, high, sign=1.0, a=fall_off)
    return prob


def powerlaw_pdf(xx, alpha, low, high, floor=0.0):
    """
    powerlaw_pdf pdf of sharp truncated powerlaw:

    Args:
        xx (array_like): points to evaluate pdf at
        alpha (float): power law index
        low (float): low end truncation bound
        high (float): high end truncation bound
        floor (float, optional): lower bound of pdf (Defaults to 0.0)
    """
    prob = jnp.power(xx, alpha)
    return jnp.where(jnp.less(xx, low) | jnp.greater(xx, high), floor, prob)


def truncnorm_pdf(xx, mu, sig, low, high, log=False):
    """
    $$ p(x) \propto \mathcal{N}(x | \mu, \sigma)\Theta(x-x_\mathrm{min})\Theta(x_\mathrm{max}-x) $$
    """

    if log:
        prob = jnp.exp(-jnp.power(jnp.log(xx) - mu, 2) / (2 * sig**2))
        continuous_norm = 1 / (xx * sig * (2 * jnp.pi) ** 0.5)
        left_tail_cdf = 0.5 * (1 + erf((jnp.log(low) - mu) / (sig * (2**0.5))))
        right_tail_cdf = 0.5 * (1 + erf((jnp.log(high) - mu) / (sig * (2**0.5))))
        denom = right_tail_cdf - left_tail_cdf
    else:
        prob = jnp.exp(-jnp.power(xx - mu, 2) / (2 * sig**2))
        continuous_norm = 1 / (sig * (2 * jnp.pi) ** 0.5)
        left_tail_cdf = 0.5 * (1 + erf((low - mu) / (sig * (2**0.5))))
        right_tail_cdf = 0.5 * (1 + erf((high - mu) / (sig * (2**0.5))))
        denom = right_tail_cdf - left_tail_cdf

    norm = continuous_norm / denom
    return jnp.where(jnp.greater(xx, high) | jnp.less(xx, low), 0, prob * norm)


def ln_beta_fct(alpha, beta):
    """
    ln_beta_fct evaluate log beta fct (see: )

    Args:
        alpha (float): alpha shape parameter
        beta (float): beta shape parameter

    Returns:
        float: log Beta fct
    """
    return gammaln(alpha) + gammaln(beta) - gammaln(alpha + beta)


def betadist(xx, alpha, beta, scale=1.0, floor=0.0):
    """
    betadist pdf of Beta distribution evaluated at xx with optional max vale of scale:

    Args:
        xx (array_like): points to evaluate pdf at
        alpha (float): alpha shape parameter
        beta (float): beta shape parameter
        scale (float, optional): maximum value of support in Beta distribution. Defaults to 1.0.
        floor (float, optional): lower bound of pdf (Defaults to 0.0)

    Returns:
        array_like: pdf evaluated at xx
    """
    ln_beta = (alpha - 1) * jnp.log(xx) + (beta - 1) * jnp.log(scale - xx) - (alpha + beta - 1) * jnp.log(scale)
    ln_beta = ln_beta - ln_beta_fct(alpha, beta)
    return jnp.where(jnp.less_equal(xx, scale) & jnp.greater_equal(xx, 0), jnp.exp(ln_beta), floor)