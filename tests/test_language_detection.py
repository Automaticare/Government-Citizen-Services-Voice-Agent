"""
Language detection and switching tests via ElevenLabs conversation simulation.

Verifies that the multilingual agent:
- Responds in Turkish when caller speaks Turkish
- Responds in English when caller speaks English
- Switches language when caller changes language mid-conversation

Run:
    python -m pytest tests/test_language_detection.py -v -s
"""

import os
import pytest
from elevenlabs.client import ElevenLabs
from elevenlabs.types import (
    AgentConfig as ELAgentConfig,
    ConversationSimulationSpecification,
    PromptEvaluationCriteria,
)
from agent.config import AgentConfig


LANGUAGE_SCENARIOS = [
    {
        "name": "turkish_conversation",
        "persona": "Sen bir Türk vatandaşısın. Türkçe konuş. Randevu almak istediğini söyle.",
        "criteria": "Agent Türkçe yanıt verdi. Yanıtın tamamı Türkçe olmalı.",
    },
    {
        "name": "english_conversation",
        "persona": "You are an English-speaking citizen. Speak only in English. Ask about appointment booking.",
        "criteria": "After the user's first English message, the agent switched to English for subsequent responses. The first greeting may be in Turkish (primary language) which is expected.",
    },
    {
        "name": "english_status_check",
        "persona": "You are an English speaker. Ask to check your application status. Speak only English throughout.",
        "criteria": "Agent detected English and responded in English with application status check flow.",
    },
    {
        "name": "turkish_then_english",
        "persona": "Sen bir vatandaşsın. İlk mesajında Türkçe konuş ve randevu sor. Sonra ikinci mesajında İngilizceye geç ve 'Can you speak English?' de. Bundan sonra sadece İngilizce konuş.",
        "criteria": "Agent initially responded in Turkish, then switched to English after the user requested it.",
    },
    {
        "name": "english_greeting_turkish_continue",
        "persona": "You start by saying 'Hello' in English, but then switch to Turkish for the rest. Say 'Aslında Türkçe konuşabilir miyiz? Başvurumun durumunu öğrenmek istiyorum.'",
        "criteria": "Agent switched to Turkish after detecting the user's preference, and continued the conversation in Turkish.",
    },
]


@pytest.mark.skipif(
    not os.getenv("ELEVENLABS_API_KEY"),
    reason="ELEVENLABS_API_KEY not set — skipping live simulation tests",
)
class TestLanguageDetection:
    """Test language detection and switching via ElevenLabs conversation simulation."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.config = AgentConfig()
        self.client = ElevenLabs(api_key=self.config.api_key)

    @pytest.mark.parametrize(
        "scenario",
        LANGUAGE_SCENARIOS,
        ids=[s["name"] for s in LANGUAGE_SCENARIOS],
    )
    def test_scenario(self, scenario):
        """Run a simulated conversation and evaluate language handling."""
        result = self.client.conversational_ai.agents.simulate_conversation(
            agent_id=self.config.agent_id,
            simulation_specification=ConversationSimulationSpecification(
                simulated_user_config=ELAgentConfig(
                    prompt={"prompt": scenario["persona"]},
                ),
            ),
            extra_evaluation_criteria=[
                PromptEvaluationCriteria(
                    id=scenario["name"],
                    name=scenario["name"],
                    conversation_goal_prompt=scenario["criteria"],
                ),
            ],
            new_turns_limit=6,
        )

        def safe_print(text: str) -> None:
            print(text.encode("ascii", errors="replace").decode("ascii"))

        safe_print(f"\n{'='*60}")
        safe_print(f"Scenario: {scenario['name']}")
        safe_print(f"{'='*60}")
        if result.simulated_conversation:
            for turn in result.simulated_conversation:
                safe_print(f"  {turn.role}: {turn.message}")

        assert result.analysis, f"Scenario '{scenario['name']}' returned no analysis"

        if result.analysis.transcript_summary:
            safe_print(f"\n  Summary: {result.analysis.transcript_summary}")

        for eval_result in (result.analysis.evaluation_criteria_results_list or []):
            safe_print(f"  Eval [{eval_result.criteria_id}]: {eval_result.result}")
            safe_print(f"  Rationale: {eval_result.rationale}")
            assert eval_result.result == "success", (
                f"Scenario '{scenario['name']}' failed: {eval_result.rationale}"
            )
