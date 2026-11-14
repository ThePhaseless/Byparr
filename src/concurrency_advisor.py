from __future__ import annotations

import logging

from src.consts import MAX_CONCURRENCY

logger = logging.getLogger("uvicorn.error")

ESTIMATED_MEMORY_PER_SESSION_MB = 250


class ConcurrencyAdvisor:
    """
    Analyzes concurrency configuration between Jackett and Byparr,
    estimates required RAM, and generates divergence and memory warnings.
    """

    def __init__(self, byparr_concurrency: int = MAX_CONCURRENCY) -> None:
        self.byparr_concurrency = byparr_concurrency
        self.memory_per_session_mb = ESTIMATED_MEMORY_PER_SESSION_MB

    def get_memory_estimate_mb(self, sessions: int | None = None) -> int:
        count = sessions if sessions is not None else self.byparr_concurrency
        return count * self.memory_per_session_mb

    def get_memory_estimate_gb(self, sessions: int | None = None) -> float:
        return self.get_memory_estimate_mb(sessions) / 1024.0

    def generate_memory_warning(self, sessions: int | None = None) -> str:
        count = sessions if sessions is not None else self.byparr_concurrency
        mb = self.get_memory_estimate_mb(count)
        gb = self.get_memory_estimate_gb(count)
        warning = (
            f"Aviso de Memória: Rodar {count} sessões simultâneas no navegador consome "
            f"aproximadamente ~{mb} MB (~{gb:.1f} GB) de memória RAM (~{self.memory_per_session_mb} MB por sessão)."
        )
        if count >= 8:
            warning += (
                " ATENÇÃO: Alta concorrência configurada! Certifique-se de que o sistema possui "
                "memória livre suficiente para evitar travamentos ou swap excessivo."
            )
        return warning

    def evaluate_divergence(
        self, jackett_concurrency: int | None
    ) -> tuple[int, str | None]:
        """
        Compares Jackett and Byparr concurrency.
        Returns: (effective_limit, divergence_message)
        """
        if not jackett_concurrency or jackett_concurrency <= 0:
            return self.byparr_concurrency, None

        if jackett_concurrency == self.byparr_concurrency:
            msg = (
                f"Concorrência alinhada: Jackett e Byparr estão ambos configurados para "
                f"{self.byparr_concurrency} sessões simultâneas."
            )
            return self.byparr_concurrency, msg

        if jackett_concurrency < self.byparr_concurrency:
            msg = (
                f"Divergência detectada: Jackett configurado para {jackett_concurrency} sessões, "
                f"mas Byparr configurado para {self.byparr_concurrency}. "
                f"A execução simultânea está sendo LIMITADA PELO JACKETT ({jackett_concurrency} sessões)."
            )
            return jackett_concurrency, msg
        else:
            msg = (
                f"Divergência detectada: Jackett configurado para {jackett_concurrency} sessões, "
                f"mas Byparr configurado para {self.byparr_concurrency}. "
                f"A execução simultânea está sendo LIMITADA PELO BYPARR ({self.byparr_concurrency} sessões)."
            )
            return self.byparr_concurrency, msg


concurrency_advisor = ConcurrencyAdvisor()
