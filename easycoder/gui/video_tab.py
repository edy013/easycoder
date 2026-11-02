"""Zakładka WIDEO: suwak rozmiaru w MB, rozdzielczość, kodeki, dźwięk."""
from __future__ import annotations

import math
from functools import partial

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QButtonGroup, QCheckBox, QComboBox, QDoubleSpinBox, QGridLayout,
                               QGroupBox, QHBoxLayout, QLabel, QLineEdit, QPushButton,
                               QRadioButton, QSlider, QSpinBox, QVBoxLayout, QWidget)

from .. import calculator as calc
from .. import ffmpeg_cmd as fc
from ..jobqueue import Job
from ..strings import S, format_kbps, format_size, quality_text
from . import theme
from .base_tab import BaseTab, QueueItem

SIZE_PRESETS = [("Mail 20 MB", 20), ("Mail 25 MB", 25), ("Discord 10 MB", 10),
                ("WhatsApp 64 MB", 64), ("100 MB", 100)]
RESOLUTIONS = [("auto", "res_auto"), ("orig", "res_orig"), ("2160", "4K 2160p"),
               ("1440", "1440p"), ("1080", "1080p"), ("720", "720p"), ("540", "540p"),
               ("480", "480p"), ("360", "360p"), ("custom", "res_custom")]
FPS = [("orig", "fps_orig"), ("max30", "fps_max30"), ("60", "60"), ("50", "50"),
       ("30", "30"), ("25", "25"), ("24", "24")]
AUDIO_KBPS = [64, 96, 128, 192, 256, 320]

# Suwak w skali logarytmicznej: 1 MB … 10 000 MB.
SLIDER_MAX = 1000
LOG_MIN, LOG_MAX = 0.0, 4.0


def mb_to_slider(mb: float) -> int:
    mb = max(1.0, mb)
    return int(round((math.log10(mb) - LOG_MIN) / (LOG_MAX - LOG_MIN) * SLIDER_MAX))


def slider_to_mb(v: int) -> float:
    mb = 10 ** (LOG_MIN + v / SLIDER_MAX * (LOG_MAX - LOG_MIN))
    return round(mb, 1) if mb < 100 else float(round(mb))


PRESETS = {
    "preset_preview720": dict(mode="crf", crf=24, resolution="720", fps="max30", codec="x264",
                              container="mp4", audio_enabled=True, audio_codec="aac",
                              audio_kbps=128, audio_mono=False, ten_bit=False, speed="balanced"),
    "preset_preview1080": dict(mode="crf", crf=23, resolution="1080", fps="max30", codec="x264",
                               container="mp4", audio_enabled=True, audio_codec="aac",
                               audio_kbps=128, audio_mono=False, ten_bit=False, speed="balanced"),
    "preset_archive": dict(mode="crf", crf=18, resolution="orig", fps="orig", codec="x265",
                           container="mp4", audio_enabled=True, audio_codec="aac",
                           audio_kbps=256, audio_mono=False, ten_bit=True, speed="best"),
}


def _combo(items: list[tuple[str, str]]) -> QComboBox:
    cb = QComboBox()
    for key, label in items:
        cb.addItem(S[label], key)
    return cb


def _set_combo(cb: QComboBox, value) -> None:
    i = cb.findData(value)
    if i >= 0:
        cb.setCurrentIndex(i)


class VideoTab(BaseTab):
    kind = "video"
    file_kinds = {"video"}
    extract_audio_requested = Signal(list)

    def __init__(self, settings, parent=None):
        self.available: set[str] | None = None
        self.hw: list[str] = []
        self.zscale = True
        self._loading = False
        super().__init__(settings, parent)
        self.apply_settings(fc.VideoSettings.from_dict(settings.data.get("video", {})))

    # ================================================================= panel ustawień
    def build_settings_panel(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(6, 0, 6, 0)

        # --- presety
        pr = QGroupBox(S["presets"])
        pl = QVBoxLayout(pr)
        for key in PRESETS:
            b = QPushButton(S[key])
            b.clicked.connect(partial(self.apply_preset, key))
            pl.addWidget(b)
        v.addWidget(pr)

        # --- tryb + suwak rozmiaru
        box = QGroupBox(S["mode"])
        g = QVBoxLayout(box)
        mrow = QHBoxLayout()
        self.rb_size = QRadioButton(S["mode_size"])
        self.rb_crf = QRadioButton(S["mode_crf"])
        mg = QButtonGroup(box)
        mg.addButton(self.rb_size)
        mg.addButton(self.rb_crf)
        mrow.addWidget(self.rb_size)
        mrow.addWidget(self.rb_crf)
        mrow.addStretch(1)
        g.addLayout(mrow)

        self.size_widget = QWidget()
        sg = QVBoxLayout(self.size_widget)
        sg.setContentsMargins(0, 0, 0, 0)
        srow = QHBoxLayout()
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(0, SLIDER_MAX)
        self.slider.setMinimumHeight(30)
        self.spin_mb = QDoubleSpinBox()
        self.spin_mb.setObjectName("bigsize")
        self.spin_mb.setRange(0.5, 100000)
        self.spin_mb.setDecimals(1)
        self.spin_mb.setSuffix(" MB")
        self.spin_mb.setMinimumWidth(140)
        srow.addWidget(self.slider, 1)
        srow.addWidget(self.spin_mb)
        sg.addLayout(srow)
        chips = QGridLayout()
        chips.setSpacing(4)
        self.size_buttons = QButtonGroup(self)
        self.size_buttons.setExclusive(True)
        for n, (label, mb) in enumerate(SIZE_PRESETS):
            b = QPushButton(label)
            b.setObjectName("chip")
            b.setCheckable(True)
            b.setProperty("mb", mb)
            b.clicked.connect(partial(self._set_size, mb))
            self.size_buttons.addButton(b)
            chips.addWidget(b, n // 3, n % 3)
        own = QPushButton(S["size_custom"])
        own.setObjectName("chip")
        own.setCheckable(True)
        own.setProperty("mb", None)
        own.clicked.connect(lambda: (self.spin_mb.setFocus(), self.spin_mb.selectAll()))
        self.size_buttons.addButton(own)
        self.btn_size_own = own
        chips.addWidget(own, len(SIZE_PRESETS) // 3, len(SIZE_PRESETS) % 3)
        sg.addLayout(chips)
        scope_row = QHBoxLayout()
        self.cb_scope = _combo([("per_file", "size_scope_per_file"), ("total", "size_scope_total")])
        scope_row.addWidget(self.cb_scope)
        scope_row.addStretch(1)
        sg.addLayout(scope_row)
        g.addWidget(self.size_widget)

        self.crf_widget = QWidget()
        cg = QVBoxLayout(self.crf_widget)
        cg.setContentsMargins(0, 0, 0, 0)
        crow = QHBoxLayout()
        self.crf_slider = QSlider(Qt.Horizontal)
        self.crf_slider.setRange(0, 51)
        self.crf_spin = QSpinBox()
        self.crf_spin.setRange(0, 51)
        self.crf_spin.setObjectName("bigsize")
        crow.addWidget(self.crf_slider, 1)
        crow.addWidget(self.crf_spin)
        cg.addLayout(crow)
        hint = QLabel(S["crf_hint"])
        hint.setObjectName("muted")
        cg.addWidget(hint)
        g.addWidget(self.crf_widget)

        # --- panel wyliczeń na żywo
        info = QWidget()
        il = QGridLayout(info)
        il.setContentsMargins(0, 6, 0, 0)
        self.lbl_file = QLabel(S["info_no_file"])
        self.lbl_file.setObjectName("muted")
        self.lbl_bitrate = QLabel("")
        self.lbl_res = QLabel("")
        self.lbl_quality = QLabel("")
        self.lbl_est = QLabel("")
        for lbl in (self.lbl_bitrate, self.lbl_res, self.lbl_quality, self.lbl_est):
            lbl.setObjectName("bignum")
            lbl.setWordWrap(True)
        self.lbl_file.setWordWrap(True)
        self.lbl_hint = QLabel("")
        self.lbl_hint.setObjectName("warn")
        self.lbl_hint.setWordWrap(True)
        for row, lbl in enumerate((self.lbl_file, self.lbl_bitrate, self.lbl_res,
                                   self.lbl_quality, self.lbl_est, self.lbl_hint)):
            il.addWidget(lbl, row, 0)
        g.addWidget(info)
        v.addWidget(box)

        # --- obraz
        img = QGroupBox(S["resolution"])
        ig = QGridLayout(img)
        self.cb_res = _combo(RESOLUTIONS)
        self.sp_w = QSpinBox()
        self.sp_h = QSpinBox()
        for sp in (self.sp_w, self.sp_h):
            sp.setRange(0, 8192)
            sp.setSingleStep(2)
        self.custom_row = QWidget()
        cr = QHBoxLayout(self.custom_row)
        cr.setContentsMargins(0, 0, 0, 0)
        cr.addWidget(self.sp_w)
        cr.addWidget(QLabel("×"))
        cr.addWidget(self.sp_h)
        cr.addStretch(1)
        self.chk_upscale = QCheckBox(S["allow_upscale"])
        self.cb_fps = _combo(FPS)
        ig.addWidget(self.cb_res, 0, 0, 1, 2)
        ig.addWidget(self.custom_row, 1, 0, 1, 2)
        ig.addWidget(self.chk_upscale, 2, 0, 1, 2)
        ig.addWidget(QLabel(S["fps"]), 3, 0)
        ig.addWidget(self.cb_fps, 3, 1)
        v.addWidget(img)

        # --- kodek
        cod = QGroupBox(S["codec"])
        cdl = QGridLayout(cod)
        self.cb_codec = QComboBox()
        self.cb_speed = _combo([("fast", "speed_fast"), ("balanced", "speed_balanced"),
                                ("best", "speed_best")])
        self.chk_10bit = QCheckBox(S["ten_bit"])
        self.cb_container = QComboBox()
        for c in fc.CONTAINERS:
            self.cb_container.addItem(c.upper(), c)
        self.lbl_hw = QLabel(S["hw_detecting"])
        self.lbl_hw.setObjectName("muted")
        self.lbl_hw.setWordWrap(True)
        cdl.addWidget(self.cb_codec, 0, 0, 1, 2)
        cdl.addWidget(QLabel(S["speed"]), 1, 0)
        cdl.addWidget(self.cb_speed, 1, 1)
        cdl.addWidget(QLabel(S["container"]), 2, 0)
        cdl.addWidget(self.cb_container, 2, 1)
        cdl.addWidget(self.chk_10bit, 3, 0, 1, 2)
        cdl.addWidget(self.lbl_hw, 4, 0, 1, 2)
        v.addWidget(cod)
        self._fill_codecs()

        # --- dźwięk
        aud = QGroupBox(S["video_audio"])
        al = QGridLayout(aud)
        self.chk_audio = QCheckBox(S["include_audio"])
        self.chk_audio.setChecked(True)
        self.cb_acodec = _combo([("aac", "acodec_aac"), ("opus", "acodec_opus"),
                                 ("pcm", "acodec_pcm"), ("copy", "acodec_copy")])
        self.cb_akbps = QComboBox()
        for k in AUDIO_KBPS:
            self.cb_akbps.addItem(f"{k} kb/s", k)
        self.chk_mono = QCheckBox(S["mono"])
        al.addWidget(self.chk_audio, 0, 0, 1, 3)
        al.addWidget(QLabel(S["audio_codec"]), 1, 0)
        al.addWidget(self.cb_acodec, 1, 1, 1, 2)
        al.addWidget(QLabel(S["audio_bitrate"]), 2, 0)
        al.addWidget(self.cb_akbps, 2, 1)
        al.addWidget(self.chk_mono, 2, 2)
        v.addWidget(aud)

        # --- przycinanie + wyciąganie audio
        tr = QGroupBox(S["trim"])
        tl = QGridLayout(tr)
        self.ed_start = QLineEdit()
        self.ed_end = QLineEdit()
        for e in (self.ed_start, self.ed_end):
            e.setPlaceholderText(S["trim_placeholder"])
        tl.addWidget(QLabel(S["trim_start"]), 0, 0)
        tl.addWidget(self.ed_start, 0, 1)
        tl.addWidget(QLabel(S["trim_end"]), 1, 0)
        tl.addWidget(self.ed_end, 1, 1)
        v.addWidget(tr)
        self.btn_extract = QPushButton(S["extract_audio"])
        self.btn_extract.clicked.connect(self._extract_audio)
        v.addWidget(self.btn_extract)

        self.lbl_errors = QLabel("")
        self.lbl_errors.setObjectName("error")
        self.lbl_errors.setWordWrap(True)
        v.addWidget(self.lbl_errors)
        v.addStretch(1)

        # --- sygnały
        self.rb_size.toggled.connect(self._on_mode)
        self.slider.valueChanged.connect(self._on_slider)
        self.spin_mb.valueChanged.connect(self._on_spin)
        self.crf_slider.valueChanged.connect(self.crf_spin.setValue)
        self.crf_spin.valueChanged.connect(self.crf_slider.setValue)
        self.cb_res.currentIndexChanged.connect(self._on_res)
        self.cb_codec.currentIndexChanged.connect(self._on_codec)
        self.chk_audio.toggled.connect(self._on_audio_toggle)
        self.cb_acodec.currentIndexChanged.connect(self._on_audio_toggle)
        for sig in (self.crf_spin.valueChanged, self.cb_scope.currentIndexChanged,
                    self.sp_w.valueChanged, self.sp_h.valueChanged, self.chk_upscale.toggled,
                    self.cb_fps.currentIndexChanged, self.cb_speed.currentIndexChanged,
                    self.chk_10bit.toggled, self.cb_container.currentIndexChanged,
                    self.cb_akbps.currentIndexChanged, self.chk_mono.toggled,
                    self.ed_start.textChanged, self.ed_end.textChanged):
            sig.connect(self.schedule_refresh)
        return w

    def _fill_codecs(self):
        current = self.cb_codec.currentData()
        self.cb_codec.blockSignals(True)
        self.cb_codec.clear()
        for key, c in fc.VIDEO_CODECS.items():
            if c["hw"] and (self.available is None or c["encoder"] not in self.available):
                continue
            if not c["hw"] and self.available is not None and c["encoder"] not in self.available:
                continue
            self.cb_codec.addItem(("⚡ " if c["hw"] else "") + c["label"], key)
        _set_combo(self.cb_codec, current or "x264")
        self.cb_codec.blockSignals(False)

    def set_encoders(self, available: set[str], hw: list[str], zscale: bool):
        self.available, self.hw, self.zscale = set(available), hw, zscale
        self._fill_codecs()
        hw_names = ", ".join(h.replace("_", " ").upper() for h in hw) or S["encoders_none"]
        self.lbl_hw.setText(S["encoders_found"].format(hw_names))
        self._on_codec()

    # ================================================================= reakcje
    def _on_mode(self, *_):
        size = self.rb_size.isChecked()
        self.size_widget.setVisible(size)
        self.crf_widget.setVisible(not size)
        self.schedule_refresh()

    def _set_size(self, mb: float):
        self.rb_size.setChecked(True)
        self.spin_mb.setValue(mb)

    def _on_slider(self, v: int):
        if self._loading:
            return
        mb = slider_to_mb(v)
        self.spin_mb.blockSignals(True)
        self.spin_mb.setValue(mb)
        self.spin_mb.blockSignals(False)
        self._sync_size_chips(mb)
        self.schedule_refresh()

    def _on_spin(self, mb: float):
        self.slider.blockSignals(True)
        self.slider.setValue(mb_to_slider(mb))
        self.slider.blockSignals(False)
        self._sync_size_chips(mb)
        self.schedule_refresh()

    def _sync_size_chips(self, mb: float):
        for b in self.size_buttons.buttons():
            if b.property("mb") is not None and abs(b.property("mb") - mb) < 0.05:
                b.setChecked(True)
                return
        self.btn_size_own.setChecked(True)

    def _on_res(self, *_):
        self.custom_row.setVisible(self.cb_res.currentData() == "custom")
        self.schedule_refresh()

    def _on_codec(self, *_):
        key = self.cb_codec.currentData()
        if not key:
            return
        c = fc.VIDEO_CODECS[key]
        # Jeśli bieżący kontener nie pasuje – przełącz na pierwszy zgodny.
        if self.cb_container.currentData() not in c["containers"]:
            _set_combo(self.cb_container, c["containers"][0])
        if self.cb_container.currentData() == "webm" and self.cb_acodec.currentData() == "aac":
            _set_combo(self.cb_acodec, "opus")
        self.chk_10bit.setEnabled(c["family"] not in ("prores", "dnxhr"))
        self.schedule_refresh()

    def _on_audio_toggle(self, *_):
        on = self.chk_audio.isChecked()
        self.cb_acodec.setEnabled(on)
        ac = self.cb_acodec.currentData()
        self.cb_akbps.setEnabled(on and ac in ("aac", "opus"))
        self.chk_mono.setEnabled(on and ac != "copy")
        self.schedule_refresh()

    def apply_preset(self, key: str):
        s = self.current_settings()
        d = s.to_dict()
        d.update(PRESETS[key])
        self.apply_settings(fc.VideoSettings.from_dict(d))

    def apply_user_preset(self, data: dict):
        d = self.current_settings().to_dict()
        d.update(data)
        self.apply_settings(fc.VideoSettings.from_dict(d))

    def _extract_audio(self):
        items = [i for i in self.items if i.info and i.info.has_audio] or []
        rows = sorted({i.row() for i in self.table.selectedIndexes()})
        if rows:
            items = [self.items[r] for r in rows if self.items[r].info and self.items[r].info.has_audio]
        self.extract_audio_requested.emit([i.path for i in items])

    # ================================================================= ustawienia <-> UI
    def current_settings(self) -> fc.VideoSettings:
        return fc.VideoSettings(
            mode="size" if self.rb_size.isChecked() else "crf",
            target_mb=self.spin_mb.value(),
            size_scope=self.cb_scope.currentData(),
            crf=self.crf_spin.value(),
            resolution=self.cb_res.currentData(),
            custom_w=self.sp_w.value(), custom_h=self.sp_h.value(),
            allow_upscale=self.chk_upscale.isChecked(),
            fps=self.cb_fps.currentData(),
            codec=self.cb_codec.currentData() or "x264",
            speed=self.cb_speed.currentData(),
            ten_bit=self.chk_10bit.isChecked() and self.chk_10bit.isEnabled(),
            container=self.cb_container.currentData(),
            audio_enabled=self.chk_audio.isChecked(),
            audio_codec=self.cb_acodec.currentData(),
            audio_kbps=self.cb_akbps.currentData(),
            audio_mono=self.chk_mono.isChecked(),
            trim_start=self.ed_start.text(), trim_end=self.ed_end.text(),
        )

    def apply_settings(self, s: fc.VideoSettings):
        self._loading = True
        (self.rb_size if s.mode == "size" else self.rb_crf).setChecked(True)
        self.spin_mb.setValue(s.target_mb)
        self.slider.setValue(mb_to_slider(s.target_mb))
        _set_combo(self.cb_scope, s.size_scope)
        self.crf_spin.setValue(s.crf)
        _set_combo(self.cb_res, s.resolution)
        self.sp_w.setValue(s.custom_w)
        self.sp_h.setValue(s.custom_h)
        self.chk_upscale.setChecked(s.allow_upscale)
        _set_combo(self.cb_fps, s.fps)
        if self.cb_codec.findData(s.codec) < 0:
            s.codec = "x264"
        _set_combo(self.cb_codec, s.codec)
        _set_combo(self.cb_speed, s.speed)
        self.chk_10bit.setChecked(s.ten_bit)
        _set_combo(self.cb_container, s.container)
        self.chk_audio.setChecked(s.audio_enabled)
        _set_combo(self.cb_acodec, s.audio_codec)
        _set_combo(self.cb_akbps, s.audio_kbps)
        self.chk_mono.setChecked(s.audio_mono)
        self.ed_start.setText(s.trim_start)
        self.ed_end.setText(s.trim_end)
        self._loading = False
        self._sync_size_chips(s.target_mb)
        self._on_mode()
        self._on_res()
        self._on_codec()
        self._on_audio_toggle()

    def save_state(self):
        self.save_common_state()
        self.settings.data["video"] = self.current_settings().to_dict()

    # ================================================================= wyliczenia
    def output_ext(self) -> str:
        return self.cb_container.currentData() or "mp4"

    def _budgets(self, s: fc.VideoSettings, items: list[QueueItem]) -> dict[int, float]:
        """Budżet MB dla każdego pliku (na plik lub rozłożony łącznie)."""
        if s.size_scope == "total" and items:
            durs = [fc.effective_duration(i.info, s) for i in items]
            return {id(i): mb for i, mb in zip(items, calc.split_budget(s.target_mb, durs))}
        return {id(i): s.target_mb for i in items}

    def _plan(self, item: QueueItem, s: fc.VideoSettings, budgets: dict) -> fc.VideoPlan | None:
        try:
            return fc.plan_video(item.info, s, budgets.get(id(item), s.target_mb))
        except (ValueError, KeyError, ZeroDivisionError):
            return None

    def naming_values(self, item: QueueItem, index: int) -> dict:
        s = self.current_settings()
        vals = {"nr": f"{index + 1:02d}", "kodek": fc.VIDEO_CODECS[s.codec]["family"]}
        plan = getattr(item, "_plan", None)
        if plan:
            vals.update(rozdzielczosc=f"{min(plan.width, plan.height)}p",
                        rozmiarMB=f"{plan.est_mb:.0f}" if plan.est_mb >= 10 else f"{plan.est_mb:.1f}",
                        bitrate=f"{plan.video_kbps:.0f}k" if plan.video_kbps else f"crf{s.crf}")
        return vals

    def validate(self) -> list[str]:
        return fc.validate_video(self.current_settings(), self.available)

    def update_estimates(self):
        s = self.current_settings()
        errs = fc.validate_video(s, self.available)
        self.lbl_errors.setText("\n".join(errs))
        ready = self.ready_items()
        budgets = self._budgets(s, ready)
        for item in self.items:
            item._plan = None
            item.est_mb = 0.0
        for item in ready:
            plan = self._plan(item, s, budgets)
            item._plan = plan
            item.est_mb = plan.est_mb if plan else 0.0

        sized_codec = fc.codec_supports_size(s.codec)
        self.size_widget.setEnabled(sized_codec)
        sel = self.selected_item()
        plan = getattr(sel, "_plan", None) if sel else None
        if not sel or not plan:
            self.lbl_file.setText(S["info_no_file"])
            for lbl in (self.lbl_bitrate, self.lbl_res, self.lbl_quality, self.lbl_est):
                lbl.setText("")
            self.lbl_hint.setText(S["hint_no_size"] if not sized_codec else "")
            return
        self.lbl_file.setText(S["info_for_file"].format(sel.path.name))
        if plan.video_kbps:
            self.lbl_bitrate.setText(S["info_bitrate"].format(format_kbps(plan.video_kbps)))
        else:
            self.lbl_bitrate.setText(S["info_bitrate"].format("CRF " + str(s.crf)
                                                              if sized_codec else "—"))
        self.lbl_res.setText(S["info_resolution"].format(
            f"{plan.width}×{plan.height} @ {plan.fps:.3g} fps"))
        color = theme.QUALITY_COLORS[plan.quality]
        self.lbl_quality.setText(S["info_quality"].format(
            f"<span style='color:{color}'>● {quality_text(plan.quality)}</span>"))
        self.lbl_est.setText(S["info_estimate"].format(format_size(plan.est_mb)))
        hints = []
        if not sized_codec:
            hints.append(S["hint_no_size"])
        if plan.hint_lower:
            hints.append(S["hint_lower"].format(plan.hint_lower))
        if plan.upscale:
            hints.append(S["hint_upscale"])
        if plan.tonemap:
            hints.append(S["hint_tonemap"])
        if s.mode == "crf" and s.resolution == "auto":
            hints.append(S["hint_auto_crf"])
        self.lbl_hint.setText("\n".join(hints))

    # ================================================================= zadania
    def make_jobs(self, items: list[QueueItem]) -> list[Job]:
        s = self.current_settings()
        budgets = self._budgets(s, items)
        ffmpeg = str(self.ffmpeg)
        jobs = []
        sized = s.mode == "size" and fc.codec_supports_size(s.codec)
        for item in items:
            plan = fc.plan_video(item.info, s, budgets[id(item)])

            def make(kbps, info=item.info, plan=plan, out=item.out_path):
                return fc.build_video_commands(ffmpeg, info, s, plan, out, kbps, self.zscale)

            jobs.append(Job(kind="video", info=item.info, out_path=item.out_path,
                            duration=plan.duration, make_commands=make,
                            target_mb=budgets[id(item)] if sized else None,
                            video_kbps=plan.video_kbps))
        return jobs
