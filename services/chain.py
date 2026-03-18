"""On-chain interactions — ERC-8004 feedback submission on Base.

Submits reputation feedback after task completion or dispute.
Uses the same ReputationRegistry contract as the oracle (CREATE2 addresses).
"""

import json
import logging
import time

from web3 import Web3

from config import get_settings

logger = logging.getLogger(__name__)

REPUTATION_REGISTRY_ABI = json.loads("""[
    {
        "inputs": [
            {"name": "agentId", "type": "uint256"},
            {"name": "value", "type": "int128"},
            {"name": "valueDecimals", "type": "uint8"},
            {"name": "tag1", "type": "string"},
            {"name": "tag2", "type": "string"},
            {"name": "endpoint", "type": "string"},
            {"name": "feedbackURI", "type": "string"},
            {"name": "feedbackHash", "type": "bytes32"}
        ],
        "name": "giveFeedback",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    }
]""")

IDENTITY_REGISTRY_ABI = json.loads("""[
    {
        "inputs": [{"name": "owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [{"name": "agentURI", "type": "string"}],
        "name": "register",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "nonpayable",
        "type": "function"
    }
]""")

TRANSFER_EVENT_TOPIC = Web3.keccak(text="Transfer(address,address,uint256)")


class ChainService:
    """Handles on-chain ERC-8004 interactions on Base."""

    def __init__(self) -> None:
        settings = get_settings()
        if not settings.recruiter_private_key or not settings.recruiter_base_rpc_url:
            logger.warning("Chain service disabled — no private key or RPC URL configured")
            self._enabled = False
            return

        self._enabled = True
        self._w3 = Web3(Web3.HTTPProvider(settings.recruiter_base_rpc_url))
        self._account = self._w3.eth.account.from_key(settings.recruiter_private_key)

        self._reputation = self._w3.eth.contract(
            address=Web3.to_checksum_address(settings.reputation_registry),
            abi=REPUTATION_REGISTRY_ABI,
        )
        self._identity = self._w3.eth.contract(
            address=Web3.to_checksum_address(settings.identity_registry),
            abi=IDENTITY_REGISTRY_ABI,
        )

        logger.info(f"ChainService initialized — wallet={self._account.address} chain=base")

    @property
    def wallet_address(self) -> str:
        if not self._enabled:
            return ""
        return self._account.address

    @property
    def enabled(self) -> bool:
        return self._enabled

    def self_register(self, agent_uri: str) -> int | None:
        """Register this recruiter as an ERC-8004 agent. Returns token ID or None."""
        if not self._enabled:
            return None

        try:
            balance = self._identity.functions.balanceOf(self._account.address).call()
            if balance > 0:
                logger.info("Recruiter already registered on-chain")
                return None  # already registered

            call = self._identity.functions.register(agent_uri)
            estimated_gas = call.estimate_gas({"from": self._account.address})

            tx = call.build_transaction({
                "from": self._account.address,
                "nonce": self._w3.eth.get_transaction_count(self._account.address),
                "gas": int(estimated_gas * 1.3),
                "gasPrice": self._w3.eth.gas_price,
                "chainId": 8453,  # Base
            })

            signed = self._account.sign_transaction(tx)
            tx_hash = self._w3.eth.send_raw_transaction(signed.raw_transaction)
            receipt = self._w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)

            if receipt.status != 1:
                logger.error(f"Self-registration reverted: {tx_hash.hex()}")
                return None

            # Parse token ID from Transfer event
            for log in receipt.logs:
                if log.topics and log.topics[0] == TRANSFER_EVENT_TOPIC:
                    token_id = int(log.topics[3].hex(), 16)
                    logger.info(f"Recruiter registered — token_id={token_id} tx={tx_hash.hex()}")
                    return token_id

            logger.warning("Registration tx succeeded but no Transfer event found")
            return None

        except Exception as e:
            logger.error(f"Self-registration failed: {e}")
            return None

    def submit_feedback(
        self,
        agent_id: int,
        score: int,
        comment: str,
        tag1: str = "delegation",
        tag2: str = "recruiter",
    ) -> str | None:
        """Submit ERC-8004 reputation feedback on Base. Returns tx hash or None."""
        if not self._enabled:
            return None

        score = max(1, min(100, score))
        nonce_input = f"recruiter:{agent_id}:{int(time.time())}"
        feedback_hash = Web3.keccak(text=nonce_input)

        try:
            call = self._reputation.functions.giveFeedback(
                agent_id,
                score,
                0,
                tag1,
                tag2,
                comment[:256] if comment else "recruiter-delegation",
                "",
                feedback_hash,
            )

            estimated_gas = call.estimate_gas({"from": self._account.address})
            tx = call.build_transaction({
                "from": self._account.address,
                "nonce": self._w3.eth.get_transaction_count(self._account.address),
                "gas": int(estimated_gas * 1.3),
                "gasPrice": self._w3.eth.gas_price,
                "chainId": 8453,
            })

            signed = self._account.sign_transaction(tx)
            tx_hash = self._w3.eth.send_raw_transaction(signed.raw_transaction)
            receipt = self._w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)

            if receipt.status == 1:
                hex_hash = tx_hash.hex()
                logger.info(f"Feedback submitted — agent={agent_id} score={score} tx={hex_hash}")
                return hex_hash
            else:
                logger.error(f"Feedback tx reverted — agent={agent_id} tx={tx_hash.hex()}")
                return None

        except Exception as e:
            logger.error(f"Feedback submission failed for agent #{agent_id}: {e}")
            return None
