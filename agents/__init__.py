"""패키지를 불러올 때 .env를 먼저 읽어 환경변수로 넣는다 (로컬 실행용, CI에서는 파일이 없음)."""
import os
import pathlib

_env = pathlib.Path(__file__).resolve().parent.parent / ".env"
if _env.exists():
    for _line in _env.read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if not _line or _line.startswith("#") or "=" not in _line:
            continue
        _k, _v = _line.split("=", 1)
        _k, _v = _k.strip(), _v.strip().strip('"').strip("'")
        if _v and not os.environ.get(_k):
            os.environ[_k] = _v
