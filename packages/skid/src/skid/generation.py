"""Generation: kokoro in, a WAV file out.

Nothing streams to a device from in here. A file is produced and handed on,
which is what lets generation run ahead of playback without either waiting on
the other.

**The stdlib `wave` module writes the file.** kokoro returns float samples and
this scales them to signed 16-bit; that conversion is the whole of what sits
between the engine and the file. Using `soundfile` would be importing libsndfile,
which is an audio library, and skid does not have one.
"""

from __future__ import annotations

import wave
from pathlib import Path
from typing import Any

import numpy as np

SAMPLE_RATE = 24000
"""Measured 2026-08-27: kokoro 0.9.4 returns 24 kHz mono."""

VOICES = frozenset(
    [
        "af_alloy",
        "af_aoede",
        "af_bella",
        "af_heart",
        "af_jessica",
        "af_kore",
        "af_nicole",
        "af_nova",
        "af_river",
        "af_sarah",
        "af_sky",
        "am_adam",
        "am_echo",
        "am_eric",
        "am_fenrir",
        "am_liam",
        "am_michael",
        "am_onyx",
        "am_puck",
        "am_santa",
        "bf_alice",
        "bf_emma",
        "bf_isabella",
        "bf_lily",
        "bm_daniel",
        "bm_fable",
        "bm_george",
        "bm_lewis",
        "ef_dora",
        "em_alex",
        "em_santa",
        "ff_siwis",
        "hf_alpha",
        "hf_beta",
        "hm_omega",
        "hm_psi",
        "if_sara",
        "im_nicola",
        "jf_alpha",
        "jf_gongitsune",
        "jf_nezumi",
        "jf_tebukuro",
        "jm_kumo",
        "pf_dora",
        "pm_alex",
        "pm_santa",
        "zf_xiaobei",
        "zf_xiaoni",
        "zf_xiaoxiao",
        "zf_xiaoyi",
        "zm_yunjian",
        "zm_yunxi",
        "zm_yunxia",
        "zm_yunyang",
    ]
)
"""The 54 voices kokoro 0.9.4 offers.

Measured against `hexgrad/Kokoro-82M`, and re-derivable:

    from huggingface_hub import list_repo_files
    sorted(f.split('/')[-1].removesuffix('.pt')
           for f in list_repo_files('hexgrad/Kokoro-82M')
           if f.startswith('voices/'))

Held here rather than fetched, because validating a setting must not need the
network. It drifts when kokoro adds a voice, and a name refused that should not
be is the symptom.
"""


class GenerationFailed(Exception):
    """Text could not be rendered, whatever the engine's own reason was.

    kokoro sits on torch and can fail in that stack's vocabulary rather than
    skid's. Converting here means the service handles one domain error instead
    of catching anything at all, which FR-4.6 needs and a blind catch would only
    look like.
    """


REPO_ID = "hexgrad/Kokoro-82M"
"""Named rather than defaulted, which is also what silences kokoro's own warning.

kokoro prints a line on every pipeline it builds if this is not passed, and skid
now builds more than one.
"""


def _lang_code(voice: str) -> str:
    """The pipeline a voice id implies, which is its first letter.

    The default under FR-10.7 rather than the rule. A voice is a speaker and a
    pipeline is a phonemiser, and a configured voice may name a different one:
    `if_sara` implies the Italian phonemiser and is on the shortlist as an
    English speaker with an Italian accent.
    """
    return voice[0]


class Generator:
    """Holds the warm pipelines and renders text through the current one.

    A pipeline is built on first use and kept, so a second message does not pay
    model start-up. That is what the backend exists for.

    **One model, several phonemisers.** Pipelines are cached per code rather
    than dropped on a change, because assignment under FR-10.2 moves between
    voices constantly and rebuilding on every switch would pay start-up on most
    submissions. The model is the expensive part and is built once: the first
    pipeline creates it and every later one is handed the same instance, so the
    cache costs a front end rather than another 1.6 GB.
    """

    def __init__(self, voice: str = "af_heart", pipeline: str | None = None) -> None:
        """Take the voice and optionally the pipeline, refusing an unknown voice.

        `pipeline` omitted means the one the voice id implies, which is what
        every caller wanted before FR-10.7 existed.
        """
        if voice not in VOICES:
            raise ValueError(f"unknown voice: {voice!r}")
        self.voice = voice
        self.pipeline_code = pipeline or _lang_code(voice)
        self._pipelines: dict[str, Any] = {}
        self._model: Any | None = None

    def warm(self) -> None:
        """Load the model now, rather than on the first message that needs it.

        What FR-5.1 asks for, made explicit so a caller can decide when to pay
        it. The service pays it at start-up, so that being active and being able
        to answer are the same thing.

        Warming the second pipeline is cheap, because by then the model exists.
        """
        if self.pipeline_code not in self._pipelines:
            self._pipelines[self.pipeline_code] = self._build(self.pipeline_code)

    def _build(self, code: str) -> Any:
        """Construct the kokoro pipeline for `code`, sharing the one model.

        The first build lets kokoro create the model, so its device selection is
        not reimplemented here; the instance is then kept and handed to every
        later pipeline. `model=True` is kokoro's own default and means build one.
        """
        from kokoro import KPipeline

        built = KPipeline(
            lang_code=code,
            repo_id=REPO_ID,
            model=self._model if self._model is not None else True,
        )
        if self._model is None:
            self._model = built.model
        return built

    def set_voice(self, voice: str, pipeline: str | None = None) -> None:
        """Change the voice, refusing one kokoro does not have.

        Nothing is dropped. A pipeline already built stays built, so moving
        between two voices costs a dictionary lookup whether or not they share a
        phonemiser.
        """
        if voice not in VOICES:
            raise ValueError(f"unknown voice: {voice!r}")
        self.voice = voice
        self.pipeline_code = pipeline or _lang_code(voice)

    @property
    def pipeline(self) -> Any:
        """The warm pipeline for the current code, built once on first use."""
        self.warm()
        return self._pipelines[self.pipeline_code]

    def generate(self, text: str, path: Path) -> Path:
        """Render `text` to a WAV at `path`, and return it.

        Any failure from the engine becomes GenerationFailed, so a caller has
        one thing to handle rather than the whole of torch's error surface.
        """
        try:
            chunks = list(self.pipeline(text, voice=self.voice))
            audio = np.concatenate([chunk.audio.numpy() for chunk in chunks])
        except Exception as exc:
            raise GenerationFailed(f"could not render {text!r}: {exc}") from exc

        path.parent.mkdir(parents=True, exist_ok=True)
        # `Wave_write` rather than `wave.open(..., "wb")`: both are public, and
        # naming the class says which of the overload's two return types this
        # is, which a reader and a checker otherwise have to infer from a mode
        # string.
        with wave.Wave_write(str(path)) as out:
            out.setnchannels(1)
            out.setsampwidth(2)
            out.setframerate(SAMPLE_RATE)
            out.writeframes((audio * 32767).astype("<i2").tobytes())
        return path
