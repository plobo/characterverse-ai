from __future__ import annotations

import pytest

from app.services.moderation import DenyList, ImitationPatternClassifier, Moderator, normalize
from tests.conftest import FIXTURES, template_recipe


@pytest.fixture
def moderator():
    return Moderator(DenyList.from_file(FIXTURES / "test_denylist.txt"), ImitationPatternClassifier.default())


@pytest.mark.parametrize(
    "text",
    [
        "Captain Starlance",
        "make me captain starlance with a red cape",
        "C4pt4in St4rl4nce",  # leetspeak
        "Captian Starlance",  # transposed letters
        "captain star lance",  # spacing trick
        "CAPTAIN  STARLANCEEE",  # repeated letters
        "Prinçess Quíllara",  # accents
        "megaglimmerbot",  # glued tokens
        "Mega Glimerbot",  # missing letter
    ],
)
def test_denylist_variants_blocked(moderator, text):
    result = moderator.check(text)
    assert result.decision == "block" and result.reason_code == "PROTECTED_CHARACTER_REFERENCE"


@pytest.mark.parametrize(
    "text",
    [
        "an exact copy of the famous superhero from the movie",
        "a lookalike of the mascot, same costume as the one from the game",
    ],
)
def test_indirect_imitation_blocked(moderator, text):
    assert moderator.check(text).decision == "block"


def test_single_indirect_signal_flagged_not_blocked(moderator):
    r = moderator.check("a forest guardian in the style of an old painting")
    assert r.decision == "flag" and r.reason_code == "POSSIBLE_IMITATION"


@pytest.mark.parametrize(
    "text", ["A kind moth knight who loves tea", "captain of a starship", "glimmering robot", "a princess of quills"]
)
def test_original_prompts_allowed(moderator, text):
    assert moderator.check(text).decision == "allow"


def test_normalize():
    assert normalize("  H3ll0,  W0rld!! ") == "hello world"


def test_blocked_prompt_returns_error_and_is_audited(client, auth, container):
    r = client.post("/v1/characters/generate-recipe", headers=auth, json={"description": "C4ptain Starlance"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "MODERATION_BLOCKED"
    from app.domain.models import ModerationEvent

    with container.db.session() as s:
        ev = s.query(ModerationEvent).filter_by(decision="block").one()
        assert ev.reason_code == "PROTECTED_CHARACTER_REFERENCE" and ev.policy_version


def test_blocked_character_name(client, auth, container):
    recipe = template_recipe(container, "tmpl_voltwood_guardian")
    recipe["name"] = "Princess Quillara"
    r = client.post("/v1/characters", json={"recipe": recipe}, headers=auth)
    assert r.json()["error"]["code"] == "MODERATION_BLOCKED"


def test_check_endpoint_and_reports(client, auth):
    r = client.post("/v1/moderation/check", headers=auth, json={"text": "megaglimmerbot", "contentType": "name"})
    assert r.json()["decision"] == "block" and r.json()["feedback"]
    rep = client.post(
        "/v1/reports",
        headers=auth,
        json={"contentType": "character", "contentId": "abc", "reason": "copyright", "details": "looks copied"},
    )
    assert rep.status_code == 201 and rep.json()["status"] == "open"
