"""
Module for estimating the condition number of sparse matrices.
"""

__author__ = "Thomas Guillod"
__copyright__ = "Thomas Guillod - Dartmouth College"
__license__ = "Mozilla Public License Version 2.0"

import os
import warnings

import numpy as np
import scipy.sparse as sps
import scipy.sparse.linalg as sla
import scilogger

# get a logger
LOGGER = scilogger.get_logger(__name__, "pypeec")


def _get_inverse_operator(mat, decomposition):
    """
    Get an inverse operator (with LU decomposition) for the provided matrix and the Hermitian matrix.
    """

    # get the function for the linear operator (original matrix)
    def fct_matvec(rhs):
        sol = decomposition.solve(rhs, trans="N")
        return sol

    # get the function for the linear operator (transposed matrix)
    def fct_rmatvec(rhs):
        sol = decomposition.solve(rhs, trans="H")
        return sol

    # assign linear operator for inversion
    op = sla.LinearOperator(mat.shape, matvec=fct_matvec, rmatvec=fct_rmatvec, dtype=np.complex128)

    return op


def _get_lu_decomposition(mat, library, pardiso_options):
    """Get an LU decomposition object for the provided matrix.

    Depending on ``library``, either SciPy SuperLU or PARDISO (via Pydiso)
    is used. The returned object must expose a ``solve(rhs, trans=...)``
    method compatible with ``scipy.sparse.linalg.splu``.
    """

    # Default: always-available SciPy SuperLU
    if library == "SuperLU" or library is None:
        LOGGER.debug("LU decomposition backend = SuperLU")
        # prevent problematic matrices to trigger warnings
        warnings.filterwarnings("error", module="scipy.sparse.linalg")
        return sla.splu(mat)

    if library == "PARDISO":
        LOGGER.debug("LU decomposition backend = PARDISO")

        try:
            import pydiso.mkl_solver as lib
        except ImportError as exc:
            raise RuntimeError("PARDISO requested for condition check, but pydiso.mkl_solver is not available") from exc

        # get options (reuse factorization PARDISO options when provided)
        if pardiso_options is None:
            pardiso_options = {"thread_pardiso": None, "thread_mkl": None}

        thread_pardiso = pardiso_options.get("thread_pardiso")
        thread_mkl = pardiso_options.get("thread_mkl")

        # find the number of threads (same convention as matrix_factorization)
        if isinstance(thread_pardiso, int) and thread_pardiso < 0:
            thread_pardiso = os.cpu_count() + thread_pardiso + 1
        if isinstance(thread_mkl, int) and thread_mkl < 0:
            thread_mkl = os.cpu_count() + thread_mkl + 1
        if thread_pardiso == 0:
            thread_pardiso = 1
        if thread_mkl == 0:
            thread_mkl = 1

        # set number of threads
        if thread_pardiso is not None:
            lib.set_mkl_pardiso_threads(thread_pardiso)
        if thread_mkl is not None:
            lib.set_mkl_threads(thread_mkl)

        # ensure proper sparse format
        mat_csr = mat.tocsr() if not sps.isspmatrix_csr(mat) else mat
        mat_csr_H = mat_csr.conjugate().transpose().tocsr()

        # build separate factorizations for A and A^H
        try:
            fact_N = lib.MKLPardisoSolver(mat_csr, factor=True, verbose=False)
            fact_H = lib.MKLPardisoSolver(mat_csr_H, factor=True, verbose=False)
        except Warning:
            raise RuntimeError("invalid factorization: PARDISO (condition check)") from None

        class _PardisoDecomposition:
            def solve(self, rhs, trans="N"):
                # Ensure RHS has the same dtype as the matrix to avoid
                # PardisoTypeConversionWarning and extra casting.
                rhs_arr = np.asarray(rhs, dtype=mat_csr.dtype)

                if trans == "N":
                    return fact_N.solve(rhs_arr)
                if trans in ("H", "C"):
                    return fact_H.solve(rhs_arr)
                raise ValueError("invalid transpose flag for PARDISO decomposition")

        return _PardisoDecomposition()

    raise ValueError("invalid LU backend for condition check: %s" % library)


def get_condition_matrix(mat, norm_options, library="SuperLU", pardiso_options=None):
    """
    Compute an estimate of the condition number (norm 1) of a sparse matrix.
    """

    # check shape
    nnz = mat.size
    (nx, ny) = mat.shape

    # get the options
    t_accuracy = norm_options["t_accuracy"]
    n_iter_max = norm_options["n_iter_max"]

    # display
    LOGGER.debug("matrix / size = (%d, %d)", nx, ny)
    LOGGER.debug("matrix / sparsity = %d", nnz)

    # check if the matrix is empty
    if (nx, ny) == (0, 0):
        return 0.0

    # get LU decomposition
    LOGGER.debug("compute LU decomposition")
    decomposition = _get_lu_decomposition(mat, library, pardiso_options)

    # get the inverse operator
    op = _get_inverse_operator(mat, decomposition)

    # compute the norm of the matrix inverse (estimate)
    LOGGER.debug("estimate norm of the inverse")
    nrm_inv = sla.onenormest(op, t=t_accuracy, itmax=n_iter_max)

    # compute the norm of the matrix (estimate)
    LOGGER.debug("estimate norm of the matrix")
    nrm_ori = sla.onenormest(mat, t=t_accuracy, itmax=n_iter_max)

    # compute an estimate of the condition
    LOGGER.debug("compute condition estimate")
    cond = nrm_ori * nrm_inv

    return cond
