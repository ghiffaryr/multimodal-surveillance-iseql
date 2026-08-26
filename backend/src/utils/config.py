from __future__ import annotations

import os
from pathlib import Path

import yaml
from munch import munchify

VALID_CONDITIONS = ("A", "B", "C")

class Config:
    _config = None

    @classmethod
    def _load_config(cls):
        if cls._config is None:
            def deep_merge(a, b):
                for k, v in b.items():
                    if k in a and isinstance(a[k], dict) and isinstance(v, dict):
                        deep_merge(a[k], v)
                    else:
                        a[k] = v
                return a
            config_path = Path(__file__).parents[1] / 'resources' / 'config.yml'
            with open(config_path, 'r') as file:
                config = yaml.safe_load(file)
            profile = os.getenv('PROFILE', '').strip().lower()
            if profile:
                overlay = Path(__file__).parents[1] / 'resources' / f'config.{profile}.yml'
                if overlay.exists():
                    with open(overlay, 'r') as f:
                        deep_merge(config, yaml.safe_load(f) or {})
            
            # Resolve relative paths to the project root (backend/src/resources -> backend -> ..)
            project_root = Path(__file__).parents[2].resolve()
            for section, keys in (('data', ('dir', 'db_path', 'upload_dir')),):
                if section in config:
                    for key in keys:
                        if key in config[section]:
                            p = config[section][key]
                            if isinstance(p, str) and not Path(p).is_absolute():
                                config[section][key] = str((project_root / p).resolve())

            env_vars = {
                'OPENAI_API_KEY': os.getenv('OPENAI_API_KEY', ''),
                'GOOGLE_API_KEY': os.getenv('GOOGLE_API_KEY', ''),
                'ANTHROPIC_API_KEY': os.getenv('ANTHROPIC_API_KEY', ''),
                'MISTRAL_API_KEY': os.getenv('MISTRAL_API_KEY', ''),
                'ZHIPUAI_API_KEY': os.getenv('ZHIPUAI_API_KEY', ''),
                'HF_TOKEN': os.getenv('HF_TOKEN', ''),
            }
            
            config['secrets'] = env_vars

            if os.getenv('OLLAMA_BASE_URL'):
                config.setdefault('vlm', {})['ollama_base_url'] = os.getenv('OLLAMA_BASE_URL')
            elif os.getenv('OLLAMA_HOST'):
                host = os.getenv('OLLAMA_HOST')
                if not host.startswith('http'):
                    host = f'http://{host}'
                config.setdefault('vlm', {})['ollama_base_url'] = host

            cls._config = munchify(config)

    @classmethod
    def get(cls):
        cls._load_config()
        return cls._config

    @classmethod
    def get_available_providers(cls):
        cls._load_config()
        
        providers = []
        secrets = cls._config.get('secrets', {})
        
        if secrets.get('OPENAI_API_KEY'):
            providers.append('openai')
        if secrets.get('GOOGLE_API_KEY'):
            providers.append('gemini')
        if secrets.get('ANTHROPIC_API_KEY'):
            providers.append('claude')
        if secrets.get('MISTRAL_API_KEY'):
            providers.append('mistral')
        if secrets.get('ZHIPUAI_API_KEY'):
            providers.append('zhipu')
        
        providers.append('ollama')
        
        return providers

    @classmethod
    def get_available_audio_providers(cls):
        cls._load_config()
        return ['panns', 'huggingface']
