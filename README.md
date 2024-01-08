# tendermint_refund

The purpose of this script is to create a json file to refund users from a slash event.

## Important Notes:
In order for this to work, you will need access to a node that has history as far back as your slashing event. 
Most public nodes only keep ~100 blocks! We maintain the last 10,000 blocks for every chain we validate on.
If you need an endpoint for a network [we support](https://www.lavenderfive.com/), please reach out! 

Note also that this will only refund the **LATEST** slashing event!!

## Requirements:
1. You will need to install the dependencies. 

```python:
  # using poetry:
  poetry install

  # using pip:
  pip install
```

2. In order to send the commands, the daemon will need to be installed locally. This is not ideal, but was the choice
made early on. Rebuilding with https://github.com/fetchai/cosmpy would be neato.

3. Add your refund mnemonics to the daemon as `--keyring-backend test` that way you won't need to enter a password. Do
**NOT** use your validator wallet for the refunds. Create a different wallet, load up the amount you'll need to refund,
and go from there.

## Usage:
```
git clone https://github.com/LavenderFive/slash_refunds_tendermint.git
cd slash_refunds_tendermint
python3 src/slash_refund.py --denom {denom} --daemon {daemon} --c {chain_id} -e {rpc_endpoint} -vc {valcons_address} -v {valoper_address} -s {send_address}

# example:
python3 src/slash_refund.py --denom uatom --min_refund 100 --daemon gaiad --c cosmoshub-4 -e http://65.21.132.124:10657 -vc cosmosvalcons1c5e86exd7jsyhcfqdejltdsagjfrvv8xv22368 -v cosmosvaloper140l6y2gp3gxvay6qtn70re7z2s0gn57zfd832j -s cosmos15s9vggt9d0xumzqeq89scy4lku4k6qlzvvv2lz -m "With 💜 from Lavender.Five Nodes 🐝"
```

This will output two different kinds of files

* `/tmp/dist_<batch #>.json` which is the unsigned JSON representation of a batch transaction
* `~/dist_<batch #>_signed.json` which represents the signed, but not yet broadcast batch transaaction

```bash
$ python3 src/slash_refund.py --help
usage: slash_refund.py [-h] --denom DENOM --daemon DAEMON -c CHAIN_ID -e ENDPOINT -vc VALCONS_ADDRESS -v VALOPER_ADDRESS -s SEND_ADDRESS [-m MEMO] -k KEYNAME [--dry_run [DRY_RUN]] [-f REFUND_FILE]

Create json file for refunding slashing to delegators

optional arguments:
  -h, --help            show this help message and exit
  --denom DENOM         denom for refunds (ex. uatom)
  --mr MIN_REFUND, --min_refund MIN_REFUND
                        the minimum threshold for slashing compensation (ex. to refund any value more than 0.001 $ATOM, you should set --min_refund 1000)
  --daemon DAEMON       daemon for refunds (ex. gaiad)
  -c CHAIN_ID, --chain_id CHAIN_ID
                        Chain ID (ex. cosmoshub-4)
  -e ENDPOINT, --endpoint ENDPOINT
                        RPC endpoint to node for gathering data
  -vc VALCONS_ADDRESS, --valcons_address VALCONS_ADDRESS
                        Valcons address of validator (ex. cosmosvalcons1c5e86exd7jsyhcfqdejltdsagjfrvv8xv22368),
                        you can get this by doing {daemon} tendermint show-address
  -v VALOPER_ADDRESS, --valoper_address VALOPER_ADDRESS
                        Valoper address of validator (ex. cosmosvaloper140l6y2gp3gxvay6qtn70re7z2s0gn57zfd832j),
                        you can get this by doing {daemon} keys show --bech=val -a {keyname}
  -s SEND_ADDRESS, --send_address SEND_ADDRESS
                        Address to send funds from
  -m MEMO, --memo MEMO  Optional. Memo to send in each tx (ex. With 💜 from Lavender.Five Nodes 🐝)
  -k KEYNAME, --keyname KEYNAME
                        Wallet to issue refunds from
  -f REFUND_FILE, --refund_file REFUND_FILE
                        CSV file that encodes the delegator addresses and refund amounts. Note: delegator address is expected to be in the first column and the refund amount in [DENOM] is expected to be in the fourth column.
  --dry_run             Indicates whether this should actually broadcast transactions or not
  --no_broadcast        Similar to dry run, but in this case the tx JSON is output and signed, but not broadcast. This is useful for testing.

```



## No Liability

As far as the law allows, this software comes as is, without any warranty or condition, 
and no contributor will be liable to anyone for any damages related to this software or 
this license, under any kind of legal claim.

Please do your due diligence and review the transactions before they are sent!
