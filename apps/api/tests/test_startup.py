from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from app.blockchain.adapter import LocalSmartAccountAdapter
from app.schemas.domain import Deployment


def test_missing_deployment_has_recovery_instructions(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match=r"scripts/deploy.py"):
        LocalSmartAccountAdapter("http://127.0.0.1:8545", str(tmp_path / "missing.json"))


def test_stale_deployment_does_not_enable_execution(tmp_path: Path, deployment: Deployment) -> None:
    path = tmp_path / "deployment.json"
    path.write_text(deployment.model_dump_json())
    web3 = Mock()
    web3.eth.chain_id = 31337
    web3.client_version = "anvil/test"
    web3.eth.get_code.return_value = b""
    with (
        patch("app.blockchain.adapter.Web3", return_value=web3),
        patch.object(LocalSmartAccountAdapter, "contract", return_value=Mock()),
    ):
        with pytest.raises(RuntimeError, match="saved deployment.json does not restore"):
            LocalSmartAccountAdapter("http://127.0.0.1:8545", str(path))
    web3.eth.send_transaction.assert_not_called()
