import yaml
import ast
    
class YamlCfg:
    def __init__(self, path: str):
        with open(path, 'r', encoding='utf-8') as f:
            self._data = yaml.safe_load(f) or {}

        for key in self._data:
            def getter(self, k=key):
                return self._data[k] if isinstance(self._data[k], int) or (isinstance(self._data[k], str) and not ("(" == self._data[k][0] and ")" == self._data[k][-1])) else ast.literal_eval(self._data[k])
            setattr(self.__class__, key, property(getter))

