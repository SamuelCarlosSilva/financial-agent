"""Exceções de domínio levantadas pelo grafo e traduzidas para HTTP em `api/errors.py`."""


class UpstreamUnavailableError(Exception):
    def __init__(self, message: str = "Serviço temporariamente indisponível.") -> None:
        super().__init__(message)
        self.message = message
