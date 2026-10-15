"""Pillow compositor for the documentary timeline.

Text is shaped with the local Devanagari font. Frames are streamed to FFmpeg.
No browser, no Flow, and no remote fonts.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from PIL import Image, ImageDraw

from animation_core.outputs import ffmpeg_exe

from .textutil import TextLayoutError, colorize, shape

WIDTH = 1920
HEIGHT = 1080
LINE_Y = 560


def ease(value: float) -> float:
    value = max(0.0, min(1.0, value))
    return value * value * (3 - 2 * value)


def _hex(value: str) -> tuple[int, int, int]:
    return tuple(int(value[index:index + 2], 16) for index in (1, 3, 5))


def _gradient(top: str, bottom: str) -> Image.Image:
    column = Image.new("RGB", (1, HEIGHT))
    draw = ImageDraw.Draw(column)
    start, end = _hex(top), _hex(bottom)
    for y in range(HEIGHT):
        mix = y / (HEIGHT - 1)
        colour = tuple(round(start[channel] + (end[channel] - start[channel]) * mix) for channel in range(3))
        draw.point((0, y), fill=colour)
    return column.resize((WIDTH, HEIGHT), Image.Resampling.BILINEAR)


def _head(events: list[dict], t: float, overview: float) -> float:
    if t >= overview:
        return events[-1]["x"]
    for index, event in enumerate(events):
        nxt_t = events[index + 1]["reveal"] if index + 1 < len(events) else overview
        nxt_x = events[index + 1]["x"] if index + 1 < len(events) else event["x"]
        if t < event["reveal"]:
            return events[0]["x"]
        if t < nxt_t:
            span = max(0.001, nxt_t - event["reveal"])
            return event["x"] + (nxt_x - event["x"]) * ease((t - event["reveal"]) / span)
    return events[-1]["x"]


class TimelineRenderer:
    def __init__(self, compiled: dict):
        self.plan = compiled
        self.style = compiled["style"]
        self.background = _gradient(self.style["background"], self.style["background_end"]).convert("RGBA")
        self.assets = self._prepare()

    def _prepare(self) -> dict:
        style = self.style
        title = shape(self.plan["title"], 46, 1480, 130)
        labels = []
        for event in self.plan["events"]:
            box = int(event["caption_width"])
            try:
                year = shape(event["date_label"], 72, box, 120)
                caption = shape(event["caption"], 32, box, 150)
            except TextLayoutError as error:
                raise TextLayoutError(f"{event['id']}: {error}") from error
            labels.append({
                "year_accent": colorize(year, style["accent"]),
                "year_text": colorize(year, style["text"]),
                "caption": colorize(caption, style["text"]),
            })
        return {"title": colorize(title, style["text"]), "labels": labels}

    def frame(self, t: float) -> Image.Image:
        plan = self.plan
        style = self.style
        events = plan["events"]
        overview = plan["overview_start"]
        image = self.background.copy()
        draw = ImageDraw.Draw(image)
        title = self.assets["title"]
        image.alpha_composite(title, ((WIDTH - title.width) // 2, 108))
        rule_y = 108 + title.height + 18
        draw.line((WIDTH // 2 - 90, rule_y, WIDTH // 2 + 90, rule_y), fill=style["accent"], width=3)

        xs = [event["x"] for event in events]
        draw.line((xs[0], LINE_Y, xs[-1], LINE_Y), fill=style["track"], width=4)
        head = _head(events, t, overview)
        if head > xs[0]:
            draw.line((xs[0], LINE_Y, head, LINE_Y), fill=style["accent"], width=6)

        transition = float(style["transition_seconds"])
        emphasis = plan["emphasis_event"]
        for index, event in enumerate(events):
            revealed = t >= event["reveal"] or t >= overview
            future = not revealed
            radius = 6
            ring = False
            if revealed:
                grown = 1.0 if t >= overview else ease(min(1.0, (t - event["reveal"]) / 0.35))
                radius = 7 + 6 * grown
                active = t >= overview and event["id"] == emphasis
                if not active and t < overview:
                    nxt = events[index + 1]["reveal"] if index + 1 < len(events) else overview
                    active = event["reveal"] <= t < nxt
                ring = active
            colour = style["muted"] if future else (style["accent"] if ring else style["text"])
            x = event["x"]
            draw.ellipse((x - radius, LINE_Y - radius, x + radius, LINE_Y + radius), fill=colour)
            if ring:
                outer = radius + 11
                draw.ellipse(
                    (x - outer, LINE_Y - outer, x + outer, LINE_Y + outer),
                    outline=style["accent"],
                    width=3,
                )
            if future:
                continue
            opacity = 1.0 if t >= overview else ease(min(1.0, (t - event["reveal"]) / transition))
            labels = self.assets["labels"][index]
            year = labels["year_accent"] if ring else labels["year_text"]
            self._paste(image, year, x, LINE_Y - year.height - 36, opacity)
            caption = labels["caption"]
            self._paste(image, caption, x, LINE_Y + 42, opacity)
        return image.convert("RGB")

    @staticmethod
    def _paste(image: Image.Image, layer: Image.Image, x: float, y: float, opacity: float) -> None:
        if opacity <= 0.01:
            return
        sprite = layer
        if opacity < 0.999:
            red, green, blue, alpha = layer.split()
            alpha = alpha.point(lambda pixel: int(pixel * opacity))
            sprite = Image.merge("RGBA", (red, green, blue, alpha))
        image.alpha_composite(sprite, (int(round(x - sprite.width / 2)), int(round(y))))

    def still_times(self) -> list[tuple[str, str, float]]:
        events = self.plan["events"]
        overview = self.plan["overview_start"]
        chosen = []
        for index, event in enumerate(events):
            nxt = events[index + 1]["reveal"] if index + 1 < len(events) else overview
            moment = min(event["reveal"] + 0.9, nxt - 0.05)
            chosen.append((f"milestone-{index + 1:02d}", event["date_label"], moment))
        chosen.append(("overview", "अवलोकन", min(self.plan["duration_seconds"] - 0.2, overview + 0.5)))
        return chosen

    def write_stills(self, directory: Path) -> list[dict]:
        directory.mkdir(parents=True, exist_ok=True)
        written = []
        for name, label, moment in self.still_times():
            path = directory / f"{name}.png"
            self.frame(moment).save(path)
            written.append({"name": name, "label": label, "time": moment, "path": str(path)})
        return written

    def contact_sheet(self, stills: list[dict], path: Path) -> None:
        thumbs = []
        for still in stills:
            with Image.open(still["path"]) as source:
                frame = source.convert("RGB").resize((760, 428), Image.Resampling.LANCZOS)
            label = shape(still["label"], 28, 720, 50)
            label = colorize(label, "#F4F0E8")
            card = Image.new("RGB", (800, 560), "#10161E")
            card.paste(frame, (20, 16))
            sprite = label
            card.paste(sprite, ((800 - sprite.width) // 2, 468), sprite)
            thumbs.append(card)
        columns = 2 if len(thumbs) <= 4 else 3
        rows = (len(thumbs) + columns - 1) // columns
        sheet = Image.new("RGB", (columns * 800, rows * 560), "#0B1016")
        for index, card in enumerate(thumbs):
            sheet.paste(card, ((index % columns) * 800, (index // columns) * 560))
        path.parent.mkdir(parents=True, exist_ok=True)
        sheet.save(path)

    def encode(self, path: Path) -> None:
        fps = int(self.plan["fps"])
        frames = int(round(self.plan["duration_seconds"] * fps))
        path.parent.mkdir(parents=True, exist_ok=True)
        command = [
            ffmpeg_exe(), "-y", "-loglevel", "error",
            "-f", "rawvideo", "-pix_fmt", "rgb24",
            "-s", f"{WIDTH}x{HEIGHT}", "-r", str(fps), "-i", "-",
            "-an", "-c:v", "libx264", "-preset", "fast", "-crf", "18",
            "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(path),
        ]
        proc = subprocess.Popen(command, stdin=subprocess.PIPE)
        try:
            for number in range(frames):
                frame = self.frame(number / fps)
                proc.stdin.write(frame.tobytes())
        except Exception:
            proc.kill()
            raise
        finally:
            if proc.stdin:
                proc.stdin.close()
            code = proc.wait()
        if code != 0:
            raise RuntimeError(f"FFmpeg exited {code}")


def render_compiled(compiled: dict, output_mp4: Path, still_dir: Path, contact_path: Path) -> dict:
    renderer = TimelineRenderer(compiled)
    output_mp4.parent.mkdir(parents=True, exist_ok=True)
    partial = output_mp4.with_name(output_mp4.stem + ".partial.mp4")
    try:
        renderer.encode(partial)
    except Exception:
        partial.unlink(missing_ok=True)
        raise
    stills = renderer.write_stills(still_dir)
    renderer.contact_sheet(stills, contact_path)
    poster = still_dir / "overview.png"
    return {"partial": partial, "stills": stills, "poster": poster, "contact_sheet": contact_path}
