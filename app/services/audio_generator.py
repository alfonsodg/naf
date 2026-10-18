from typing import List
from app.contracts.tts import TTSProvider, TTSConfig, AudioSegment


class AudioGenerator:
    def __init__(self, tts_provider: TTSProvider):
        self.tts_provider = tts_provider

    async def generate_audio(
        self, texts: List[str], config: TTSConfig
    ) -> List[AudioSegment]:
        segments = []
        for i, text in enumerate(texts):
            seg = await self.tts_provider.synthesize_segment(text, config)
            seg.index = i
            segments.append(seg)
        return segments
