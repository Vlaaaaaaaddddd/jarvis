import os
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

        live_config = types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            tools=[delegate_tool],
            system_instruction=types.Content(parts=[types.Part(text=live_model_system_prompt)])
        )

        while self._is_running:
            try:
                async with self.client.aio.live.connect(model=self.model_name, config=live_config) as session:
                    self._session = session
                    
                    # Ожидаем завершения цикла получения данных
                    await self._receive_loop(on_delegate, on_text_received, on_audio_received)
            except Exception as e:
                if self._is_running:
                    await asyncio.sleep(2) 
            finally:
                self._session = None


    async def send_text(self, text: str) -> None:
        if self._session and self._is_running:
            try:
                await self._session.send(input=text, end_of_turn=True)
            except Exception as e:
                pass

    async def send_audio(self, audio_bytes: bytes):
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
                            query = function_call.args.get("query")
                            try:
                                result_text = await on_delegate(query)
                                await self._session.send(
                                    input=types.LiveClientToolResponse(
                                        function_responses=[
                                            types.FunctionResponse(
                                                name=function_call.name,
                                                id=function_call.id,
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
                                                name=function_call.name,
                                                id=function_call.id,
                                                response={"error": str(e)}
                                            )
                                        ]
                                    )
                                )
        except Exception as e:
            pass
    async def stop(self) -> None:
        self._is_running = False
        self._session = None