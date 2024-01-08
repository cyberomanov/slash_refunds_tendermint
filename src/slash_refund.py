import argparse
import json
import logging
import shutil
from subprocess import run
from time import sleep

import requests

from utils.csv_utils import writeRefundsCsv

BIN_DIR = ""  # if this isn't empty, make sure it ends with a slash

logger = logging.getLogger(__name__)
stream_handler = logging.StreamHandler()
stream_handler.setLevel(logging.DEBUG)
logger.addHandler(stream_handler)
logger.setLevel(logging.INFO)


def getResponse(end_point, query_field=None, query_msg=None):
    response = None

    try:
        if query_msg is not None and query_field is not None:
            response = requests.get(end_point, params={query_field: query_msg})
        else:
            response = requests.get(end_point, params={})
    except Exception as e:
        logger.exception(e)

    if response is not None and response.status_code == 200:
        return json.loads(response.text)
    else:
        if response is not None:
            logger.error(
                "\n\t".join(
                    (
                        "Response Error",
                        str(response.status_code),
                        str(response.text),
                    )
                )
            )
        else:
            logger.error("Response is None")

        return None


def getSlashBlock(url: str, val_address: str) -> int:
    endpoint = url + "/block_search?query=%22slash.address=%27" + val_address + "%27%22"
    data = getResponse(endpoint)
    latest_slash = 0
    # earliest_slash = len(data["result"]["blocks"]) - 1
    return data["result"]["blocks"][latest_slash]["block"]["header"]["height"]


def getDelegationAmounts(
    daemon: str, endpoint: str, chain_id: str, block_height: int, valoper_address: str
):
    endpoints = [endpoint]
    delegations = {}
    page = 1
    page_limit = 200
    more_pages = True

    while more_pages:
        endpoint_choice = (page % len(endpoints)) - 1
        command = (
            f"{BIN_DIR}{daemon} q staking delegations-to {valoper_address} "
            f"--height {block_height} "
            f"--page {page} "
            f"--output json "
            f"--limit {page_limit} "
            f"--node {endpoints[endpoint_choice]} "
            f"--chain-id {chain_id}"
        )
        logger.debug(f"Delegation amount command: {command}")
        logger.info(f"Page: {page}")
        result = run(
            command,
            shell=True,
            capture_output=True,
            text=True,
        )
        if result.returncode == 1:
            logger.info(f"Failed endpoint: {endpoints[endpoint_choice]}")
            continue
        response = json.loads(result.stdout)

        for delegation in response["delegation_responses"]:
            delegator_address = delegation["delegation"]["delegator_address"]
            delegation_amount = delegation["balance"]["amount"]
            if delegator_address not in delegations:
                delegations[delegator_address] = delegation_amount
            else:
                logger.info(delegator_address)
        page += 1
        sleep(2)
        if len(response["delegation_responses"]) < page_limit:
            more_pages = False

    return delegations


def calculateRefundAmounts(
    daemon: str,
    endpoint: str,
    chain_id: str,
    slash_block: int,
    valoper_address: str,
    min_refund: int,
):
    pre_slack_block = int(slash_block) - 5
    refund_amounts = {}
    pre_slash_delegations = getDelegationAmounts(
        daemon, endpoint, chain_id, pre_slack_block, valoper_address
    )
    logger.debug(f"Pre slash amounts: {pre_slash_delegations}")
    post_slash_delegations = getDelegationAmounts(
        daemon, endpoint, chain_id, slash_block, valoper_address
    )
    logger.debug(f"Post slash amounts: {post_slash_delegations}")

    if len(pre_slash_delegations) != len(post_slash_delegations):
        raise ("Something went awry on delegation calcs")
    for delegation_address in pre_slash_delegations:
        refund_amount = int(pre_slash_delegations[delegation_address]) - int(
            post_slash_delegations[delegation_address]
        )
        if refund_amount > int(min_refund):
            refund_amounts[delegation_address] = refund_amount

    logger.info(f"Number of refunds: {len(refund_amounts)}")
    return refund_amounts


def buildRefundJSON(
    refund_amounts: dict, send_address: str, denom: str, memo: str
) -> dict:
    data = {
        "body": {
            "messages": [],
            "memo": memo,
            "timeout_height": "0",
            "extension_options": [],
            "non_critical_extension_options": [],
        },
        "auth_info": {
            "signer_infos": [],
            "fee": {
                "amount": [{"denom": denom, "amount": "50000"}],
                "gas_limit": "1500000",
                "payer": "",
                "granter": "",
            },
        },
        "signatures": [],
    }
    message_list = []
    for refund_address in refund_amounts:
        message = {
            "@type": "/cosmos.bank.v1beta1.MsgSend",
            "from_address": send_address,
            "to_address": refund_address,
            "amount": [{"denom": denom, "amount": str(refund_amounts[refund_address])}],
        }
        message_list.append(message)
    data["body"]["messages"] = message_list
    return data


def buildRefundScript(
    refund_amounts: dict, send_address: str, denom: str, memo: str
) -> int:
    batch_size = 75
    batch = 0
    batches = []
    batched = {}
    while batch < len(refund_amounts):
        batched_refund_amounts = {}
        for x in list(refund_amounts)[batch : batch + batch_size]:
            batched_refund_amounts[x] = refund_amounts[x]
        batches.append(batched_refund_amounts)
        batch += batch_size

    batch = 0
    for batch_refund in batches:
        refundJson = buildRefundJSON(batch_refund, send_address, denom, memo)
        with open(f"/tmp/dist_{batch}.json", "w+") as f:
            f.write(json.dumps(refundJson))
        for address in batch_refund:
            batched[address] = batch_refund[address]
        batch += 1
    return batch


def issue_refunds(
    batch_count: int,
    daemon: str,
    chain_id: str,
    keyname: str,
    node: str,
    broadcast: bool = True,
):
    i = 0
    while i < batch_count:
        sign_cmd = (
            f"{BIN_DIR}{daemon} tx sign /tmp/dist_{i}.json --from {keyname} -o json "
            f"--output-document /tmp/dist_{i}_signed.json --node {node} --chain-id {chain_id} "
            f"--keyring-backend test"
        )
        broadcast_cmd = (
            f"{BIN_DIR}{daemon} tx broadcast /tmp/dist_{i}_signed.json --node {node} "
            f"--chain-id {chain_id}"
        )

        # sign refund
        result = run(
            sign_cmd,
            shell=True,
            capture_output=True,
            text=True,
        )
        sleep(1)

        if broadcast:
            # broadcast refund
            result = run(
                broadcast_cmd,
                shell=True,
                capture_output=True,
                text=True,
            )
            logger.info(f"Broadcasted refund: {result}")
            shutil.move(
                f"/tmp/dist_{i}_signed.json", f"/tmp/dist_{i}_signed_refunded.json"
            )

        i += 1
        # if this is not the last batch, sleep
        if i < batch_count:
            sleep(16)


def parseArgs():
    parser = argparse.ArgumentParser(
        description="Create json file for refunding slashing to delegators"
    )
    parser.add_argument(
        "--denom",
        dest="denom",
        required=True,
        default="uatom",
        help="denom for refunds (ex. uatom)",
    )
    parser.add_argument(
        "--mr",
        "--min_refund",
        dest="min_refund",
        required=False,
        default=1,
        help=(
            "An integer value that sets the minimum threshold for slashing compensation. "
            "If not specified, defaults to 1. "
            "(ex. to refund any value more than 0.001 $ATOM, you should set --min_refund 1000)"
        ),
    )
    parser.add_argument(
        "--daemon",
        dest="daemon",
        required=True,
        default="gaiad",
        help="daemon for refunds (ex. gaiad)",
    )
    parser.add_argument(
        "-c",
        "--chain_id",
        dest="chain_id",
        required=True,
        default="cosmoshub-4",
        help="Chain ID (ex. cosmoshub-4)",
    )
    parser.add_argument(
        "-e",
        "--endpoint",
        dest="endpoint",
        required=True,
        help="RPC endpoint to node for gathering data",
    )
    parser.add_argument(
        "-vc",
        "--valcons_address",
        dest="valcons_address",
        required=True,
        help="Valcons address of validator (ex. cosmosvalcons1c5e86exd7jsyhcfqdejltdsagjfrvv8xv22368), "
        "you can get this by doing {daemon} tendermint show-address",
    )
    parser.add_argument(
        "-v",
        "--valoper_address",
        dest="valoper_address",
        required=True,
        help="Valoper address of validator (ex. cosmosvaloper140l6y2gp3gxvay6qtn70re7z2s0gn57zfd832j), "
        "you can get this by doing {daemon} keys show --bech=val -a {keyname}",
    )
    parser.add_argument(
        "-s",
        "--send_address",
        dest="send_address",
        required=True,
        help="Address to send funds from",
    )
    parser.add_argument(
        "-m",
        "--memo",
        dest="memo",
        help="Optional. Memo to send in each tx (ex. With 💜 from Lavender.Five Nodes 🐝)",
    )
    parser.add_argument(
        "-k",
        "--keyname",
        dest="keyname",
        required=True,
        help="Wallet to issue refunds from",
    )
    parser.add_argument(
        "-f",
        "--refund_file",
        dest="refund_file",
        required=False,
        default=None,
        type=open,
        help=(
            "CSV file that encodes the delegator addresses and refund amounts. Note: delegator "
            "address is expected to be in the first column and the refund amount in [DENOM] is "
            "expected to be in the fourth column."
        ),
    )
    parser.add_argument(
        "--dry_run",
        dest="dry_run",
        action="store_const",
        required=False,
        default=False,
        const=True,
        help="Indicates whether this should actually broadcast transactions or not",
    )
    parser.add_argument(
        "--no_broadcast",
        dest="no_broadcast",
        action="store_const",
        required=False,
        default=False,
        const=True,
        help=(
            "Similar to dry run, but in this case the tx JSON is output and signed, but not "
            "broadcast. This is useful for testing."
        ),
    )
    return parser.parse_args()


def get_daemon_path(daemon: str) -> str:
    result = run(
        f"which {daemon}",
        shell=True,
        capture_output=True,
        text=True,
    )
    binary_path = result.stdout.strip().removesuffix(daemon)
    logger.info(f"Binary path: {binary_path}")
    return binary_path


def main():
    global BIN_DIR
    args = parseArgs()
    denom = args.denom
    min_refund = args.min_refund
    daemon = args.daemon
    chain_id = args.chain_id
    endpoint = args.endpoint
    valcons_address = args.valcons_address
    valoper_address = args.valoper_address
    send_address = args.send_address
    memo = args.memo
    keyname = args.keyname
    refund_file = args.refund_file
    dry_run = args.dry_run
    should_broadcast = not args.no_broadcast
    logger.debug(f"DEBUG: args: {args}")

    if not BIN_DIR:
        BIN_DIR = get_daemon_path(daemon)

    slash_block = getSlashBlock(endpoint, valcons_address)
    logger.info(f"Slash block: {slash_block}")
    refund_amounts = calculateRefundAmounts(
        daemon, endpoint, chain_id, slash_block, valoper_address, min_refund
    )

    writeRefundsCsv(refund_amounts)

    batch_count = buildRefundScript(refund_amounts, send_address, denom, memo)
    if not dry_run:
        issue_refunds(
            batch_count, daemon, chain_id, keyname, endpoint, should_broadcast
        )


if __name__ == "__main__":
    main()
