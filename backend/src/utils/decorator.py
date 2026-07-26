import os
import traceback
from functools import wraps
from utils.api_logger import get_logger

logger = get_logger(__name__)

class Handler:
    def error(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            names = func.__qualname__.split(".")
            endpoint_name = f"{names[0]}.{names[1]}"
            try:
                logger.info(f"Entering {endpoint_name} process")
                res = await func(*args, **kwargs)
                logger.info(f"Return result of {endpoint_name} process")
            except Exception as e:
                error_description = repr(e)
                logger.error(f"Error in {endpoint_name}: {error_description}")
                for lines in traceback.format_tb(e.__traceback__):
                    for line in lines.split("\n"):
                        logger.error(line)
                res = {
                    "title": "Error",
                    "status": "500",
                    "description": error_description
                }, 500
            finally:
                return res
        return wrapper

class Form:
    @classmethod
    def validator(self, form, required_keys, default_optional_keys={}):
        keys = set(form.keys())
        values = form.values()

        if any(key not in keys for key in required_keys):
            raise Exception(f"Missing required keys {required_keys}")
        elif any(value is None for value in values):
            raise Exception(f"Missing required keys {required_keys}")

        if default_optional_keys:
            missing_optional_keys = [p for p in default_optional_keys.keys() if p not in keys]
            for key, value in default_optional_keys.items():
                if key in missing_optional_keys:
                    form[key] = value
                    logger.info(f"Missing optional key {key}: Set default value '{form[key]}'.")
                    missing_optional_keys.remove(key)
        return form
