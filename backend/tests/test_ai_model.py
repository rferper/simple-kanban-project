"""Extraction by model call — issue #20.

No network and no API key: the SDK client is replaced with a stub, so these
tests are about the things that are actually ours — which reader gets chosen,
how the model's answer is mapped onto the API's shape, and what a user sees when
the call fails.

What is deliberately *not* tested here is whether Claude reads adverts well.
That is not something a unit test can assert, and pretending otherwise with a
canned response would only test the stub.
"""

import pytest

from app import ai, ai_model
from app.ai_model import Extraction
from app.errors import AiUnreadable

ADVERT = """\
Nimbus Labs is hiring a Senior Research Engineer to work on large scale language
model evaluation.

Location: Berlin
This is a hybrid role.

Requirements
- Strong Python and PyTorch
- Published research in NLP
"""


class FakeResponse:
    def __init__(self, parsed):
        self.parsed_output = parsed


class FakeMessages:
    """Stands in for `client.messages`, and records what it was asked."""

    def __init__(self, parsed=None, error=None):
        self.parsed = parsed
        self.error = error
        self.calls = []

    def parse(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return FakeResponse(self.parsed)


class FakeClient:
    def __init__(self, parsed=None, error=None):
        self.messages = FakeMessages(parsed=parsed, error=error)


def a_parsed(**overrides) -> Extraction:
    values = dict(
        company="Nimbus Labs",
        role="Senior Research Engineer",
        location="Berlin",
        salary_text="EUR 90,000 - 120,000",
        work_mode="HYBRID",
        application_deadline="2026-11-30",
        requirements=["Strong Python and PyTorch", "Published research in NLP"],
        nice_to_have=["Interpretability"],
        summary="Large scale language model evaluation at Nimbus Labs.",
        tags=["python", "nlp"],
    )
    values.update(overrides)
    return Extraction(**values)


@pytest.fixture
def use_model(monkeypatch):
    """Force the model reader and hand it a stub client."""
    monkeypatch.setenv("NEXTLANE_AI", "model")

    def install(parsed=None, error=None):
        client = FakeClient(parsed=parsed, error=error)
        monkeypatch.setattr(ai_model, "_client", lambda: client)
        return client

    return install


@pytest.fixture(autouse=True)
def no_ambient_key(monkeypatch):
    """Never let a real key on the developer's machine change what these do."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("NEXTLANE_AI", raising=False)


class TestChoosingAReader:
    def test_without_a_key_it_is_the_heuristic(self):
        assert ai.reader() == "heuristic"

    def test_with_a_key_it_is_the_model(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-not-a-real-key")
        assert ai.reader() == "model"

    def test_the_choice_can_be_forced_either_way(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-not-a-real-key")
        monkeypatch.setenv("NEXTLANE_AI", "heuristic")
        assert ai.reader() == "heuristic"

        monkeypatch.delenv("ANTHROPIC_API_KEY")
        monkeypatch.setenv("NEXTLANE_AI", "model")
        assert ai.reader() == "model"

    def test_an_unrecognised_setting_falls_back_to_auto(self, monkeypatch):
        monkeypatch.setenv("NEXTLANE_AI", "nonsense")
        assert ai.reader() == "heuristic"


class TestTheModelPath:
    def test_the_result_is_mapped_onto_the_api_shape(self, use_model):
        use_model(parsed=a_parsed())
        result = ai.extract(ADVERT)

        assert result.extracted.company == "Nimbus Labs"
        assert result.extracted.role == "Senior Research Engineer"
        assert result.extracted.work_mode == "HYBRID"
        assert str(result.extracted.application_deadline) == "2026-11-30"
        assert result.extracted.requirements == [
            "Strong Python and PyTorch",
            "Published research in NLP",
        ]

    def test_the_result_says_the_model_read_it(self, use_model):
        use_model(parsed=a_parsed())
        assert ai.extract(ADVERT).source == "model"

    def test_the_advert_is_what_gets_sent(self, use_model):
        client = use_model(parsed=a_parsed())
        ai.extract(ADVERT)

        call = client.messages.calls[0]
        assert call["messages"][0]["content"].startswith("Nimbus Labs is hiring")
        assert call["messages"][0]["role"] == "user"

    def test_it_asks_for_a_validated_schema(self, use_model):
        """Structured output, not prose with JSON in it."""
        client = use_model(parsed=a_parsed())
        ai.extract(ADVERT)
        assert client.messages.calls[0]["output_format"] is Extraction

    def test_the_system_prompt_forbids_scoring_the_candidate(self, use_model):
        """§15.2 — the app must not judge suitability, so the prompt says so."""
        client = use_model(parsed=a_parsed())
        ai.extract(ADVERT)
        assert "fit" in client.messages.calls[0]["system"].lower()

    def test_the_system_prompt_treats_the_advert_as_untrusted(self, use_model):
        """It is text pasted from the internet; instructions in it are not ours."""
        client = use_model(parsed=a_parsed())
        ai.extract(ADVERT)
        system = client.messages.calls[0]["system"].lower()
        assert "untrusted" in system
        assert "ignore" in system

    def test_fit_is_not_in_the_schema_at_all(self):
        """A field the model cannot fill is a field it cannot invent."""
        assert "fit" not in Extraction.model_fields

    def test_a_very_long_advert_is_capped(self, use_model):
        client = use_model(parsed=a_parsed())
        ai.extract("word " * 20_000)
        assert len(client.messages.calls[0]["messages"][0]["content"]) <= ai_model.MAX_ADVERT_CHARS


class TestMappingTheAnswer:
    def test_a_nonsense_work_mode_becomes_unknown(self, use_model):
        use_model(parsed=a_parsed(work_mode="WHENEVER"))
        assert ai.extract(ADVERT).extracted.work_mode == "UNKNOWN"

    def test_work_mode_is_case_insensitive(self, use_model):
        use_model(parsed=a_parsed(work_mode="hybrid"))
        assert ai.extract(ADVERT).extracted.work_mode == "HYBRID"

    def test_a_malformed_date_is_dropped_not_fatal(self, use_model):
        """The user is about to see and edit this anyway (§15.3)."""
        use_model(parsed=a_parsed(application_deadline="two weeks from now"))
        assert ai.extract(ADVERT).extracted.application_deadline is None

    def test_a_missing_date_stays_missing(self, use_model):
        use_model(parsed=a_parsed(application_deadline=None))
        assert ai.extract(ADVERT).extracted.application_deadline is None

    def test_whitespace_is_tidied(self, use_model):
        use_model(parsed=a_parsed(company="  Nimbus   Labs \n"))
        assert ai.extract(ADVERT).extracted.company == "Nimbus Labs"

    def test_empty_list_items_are_dropped(self, use_model):
        use_model(parsed=a_parsed(requirements=["Python", "   ", ""]))
        assert ai.extract(ADVERT).extracted.requirements == ["Python"]

    def test_tags_are_lowercased_and_capped(self, use_model):
        use_model(parsed=a_parsed(tags=["Python", "NLP", "ML", "AI", "Research", "Extra"]))
        tags = ai.extract(ADVERT).extracted.tags
        assert tags == ["python", "nlp", "ml", "ai", "research"]

    def test_missing_fields_are_reported_not_invented(self, use_model):
        use_model(parsed=a_parsed(company="", role=""))
        result = ai.extract(ADVERT)
        assert set(result.missing) == {"company", "role"}
        assert result.confidence == "partial"


class TestWhenTheModelFails:
    @pytest.mark.parametrize(
        "error",
        [
            ConnectionError("no route to host"),
            TimeoutError("took too long"),
            RuntimeError("rate limited"),
            ValueError("the response did not validate"),
        ],
    )
    def test_every_failure_becomes_one_friendly_message(self, use_model, error):
        use_model(error=error)
        with pytest.raises(AiUnreadable) as raised:
            ai.extract(ADVERT)
        assert "manually" in str(raised.value)

    def test_the_failure_does_not_leak_the_detail_to_the_user(self, use_model):
        """An API key or an internal URL must not reach the paste box."""
        use_model(error=RuntimeError("401 invalid x-api-key sk-ant-secret"))
        with pytest.raises(AiUnreadable) as raised:
            ai.extract(ADVERT)
        assert "sk-ant-secret" not in str(raised.value)
        assert "401" not in str(raised.value)

    def test_it_does_not_quietly_fall_back_to_the_regex(self, use_model):
        """Silently downgrading would hide a broken integration behind output
        that looks plausible."""
        use_model(error=RuntimeError("down"))
        with pytest.raises(AiUnreadable):
            ai.extract(ADVERT)

    def test_a_short_advert_never_reaches_the_model(self, use_model):
        """Nine characters should not cost money."""
        client = use_model(parsed=a_parsed())
        with pytest.raises(AiUnreadable):
            ai.extract("too short")
        assert client.messages.calls == []


CONVENTIONAL_ADVERT = """Nimbus Labs

Senior Research Engineer

Nimbus Labs is hiring a Senior Research Engineer to work on large scale language
model evaluation.

Location: Berlin
This is a hybrid role.

Requirements
- Strong Python and PyTorch
"""


class TestTheHeuristicStillWorks:
    """The fallback is the reason a fresh clone works without an API key."""

    def test_it_reads_a_conventionally_laid_out_advert(self):
        result = ai.extract(CONVENTIONAL_ADVERT)
        assert result.extracted.company == "Nimbus Labs"
        assert result.extracted.role == "Senior Research Engineer"
        assert result.extracted.location == "Berlin"

    def test_it_says_it_was_the_heuristic(self):
        assert ai.extract(CONVENTIONAL_ADVERT).source == "heuristic"

    def test_the_endpoint_works_without_any_key(self, client):
        response = client.post(
            "/api/ai/extract-job-advert", json={"advert": CONVENTIONAL_ADVERT}
        )
        assert response.status_code == 200
        assert response.json()["source"] == "heuristic"


class TestWhyTheModelIsWorthIt:
    """The honest limitation of a regex, recorded rather than papered over.

    The heuristic wants an advert laid out the way it expects - the role on its
    own line near the top. Written as prose, it takes the whole sentence. This is
    the case issue #20 exists for, and the reason the fallback is a fallback."""

    def test_prose_defeats_the_heuristic(self):
        result = ai.extract(ADVERT)
        assert result.extracted.role != "Senior Research Engineer"
        assert result.source == "heuristic"

    def test_the_model_handles_the_same_advert(self, use_model):
        use_model(parsed=a_parsed())
        result = ai.extract(ADVERT)
        assert result.extracted.role == "Senior Research Engineer"
        assert result.source == "model"
