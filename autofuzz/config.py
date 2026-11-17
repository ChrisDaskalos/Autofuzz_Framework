# File: autofuzz/config.py
"""
Load and check autofuzz.yaml.

Everything that is specific to one C project lives in the YAML file.
`autofuzz/defaults.yaml` holds the default values; the project file is
merged on top of it:

  * a list under `limits.string_seeds` is ADDED to the default seeds
    (set `limits.default_string_seeds: false` to drop the defaults);
  * every other key REPLACES the default value.

Paths in the YAML (sources, include_dirs, output_dir) are relative to the
folder that contains the YAML file.
"""
import fnmatch
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

try:
    import yaml
except ImportError:  # pragma: no cover - checked again by `autofuzz check`
    yaml = None

PACKAGE_DIR = Path(__file__).resolve().parent
DEFAULTS_FILE = PACKAGE_DIR / "defaults.yaml"
DEFAULT_CONFIG_NAME = "autofuzz.yaml"


class ConfigError(Exception):
    """A problem in autofuzz.yaml. The message is shown to the user as is."""


# ---------------------------------------------------------------------------
# Schema: what keys exist and what type each one has
# ---------------------------------------------------------------------------
STR, INT, BOOL, STR_LIST = "text", "whole number", "true/false", "list of text"
SEED_LIST = "list of seeds"
RANGES = "map of Function.param: [min, max]"
SETUP_LIST = "list of setup entries"

SCHEMA: Dict[str, Any] = {
    "sources": STR_LIST,
    "include_dirs": STR_LIST,
    "defines": STR_LIST,
    "cflags": STR_LIST,
    "compiler": STR,
    "functions": {"include": STR_LIST, "exclude": STR_LIST},
    "limits": {
        "edge_cap": INT,
        "buffer_size": INT,
        "int_ranges": RANGES,
        "string_seeds": SEED_LIST,
        "default_string_seeds": BOOL,
    },
    "harness": {"includes": STR_LIST, "setup": SETUP_LIST},
    "fuzz": {"seconds": INT, "rss_limit_mb": INT},
    "output_dir": STR,
}
SETUP_KEYS = {"type": STR, "var": STR, "lines": STR_LIST}
SEED_DICT_KEYS = {"repeat": STR, "times": INT, "prefix": STR, "suffix": STR}


def _type_ok(kind: str, value: Any) -> bool:
    if kind == STR:
        return isinstance(value, str)
    if kind == INT:
        return isinstance(value, int) and not isinstance(value, bool)
    if kind == BOOL:
        return isinstance(value, bool)
    if kind == STR_LIST:
        return isinstance(value, list) and all(isinstance(v, (str, int)) and not isinstance(v, bool) for v in value)
    if kind in (SEED_LIST, SETUP_LIST):
        return isinstance(value, list)
    if kind == RANGES:
        return isinstance(value, dict)
    return False


def _check(data: Any, schema: Dict[str, Any], where: str, src: str) -> None:
    if not isinstance(data, dict):
        raise ConfigError(f"{src}: '{where or 'top level'}' must be a map of keys (key: value).")
    for key, value in data.items():
        path = f"{where}.{key}" if where else str(key)
        if key not in schema:
            allowed = ", ".join(sorted(schema))
            hint = ""
            close = fnmatch.filter(schema, f"{str(key)[:3]}*")
            if close:
                hint = f" Did you mean '{close[0]}'?"
            raise ConfigError(f"{src}: unknown key '{path}'.{hint} Allowed keys here: {allowed}.")
        kind = schema[key]
        if isinstance(kind, dict):
            _check(value if value is not None else {}, kind, path, src)
            continue
        if value is None:
            continue  # empty value = keep the default
        if not _type_ok(kind, value):
            raise ConfigError(f"{src}: '{path}' must be a {kind}, not {type(value).__name__} ({value!r}).")
        if kind == RANGES:
            for name, rng in value.items():
                if "." not in str(name):
                    raise ConfigError(f"{src}: '{path}.{name}': write the key as Function.parameter, e.g. Servo_SetAngle.angle.")
                if (not isinstance(rng, list) or len(rng) != 2
                        or not all(isinstance(x, int) and not isinstance(x, bool) for x in rng) or rng[0] > rng[1]):
                    raise ConfigError(f"{src}: '{path}.{name}' must be [min, max] with min <= max, not {rng!r}.")
        if kind == SETUP_LIST:
            for i, entry in enumerate(value):
                _check(entry, SETUP_KEYS, f"{path}[{i}]", src)
                for need in SETUP_KEYS:
                    if need not in entry:
                        raise ConfigError(f"{src}: '{path}[{i}]' needs the key '{need}'.")
        if kind == SEED_LIST:
            for i, seed in enumerate(value):
                if isinstance(seed, dict):
                    _check(seed, SEED_DICT_KEYS, f"{path}[{i}]", src)
                    if "repeat" not in seed or "times" not in seed:
                        raise ConfigError(f"{src}: '{path}[{i}]' needs 'repeat' and 'times'.")
                elif isinstance(seed, bool) or not isinstance(seed, (str, int)):
                    raise ConfigError(f"{src}: '{path}[{i}]' must be text or {{repeat: A, times: 100}}.")


def _load_yaml(path: Path) -> Dict[str, Any]:
    if yaml is None:
        raise ConfigError("PyYAML is not installed. Install it with:  pip install PyYAML")
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        raise ConfigError(f"{path}: this is not valid YAML:\n{e}")
    data = data or {}
    _check(data, SCHEMA, "", str(path))
    return data


def _merge(base: Dict[str, Any], top: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(base)
    for key, value in top.items():
        if value is None:
            continue
        if isinstance(value, dict) and isinstance(out.get(key), dict) and key != "int_ranges":
            out[key] = _merge(out[key], value)
        else:
            out[key] = value
    return out


# ---------------------------------------------------------------------------
# Seeds: YAML text -> C string literal
# ---------------------------------------------------------------------------
_C_ESCAPES = {"\\": "\\\\", '"': '\\"', "\t": "\\t", "\n": "\\n", "\r": "\\r"}
_HEX = set("0123456789abcdefABCDEF")


def c_string_literal(text: str) -> str:
    """Plain text from the YAML -> a C string literal, e.g. tab -> "\\t"."""
    out: List[str] = []
    after_hex = False
    for ch in text:
        if ch in _C_ESCAPES:
            piece, hexed = _C_ESCAPES[ch], False
        elif " " <= ch <= "~":
            piece, hexed = ch, False
        else:
            data = bytes([ord(ch)]) if ord(ch) < 256 else ch.encode("utf-8")
            piece, hexed = "".join(f"\\x{b:02x}" for b in data), True
        if after_hex and piece[0] in _HEX:
            out.append('" "')  # stop the \x escape from eating the next char
        out.append(piece)
        after_hex = hexed
    return '"' + "".join(out) + '"'


def _seed_to_c(seed: Union[str, int, Dict[str, Any]]) -> str:
    if isinstance(seed, dict):
        text = str(seed.get("prefix", "")) + str(seed["repeat"]) * int(seed["times"]) + str(seed.get("suffix", ""))
        return c_string_literal(text)
    return c_string_literal(str(seed))


# ---------------------------------------------------------------------------
# Integer edge values (a rule, the same for every project)
# ---------------------------------------------------------------------------
def mk_int_edges(bit_width: int, signed: bool) -> List[int]:
    """Canonical edges for an integer type."""
    lo = -(1 << (bit_width - 1)) if signed else 0
    hi = (1 << (bit_width - 1)) - 1 if signed else (1 << bit_width) - 1
    extras = {2, -2}
    if bit_width >= 16:
        extras |= {0x7FFF, 0x8000, -0x8000, 0xFFFF}
    if bit_width >= 32:
        extras |= {0x7FFFFFFF, 0x80000000, -0x80000000, 0xFFFFFFFF}
    core = [lo, lo + 1, -1, 0, 1, 2, hi - 1, hi] + [e for e in extras]
    return [v for v in sorted(set(core)) if lo <= v <= hi]


_INT_TYPES: Dict[str, Tuple[int, bool]] = {
    "uint8_t": (8, False), "int8_t": (8, True),
    "unsigned char": (8, False), "signed char": (8, True), "char": (8, True),
    "uint16_t": (16, False), "int16_t": (16, True),
    "unsigned short": (16, False), "short": (16, True), "short int": (16, True),
    "uint32_t": (32, False), "int32_t": (32, True), "int": (32, True),
    "signed int": (32, True), "unsigned int": (32, False), "unsigned": (32, False),
    "uint64_t": (64, False), "int64_t": (64, True),
    "unsigned long": (64, False), "long": (64, True),
    "unsigned long long": (64, False), "long long": (64, True),
    "size_t": (64, False), "ssize_t": (64, True), "ptrdiff_t": (64, True),
}
_STRING_TYPES = ("const char *", "char *", "char*", "const char*")


class SetupEntry:
    """harness.setup: C lines that prepare a struct before the call."""

    def __init__(self, type_name: str, var: str, lines: List[str]):
        self.type_name = type_name
        self.var = var
        self.lines = [str(x) for x in lines]
        self._ptr_re = re.compile(r"\b" + re.escape(type_name) + r"\s*\*")

    def matches(self, param_type: str) -> bool:
        return bool(self._ptr_re.search(param_type))

    def calls(self, func: str) -> bool:
        """True if a setup line calls `func` (then the setup is skipped for it)."""
        rx = re.compile(r"\b" + re.escape(func) + r"\s*\(")
        return any(rx.search(line) for line in self.lines)


class Config:
    """The checked, merged settings of one project."""

    def __init__(self, data: Dict[str, Any], path: Optional[Path]):
        self.path = path
        self.base_dir = path.parent if path else Path.cwd()
        d = data
        self.sources = [self._abs(s) for s in d.get("sources") or []]
        self.include_dirs = [self._abs(s) for s in d.get("include_dirs") or []]
        self.defines = [str(x) for x in d.get("defines") or []]
        self.cflags = [str(x) for x in d.get("cflags") or []]
        self.compiler = d.get("compiler") or "clang"
        fn = d.get("functions") or {}
        self.functions_include = [str(x) for x in fn.get("include") or []]
        self.functions_exclude = [str(x) for x in fn.get("exclude") or []]
        lim = d.get("limits") or {}
        self.edge_cap = int(lim.get("edge_cap", 12))
        self.buffer_size = int(lim.get("buffer_size", 4096))
        if self.edge_cap < 1 or self.buffer_size < 2:
            raise ConfigError(f"{path}: limits.edge_cap must be >= 1 and limits.buffer_size >= 2.")
        self.int_ranges: Dict[str, Tuple[int, int]] = {
            str(k): (int(v[0]), int(v[1])) for k, v in (lim.get("int_ranges") or {}).items()
        }
        self.string_seeds: List[str] = list(d.get("_string_seeds_c") or [])
        h = d.get("harness") or {}
        self.harness_includes = [str(x) for x in h.get("includes") or []]
        self.setup = [SetupEntry(str(e["type"]), str(e["var"]), e.get("lines") or []) for e in h.get("setup") or []]
        fz = d.get("fuzz") or {}
        self.fuzz_seconds = int(fz.get("seconds", 10))
        self.rss_limit_mb = int(fz.get("rss_limit_mb", 600))
        self.output_dir = self._abs(d.get("output_dir") or "autofuzz-out")

        # Edge values per C type (used by scanner and generator)
        self.generic_edges: Dict[str, List[Union[int, str]]] = {t: self.string_seeds for t in _STRING_TYPES}
        for t, (bits, signed) in _INT_TYPES.items():
            self.generic_edges[t] = mk_int_edges(bits, signed)
        self.generic_edges["bool"] = [0, 1]
        self.generic_edges["_Bool"] = [0, 1]

    def _abs(self, p: str) -> Path:
        q = Path(str(p))
        return q if q.is_absolute() else (self.base_dir / q)

    # --- helpers used by the rest of the tool -----------------------------
    def clang_args(self) -> List[str]:
        """-I / -D / extra flags, in the order given in the YAML."""
        args = list(self.cflags)
        args += [f"-D{d}" for d in self.defines]
        args += [f"-I{p}" for p in self.include_dirs]
        return args

    def wants_function(self, name: str) -> bool:
        if self.functions_include and not any(fnmatch.fnmatchcase(name, p) for p in self.functions_include):
            return False
        return not any(fnmatch.fnmatchcase(name, p) for p in self.functions_exclude)

    def setup_for(self, param_type: str) -> Optional[SetupEntry]:
        for entry in self.setup:
            if entry.matches(param_type):
                return entry
        return None

    def int_range(self, func: str, param: str) -> Optional[Tuple[int, int]]:
        return self.int_ranges.get(f"{func}.{param}")


def load(path: Optional[Union[str, Path]] = None, require_sources: bool = True) -> Config:
    """Load ./autofuzz.yaml (or `path`), merge it on the defaults, check it."""
    cfg_path = Path(path) if path else Path.cwd() / DEFAULT_CONFIG_NAME
    if not cfg_path.is_file():
        raise ConfigError(
            f"config file not found: {cfg_path}\n"
            f"  Create one with:  autofuzz init\n"
            f"  or point to it:   autofuzz run --config path/to/autofuzz.yaml"
        )
    defaults = _load_yaml(DEFAULTS_FILE)
    project = _load_yaml(cfg_path)
    data = _merge(defaults, project)

    # String seeds: defaults + project (unless the project turns defaults off)
    lim_d = defaults.get("limits") or {}
    lim_p = project.get("limits") or {}
    seeds: List[Any] = []
    if lim_p.get("default_string_seeds", True):
        seeds += lim_d.get("string_seeds") or []
    seeds += lim_p.get("string_seeds") or []
    data["_string_seeds_c"] = [_seed_to_c(s) for s in seeds]

    cfg = Config(data, cfg_path.resolve())
    if require_sources:
        if not cfg.sources:
            raise ConfigError(f"{cfg_path}: 'sources' is empty. List the .c files to test, e.g.\n  sources:\n    - src/parser.c")
        missing = [str(s) for s in cfg.sources if not s.is_file()]
        if missing:
            raise ConfigError(f"{cfg_path}: source file not found: {', '.join(missing)} "
                              f"(paths are relative to {cfg.base_dir})")
        bad = [str(p) for p in cfg.include_dirs if not p.is_dir()]
        if bad:
            raise ConfigError(f"{cfg_path}: include_dirs folder not found: {', '.join(bad)}")
    return cfg


def die(err: Exception) -> None:
    print(f"autofuzz: error: {err}", file=sys.stderr)
    sys.exit(2)
