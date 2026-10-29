"""Every provider ships a complete GUIDE.md, and the skill files stay valid."""

import re
from pathlib import Path

import pytest
import yaml

from hyrox_coach.providers import AVAILABLE, PLANNED, guide

ROOT = Path(__file__).resolve().parent.parent
SKILL_DIR = ROOT / "skills" / "hyrox-coach"
REQUIRED_SECTIONS = ["## What it supplies", "## Reading the data", "## Traps", "## Recording sessions",
                     "## Setup and troubleshooting"]


@pytest.mark.parametrize("name", [*AVAILABLE, *PLANNED])
def test_every_provider_has_a_complete_guide(name):
    text = guide(name)
    assert text.startswith("# "), "guide needs a title"
    assert re.search(r"^Status: (available|planned)", text, re.M), "guide needs a Status line"
    for section in REQUIRED_SECTIONS:
        assert section in text, f"{name} guide is missing '{section}'"


@pytest.mark.parametrize("name", [*AVAILABLE, *PLANNED])
def test_guides_never_ask_for_secrets_in_chat(name):
    assert "never ask the athlete" in guide(name).lower()


def test_skill_frontmatter_is_valid_yaml():
    text = (SKILL_DIR / "SKILL.md").read_text()
    fm = yaml.safe_load(text.split("---")[1])
    assert fm["name"] == "hyrox-coach"
    assert 50 < len(fm["description"]) <= 1024


def test_skill_only_mentions_tools_that_exist():
    server_src = (ROOT / "src" / "hyrox_coach" / "server.py").read_text()
    tools = set(re.findall(r"@_guard\ndef (\w+)\(", server_src))
    assert {"get_data_source", "get_readiness", "log_session_note"} <= tools
    text = "".join(p.read_text() for p in SKILL_DIR.rglob("*.md"))
    mentioned = set(re.findall(r"`((?:get|list|log|set)_[a-z_]+)(?:\(|`)", text))
    assert mentioned <= tools, f"skill mentions unknown tools: {mentioned - tools}"


def test_skill_reference_files_are_all_linked():
    skill = (SKILL_DIR / "SKILL.md").read_text()
    for ref in (SKILL_DIR / "references").glob("*.md"):
        assert f"references/{ref.name}" in skill, f"{ref.name} is not linked from SKILL.md"
