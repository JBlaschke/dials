"""
Definition of the target function for error model minimisation.
"""

from __future__ import absolute_import, division, print_function
from dials.array_family import flex


def calculate_regression_x_y(Ih_table):
    """Calculate regression data points."""
    n = Ih_table.group_multiplicities() - 1.0
    group_variances = (
        (Ih_table.intensities - (Ih_table.inverse_scale_factors * Ih_table.Ih_values))
        ** 2
        * Ih_table.h_index_matrix
    ) / n
    sigmasq_obs = group_variances * Ih_table.h_expand_matrix
    isq = Ih_table.intensities ** 2
    y = sigmasq_obs / isq
    x = Ih_table.variances / isq
    return x, y


class ErrorModelTarget(object):

    """Error model target for finding slope of norm distribution.
    (i.e. the 'a' parameter of the basic error model)"""

    _grad_names = ["d(deltahl)_dp"]
    rmsd_names = ["RMSD_deltahl"]
    rmsd_units = ["a.u"]

    def __init__(self, error_model):
        self.error_model = error_model
        # intercept + gradient
        # Quantities to cache each step
        self._rmsds = None

    def predict(self, apm):
        """Do the next step of the prediction."""
        pass

    def get_num_matches(self):
        """Get the number of reflections."""
        return self.error_model.n_refl

    def rmsds(self, apm):
        """calculate unweighted RMSDs for the matches"""
        # cache rmsd calculation for achieved test
        R = self.calculate_residuals(apm)
        n = R.size()
        R.extend(flex.double([self.compute_restraints_functional_gradients(apm)[0]]))
        self._rmsds = [(flex.sum(R) / n) ** 0.5]
        return self._rmsds

    def achieved(self):
        """Method required for refinement engine."""
        return False  # implement a method here?

    # The following methods are for adaptlbfgs.
    def compute_functional_gradients(self, apm):
        """Compute the functional and gradients vector."""
        return flex.sum(self.calculate_residuals(apm)), self.calculate_gradients(apm)

    def compute_restraints_functional_gradients(self, _):
        """Compute the restraints for the functional and gradients."""
        return [0.0, 0.0]


class ErrorModelTargetRegression(ErrorModelTarget):
    def __init__(self, error_model):
        super(ErrorModelTargetRegression, self).__init__(error_model)
        # calculate variances needed for minimisation.
        self.x, self.y = calculate_regression_x_y(self.error_model.filtered_Ih_table)
        self.n_refl = self.y.size()

    def calculate_residuals(self, apm):
        """Return the residual vector"""
        params = apm.x
        if apm.active_parameters == ["a"]:
            assert len(params) == 1
            # if only a being refined, the R = y - xo*x - xo*b2
            b = self.error_model.parameters[1]
            R = (self.y - (params[0] * self.x) - params[0] * (b ** 2)) ** 2
        elif apm.active_parameters == ["b"]:
            assert len(params) == 1
            a = self.error_model.parameters[0]
            # R = y - a^2*x - a^2*xo
            R = (self.y - (a ** 2 * self.x) - (a ** 2 * params[0])) ** 2
        else:
            # R = y - xo*x - x1
            R = (self.y - (params[0] * self.x) - params[1]) ** 2
        return R

    def calculate_gradients(self, apm):
        "calculate the gradient vector"
        params = apm.x
        if apm.active_parameters == ["a"]:
            b = self.error_model.parameters[1]
            R = self.y - (params[0] * self.x) - params[0] * (b ** 2)
            gradient = flex.double([-2.0 * flex.sum(R * (self.x + (b ** 2)))])
        elif apm.active_parameters == ["b"]:
            a = self.error_model.parameters[0]
            R = self.y - (a ** 2 * self.x) - (a ** 2 * params[0])
            gradient = flex.double([-2.0 * flex.sum(R * (a ** 2))])
        else:
            R = self.y - (params[0] * self.x) - params[1]
            gradient = flex.double([-2.0 * flex.sum(R * self.x), -2.0 * flex.sum(R)])
        return gradient


class ErrorModelTargetA(ErrorModelTarget):

    """Target to minimise the 'a' component of the basic error model."""

    def calculate_residuals(self, apm):
        """Return the residual vector"""
        x = apm.x
        R = (self.error_model.sortedy - (x[1] * self.error_model.sortedx) - x[0]) ** 2
        return R

    def calculate_gradients(self, apm):
        "calculate the gradient vector"
        x = apm.x
        R = self.error_model.sortedy - (x[1] * self.error_model.sortedx) - x[0]
        gradient = flex.double(
            [-2.0 * flex.sum(R), -2.0 * flex.sum(R * self.error_model.sortedx)]
        )
        return gradient


class ErrorModelTargetB(ErrorModelTarget):

    """Target to minimise the 'b' component of the basic error model.

    Uses the binner to calculate residuals, gradients"""

    def predict(self, _):
        """Do the next step of the prediction."""
        self.error_model.binner.update(self.error_model.parameters)

    def calculate_residuals(self, _):
        """Return the residual vector"""
        bin_vars = self.error_model.binner.bin_variances
        R = (
            (
                (flex.double(bin_vars.size(), 0.5) - bin_vars) ** 2
                + (1.0 / bin_vars)
                - flex.double(bin_vars.size(), 1.25)
            )
            * self.error_model.binner.weights
            / flex.sum(self.error_model.binner.weights)
        )
        return R

    def calculate_gradients(self, apm):
        "calculate the gradient vector"
        a = self.error_model.components["a"].parameters[0]
        b = apm.x[0]
        Ih_table = self.error_model.binner.Ih_table
        I_hl = Ih_table.intensities
        g_hl = Ih_table.inverse_scale_factors
        weights = self.error_model.binner.weights
        bin_vars = self.error_model.binner.bin_variances
        sum_matrix = self.error_model.binner.summation_matrix
        bin_counts = self.error_model.binner.binning_info["refl_per_bin"]
        dsig_dc = (
            b
            * (I_hl ** 2)
            * (a ** 2)
            / (self.error_model.binner.sigmaprime * (g_hl ** 2))
        )
        ddelta_dsigma = (
            -1.0 * self.error_model.binner.delta_hl / self.error_model.binner.sigmaprime
        )
        deriv = ddelta_dsigma * dsig_dc
        dphi_by_dvar = -2.0 * (
            flex.double(bin_vars.size(), 0.5)
            - bin_vars
            + (1.0 / (2.0 * (bin_vars ** 2)))
        )
        term1 = 2.0 * self.error_model.binner.delta_hl * deriv * sum_matrix
        term2a = self.error_model.binner.delta_hl * sum_matrix
        term2b = deriv * sum_matrix
        grad = dphi_by_dvar * (
            (term1 / bin_counts) - (2.0 * term2a * term2b / (bin_counts ** 2))
        )
        gradients = flex.double([flex.sum(grad * weights) / flex.sum(weights)])
        return gradients
