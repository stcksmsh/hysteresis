"""Port of scripts/demucs.ts: shell out to Demucs (htdemucs), return the four stem paths."""
import os
import subprocess
import sys
from pathlib import Path

DEMUCS_MODEL = 'htdemucs'
STEM_NAMES = ['vocals', 'drums', 'bass', 'other']
# demucs.ts calls `python3 -m demucs`; here the Demucs install is a separate venv.
DEFAULT_DEMUCS_PYTHON = '/secondary/hyst-env/demucs/bin/python'


def run_demucs_separation(input_wav_path: str, out_dir: str) -> dict:
    py = os.environ.get('HYST_DEMUCS_PYTHON', DEFAULT_DEMUCS_PYTHON)
    cmd = [py, '-m', 'demucs', '-n', DEMUCS_MODEL, '-o', out_dir, input_wav_path]
    try:
        subprocess.run(cmd, check=True, stdout=sys.stderr, stderr=sys.stderr)
    except (subprocess.CalledProcessError, OSError) as err:
        raise RuntimeError(f'--stems requires Demucs installed (tried "{py} -m demucs"). '
                           f'Set HYST_DEMUCS_PYTHON to another interpreter.\nUnderlying error: {err}')
    stem_dir = Path(out_dir) / DEMUCS_MODEL / Path(input_wav_path).stem
    paths = {n: str(stem_dir / f'{n}.wav') for n in STEM_NAMES}
    for n in STEM_NAMES:
        if not os.path.exists(paths[n]):
            raise RuntimeError(f'demucs ran but expected stem output is missing: {paths[n]}')
    return paths
