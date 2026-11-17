"""Restricted loader for untrusted AIST++ .pkl files: only numpy array reconstruction globals are allowed, anything else raises."""
import io
import pickle

ALLOWED = {("numpy.core.multiarray", "_reconstruct"), ("numpy._core.multiarray", "_reconstruct"), ("numpy", "ndarray"), ("numpy", "dtype"),
           ("numpy.core.multiarray", "scalar"), ("numpy._core.multiarray", "scalar"), ("_codecs", "encode"), ("collections", "OrderedDict")}


class _U(pickle.Unpickler):
    def find_class(self, module, name):
        if (module, name) not in ALLOWED:
            raise pickle.UnpicklingError(f"refused global {module}.{name}")
        return super().find_class(module, name)


def load_pkl(path_or_bytes):
    b = path_or_bytes if isinstance(path_or_bytes, bytes) else open(path_or_bytes, "rb").read()
    return _U(io.BytesIO(b), encoding="latin1").load()
