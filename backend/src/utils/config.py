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
            config_path = Path(__file__).parents[1] / 'resources' / 'config.yml'
            with open(config_path, 'r') as file:
                config = yaml.safe_load(file)
            
            # Resolve relative paths to the project root (backend/src/resources -> backend -> ..)
            project_root = Path(__file__).parents[2].resolve()
            for section, keys in (('data', ('dir', 'db_path', 'upload_dir', 'handoff_r_csv', 'handoff_s_csv')),
                                  ('engine', ('iseql_path',))):
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
