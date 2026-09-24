#!/usr/bin/env python3
"""Add absolute RMS to existing sidecar; adaptive energy cannot identify fade-outs.

Usage: python3 scripts/arm_features.py audio.wav input.sidecar.json output.sidecar.json
PCM16 WAV only. Existing sidecar fields remain unchanged; no media copied.
"""
import array
import json
import math
import pathlib
import sys
import wave


def enrich(wav_path, sidecar):
    rate = float(sidecar["envelopeRate"])
    if not math.isfinite(rate) or not 0 < rate <= 1000:
        raise ValueError("envelopeRate must be finite, >0 and <=1000")
    rms = []
    with wave.open(str(wav_path), "rb") as audio:
        if audio.getsampwidth() != 2 or audio.getcomptype() != "NONE":
            raise ValueError("Expected uncompressed PCM16 WAV")
        sample_rate, channels = audio.getframerate(), audio.getnchannels()
        duration = audio.getnframes() / sample_rate
        if abs(duration - float(sidecar["duration"])) > 0.1:
            raise ValueError("WAV and sidecar duration mismatch (>100 ms)")
        count = math.ceil(duration * rate)
        for i in range(count):
            start = round(i * sample_rate / rate)
            end = min(audio.getnframes(), round((i + 1) * sample_rate / rate))
            samples = array.array("h", audio.readframes(end - start))
            if sys.byteorder != "little":
                samples.byteswap()
            # Channel power average preserves stereo energy without cancellation.
            value = math.sqrt(sum(x * x for x in samples) / max(1, len(samples))) / 32768
            rms.append(value)
    return dict(sidecar, rmsEnvelope=rms, rmsSource="PCM16 channel-power RMS, full scale")


if __name__ == "__main__":
    if len(sys.argv) != 4:
        raise SystemExit(__doc__)
    source, destination = pathlib.Path(sys.argv[2]), pathlib.Path(sys.argv[3])
    if source.resolve() == destination.resolve():
        raise SystemExit("Use separate output path; original sidecar preserved")
    result = enrich(sys.argv[1], json.loads(source.read_text()))
    destination.write_text(json.dumps(result, separators=(",", ":")))
    print(f"Added {len(result['rmsEnvelope'])} absolute RMS samples → {destination}")
