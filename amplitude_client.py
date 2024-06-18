
import threading
import logging

from amplitude import Amplitude, BaseEvent
from concurrent.futures import ThreadPoolExecutor
from functools import wraps

from config import settings



# Инициализация логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

amplitude = Amplitude(settings.AMPLITUDE_API_KEY)

# Singleton для ThreadPoolExecutor
class SingletonThreadPoolExecutor:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if not cls._instance:
                cls._instance = super().__new__(cls, *args, **kwargs)
                cls._instance.executor = ThreadPoolExecutor(max_workers=5)
        return cls._instance

# Функция для отправки ивентов в Amplitude
def send_event_to_amplitude(event_type, user_id, event_properties=None):
    if event_properties is None:
        event_properties = {}
    
    event = BaseEvent(
            event_type=event_type,
            user_id=str(user_id),
            event_properties={
                "source": "notification"
            }
        )
    try:
        amplitude.track(event)
        logging.info(f"Event '{event_type}' successfully sent for user '{user_id}'")
    except Exception as e:
        logging.error(f"Failed to send event '{event_type}' for user '{user_id}': {str(e)}")



# Декоратор для выполнения функции в отдельном потоке
def run_in_thread_pool(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        executor = SingletonThreadPoolExecutor().executor
        future = executor.submit(func, *args, **kwargs)
        return future
    return wrapper

@run_in_thread_pool
def track_user_event(event_name, user_id, event_properties=None):
    send_event_to_amplitude(event_name, user_id, event_properties)
