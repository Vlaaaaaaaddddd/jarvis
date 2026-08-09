import os
import time
import asyncio

from google import genai
from google.genai import types

from jarvis.config import BaseLiveService, live_model_system_prompt, Gemini_live_model
from jarvis.tools.live_tools import DelegateHeavyTaskTool, MemorizeFactTool, ForceConsolidationTool
from jarvis.utils.logger import get_logger

logger = get_logger("live")

class GeminiLiveService(BaseLiveService):
    def __init__(self):
        self.client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        self.model_name = Gemini_live_model
        self._session = None
        self._is_running = False
        self._active_tools_count = 0
        self._mute_mic_until = 0.0

        self._tools_map = {}

    async def start(
            self, 
            on_delegate, 
            on_memorize, 
            on_force_consolidation, 
            on_audio_received,
            system_prompt: str = None
            ) -> None:
        
        self._is_running = True

        current_prompt = system_prompt or live_model_system_prompt

        live_tool = DelegateHeavyTaskTool(on_delegate)
        memory_tool = MemorizeFactTool(on_memorize)
        force_tool = ForceConsolidationTool(on_force_consolidation)
        self._tools_map = {
            live_tool.name: live_tool, 
            memory_tool.name: memory_tool, 
            force_tool.name: force_tool
            }

        speech_config = types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(
                    voice_name="Aoede" 
                )
            )
        )

        live_config = types.LiveConnectConfig(
                    response_modalities=["AUDIO"],
                    tools=[tool.get_schema() for tool in self._tools_map.values()],
                    system_instruction=types.Content(
                        parts=[types.Part.from_text(text=current_prompt)]
                    ),
                    speech_config=speech_config
                )

        while self._is_running:
            try:
                async with self.client.aio.live.connect(model=self.model_name, config=live_config) as session:
                    self._session = session
                    self._mute_mic_until = 0.0
                    await self._receive_loop(on_audio_received)
            except Exception as e:
                if self._is_running:
                    logger.warning("Разрыв Live-сессии, переподключение через 2с: %s", e)
                    await asyncio.sleep(2)
            finally:
                self._session = None

    async def send_text(self, text: str) -> None:
        if self._session and self._is_running:
            try:
                self._mute_mic_until = time.time() + 2.5
                await self._session.send_client_content(
                    turns=types.Content(role="user", parts=[types.Part(text=text)]),
                    turn_complete=True 
                )
            except Exception as e:
                logger.debug("Ошибка отправки текста в Live API: %s", e)

    async def send_audio(self, audio_bytes: bytes):
        if not audio_bytes or time.time() < self._mute_mic_until or self._active_tools_count > 0:
            return
        

        if self._session and self._is_running:
            try:
                await self._session.send_realtime_input(
                    audio=types.Blob(data=audio_bytes, mime_type="audio/pcm;rate=16000")
                )
            except Exception as e:
                logger.debug("Ошибка отправки аудио в Live API: %s", e)

    async def _receive_loop(self, on_audio_received) -> None:
        try:
            while self._is_running:
                async for response in self._session.receive():
                    
                    # Обработка контента 
                    if response.server_content and response.server_content.model_turn:
                        for part in response.server_content.model_turn.parts:
                            if part.inline_data:
                                await on_audio_received(part.inline_data.data)
                                
                    # Обработка вызовов инструментов 
                    if response.tool_call:
                        for function_call in response.tool_call.function_calls:
                            func_name = function_call.name
                            if func_name in self._tools_map:
                                # Запускаем обработку в фоне, чтобы не вешать веб-сокет
                                asyncio.create_task(self._process_tool_call(function_call))
                                
        except Exception as e:
            logger.warning("Ошибка приёма данных Live API: %s", e)

    async def _process_tool_call(self, function_call) -> None:
        """обработчик для инструмента"""
        self._active_tools_count += 1
        func_name = function_call.name
        func_args = function_call.args
        tool = self._tools_map[func_name]

        try:
            result_text = await tool.execute(**func_args)
            response_data = {"result": result_text}
        except Exception as e:
            logger.error("Ошибка выполнения инструмента %s: %s", func_name, e)
            response_data = {"error": str(e)}
        finally: 
            self._active_tools_count -= 1

        try:
            await self._session.send(
                input=types.LiveClientToolResponse(
                    function_responses=[
                        types.FunctionResponse(
                            name=function_call.name,
                            id=function_call.id,
                            response=response_data
                        )
                    ]
                )
            )
            self._mute_mic_until = time.time() + 2.0
        except Exception as e:
            logger.error("Ошибка отправки ответа инструмента %s: %s", func_name, e)

    async def stop(self) -> None:
        self._is_running = False
        self._session = None