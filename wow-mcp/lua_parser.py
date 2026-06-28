"""
lua_parser.py
Parser minimaliste pour le format SavedVariables WoW (Lua).

Format attendu :
    CharExportDB = {
        ["last_active"] = "Zickatmago",
        ["characters"] = {
            ["Zickatmago"] = {
                ["exported_at"] = 1749123456,
                ...
            },
        },
    }

Pas de dépendance externe — tokenizer + descente récursive.
Les strings WoW contenant des pipe codes (|cff...|r) sont gérées normalement.
"""
import re
from typing import Any, Optional


class _Parser:
    def __init__(self, text: str) -> None:
        self.text = text
        self.pos = 0
        self.n = len(text)

    # ------------------------------------------------------------------ utils

    def _skip_ws(self) -> None:
        while self.pos < self.n and self.text[self.pos] in " \t\n\r":
            self.pos += 1

    def _peek(self) -> Optional[str]:
        self._skip_ws()
        return self.text[self.pos] if self.pos < self.n else None

    # --------------------------------------------------------------- parsers

    def parse_value(self) -> Any:
        self._skip_ws()
        if self.pos >= self.n:
            return None

        c = self.text[self.pos]

        if c == "{":
            return self._parse_table()
        if c == '"':
            return self._parse_string()
        if self.text[self.pos : self.pos + 4] == "true":
            self.pos += 4
            return True
        if self.text[self.pos : self.pos + 5] == "false":
            self.pos += 5
            return False
        if self.text[self.pos : self.pos + 3] == "nil":
            self.pos += 3
            return None
        if c == "-" or c.isdigit():
            return self._parse_number()

        # caractère inattendu — on avance pour ne pas boucler
        self.pos += 1
        return None

    def _parse_string(self) -> str:
        assert self.text[self.pos] == '"', f"Expected '\"' at pos {self.pos}"
        self.pos += 1
        buf: list[str] = []
        _escapes = {"n": "\n", "t": "\t", "r": "\r", '"': '"', "\\": "\\"}
        while self.pos < self.n:
            c = self.text[self.pos]
            if c == "\\":
                self.pos += 1
                if self.pos < self.n:
                    ec = self.text[self.pos]
                    buf.append(_escapes.get(ec, ec))
            elif c == '"':
                self.pos += 1
                break
            else:
                buf.append(c)
            self.pos += 1
        return "".join(buf)

    def _parse_number(self) -> int | float:
        m = re.match(r"-?[0-9]+(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?", self.text[self.pos :])
        if not m:
            self.pos += 1
            return 0
        s = m.group()
        self.pos += len(s)
        return float(s) if ("." in s or "e" in s.lower()) else int(s)

    def _parse_table(self) -> dict:
        assert self.text[self.pos] == "{", f"Expected '{{' at pos {self.pos}"
        self.pos += 1  # skip {
        result: dict = {}
        arr_idx = 1

        while self.pos < self.n:
            self._skip_ws()
            if self.pos >= self.n:
                break

            c = self.text[self.pos]

            if c == "}":
                self.pos += 1
                break

            if c == ",":
                self.pos += 1
                continue

            if c == "[":
                # Clé explicite : ["foo"] = val  ou  [42] = val
                self.pos += 1  # skip [
                key = self.parse_value()
                self._skip_ws()
                if self.pos < self.n and self.text[self.pos] == "]":
                    self.pos += 1  # skip ]
                self._skip_ws()
                if self.pos < self.n and self.text[self.pos] == "=":
                    self.pos += 1  # skip =
                value = self.parse_value()
                if key is not None:
                    result[key] = value
            else:
                # Valeur positionnelle (tableau Lua sans clé explicite)
                value = self.parse_value()
                if value is not None:
                    result[arr_idx] = value
                    arr_idx += 1

        return result


# ------------------------------------------------------------------ public API

def parse_saved_variables(content: str, var_name: str = "CharExportDB") -> Optional[dict]:
    """
    Extrait et parse la table Lua `var_name` d'un fichier SavedVariables WoW.

    Args:
        content:  Contenu brut du fichier .lua
        var_name: Nom de la variable globale Lua à extraire

    Returns:
        dict Python correspondant à la table, ou None si absent/invalide.

    Raises:
        ValueError: Si la table est trouvée mais syntaxiquement invalide.
    """
    pattern = rf"(?:^|\n){re.escape(var_name)}\s*=\s*(\{{)"
    m = re.search(pattern, content)
    if not m:
        return None

    parser = _Parser(content)
    parser.pos = m.start(1)
    try:
        return parser._parse_table()
    except Exception as exc:
        raise ValueError(f"Erreur parsing '{var_name}': {exc}") from exc
