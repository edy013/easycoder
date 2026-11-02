"""Kalkulator bitrate/rozmiaru i dobór rozdzielczości (w tym pionowe wideo)."""
import pytest

from easycoder import calculator as calc


class TestBitrate:
    def test_total_bitrate_formula(self):
        # 25 MB w 60 s: 25*8*1024*1024/60 bit/s
        assert calc.total_bitrate_kbps(25, 60) == pytest.approx(25 * 8 * 1024 * 1024 / 60 / 1000)

    def test_zero_duration(self):
        assert calc.total_bitrate_kbps(25, 0) == 0

    def test_video_bitrate_subtracts_audio_and_overhead(self):
        total = calc.total_bitrate_kbps(20, 100)
        v = calc.video_bitrate_kbps(20, 100, audio_kbps=128)
        assert v == pytest.approx(total * (1 - calc.CONTAINER_OVERHEAD) - 128)

    def test_no_audio_gives_more_video(self):
        assert calc.video_bitrate_kbps(20, 100, 0) > calc.video_bitrate_kbps(20, 100, 128)

    def test_minimum_bitrate_floor(self):
        assert calc.video_bitrate_kbps(1, 3600, 128) == calc.MIN_VIDEO_KBPS

    def test_estimate_roundtrip(self):
        v = calc.video_bitrate_kbps(25, 90, 128)
        assert calc.estimate_size_mb(v, 128, 90) == pytest.approx(25, rel=1e-6)

    def test_retry_bitrate_lowers(self):
        new = calc.retry_bitrate(2000, 20, 22)
        assert new < 2000 * 20 / 22

    def test_split_budget_proportional(self):
        parts = calc.split_budget(100, [10, 30, 60])
        assert parts == pytest.approx([10, 30, 60])
        assert sum(parts) == pytest.approx(100)

    def test_split_budget_zero_durations(self):
        assert calc.split_budget(30, [0, 0, 0]) == pytest.approx([10, 10, 10])


class TestResolution:
    @pytest.mark.parametrize("src,short,expected", [
        ((3840, 2160), 720, (1280, 720)),
        ((3840, 2160), 1080, (1920, 1080)),
        ((1920, 1080), 540, (960, 540)),
        ((3840, 1608), 1080, (1920, 804)),     # 2.39:1 mieści się w ramce
        ((1440, 1080), 720, (960, 720)),       # 4:3
        ((1080, 1080), 720, (720, 720)),       # kwadrat
    ])
    def test_landscape_and_odd_aspects(self, src, short, expected):
        assert calc.fit_resolution(*src, short) == expected

    def test_vertical_720p_means_720_width(self):
        assert calc.fit_resolution(1080, 1920, 720) == (720, 1280)
        assert calc.fit_resolution(2160, 3840, 1080) == (1080, 1920)

    def test_never_upscale_by_default(self):
        assert calc.fit_resolution(1280, 720, 1080) == (1280, 720)
        assert calc.fit_resolution(720, 1280, 1080) == (720, 1280)

    def test_upscale_when_allowed(self):
        assert calc.fit_resolution(1280, 720, 1080, allow_upscale=True) == (1920, 1080)

    def test_dimensions_always_even(self):
        for src in [(1921, 1081), (3839, 1607), (1001, 1777)]:
            for short in calc.RESOLUTION_LADDER:
                w, h = calc.fit_resolution(*src, short)
                assert w % 2 == 0 and h % 2 == 0

    def test_custom_box(self):
        assert calc.fit_custom(3840, 2160, 1000, 0) == (1000, 562)
        assert calc.fit_custom(3840, 2160, 0, 500) == (888, 500)
        assert calc.fit_custom(1280, 720, 1920, 1080) == (1280, 720)

    def test_suggest_lower(self):
        assert calc.suggest_lower(1920, 1080, 720) == 540
        assert calc.suggest_lower(1920, 1080, 360) is None


class TestQuality:
    def test_levels_ordered(self):
        q_high = calc.quality_level(8000, 1920, 1080, 30)
        q_low = calc.quality_level(300, 1920, 1080, 30)
        assert q_high == "excellent" and q_low == "poor"

    def test_hevc_more_efficient(self):
        k = 2500
        assert calc.QUALITY_ORDER.index(calc.quality_level(k, 1920, 1080, 30, "hevc")) >= \
            calc.QUALITY_ORDER.index(calc.quality_level(k, 1920, 1080, 30, "h264"))

    def test_auto_picks_lower_resolution_for_small_budget(self):
        v = calc.video_bitrate_kbps(10, 120, 128)          # ~550 kb/s
        ch = calc.auto_resolution(3840, 2160, 25, v)
        assert ch.short_side <= 540

    def test_auto_keeps_high_resolution_for_big_budget(self):
        ch = calc.auto_resolution(3840, 2160, 25, 40000)
        assert (ch.width, ch.height) == (3840, 2160)

    def test_auto_drops_60_to_30_before_resolution(self):
        # bitrate wystarczający dla 1080p30, ale nie 1080p60
        kbps = 0.07 * 1920 * 1080 * 30 / 1000
        ch = calc.auto_resolution(1920, 1080, 60, kbps)
        assert (ch.height, ch.fps) == (1080, 30)

    def test_auto_vertical(self):
        v = calc.video_bitrate_kbps(10, 60, 128)
        ch = calc.auto_resolution(1080, 1920, 30, v)
        assert ch.height > ch.width

    def test_auto_never_exceeds_source(self):
        ch = calc.auto_resolution(1280, 720, 30, 100000)
        assert (ch.width, ch.height) == (1280, 720)


def test_audio_estimates():
    assert calc.audio_estimate_mb("wav", 60, 44100, 2, 16) == pytest.approx(60 * 44100 * 4 / calc.MB)
    assert calc.audio_estimate_mb("mp3", 60, 44100, 2, kbps=320) == pytest.approx(320e3 * 60 / 8 / calc.MB)
