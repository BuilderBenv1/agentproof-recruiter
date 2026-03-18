from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class RecruiterSettings(BaseSettings):
    # Wallet
    recruiter_private_key: str = ""
    recruiter_base_rpc_url: str = ""

    # AgentProof oracle
    agentproof_api_key: str = ""
    agentproof_oracle_url: str = "https://oracle.agentproof.sh"

    # ERC-8004 contracts (Base mainnet CREATE2)
    identity_registry: str = "0x8004A169FB4a3325136EB29fA0ceB6D2e539a432"
    reputation_registry: str = "0x8004BAa17C55a88189AE136b182e5fdA19dE9b63"
    agent_payments: str = "0x4E3092E46233c32F3A0E4b782230cA67E359f35f"

    # Server
    port: int = 8002
    base_url: str = "https://recruiter.agentproof.sh"

    # Recruiter policy
    min_agent_score: float = 40.0
    min_agent_tier: str = "bronze"
    max_task_value_wei: int = 50_000_000_000_000_000  # 0.05 ETH max escrow
    recruiter_fee_bps: int = 250  # 2.5% fee

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )


@lru_cache()
def get_settings() -> RecruiterSettings:
    return RecruiterSettings()
