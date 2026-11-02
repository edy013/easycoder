"""Budowanie komend FFmpeg i analiza wyniku ffprobe."""
from pathlib import Path

import pytest

from easycoder import ffmpeg_cmd as fc
from easycoder.jobqueue import friendly_error, parse_progress_line
from easycoder.probe import MediaInfo, parse_probe_json


def info(**kw):
    base = dict(path=Path("in.mov"), duration=60.0, has_video=True, width=3840, height=2160,
                fps=50.0, has_audio=True, sample_rate=48000, channels=2, acodec="aac")
    base.update(kw)
    return MediaInfo(**base)


def cmd_str(cmds):
    return [" ".join(c) for c in cmds]


def test_x264_size_mode_is_two_pass():
    s = fc.VideoSettings(codec="x264", target_mb=20, resolution="720")
    i = info()
    cmds = fc.build_video_commands("ffmpeg", i, s, fc.plan_video(i, s), Path("out.mp4"))
    assert len(cmds) == 2
    p1, p2 = cmd_str(cmds)
    assert "-pass 1" in p1 and "-an" in p1 and "-f null" in p1
    assert "-pass 2" in p2 and "-movflags +faststart" in p2
    assert "scale=1280:720:flags=lanczos" in p2


def test_x265_uses_x265_params_and_hvc1():
    s = fc.VideoSettings(codec="x265", container="mp4")
    i = info()
    p2 = cmd_str(fc.build_video_commands("ffmpeg", i, s, fc.plan_video(i, s), Path("o.mp4")))[1]
    assert "pass=2:stats=ec2pass.log" in p2 and "-tag:v hvc1" in p2


def test_hw_encoder_single_pass_vbr():
    s = fc.VideoSettings(codec="h264_nvenc")
    i = info()
    cmds = fc.build_video_commands("ffmpeg", i, s, fc.plan_video(i, s), Path("o.mp4"))
    assert len(cmds) == 1
    c = " ".join(cmds[0])
    assert "-maxrate" in c and "-bufsize" in c and "-rc vbr" in c


def test_crf_mode_single_pass():
    s = fc.VideoSettings(mode="crf", crf=28, codec="x264", resolution="orig")
    i = info()
    cmds = fc.build_video_commands("ffmpeg", i, s, fc.plan_video(i, s), Path("o.mp4"))
    assert len(cmds) == 1 and "-crf 28" in " ".join(cmds[0])


def test_no_audio_gives_bigger_video_budget_and_an():
    i = info()
    on = fc.plan_video(i, fc.VideoSettings(audio_enabled=True, audio_kbps=128))
    off_s = fc.VideoSettings(audio_enabled=False)
    off = fc.plan_video(i, off_s)
    assert off.video_kbps == pytest.approx(on.video_kbps + 128)
    p2 = fc.build_video_commands("ffmpeg", i, off_s, off, Path("o.mp4"))[-1]
    assert "-an" in p2


def test_vertical_720p():
    i = info(width=1080, height=1920, fps=30)
    plan = fc.plan_video(i, fc.VideoSettings(resolution="720"))
    assert (plan.width, plan.height) == (720, 1280)


def test_preview_fps_cap():
    plan = fc.plan_video(info(fps=50), fc.VideoSettings(fps="max30", mode="crf"))
    assert plan.fps == 30 and plan.fps_changed
    plan = fc.plan_video(info(fps=25), fc.VideoSettings(fps="max30", mode="crf"))
    assert plan.fps == 25 and not plan.fps_changed


def test_trim_changes_duration_and_args():
    s = fc.VideoSettings(trim_start="0:10", trim_end="0:40")
    i = info()
    plan = fc.plan_video(i, s)
    assert plan.duration == pytest.approx(30)
    c = " ".join(fc.build_video_commands("ffmpeg", i, s, plan, Path("o.mp4"))[-1])
    assert "-ss 10.000" in c and "-t 30.000" in c


def test_hdr_tonemap():
    i = info(hdr=True)
    s = fc.VideoSettings(codec="x264")
    plan = fc.plan_video(i, s)
    assert plan.tonemap
    c = " ".join(fc.build_video_commands("ffmpeg", i, s, plan, Path("o.mp4"))[-1])
    assert "tonemap=tonemap=hable" in c
    plan10 = fc.plan_video(i, fc.VideoSettings(codec="x265", ten_bit=True))
    assert not plan10.tonemap


def test_validation_blocks_bad_combos():
    assert fc.validate_video(fc.VideoSettings(codec="prores_hq", container="mp4"))
    assert fc.validate_video(fc.VideoSettings(codec="vp9", container="webm", audio_codec="aac"))
    assert not fc.validate_video(fc.VideoSettings(codec="vp9", container="webm", audio_codec="opus"))
    assert fc.validate_video(fc.VideoSettings(trim_start="1:00", trim_end="0:30"))
    assert fc.validate_video(fc.VideoSettings(codec="x265"), available={"libx264"})


def test_prores_ignores_size():
    i = info()
    s = fc.VideoSettings(codec="prores_hq", container="mov")
    plan = fc.plan_video(i, s)
    assert plan.video_kbps == 0
    c = " ".join(fc.build_video_commands("ffmpeg", i, s, plan, Path("o.mov"))[0])
    assert "-profile:v 3" in c and "yuv422p10le" in c and "-b:v" not in c


def test_parse_time():
    assert fc.parse_time("90") == 90
    assert fc.parse_time("1:30") == 90
    assert fc.parse_time("1:02:03,5") == pytest.approx(3723.5)
    assert fc.parse_time("") is None
    with pytest.raises(ValueError):
        fc.parse_time("abc")


@pytest.mark.parametrize("fmt,needle", [
    ("mp3", "libmp3lame"), ("wav", "pcm_s24le"), ("aiff", "pcm_s24be"), ("flac", "flac"),
    ("aac", "-c:a aac"), ("alac", "alac"), ("ogg", "libvorbis"), ("opus", "libopus"),
])
def test_audio_formats(fmt, needle):
    a = fc.AudioSettings(fmt=fmt, bit_depth="24")
    c = " ".join(fc.build_audio_command("ffmpeg", info(), a, Path("o")))
    assert needle in c


def test_audio_mono_loudnorm_rate():
    a = fc.AudioSettings(fmt="mp3", channels="mono", loudnorm="-16")
    c = " ".join(fc.build_audio_command("ffmpeg", info(sample_rate=44100), a, Path("o.mp3")))
    assert "-ac 1" in c and "loudnorm=I=-16" in c and "-ar 44100" in c


def test_mp3_v0():
    c = " ".join(fc.build_audio_command("ffmpeg", info(), fc.AudioSettings(mp3_mode="v0"), Path("o")))
    assert "-q:a 0" in c


def test_probe_parse_rotation_and_hdr():
    data = {"format": {"duration": "12.5", "size": "1000", "format_name": "mov,mp4,m4a"},
            "streams": [
                {"codec_type": "video", "width": 3840, "height": 2160, "avg_frame_rate": "50/1",
                 "codec_name": "hevc", "pix_fmt": "yuv420p10le", "color_transfer": "smpte2084",
                 "side_data_list": [{"rotation": -90}]},
                {"codec_type": "audio", "codec_name": "aac", "sample_rate": "48000",
                 "channels": 2, "bit_rate": "192000"},
                {"codec_type": "video", "disposition": {"attached_pic": 1}},
            ]}
    i = parse_probe_json(data, Path("x.mov"))
    assert (i.width, i.height) == (2160, 3840) and i.is_vertical
    assert i.hdr and i.bit_depth == 10 and i.fps == 50 and i.duration == 12.5
    assert i.audio_kbps == 192 and i.has_cover and i.format_name == "mov"


def test_progress_and_errors():
    assert parse_progress_line("out_time_us=2500000") == 2.5
    assert parse_progress_line("frame=12") is None
    assert "Brak miejsca" in friendly_error("... No space left on device", 1)
    assert "kod 7" in friendly_error("cos innego", 7)
