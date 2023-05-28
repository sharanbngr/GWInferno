import jax.numpy as jnp
import numpy as np


class BasisSpline(object):
    def __init__(
        self,
        n_df,
        knots=None,
        interior_knots=None,
        xrange=(0, 1),
        k=4,
        proper=True,
        normalize=True,
    ):
        """
        Class to construct a basis spline (with the M-Spline basis)

        Args:
            n_df (int): number of degrees of freedom for the spline
            knots (array_like, optional): array of knots, if non-uniform knot placing is preferred.
                Defaults to None.
            interior_knots (array_like, optional): array of interior knots,
                if non-uniform knot placing is preferred. Defaults to None.
            xrange (tuple, optional): domain of spline. Defaults to (0, 1).
            k (int, optional): order of the spline +1, i.e. cubcic splines->k=4. Defaults to 4 (cubic spline).
            proper (bool, optional): flag to extend knots past boundaries (no stacking on bounds). Defaults to True.
            normalize (bool, optional): flag whether or not to numerically normalize the spline. Defaults to True.
        """
        self.order = k
        self.N = n_df
        self.xrange = xrange
        if knots is None:
            if interior_knots is None:
                interior_knots = np.linspace(*(0, 1), n_df - k + 2)
            if proper:
                dx = interior_knots[1] - interior_knots[0]
                knots = (xrange[1] - xrange[0]) * jnp.linspace(-dx * (k - 1), 1 + dx * (k - 1), len(interior_knots) + (k - 1) * 2)

            else:
                knots = np.append(
                    np.append(np.array([xrange[0]] * (k - 1)), interior_knots),
                    np.array([xrange[1]] * (k - 1)),
                )
        self.knots = knots
        self.interior_knots = (xrange[1] - xrange[0]) * interior_knots
        assert len(self.knots) == self.N + self.order

        self.normalize = normalize
        self.basis_vols = np.ones(self.N)
        if normalize:
            grid = jnp.linspace(*xrange, 1000)
            grid_bases = jnp.array(self.bases(grid))
            self.basis_vols = jnp.array([jnp.trapz(grid_bases[i, :], grid) for i in range(self.N)])

    def norm(self, coefs):
        """
        norm numerically normalizes the spline

        Args:
            coefs (array_like): coefficients for the basis components

        Returns:
            float: the normalization factor given the coefficients
        """
        n = 1.0 / jnp.sum(self.basis_vols * coefs.flatten()) if self.normalize else 1.0
        return n

    def _basis(self, xs, i, k):
        """
        _basis protected method that computes the ith basis compoentn of order k recursively using
            the Cox-de Boor recursion relation

        Args:
            xs (array_like): input values to evaluate the basis spline at
            i (int): the ith basis component
            k (int): order of the spline

        Returns:
            array_like: the ith basis component of order k evaluated at xs
        """
        if self.knots[i + k] - self.knots[i] < 1e-6:
            return np.zeros_like(xs)
        elif k == 1:
            v = np.zeros_like(xs)
            v[(xs >= self.knots[i]) & (xs < self.knots[i + 1])] = 1 / (self.knots[i + 1] - self.knots[i])
            return v
        else:
            v = (xs - self.knots[i]) * self._basis(xs, i, k - 1) + (self.knots[i + k] - xs) * self._basis(xs, i + 1, k - 1)
            return (v * k) / ((k - 1) * (self.knots[i + k] - self.knots[i]))

    def _bases(self, xs):
        """
        _bases construct the set of basis components

        Args:
            xs (array_like): input values to evaluate the basis spline at

        Returns:
            list: list of all N basis components evaluated at xs
        """
        return [self._basis(xs, i, k=self.order) for i in range(self.N)]

    def bases(self, xs):
        """
        bases form the basis spline design matrix evaluated at xs

        Args:
            xs (array_like): input values to evaluate the basis spline at

        Returns:
            array_like: the design matrix evaluated at xs. shape (N, *xs.shape)
        """
        return jnp.concatenate(self._bases(xs)).reshape(self.N, *xs.shape)

    def get_coefficients(self, xs, ys):
        """
        computes the coefficients of the basis components given data 1-D data (xs, ys)

        Args:
            xs (array_like): The x values of data
            ys (array_like): The y values of data

        Returns:
            the coefficients (array_like), interpolated y-values evaluated at xs (array_like),
            the design matrix evaluated at xs with shape (N, *xs.shape)
        """

        design_matrix = jnp.transpose(self.bases(xs))
        BtBi = jnp.linalg.inv(jnp.matmul(jnp.transpose(design_matrix), design_matrix))
        alpha = jnp.matmul(jnp.matmul(BtBi, jnp.transpose(design_matrix)), ys)
        return alpha, np.einsum("ji,i->j", design_matrix, alpha), design_matrix

    def project(self, bases, coefs):
        """
        project given a design matrix (or bases) and coefficients, project the coefficients onto the spline

        Args:
            bases (array_like): The set of basis components or design matrix to project onto
            coefs (array_like): coefficients for the basis components

        Returns:
            array_like: The linear combination of the basis components given the coefficients
        """
        coefs /= jnp.sum(coefs)
        return jnp.einsum("i...,i->...", bases, coefs) * self.norm(coefs)

    def eval(self, xs, coefs):
        """
        eval Evalulate basis spline at xs given coefficients

        Args:
            xs (array_like): input values to evaluate the basis spline at
            coefs (array_like): coefficients for the basis components

        Returns:
            array_like: The linear combination of the basis components evaluated at xs given the coefficients
        """
        return self.project(self.bases(xs), coefs)

    def __call__(self, xs, coefs):
        """
        __call__ Evalulate basis spline at xs given coefficients

        Args:
            xs (array_like): input values to evaluate the basis spline at
            coefs (array_like): coefficients for the basis components

        Returns:
            array_like: The linear combination of the basis components evaluated at xs given the coefficients
        """
        return self.eval(xs, coefs)


class BSpline(BasisSpline):
    def __init__(
        self,
        n_df,
        knots=None,
        interior_knots=None,
        xrange=(0, 1),
        k=4,
        proper=True,
        normalize=False,
    ):
        """
        Class to construct a basis spline (B-Spline)

        Args:
            n_df (int): number of degrees of freedom for the spline
            knots (array_like, optional): array of knots, if non-uniform knot placing is preferred.
                Defaults to None.
            interior_knots (array_like, optional): array of interior knots,
                if non-uniform knot placing is preferred. Defaults to None.
            xrange (tuple, optional): domain of spline. Defaults to (0, 1).
            k (int, optional): order of the spline +1, i.e. cubcic splines->k=4. Defaults to 4 (cubic spline).
            proper (bool, optional): flag to extend knots past boundaries (no stacking on bounds). Defaults to True.
            normalize (bool, optional): flag whether or not to numerically normalize the spline. Defaults to False.
        """
        super().__init__(
            n_df=n_df,
            knots=knots,
            interior_knots=interior_knots,
            xrange=xrange,
            k=k,
            proper=proper,
            normalize=normalize,
        )

    def _bases(self, xs):
        """
        _bases construct the set of basis components for the canonical B-Spline with the Cox-de Boor recursion relation

        Args:
            xs (array_like): input values to evaluate the basis spline at

        Returns:
            list: list of all N basis components evaluated at xs
        """
        return [(self.knots[i + self.order] - self.knots[i]) / self.order * self._basis(xs, i, k=self.order) for i in range(self.N)]

    def project(self, bases, coefs):
        """
        project given a design matrix (or bases) and coefficients, project the coefficients onto the spline

        Args:
            bases (array_like): The set of basis components or design matrix to project onto
            coefs (array_like): coefficients for the basis components

        Returns:
            array_like: The linear combination of the basis components given the coefficients
        """
        return jnp.einsum("i...,i->...", bases, coefs) * self.norm(coefs)


class LogXBSpline(BSpline):
    def __init__(self, n_df, knots=None, interior_knots=None, xrange=(0.01, 1), normalize=True, **kwargs):
        """
        Class to construct a basis spline (B-Spline) in the log space of the domain (X)

        Args:
            n_df (int): number of degrees of freedom for the spline
            knots (array_like, optional): array of knots, if non-uniform knot placing is preferred.
                Defaults to None.
            interior_knots (array_like, optional): array of interior knots,
                if non-uniform knot placing is preferred. Defaults to None.
            xrange (tuple, optional): domain of spline. Defaults to (0.01, 1).
            k (int, optional): order of the spline +1, i.e. cubcic splines->k=4. Defaults to 4 (cubic spline).
            proper (bool, optional): flag to extend knots past boundaries (no stacking on bounds). Defaults to True.
            normalize (bool, optional): flag whether or not to numerically normalize the spline. Defaults to True.
        """
        knots = None if knots is None else np.log(knots)
        interior_knots = None if interior_knots is None else np.log(interior_knots)
        xrange = np.log(xrange)
        super().__init__(n_df, knots=knots, interior_knots=interior_knots, xrange=xrange, **kwargs)

        self.normalize = normalize
        self.basis_vols = np.ones(self.N)
        if normalize:
            self.grid = jnp.linspace(*np.exp(xrange), 1000)
            self.grid_bases = jnp.array(self.bases(self.grid))

    def bases(self, xs):
        """
        bases form the basis spline design matrix evaluated at xs (in log space)

        Args:
            xs (array_like): input values to evaluate the basis spline at

        Returns:
            array_like: the design matrix evaluated at xs. shape (N, *xs.shape)
        """
        return super().bases(jnp.log(xs))


class LogYBSpline(BSpline):
    def __init__(self, n_df, knots=None, interior_knots=None, xrange=(0, 1), normalize=True, **kwargs):
        """
        Class to construct a basis spline (B-Spline) in the log space of the range (Y)

        Args:
            n_df (int): number of degrees of freedom for the spline
            knots (array_like, optional): array of knots, if non-uniform knot placing is preferred.
                Defaults to None.
            interior_knots (array_like, optional): array of interior knots,
                if non-uniform knot placing is preferred. Defaults to None.
            xrange (tuple, optional): domain of spline. Defaults to (0, 1).
            k (int, optional): order of the spline +1, i.e. cubcic splines->k=4. Defaults to 4 (cubic spline).
            proper (bool, optional): flag to extend knots past boundaries (no stacking on bounds). Defaults to True.
            normalize (bool, optional): flag whether or not to numerically normalize the spline. Defaults to True.
        """
        super().__init__(n_df, knots=knots, interior_knots=interior_knots, xrange=xrange, **kwargs)
        self.normalize = normalize
        if normalize:
            self.grid = jnp.linspace(*xrange, 1000)
            self.grid_bases = jnp.array(self.bases(self.grid))

    def _project(self, bases, coefs):
        """
        _project given a design matrix (or bases) and coefficients, project the coefficients onto the spline

        Args:
            bases (array_like): The set of basis components or design matrix to project onto
            coefs (array_like): coefficients for the basis components

        Returns:
            array_like: The linear combination of the basis components given the coefficients
        """
        return jnp.exp(jnp.einsum("i...,i->...", bases, coefs))

    def project(self, bases, coefs):
        """
        project given a design matrix (or bases) and coefficients, project the coefficients onto the spline with normalization

        Args:
            bases (array_like): The set of basis components or design matrix to project onto
            coefs (array_like): coefficients for the basis components

        Returns:
            array_like: The linear combination of the basis components given the coefficients
        """
        return self._project(bases, coefs) * self.norm(coefs)

    def norm(self, coefs):
        """
        norm numerically normalizes the spline

        Args:
            coefs (array_like): coefficients for the basis components

        Returns:
            float: the normalization factor given the coefficients
        """
        n = 1.0 / jnp.trapz(self._project(self.grid_bases, coefs), self.grid) if self.normalize else 1.0
        return n


class LogXLogYBSpline(LogYBSpline):
    def __init__(self, n_df, knots=None, interior_knots=None, xrange=(0.1, 1), normalize=True, **kwargs):
        """
        Class to construct a basis spline (B-Spline) in the log-log space of the domain and range (X and Y)

        Args:
            n_df (int): number of degrees of freedom for the spline
            knots (array_like, optional): array of knots, if non-uniform knot placing is preferred.
                Defaults to None.
            interior_knots (array_like, optional): array of interior knots,
                if non-uniform knot placing is preferred. Defaults to None.
            xrange (tuple, optional): domain of spline. Defaults to (0.01, 1).
            k (int, optional): order of the spline +1, i.e. cubcic splines->k=4. Defaults to 4 (cubic spline).
            proper (bool, optional): flag to extend knots past boundaries (no stacking on bounds). Defaults to True.
            normalize (bool, optional): flag whether or not to numerically normalize the spline. Defaults to True.
        """
        knots = None if knots is None else np.log(knots)
        interior_knots = None if interior_knots is None else np.log(interior_knots)
        xrange = np.log(xrange)
        super().__init__(n_df, knots=knots, interior_knots=interior_knots, xrange=xrange, **kwargs)

        self.normalize = normalize
        self.basis_vols = np.ones(self.N)
        if normalize:
            self.grid = jnp.linspace(*jnp.exp(xrange), 1500)
            self.grid_bases = jnp.array(self.bases(self.grid))

    def bases(self, xs):
        """
        bases form the basis spline design matrix evaluated at xs (in log space)

        Args:
            xs (array_like): input values to evaluate the basis spline at

        Returns:
            array_like: the design matrix evaluated at xs. shape (N, *xs.shape)
        """
        return super().bases(jnp.log(xs))

    def project(self, bases, coefs):
        """
        project given a design matrix (or bases) and coefficients, project the coefficients onto the spline with normalization

        Args:
            bases (array_like): The set of basis components or design matrix to project onto
            coefs (array_like): coefficients for the basis components

        Returns:
            array_like: The linear combination of the basis components given the coefficients
        """
        return self._project(bases, coefs) * self.norm(coefs)


class RectBivariateBasisSpline(object):
    def __init__(
        self,
        xdf,
        ydf,
        xrange=(0, 1),
        yrange=(0, 1),
        kx=4,
        ky=4,
        xbasis=BSpline,
        ybasis=BSpline,
        normalize=True,
    ):
        """
        Class to construct a 2D (bivariate) rectangular basis spline

        Args:
            xdf (int): number of degrees of freedom for the spline in the X direction
            ydf (int): number of degrees of freedom for the spline in the Y direction
            xrange (tuple, optional): domain of X spline. Defaults to (0, 1).
            yrange (tuple, optional): domain of Y spline. Defaults to (0, 1).
            kx (int, optional): order of the X spline +1, i.e. cubcic splines->k=4. Defaults to 4 (cubic spline).
            ky (int, optional): order of the Y spline +1, i.e. cubcic splines->k=4. Defaults to 4 (cubic spline).
            xbasis (object, optional): Choice of basis to use for the X spline. Defaults to BSpline.
            ybasis (object, optional): Choice of basis to use for the Y spline. Defaults to BSpline.
            normalize (bool, optional): flag whether or not to numerically normalize the spline. Defaults to True.
        """
        self.xdf = xdf
        self.ydf = ydf
        self.x_interpolator = xbasis(xdf, xrange=xrange, k=kx, normalize=False)
        self.y_interpolator = ybasis(ydf, xrange=yrange, k=ky, normalize=False)
        self.normalize = normalize
        self.x_bases = None
        self.y_bases = None
        if self.normalize:
            self.gridx = jnp.linspace(*xrange, 750)
            self.gridy = jnp.linspace(*yrange, 750)
            self.gxx, self.gyy = jnp.meshgrid(self.gridx, self.gridy)
            self.grid_bases = self.bases(self.gxx, self.gyy)

    def norm_2d(self, coefs):
        """
        norm_2d numerically normalizes the 2D spline

        Args:
            coefs (array_like): coefficients for the basis components

        Returns:
            float: the normalization factor given the coefficients
        """
        n = 1.0 / jnp.trapz(jnp.trapz(self._project(self.grid_bases, coefs), self.gridy), self.gridx) if self.normalize else 1.0
        return n

    def _reset_bases(self):
        self.x_bases = None
        self.y_bases = None

    def bases(self, xs, ys):
        """
        bases form the basis spline design matrix evaluated at xs and ys

        Args:
            xs (array_like): input values to evaluate the X basis spline at
            xs (array_like): input values to evaluate the Y basis spline at

        Returns:
            array_like: the design matrix evaluated at xs. shape (xdf, ydf, *xs.shape)
        """
        self.x_bases = self.x_interpolator.bases(xs)
        self.y_bases = self.y_interpolator.bases(ys)
        out = jnp.array([[self.x_bases[i] * self.y_bases[j] for i in range(self.xdf)] for j in range(self.ydf)]).reshape(
            self.xdf, self.ydf, *xs.shape
        )
        self.reset_bases()
        return out

    def _project(self, bases, coefs):
        """
        _project given a design matrix (or bases) and coefficients, project the coefficients onto the spline

        Args:
            bases (array_like): The set of basis components or design matrix to project onto
            coefs (array_like): coefficients for the basis components

        Returns:
            array_like: The linear combination of the basis components given the coefficients
        """
        return jnp.exp(jnp.einsum("ij...,ij->...", bases, coefs))

    def project(self, bases, coefs):
        """
        project given a design matrix (or bases) and coefficients, project the coefficients onto the spline with normalization

        Args:
            bases (array_like): The set of basis components or design matrix to project onto
            coefs (array_like): coefficients for the basis components

        Returns:
            array_like: The linear combination of the basis components given the coefficients
        """
        return self._project(bases, coefs) * self.norm_2d(coefs)