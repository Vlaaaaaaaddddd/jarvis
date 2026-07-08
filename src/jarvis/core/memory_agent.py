import json
import logging
import os
from jarvis.config import MEMORY_AGENT_PROMPT
from jarvis.db.repository import PostgresRepository
from jarvis.services.memory_llm import MemoryLLMService 


logger = logging.getLogger("jarvis.memory_agent")
logger.setLevel(logging.DEBUG)
logger.propagate = False

if not logger.handlers:
    os.makedirs("logs", exist_ok=True)
    file_handler = logging.FileHandler("logs/memory_agent.log", encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

class MemoryAgent:
    def __init__(self, repository: PostgresRepository, llm_service: MemoryLLMService):
        self.repo = repository
        self.llm = llm_service
        logger.info("Агент Памяти успешно инициализирован. Логирование запущено в logs/memory_agent.log")

    async def consolidate(self) -> None:
        """Основной цикл: сбор фактов, отправка в LLM, обновление БД"""
        try:
            # Забираем сырые необработанные факты
            unprocessed = await self.repo.get_unprocessed_facts()
            if not unprocessed:
                return
            logger.info(f"Агент Памяти: Найдено {len(unprocessed)} необработанных фактов. Анализирую...")

            # Поднимаем профиль и формируем промпт
            current_profile = await self.repo.get_user_profile()
            profile_json_str = json.dumps(current_profile, ensure_ascii=False, indent=2)
            
            # Подставляем профиль в шаблон промпта
            system_prompt = MEMORY_AGENT_PROMPT.format(profile_json=profile_json_str)

            # Подготавливаем нагрузку 
            facts_payload = "Новые факты:\n" + "\n".join([f"- [ID: {f['id']}] {f['content']}" for f in unprocessed])

            # Делегируем запрос в LLM-сервис
            llm_response_text = await self.llm.analyze_facts(facts_payload, system_prompt)

            # Парсим ответ
            actions = json.loads(llm_response_text)
            
            # Распределяем по базам (Горячая, Теплая и Удаление)
            for key_to_delete in actions.get("hot_deletes", []):
                await self.repo.delete_user_profile_key(key_to_delete)
                logger.debug(f"Удален ключ: {key_to_delete}")

            for key, value in actions.get("hot_updates", {}).items():
                await self.repo.update_user_profile(key, str(value))
                logger.debug(f"Обновлен профиль: {key} -> {value}")

            for warm_text in actions.get("warm_additions", []):
                await self.repo.add_vector_memory(text=warm_text, embedding=None)
                logger.debug(f"Добавлено в теплую память: {warm_text[:30]}...")

            # Закрываем транзакцию
            processed_ids = [f["id"] for f in unprocessed]
            await self.repo.mark_facts_as_processed(processed_ids)
            logger.info(f"Агент Памяти: Успешно заархивировано {len(processed_ids)} фактов.")

        except json.JSONDecodeError:
            logger.error("Агент Памяти: Ошибка парсинга JSON ответа от модели.")
            processed_ids = [f["id"] for f in unprocessed]
            if processed_ids:
                await self.repo.mark_facts_as_processed(processed_ids)
                logger.warning(f"Агент Памяти: {len(processed_ids)} фактов помечены как обработанные из-за ошибки JSON, чтобы избежать зацикливания.")
        except Exception as e:
            logger.error(f"Агент Памяти: Ошибка консолидации: {e}")