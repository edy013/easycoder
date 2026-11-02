"""Zakładka AUDIO: konwersja formatów, częstotliwość, kanały, normalizacja."""
from __future__ import annotations

from functools import partial

from PySide6.QtWidgets import (QCheckBox, QComboBox, QGridLayout, QGroupBox, QLabel, QPushButton,
                               QSpinBox, QVBoxLayout, QWidget)

from .. import ffmpeg_cmd as fc
from ..jobqueue import Job
from ..strings import S
from .base_tab import BaseTab, QueueItem
from .video_tab import _combo, _set_combo

LOSSY_CODECS = {"mp3", "aac", "vorbis", "opus", "wmav2", "wmav1", "ac3", "eac3", "mp2", "wmapro"}

FORMATS = [(k, f"fmt_{k}") for k in fc.AUDIO_FORMATS]
BITRATES = {
    "mp3": [128, 192, 256, 320],
    "aac": [128, 160, 192, 256, 320],
    "ogg": [96, 128, 192, 256, 320],
    "opus": [64, 96, 128, 160, 192, 256],
}
DEPTHS = {
    "wav": [("16", "16-bit"), ("24", "24-bit"), ("32f", "bit_32f")],
    "aiff": [("16", "16-bit"), ("24", "24-bit")],
    "flac": [("16", "16-bit"), ("24", "24-bit")],
    "alac": [("16", "16-bit"), ("24", "24-bit")],
}

PRESETS = {
    "preset_mp3_128": dict(fmt="mp3", mp3_mode="cbr", bitrate=128),
    "preset_mp3_320": dict(fmt="mp3", mp3_mode="cbr", bitrate=320),
    "preset_wav_cd": dict(fmt="wav", bit_depth="16", sample_rate="44100", channels="stereo"),
    "preset_wav_studio": dict(fmt="wav", bit_depth="24", sample_rate="48000", channels="stereo"),
    "preset_flac": dict(fmt="flac", bit_depth="24", flac_level=5, sample_rate="orig"),
}


class AudioTab(BaseTab):
    kind = "audio"
    file_kinds = {"video", "audio"}

    def __init__(self, settings, parent=None):
        self._loading = False
        super().__init__(settings, parent)
        self.apply_settings(fc.AudioSettings.from_dict(settings.data.get("audio", {})))

    def build_settings_panel(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(6, 0, 6, 0)

        pr = QGroupBox(S["presets"])
        pl = QVBoxLayout(pr)
        for key in PRESETS:
            b = QPushButton(S[key])
            b.clicked.connect(partial(self.apply_preset, key))
            pl.addWidget(b)
        v.addWidget(pr)

        box = QGroupBox(S["out_format"])
        g = QGridLayout(box)
        self.cb_fmt = _combo(FORMATS)
        self.cb_bitrate = QComboBox()
        self.lbl_bitrate = QLabel(S["audio_bitrate"])
        self.cb_depth = QComboBox()
        self.lbl_depth = QLabel(S["bit_depth"])
        self.sp_flac = QSpinBox()
        self.sp_flac.setRange(0, 8)
        self.lbl_flac = QLabel(S["flac_level"])
        self.cb_rate = _combo([("orig", "rate_orig"), ("44100", "44.1 kHz"),
                               ("48000", "48 kHz"), ("96000", "96 kHz")])
        self.cb_channels = _combo([("stereo", "stereo"), ("mono", "mono")])
        self.cb_loud = _combo([("off", "loud_off"), ("-14", "loud_14"), ("-16", "loud_16"),
                               ("-23", "loud_23")])
        self.chk_meta = QCheckBox(S["keep_meta"])
        self.chk_parallel = QCheckBox(S["parallel"])
        rows = [(QLabel(S["out_format"]), self.cb_fmt), (self.lbl_bitrate, self.cb_bitrate),
                (self.lbl_depth, self.cb_depth), (self.lbl_flac, self.sp_flac),
                (QLabel(S["sample_rate"]), self.cb_rate), (QLabel(S["channels"]), self.cb_channels),
                (QLabel(S["loudnorm"]), self.cb_loud)]
        for r, (lbl, wdg) in enumerate(rows):
            g.addWidget(lbl, r, 0)
            g.addWidget(wdg, r, 1)
        g.addWidget(self.chk_meta, len(rows), 0, 1, 2)
        g.addWidget(self.chk_parallel, len(rows) + 1, 0, 1, 2)
        g.setColumnStretch(1, 1)
        v.addWidget(box)

        self.lbl_note = QLabel(S["lossy_note"])
        self.lbl_note.setObjectName("warn")
        self.lbl_note.setWordWrap(True)
        v.addWidget(self.lbl_note)
        self.lbl_info = QLabel("")
        self.lbl_info.setObjectName("bignum")
        self.lbl_info.setWordWrap(True)
        v.addWidget(self.lbl_info)
        v.addStretch(1)

        self.cb_fmt.currentIndexChanged.connect(self._on_format)
        for sig in (self.cb_bitrate.currentIndexChanged, self.cb_depth.currentIndexChanged,
                    self.sp_flac.valueChanged, self.cb_rate.currentIndexChanged,
                    self.cb_channels.currentIndexChanged, self.cb_loud.currentIndexChanged,
                    self.chk_meta.toggled):
            sig.connect(self.schedule_refresh)
        return w

    # ================================================================= reakcje
    def _on_format(self, *_):
        fmt = self.cb_fmt.currentData()
        prev_rate, prev_depth = self.cb_bitrate.currentData(), self.cb_depth.currentData()
        self.cb_bitrate.blockSignals(True)
        self.cb_bitrate.clear()
        for k in BITRATES.get(fmt, []):
            self.cb_bitrate.addItem(f"{k} kb/s", k)
        if fmt == "mp3":
            self.cb_bitrate.addItem(S["mp3_vbr"], "v0")
        _set_combo(self.cb_bitrate, prev_rate)
        if self.cb_bitrate.currentIndex() < 0 or self.cb_bitrate.findData(prev_rate) < 0:
            _set_combo(self.cb_bitrate, 320 if fmt in ("mp3", "aac", "ogg") else 128)
        self.cb_bitrate.blockSignals(False)
        self.cb_depth.blockSignals(True)
        self.cb_depth.clear()
        for key, label in DEPTHS.get(fmt, []):
            self.cb_depth.addItem(S[label], key)
        # Ze źródła stratnego do WAV/AIFF domyślnie 16-bit (więcej nic nie da).
        if not self._loading and fmt in ("wav", "aiff") and self._sources_lossy():
            prev_depth = "16"
        _set_combo(self.cb_depth, prev_depth)
        self.cb_depth.blockSignals(False)
        has_rate = fmt in BITRATES
        self.cb_bitrate.setVisible(has_rate)
        self.lbl_bitrate.setVisible(has_rate)
        has_depth = fmt in DEPTHS
        self.cb_depth.setVisible(has_depth)
        self.lbl_depth.setVisible(has_depth)
        self.sp_flac.setVisible(fmt == "flac")
        self.lbl_flac.setVisible(fmt == "flac")
        self.schedule_refresh()

    def _sources_lossy(self) -> bool:
        infos = [i.info for i in self.ready_items()]
        return bool(infos) and any(i.acodec in LOSSY_CODECS for i in infos)

    def apply_preset(self, key: str):
        d = self.current_settings().to_dict()
        d.update(PRESETS[key])
        self.apply_settings(fc.AudioSettings.from_dict(d))

    def apply_user_preset(self, data: dict):
        d = self.current_settings().to_dict()
        d.update(data)
        self.apply_settings(fc.AudioSettings.from_dict(d))

    # ================================================================= ustawienia <-> UI
    def current_settings(self) -> fc.AudioSettings:
        br = self.cb_bitrate.currentData()
        return fc.AudioSettings(
            fmt=self.cb_fmt.currentData(),
            mp3_mode="v0" if br == "v0" else "cbr",
            bitrate=br if isinstance(br, int) else 320,
            bit_depth=self.cb_depth.currentData() or "16",
            flac_level=self.sp_flac.value(),
            sample_rate=self.cb_rate.currentData(),
            channels=self.cb_channels.currentData(),
            loudnorm=self.cb_loud.currentData(),
            keep_metadata=self.chk_meta.isChecked(),
            parallel=self.chk_parallel.isChecked(),
        )

    def apply_settings(self, s: fc.AudioSettings):
        self._loading = True
        _set_combo(self.cb_fmt, s.fmt)
        self._on_format()
        _set_combo(self.cb_bitrate, "v0" if (s.fmt == "mp3" and s.mp3_mode == "v0") else s.bitrate)
        _set_combo(self.cb_depth, s.bit_depth)
        self.sp_flac.setValue(s.flac_level)
        _set_combo(self.cb_rate, s.sample_rate)
        _set_combo(self.cb_channels, s.channels)
        _set_combo(self.cb_loud, s.loudnorm)
        self.chk_meta.setChecked(s.keep_metadata)
        self.chk_parallel.setChecked(s.parallel)
        self._loading = False
        self.schedule_refresh()

    def save_state(self):
        self.save_common_state()
        self.settings.data["audio"] = self.current_settings().to_dict()

    # ================================================================= wyliczenia
    def output_ext(self) -> str:
        return fc.audio_output_ext(self.current_settings())

    def describe_source(self, info) -> str:
        if info.has_audio:
            ch = {1: "mono", 2: "stereo"}.get(info.channels, f"{info.channels} kan.")
            return f"{info.sample_rate / 1000:g} kHz {ch}"
        return "—"

    def ready_items(self) -> list[QueueItem]:
        return [i for i in super().ready_items() if i.info.has_audio]

    def naming_values(self, item: QueueItem, index: int) -> dict:
        s = self.current_settings()
        rate = fc.audio_out_rate(item.info, s) if item.info else 0
        if s.fmt in ("mp3", "aac", "ogg", "opus"):
            br = "V0" if (s.fmt == "mp3" and s.mp3_mode == "v0") else f"{s.bitrate}k"
        else:
            br = "32f" if s.bit_depth == "32f" else f"{s.bit_depth}bit"
        return {"nr": f"{index + 1:02d}", "kodek": s.fmt, "rozdzielczosc": f"{rate / 1000:g}kHz",
                "rozmiarMB": f"{item.est_mb:.1f}", "bitrate": br}

    def update_estimates(self):
        s = self.current_settings()
        for item in self.items:
            item.est_mb = fc.audio_estimate(item.info, s) if (item.info and item.info.has_audio) else 0.0
        lossless = fc.AUDIO_FORMATS[s.fmt]["lossless"]
        self.lbl_note.setVisible(lossless and self._sources_lossy())
        ready = self.ready_items()
        total = sum(i.est_mb for i in ready)
        self.lbl_info.setText(f"{S['info_estimate'].format(f'{total:.1f} MB')} "
                              f"({len(ready)})" if ready else S["info_no_file"])

    def parallel_jobs(self) -> int:
        return 2 if self.chk_parallel.isChecked() else 1

    def make_jobs(self, items: list[QueueItem]) -> list[Job]:
        s = self.current_settings()
        ffmpeg = str(self.ffmpeg)
        jobs = []
        for item in items:
            def make(_kbps, info=item.info, out=item.out_path):
                return [fc.build_audio_command(ffmpeg, info, s, out)]
            jobs.append(Job(kind="audio", info=item.info, out_path=item.out_path,
                            duration=item.info.duration, make_commands=make))
        return jobs
