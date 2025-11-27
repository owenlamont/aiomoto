from typing import Any, TYPE_CHECKING

import aioboto3
import pytest

from aiomoto import mock_aws


if TYPE_CHECKING:
    from aioboto3.client import ClientCreatorContext


PUBKEY_LINES = [
    "ssh-rsa",
    "AAAAB3NzaC1yc2EAAAADAQABAAABAQDV5+voluw2zmzqpqCAqtsyoP01TQ8Ydx1eS1yD6wUsHcPqMIqpo57YxiC8XPwrdeKQ6GG6MC3bHsgXoPypGP0LyixbiuLTU31DnnqorcHt4bWs6rQa7dK2pCCflz2fhYRt5ZjqSNsAKivIbqkH66JozN0SySIka3kEV79GdB0BicioKeEJlCwM9vvxafyzjWf/z8E0lh4ni3vkLpIVJ0t5l+Qd9QMJrT6Is0SCQPVagTYZoi8+fWDoGsBa8vyRwDjEzBl28ZplKh9tSyDkRIYszWTpmK8qHiqjLYZBfAxXjGJbEYL1iig4ZxvbYzKEiKSBi1ZMW9iWjHfZDZuxXAmB",
    "example",
]
PUBKEY = "\n".join(PUBKEY_LINES)


def _client() -> ClientCreatorContext[Any]:
    return aioboto3.Session().client("ec2-instance-connect", region_name="us-east-1")


@pytest.mark.asyncio
async def test_send_ssh_public_key_async() -> None:
    with mock_aws():
        async with _client() as client:
            resp = await client.send_ssh_public_key(
                InstanceId="i-abcdefg12345",
                InstanceOSUser="ec2-user",
                SSHPublicKey=PUBKEY,
                AvailabilityZone="us-east-1a",
            )

    assert resp["RequestId"]
