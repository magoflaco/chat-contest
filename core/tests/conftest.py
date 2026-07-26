"""Configuracion comun de los tests.

Cada test corre contra una base de datos temporal y con el juez en modo
`subprocess`, para que no haga falta tener Docker levantado para desarrollar.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "core"))

# hay que fijar el entorno ANTES de importar contest.config, porque la config se
# construye una sola vez al importarse el modulo
os.environ["JUDGE_BACKEND"] = "subprocess"
os.environ["CORE_TOKEN"] = "token-de-prueba"
os.environ["ADMINS"] = "5490000000000"
os.environ["COOLDOWN_ENTREGA_SEG"] = "0"
os.environ["DB_PATH"] = str(Path(tempfile.mkdtemp(prefix="cc-test-")) / "test.db")


@pytest.fixture(autouse=True)
def base_limpia(tmp_path, monkeypatch):
    """Una base vacia por test, para que no se pisen entre si."""
    from contest import db

    monkeypatch.setattr(type(db.config), "db_path",
                        property(lambda self: tmp_path / "contest.db"))
    monkeypatch.setattr(type(db.config), "dir_entregas",
                        property(lambda self: tmp_path / "submissions"))

    if hasattr(db._local, "con"):
        db._local.con.close()
        del db._local.con

    db.inicializar()
    yield db

    if hasattr(db._local, "con"):
        db._local.con.close()
        del db._local.con


@pytest.fixture
def solucion_correcta() -> str:
    """La solucion de referencia de suma-de-digitos, que es el problema mas simple."""
    return (RAIZ / "data" / "problems" / "suma-de-digitos" / "solucion.py").read_text(encoding="utf-8")
