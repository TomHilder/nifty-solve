import matplotlib.pyplot as plt
import finufft
import numpy as np
import numpy.typing as npt
from pylops import LinearOperator, Diagonal
from typing import Optional, Union

from nifty_solve.operators import expand_to_dim, Finufft1DRealOperator

class FinufftOperator(LinearOperator):
   def __init__(self, *points, n_modes: Union[int, tuple[int]], **kwargs):
      if len(set(map(len, points))) != 1:
         raise ValueError("All point arrays must have the same length.")
      self.n_modes = expand_to_dim(n_modes, len(points))

      if points[0].dtype == np.float64:
         self.DTYPE_REAL, self.DTYPE_COMPLEX = (np.float64, np.complex128)
      else:
         self.DTYPE_REAL, self.DTYPE_COMPLEX = (np.float32, np.complex64)

      super().__init__(dtype=self.DTYPE_REAL, shape=(len(points[0]), int(np.prod(self.n_modes))))
      self.explicit = False
      kwds = dict(
         n_modes_or_dim=self.n_modes,
         n_trans=1,
         eps=1e-6,
         isign=None,
         dtype=self.DTYPE_COMPLEX.__name__,
         modeord=0
      )
      kwds.update(kwargs)
      self._plan_matvec = finufft.Plan(2, **kwds)
      self._plan_rmatvec = finufft.Plan(1, **kwds)
      self._plan_matvec.setpts(*points)
      self._plan_rmatvec.setpts(*points)
      return None

   def _matvec(self, c):
      return self._plan_matvec.execute(c.astype(self.DTYPE_COMPLEX))

   def _rmatvec(self, f):
      return self._plan_rmatvec.execute(f.astype(self.DTYPE_COMPLEX))


def design_matrix_as_is(xs, P):
   X = np.ones_like(xs).reshape(len(xs), 1)
   for j in range(1, P):
      if j % 2 == 0:
         X = np.concatenate((X, np.cos(j * xs)[:, None]), axis=1)
      else:
         X = np.concatenate((X, np.sin((j + 1) * xs)[:, None]), axis=1)
   return X



x = np.linspace(0, 2 * np.pi, 100)

for P in (6, 7):

   A = FinufftOperator(x, n_modes=P)
   A_dense = A.todense()

   A_local = design_matrix_as_is(x/2, P)

   A_real = Finufft1DRealOperator(x, n_modes=P).todense()

   fig, (ax_real, ax_imag, ax_comp, ax_real_only) = plt.subplots(1, 4, figsize=(10, 5))

   for i, mode in enumerate(A_dense.T):
      ax_real.plot(x, mode.real/2 + i, label=f"mode {i}")
      ax_imag.plot(x, mode.imag/2 + i, label=f"mode {i}")
      for ax in (ax_real, ax_imag):
         ax.axhline(i, c="#666666", lw=0.5)

   # re-order the modes as we expect them to be
   local_mode_indices = np.hstack([0, (np.tile(np.arange(1, P // 2 + 1), 2).reshape((2, -1)).T* np.array([-1, 1])).flatten()[:P-1]])
   finufft_mode_indices = np.arange(-P // 2 + 1, P//2 + 1)

   for i, mode in enumerate(A_local[:, np.argsort(local_mode_indices)].T):
      ax_comp.plot(x, mode/2 + i, label=f"mode {i}")
      ax_comp.axhline(i, c="#666666", lw=0.5)


   for i, mode in enumerate(A_real.T):
      ax_real_only.plot(x, mode/2 + i, label=f"mode {i}")
      ax_real_only.axhline(i, c="#666666", lw=0.5)


   ax_real.set_title("Real")
   ax_imag.set_title("Imag")
   ax_comp.set_title("Hogg DM (re-ordered)")
   ax_real_only.set_title("Finufft1DRealOperator")
   fig.savefig(f"check_design_matrix_P_{P}.png")


# Extend to 2D

class Finufft2DOperator(LinearOperator):
    def __init__(self, *points, n_modes: Union[int, tuple[int]], **kwargs):
        if len(set(map(len, points))) != 1:
            raise ValueError("All point arrays must have the same length.")
        self.n_modes = expand_to_dim(n_modes, len(points))

        if points[0].dtype == np.float64:
            self.DTYPE_REAL, self.DTYPE_COMPLEX = (np.float64, np.complex128)
        else:
            self.DTYPE_REAL, self.DTYPE_COMPLEX = (np.float32, np.complex64)

        super().__init__(dtype=self.DTYPE_REAL, shape=(len(points[0]), int(np.prod(self.n_modes))))
        self.explicit = False
        kwds = dict(
            n_modes_or_dim=self.n_modes,
            n_trans=1,
            eps=1e-6,
            isign=None,
            dtype=self.DTYPE_COMPLEX.__name__,
            modeord=0
        )
        kwds.update(kwargs)
        self._plan_matvec = finufft.Plan(2, **kwds)
        self._plan_rmatvec = finufft.Plan(1, **kwds)
        self._plan_matvec.setpts(*points)
        self._plan_rmatvec.setpts(*points)
        self._Hx, self._Hy = tuple(map(_halfish, self.n_modes))
        return None

    def _matvec(self, c):
        return self._plan_matvec.execute(self._pre_process_matvec(c))

    def _rmatvec(self, f):
        return self._post_process_rmatvec(self._plan_rmatvec.execute(f.astype(self.DTYPE_COMPLEX)))

    def _pre_process_matvec(self, c):
        return c.reshape(self.n_modes).astype(self.DTYPE_COMPLEX)

    def _post_process_rmatvec(self, f):
        return f

x = np.linspace(0, 2 * np.pi, 10)
y = np.linspace(0, 2 * np.pi, 11)
Px, Py = (7, 8)

Ax = FinufftOperator(x, n_modes=Px)
Ay = FinufftOperator(y, n_modes=Py)

A = np.kron(Ax.todense(), Ay.todense())

xg, yg = np.meshgrid(x, y, indexing="ij")
xg, yg = xg.ravel(), yg.ravel()

A2d = Finufft2DOperator(xg, yg, n_modes=(Px, Py))

fig, (ax_real, ax_imag, ax_2d_real, ax_2d_imag, ax_exact) = plt.subplots(1, 5)
ax_real.set_title("Real")
ax_imag.set_title("Imag")
ax_2d_real.set_title("2D Real")
ax_2d_imag.set_title("2D Imag")
ax_exact.set_title("Exact")
ax_real.imshow(A.real, aspect="auto")
ax_imag.imshow(A.imag, aspect="auto")
ax_2d_real.imshow(A2d.todense().real, aspect="auto")
ax_2d_imag.imshow(A2d.todense().imag, aspect="auto")


local_mode_indices_x = np.argsort(np.hstack([0, (np.tile(np.arange(1, Px // 2 + 1), 2).reshape((2, -1)).T* np.array([-1, 1])).flatten()[:Px-1]]))
local_mode_indices_y = np.argsort(np.hstack([0, (np.tile(np.arange(1, Py // 2 + 1), 2).reshape((2, -1)).T* np.array([-1, 1])).flatten()[:Py-1]]))

A_local_x = design_matrix_as_is(x/2, Px)[:, local_mode_indices_x]
A_local_y = design_matrix_as_is(y/2, Py)[:, local_mode_indices_y]

A_local = np.kron(A_local_x, A_local_y)
ax_exact.imshow(A_local, aspect="auto")

