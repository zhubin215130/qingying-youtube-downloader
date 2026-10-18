"""YouTube inspection and download logic for Qingying."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from threading import Event
from typing import Callable
from urllib.parse import urlparse

import yt_dlp


class DownloadCancelled(Exception):
    pass


@dataclass(frozen=True)
class FormatChoice:
    quality: int
    width: int
    height: int
    fps: int
    video_id: str
    audio_id: str | None
    extension: str
    estimated_bytes: int | None

    @property
    def label(self) -> str:
        return f"{self.quality}p  ·  {self.width} × {self.height}  ·  {self.fps} fps"


@dataclass(frozen=True)
class VideoDetails:
    url: str
    video_id: str
    title: str
    channel: str
    duration: int | None
    choices: tuple[FormatChoice, ...]


def normalize_url(value: str) -> str:
    url = value.strip()
    if not url:
        raise ValueError("请粘贴 YouTube 视频链接。")
    if "://" not in url:
        url = "https://" + url
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if parsed.scheme not in {"http", "https"} or not (
        host == "youtu.be" or host == "youtube.com" or host.endswith(".youtube.com")
    ):
        raise ValueError("请输入有效的 YouTube 视频或 Shorts 链接。")
    return url


def _quality(width: int, height: int) -> int:
    short_edge = min(width, height)
    standards = (144, 240, 360, 480, 720, 1080, 1440, 2160, 4320)
    return max((value for value in standards if value <= short_edge), default=short_edge)


def _is_drc(fmt: dict) -> bool:
    return "drc" in str(fmt.get("format_id", "")).lower() or "drc" in str(fmt.get("format_note", "")).lower()


def _select_audio(formats: list[dict], extension: str) -> dict | None:
    audio = [
        fmt for fmt in formats
        if fmt.get("vcodec") == "none" and fmt.get("acodec") not in (None, "none")
        and fmt.get("protocol") in ("https", "http", "m3u8_native", "m3u8")
        and not _is_drc(fmt)
    ]
    if not audio:
        return None
    def score(fmt: dict) -> tuple:
        codec = str(fmt.get("acodec", ""))
        match = codec.startswith("opus") if extension == "webm" else codec.startswith("mp4a")
        return (match, fmt.get("protocol") in ("https", "http"), float(fmt.get("abr") or 0))
    return max(audio, key=score)


def _select_choices(formats: list[dict]) -> tuple[FormatChoice, ...]:
    video = [
        fmt for fmt in formats
        if fmt.get("vcodec") not in (None, "none")
        and fmt.get("acodec") in (None, "none")
        and int(fmt.get("width") or 0) > 0 and int(fmt.get("height") or 0) > 0
        and "premium" not in str(fmt.get("format_note", "")).lower()
    ]
    grouped: dict[int, list[dict]] = {}
    for fmt in video:
        quality = _quality(int(fmt["width"]), int(fmt["height"]))
        grouped.setdefault(quality, []).append(fmt)

    choices = []
    for quality, candidates in grouped.items():
        def score(fmt: dict) -> tuple:
            codec = str(fmt.get("vcodec", ""))
            return (
                int(fmt.get("fps") or 0),
                codec.startswith("vp9") or codec.startswith("vp09"),
                fmt.get("protocol") in ("https", "http"),
                float(fmt.get("tbr") or 0),
            )
        selected = max(candidates, key=score)
        codec = str(selected.get("vcodec", ""))
        extension = "webm" if codec.startswith(("vp9", "vp09")) else "mp4"
        audio = _select_audio(formats, extension)
        if audio is None and selected.get("acodec") in (None, "none"):
            continue
        video_size = selected.get("filesize") or selected.get("filesize_approx")
        audio_size = (audio or {}).get("filesize") or (audio or {}).get("filesize_approx")
        estimate = int(video_size + (audio_size or 0)) if video_size else None
        choices.append(FormatChoice(
            quality=quality,
            width=int(selected["width"]),
            height=int(selected["height"]),
            fps=int(selected.get("fps") or 30),
            video_id=str(selected["format_id"]),
            audio_id=str(audio["format_id"]) if audio else None,
            extension=extension,
            estimated_bytes=estimate,
        ))
    return tuple(sorted(choices, key=lambda item: item.quality, reverse=True))


def _options(node_path: Path) -> dict:
    return {
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "noplaylist": True,
        "js_runtimes": {"node": {"path": str(node_path)}},
    }


def inspect_video(url: str, node_path: Path) -> VideoDetails:
    url = normalize_url(url)
    with yt_dlp.YoutubeDL(_options(node_path)) as ydl:
        info = ydl.extract_info(url, download=False)
    if not isinstance(info, dict) or info.get("_type") == "playlist":
        raise ValueError("请粘贴单个视频链接。")
    choices = _select_choices(info.get("formats") or [])
    if not choices:
        raise ValueError("没有找到可下载的视频画质。")
    return VideoDetails(
        url=url,
        video_id=str(info.get("id") or ""),
        title=str(info.get("title") or "未命名视频"),
        channel=str(info.get("uploader") or info.get("channel") or "YouTube"),
        duration=int(info["duration"]) if info.get("duration") else None,
        choices=choices,
    )


def download_video(
    details: VideoDetails,
    choice: FormatChoice,
    destination: Path,
    node_path: Path,
    ffmpeg_path: Path,
    progress: Callable[[int], None],
    stage: Callable[[str], None],
    cancelled: Event,
) -> Path:
    destination.mkdir(parents=True, exist_ok=True)
    if cancelled.is_set():
        raise DownloadCancelled()
    last_progress = 0

    def on_progress(status: dict) -> None:
        nonlocal last_progress
        if cancelled.is_set():
            raise DownloadCancelled()
        if status.get("status") != "downloading":
            return
        stream_id = str((status.get("info_dict") or {}).get("format_id") or "")
        total = status.get("total_bytes") or status.get("total_bytes_estimate")
        if not total:
            return
        fraction = min(1.0, (status.get("downloaded_bytes") or 0) / total)
        if choice.audio_id and stream_id == choice.audio_id:
            current = 88 + int(10 * fraction)
            stage("正在下载音频…")
        else:
            current = int(88 * fraction) if choice.audio_id else int(98 * fraction)
            stage("正在下载视频…")
        last_progress = max(last_progress, current)
        progress(last_progress)

    def on_postprocess(status: dict) -> None:
        if cancelled.is_set():
            raise DownloadCancelled()
        if status.get("status") == "started":
            stage("正在合并视频和音频…")
            progress(98)

    opts = _options(node_path)
    opts.update({
        "format": choice.video_id + (f"+{choice.audio_id}" if choice.audio_id else ""),
        "paths": {"home": str(destination)},
        "outtmpl": "%(title).150B [%(id)s].%(ext)s",
        "merge_output_format": choice.extension,
        "ffmpeg_location": str(ffmpeg_path),
        "progress_hooks": [on_progress],
        "postprocessor_hooks": [on_postprocess],
        "continuedl": True,
        "overwrites": False,
    })
    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.extract_info(details.url, download=True)
    if cancelled.is_set():
        raise DownloadCancelled()
    suffix = f"[{details.video_id}].{choice.extension}"
    matches = [path for path in destination.iterdir() if path.is_file() and path.name.endswith(suffix)]
    if not matches:
        raise RuntimeError("下载完成，但未找到合并后的文件。")
    progress(100)
    return max(matches, key=lambda path: path.stat().st_mtime)
