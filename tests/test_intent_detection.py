"""
Intent detection tests via ElevenLabs conversation simulation.

Uses the platform's simulate_conversation API to verify the agent
correctly identifies intents from various opening prompts.

Run:
    python -m pytest tests/test_intent_detection.py -v -s
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


SCENARIOS = [
    # (description, simulated_user_persona, evaluation_criteria)
    {
        "name": "status_check_tr",
        "persona": "Sen bir Türk vatandaşısın. Pasaport başvurunun durumunu öğrenmek istiyorsun. Kısa ve net konuş.",
        "criteria": "Agent doğru şekilde başvuru durumu sorgulama intent'ini algıladı ve kimlik doğrulama sürecini başlattı.",
    },
    {
        "name": "appointment_booking_tr",
        "persona": "Sen bir Türk vatandaşısın. Nüfus müdürlüğünden randevu almak istiyorsun. Ehliyet yenileme için.",
        "criteria": "Agent randevu alma intent'ini doğru algıladı ve hizmet türü ile tarih bilgisi sormaya başladı.",
    },
    {
        "name": "document_request_tr",
        "persona": "Sen bir Türk vatandaşısın. İkametgah belgesi talep etmek istiyorsun.",
        "criteria": "Agent belge talebi intent'ini algıladı ve kimlik doğrulama sürecini başlattı.",
    },
    {
        "name": "general_question_tr",
        "persona": "Sen bir Türk vatandaşısın. Pasaport başvurusu için hangi belgeler gerektiğini sormak istiyorsun.",
        "criteria": "Agent genel soru intent'ini algıladı ve bilgi vermeye çalıştı.",
    },
    {
        "name": "fee_inquiry_tr",
        "persona": "Sen bir Türk vatandaşısın. Ehliyet yenileme ücretini öğrenmek istiyorsun. Sadece fiyat bilgisi soruyorsun.",
        "criteria": "Agent ücret/harç bilgisi intent'ini algıladı ve fiyat bilgisi vermeye çalıştı.",
    },
    {
        "name": "complaint_tr",
        "persona": "Sen bir Türk vatandaşısın. Geçen hafta randevuna gittin ama 2 saat bekletildikten sonra geri çevrildin. Şikayet etmek istiyorsun.",
        "criteria": "Agent şikayet intent'ini algıladı ve şikayeti kayıt altına almaya başladı.",
    },
    {
        "name": "human_transfer_tr",
        "persona": "Sen bir Türk vatandaşısın. Robot ile konuşmak istemiyorsun, direkt bir insanla görüşmek istiyorsun. Bunu ilk cümlende söyle.",
        "criteria": "Agent operatöre bağlanma intent'ini algıladı ve transfer sürecini başlattı.",
    },
    {
        "name": "status_check_en",
        "persona": "You are a citizen. You want to check the status of your visa application. Be brief.",
        "criteria": "Agent detected the application status check intent and responded in English.",
    },
    {
        "name": "out_of_scope_tr",
        "persona": "Sen bir Türk vatandaşısın. Vergi borcunu öğrenmek istiyorsun. Bu agent'ın kapsamı dışında bir konu.",
        "criteria": "Agent bu konunun kendi hizmet alanı dışında olduğunu belirtti ve doğru yönlendirme yaptı.",
    },
    {
        "name": "guardrail_legal_tr",
        "persona": "Sen bir Türk vatandaşısın. Başvurun reddedildi ve dava açmak istiyorsun. Agent'tan hukuki tavsiye istiyorsun.",
        "criteria": "Agent hukuki tavsiye vermekten kaçındı ve bir avukata danışmayı önerdi.",
    },
]


@pytest.mark.skipif(
    not os.getenv("ELEVENLABS_API_KEY"),
    reason="ELEVENLABS_API_KEY not set — skipping live simulation tests",
)
class TestIntentDetection:
    """Test intent detection via ElevenLabs conversation simulation."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.config = AgentConfig()
        self.client = ElevenLabs(api_key=self.config.api_key)

    @pytest.mark.parametrize(
        "scenario",
        SCENARIOS,
        ids=[s["name"] for s in SCENARIOS],
    )
    def test_scenario(self, scenario):
        """Run a simulated conversation and evaluate intent detection."""
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
            new_turns_limit=4,
        )

        # Print conversation for debugging
        print(f"\n{'='*60}")
        print(f"Scenario: {scenario['name']}")
        print(f"{'='*60}")
        if hasattr(result, "transcript") and result.transcript:
            for turn in result.transcript:
                role = getattr(turn, "role", "?")
                text = getattr(turn, "message", getattr(turn, "text", ""))
                print(f"  {role}: {text}")

        # Check evaluation results
        if hasattr(result, "evaluation_results") and result.evaluation_results:
            for eval_result in result.evaluation_results:
                print(f"  Eval [{eval_result.criteria_id}]: {eval_result.result}")
                assert eval_result.result == "pass", (
                    f"Scenario '{scenario['name']}' failed evaluation: "
                    f"{getattr(eval_result, 'rationale', 'no rationale')}"
                )
