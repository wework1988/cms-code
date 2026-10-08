from __future__ import annotations

from pathlib import Path

import pytest

from helper.prompts import (
    detect_format,
    filter_scene_range,
    parse_image_prompts,
    scene_filename_stem,
)

SAMPLE = Path(__file__).resolve().parents[3] / "general" / "165-pakistan-army" / "image-prompts" / "image-prompts-only.txt"


def test_scene_filename_padding():
    assert scene_filename_stem(1) == "001"
    assert scene_filename_stem(12) == "012"
    assert scene_filename_stem(202) == "202"
    assert scene_filename_stem(1000) == "1000"


def test_multiline_pipe_delimited():
    text = "Scene 1. Hello\n\nworld paragraph||\nScene 2. Second\nline||\n"
    scenes = parse_image_prompts(text)
    assert [s.scene for s in scenes] == [1, 2]
    assert "world paragraph" in scenes[0].text
    assert "Second\nline" in scenes[1].text


def test_crlf_and_bom():
    text = "\ufeffScene 1. A||\r\nScene 2. B||\r\n"
    scenes = parse_image_prompts(text)
    assert len(scenes) == 2
    assert scenes[0].text.startswith("Scene 1.")


def test_duplicate_scene_error():
    text = "Scene 1. A||\nScene 1. B||\n"
    with pytest.raises(ValueError, match="Duplicate scene number 1"):
        parse_image_prompts(text)


def test_missing_heading_error():
    text = "No heading here||\nScene 2. Ok||\n"
    with pytest.raises(ValueError, match="missing Scene"):
        parse_image_prompts(text)


def test_non_contiguous_sorted():
    text = "Scene 10. Ten||\nScene 2. Two||\nScene 5. Five||\n"
    scenes = parse_image_prompts(text)
    assert [s.scene for s in scenes] == [2, 5, 10]


def test_scene_range_and_list():
    text = "Scene 1. A||\nScene 2. B||\nScene 3. C||\n"
    scenes = parse_image_prompts(text)
    assert [s.scene for s in filter_scene_range(scenes, 1, 2)] == [1, 2]
    assert [s.scene for s in filter_scene_range(scenes, scene_list=[1, 3])] == [1, 3]
    with pytest.raises(ValueError, match="not in prompt"):
        filter_scene_range(scenes, scene_list=[9])


def test_detect_format():
    assert detect_format("Scene 1. x||\nScene 2. y||") == "pipe_delimited_scene_blocks"


@pytest.mark.skipif(not SAMPLE.is_file(), reason="sample story not present")
def test_real_pakistan_army_sample():
    text = SAMPLE.read_text(encoding="utf-8")
    scenes = parse_image_prompts(text)
    assert len(scenes) == 202
    assert scenes[0].scene == 1
    assert scenes[-1].scene == 202
    assert scenes[0].text.startswith("Scene 1.")
    assert "||" not in scenes[0].text
    # Prompt body is long and multi-sentence
    assert len(scenes[0].text) > 500
    selected = filter_scene_range(scenes, 1, 2)
    assert [s.scene for s in selected] == [1, 2]
