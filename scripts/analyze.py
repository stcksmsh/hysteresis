#!/usr/bin/env python3
"""Offline analyzer CLI, port of scripts/analyze.ts: analyze.py input.wav [output.json] [--stems]."""
import os
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from analyze.demucs import run_demucs_separation  # noqa: E402
from analyze.jsjson import dumps, js_number  # noqa: E402
from analyze.structure import analyze_mix, compute_stem_presence  # noqa: E402
from analyze.wav import decode_wav_file  # noqa: E402


def main(argv) -> int:
    args = list(argv)
    with_stems = '--stems' in args
    if with_stems:
        args.remove('--stems')
    input_arg = args[0] if len(args) > 0 else None
    output_arg = args[1] if len(args) > 1 else None
    if not input_arg:
        print('usage: analyze.py <path/to/master.wav> [output.sidecar.json] [--stems]', file=sys.stderr)
        return 1

    input_path = os.path.abspath(input_arg)
    sidecar = analyze_mix(decode_wav_file(input_path))

    if with_stems:
        out_dir = tempfile.mkdtemp(prefix='sinteza-demucs-')
        try:
            p = run_demucs_separation(input_path, out_dir)
            sidecar['stemPresence'] = compute_stem_presence(*(decode_wav_file(p[n]) for n in ('vocals', 'drums', 'bass', 'other')))
        finally:
            shutil.rmtree(out_dir, ignore_errors=True)

    slug = Path(input_arg).stem
    output_path = os.path.abspath(output_arg or f'{slug}.sidecar.json')
    Path(output_path).write_text(dumps(sidecar), encoding='utf-8')

    print(f"wrote {output_path} — {sidecar['tempo']:.1f}bpm, {len(sidecar['beats'])} beats, "
          f"{len(sidecar['events'])} events, {len(sidecar['onsets'])} onsets, {len(sidecar['sections'])} sections, "
          f"{sidecar['duration']:.1f}s{', with stem presence' if 'stemPresence' in sidecar else ''}")
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
