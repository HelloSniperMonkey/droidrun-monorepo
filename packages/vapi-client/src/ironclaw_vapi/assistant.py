"""
Pre-configured assistant templates for Vapi.
"""
import random


class WakeUpAssistant:
    """
    Wake-up call assistant configuration.
    Generates Vapi assistant config for cognitive verification calls.
    """

    def __init__(
        self,
        voice_provider: str = "11labs",
        voice_id: str = "rachel",
        transcriber_provider: str = "deepgram",
        transcriber_model: str = "nova-2",
        max_duration_seconds: int = 300,
    ):
        self.voice_provider = voice_provider
        self.voice_id = voice_id
        self.transcriber_provider = transcriber_provider
        self.transcriber_model = transcriber_model
        self.max_duration_seconds = max_duration_seconds

    def generate_verification_question(self) -> tuple[str, int]:
        """Generate a random math verification question."""
        a, b = random.randint(3, 9), random.randint(3, 9)
        return (f"What is {a} times {b}?", a * b)

    def build_config(
        self,
        custom_message: str | None = None,
        verification_question: str | None = None,
    ) -> dict:
        """
        Build the Vapi assistant configuration.

        Args:
            custom_message: Custom first message
            verification_question: Custom verification question

        Returns:
            Dict for Vapi assistant config
        """
        if verification_question is None:
            verification_question, _ = self.generate_verification_question()

        first_message = custom_message or (
            "WAKE UP! This is Iron Claw. "
            "I need to verify you're fully conscious. "
            f"{verification_question}"
        )

        system_prompt = f"""
You are Iron Claw, a ruthless but caring productivity assistant.
Your mission is to ensure the user is FULLY AWAKE.

Current verification question: {verification_question}

Rules:
1. Be energetic and motivating, but firm
2. Do NOT accept "I'm awake" or "I'm up" as proof - they could be half-asleep
3. Ask them to answer the verification question
4. If they get it wrong, encourage them to try again
5. If they answer correctly, congratulate them and wish them a productive day
6. If they seem confused or groggy, ask them to splash water on their face
7. Do not end the call until they prove they're cognitively alert

Remember: You're helping them achieve their goals. Being firm is being kind.
"""

        return {
            "transcriber": {
                "provider": self.transcriber_provider,
                "model": self.transcriber_model,
                "language": "en",
            },
            "model": {
                "provider": "openai",
                "model": "gpt-4o-mini",
                "messages": [{"role": "system", "content": system_prompt}],
                "temperature": 0.7,
            },
            "voice": {
                "provider": self.voice_provider,
                "voiceId": self.voice_id,
            },
            "firstMessage": first_message,
            "maxDurationSeconds": self.max_duration_seconds,
        }
