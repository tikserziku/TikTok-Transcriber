import os
import time
from typing import Optional, Dict
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class APIKeyManager:
    def __init__(self):
        # Загружаем ключи из переменных окружения
        self.api_keys = [
            os.getenv('GOOGLE_API_KEY_1'),
            os.getenv('GOOGLE_API_KEY_2'),
            os.getenv('GOOGLE_API_KEY_3')
        ]
        
        # Удаляем None значения
        self.api_keys = [key for key in self.api_keys if key]
        
        if not self.api_keys:
            raise ValueError("No API keys found in environment variables")
            
        # Состояние каждого ключа
        self.key_states: Dict[str, Dict] = {
            key: {
                'last_used': None,
                'error_count': 0,
                'quota_reset': None,
                'available': True,
                'requests_today': 0,
                'last_error': None
            }
            for key in self.api_keys
        }
        
        # Константы
        self.MAX_REQUESTS_PER_DAY = 50  # Лимит запросов в день
        self.ERROR_THRESHOLD = 3  # После скольких ошибок ключ временно блокируется
        self.COOLDOWN_PERIOD = 60  # Время остывания после ошибки (в секундах)
        
    def _is_key_available(self, key: str) -> bool:
        """Проверяет доступность ключа"""
        state = self.key_states[key]
        now = datetime.now()
        
        # Проверка дневной квоты
        if state['quota_reset'] is None or now.date() > state['quota_reset'].date():
            state['quota_reset'] = now
            state['requests_today'] = 0
            state['error_count'] = 0
            state['available'] = True
        
        # Проверка количества запросов
        if state['requests_today'] >= self.MAX_REQUESTS_PER_DAY:
            return False
            
        # Проверка периода остывания после ошибок
        if state['error_count'] >= self.ERROR_THRESHOLD:
            if state['last_error'] and (now - state['last_error']).seconds < self.COOLDOWN_PERIOD:
                return False
            state['error_count'] = 0
            
        return state['available']

    def get_next_key(self) -> Optional[str]:
        """Возвращает следующий доступный ключ"""
        available_keys = [
            key for key in self.api_keys 
            if self._is_key_available(key)
        ]
        
        if not available_keys:
            logger.warning("No available API keys!")
            return None
            
        # Выбираем ключ с наименьшим использованием
        selected_key = min(
            available_keys,
            key=lambda k: (
                self.key_states[k]['requests_today'],
                self.key_states[k]['last_used'] or datetime.min
            )
        )
        
        # Обновляем состояние
        self.key_states[selected_key]['last_used'] = datetime.now()
        self.key_states[selected_key]['requests_today'] += 1
        
        return selected_key

    def mark_key_error(self, key: str, error_message: str):
        """Отмечает ошибку для ключа"""
        state = self.key_states[key]
        state['error_count'] += 1
        state['last_error'] = datetime.now()
        
        if "quota exceeded" in error_message.lower():
            state['available'] = False
            state['requests_today'] = self.MAX_REQUESTS_PER_DAY
            logger.warning(f"API key {key[:10]}... quota exceeded")
        
        if state['error_count'] >= self.ERROR_THRESHOLD:
            logger.warning(f"API key {key[:10]}... temporarily disabled due to errors")

    def get_key_status(self) -> Dict:
        """Возвращает статус всех ключей"""
        return {
            f"key_{i+1}": {
                'available': self._is_key_available(key),
                'requests_today': self.key_states[key]['requests_today'],
                'error_count': self.key_states[key]['error_count'],
                'last_used': self.key_states[key]['last_used']
            }
            for i, key in enumerate(self.api_keys)
        }
