import os
import time
import asyncio

from google import genai
from google.genai import types

from jarvis.config import BaseLiveService, live_model_system_prompt, Gemini_live_model

class GeminiLiveService(BaseLiveService):
    def __init__(self):
        self.client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        self.model_name = Gemini_live_model
        self._session = None
        self._is_running = False

        self._mute_mic_until = 0.0
        self._chat_history = []
        self._max_history = 15

    def _log(self, text: str):
        try:
            with open("debug_live.log", "a", encoding="utf-8") as f:
                f.write(f"{text}\n")
        except Exception:
            pass

    def _append_to_history(self, role: str, text: str):
        if not text or not text.strip(): 
            return
        self._chat_history.append(f"{role}: {text.strip()}")
        # Удаляем самые старые сообщения, выходящие из лимита 
        if len(self._chat_history) > self._max_history:
            self._chat_history.pop(0)

    async def start(self, on_delegate, on_text_received, on_audio_received) -> None:
        self._is_running = True

        # Конфигурируем инструмент делегирования для голосового фронтенда
        delegate_tool = types.Tool(
            function_declarations=[
                types.FunctionDeclaration(
                    name="delegate_heavy_task",
                    description="Делегировать сложную системную задачу или задачу требующую точных данных, заний времени, локации и тд, работу с календарем, расписанием или базой данных внутреннему агенту.",
                    parameters=types.Schema(
                        type="OBJECT",
                        properties={
                            "query": types.Schema(
                                type="STRING", 
                                description="Оригинальный текстовый запрос пользователя для обработки бэк-офисом."
                            )
                        },
                        required=["query"]
                    )
                )
            ]
        )
        
        speech_config = types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(
                    voice_name="Aoede" 
                )
            )
        )

        while self._is_running:
            try:
                current_memory = "\n".join(self._chat_history)
                dynamic_prompt = live_model_system_prompt
                if current_memory:
                    dynamic_prompt += f"\n\n[ТЕКУЩИЙ КОНТЕКСТ ДИАЛОГА]:\n{current_memory}"

                live_config = types.LiveConnectConfig(
                    response_modalities=["AUDIO"],
                    tools=[delegate_tool],
                    system_instruction=types.Content(parts=[types.Part(text=dynamic_prompt)]),
                    speech_config=speech_config
                )



                async with self.client.aio.live.connect(model=self.model_name, config=live_config) as session:
                    self._session = session
                    self._log("[CONNECT SUCCESS]: Соединение успешно установлено!")
                    self._mute_mic_until = 0.0

                    await self._receive_loop(on_delegate, on_text_received, on_audio_received)
            except Exception as e:
                self._log(f"[SESSION CRASHED]: APIError или сбой сети: {repr(e)}")
                    
                if self._is_running:
                    await asyncio.sleep(2) 
            finally:
                self._session = None
                self._log("[CONNECT FINALLY]: Сессия сброшена в None.")

    async def send_text(self, text: str) -> None:
        # self._append_to_history("Пользователь", text)
        if self._session and self._is_running:
            try:
                # Затыкаем микрофон
                self._mute_mic_until = time.time() + 2.5
                await self._session.send_client_content(
                    turns=types.Content(
                        role="user",
                        parts=[types.Part(text=text)]
                    ),
                    turn_complete=True # Актуальный параметр завершения очереди
                )
            except Exception as e:
                pass

    async def send_audio(self, audio_bytes: bytes):
        if not audio_bytes:
            return
        
        if time.time() < self._mute_mic_until:
            return
        
        if self._session and self._is_running:
            try:
                await self._session.send_realtime_input(
                    audio=types.Blob(
                        data=audio_bytes,
                        mime_type="audio/pcm;rate=16000"
                    )
                )
            except Exception as e:
                pass

    async def _receive_loop(self, on_delegate, on_text_received, on_audio_received) -> None:
        try:
            # Оборачиваем генератор в цикл, чтобы удерживать сессию после завершения ответа
            while self._is_running:
                async for response in self._session.receive():
                    server_content = response.server_content
                    if server_content is not None:
                        model_turn = server_content.model_turn
                        if model_turn is not None:
                            for part in model_turn.parts:
                                if part.inline_data is not None:
                                    await on_audio_received(part.inline_data.data)
                                if part.text:
                                    await on_text_received(part.text)
                                    
                    tool_call = response.tool_call
                    if tool_call is not None:
                        for function_call in tool_call.function_calls:
                            if function_call.name == "delegate_heavy_task":
                                async def handle_tool(f_call):
                                    query = f_call.args.get("query")
                                    try:
                                        result_text = await on_delegate(query)
                                        await self._session.send(
                                            input=types.LiveClientToolResponse(
                                                function_responses=[
                                                    types.FunctionResponse(
                                                        name=f_call.name,
                                                        id=f_call.id,
                                                        response={"result": result_text}
                                                    )
                                                ]
                                            )
                                        )
                                    except Exception as e:
                                        await self._session.send(
                                            input=types.LiveClientToolResponse(
                                                function_responses=[
                                                    types.FunctionResponse(
                                                        name=f_call.name,
                                                        id=f_call.id,
                                                        response={"error": str(e)}
                                                    )
                                                ]
                                            )
                                        )
                                asyncio.create_task(handle_tool(function_call))
                                
        except Exception as e:
            self._log(f"[RECEIVE LOOP CRASHED]: {repr(e)}")
    async def stop(self) -> None:
        self._is_running = False
        self._session = None