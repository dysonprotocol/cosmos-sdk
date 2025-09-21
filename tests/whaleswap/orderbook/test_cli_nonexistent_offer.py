import json


def test_take_nonexistent_offer_fails(chainnet, generate_account, faucet):
    dysond = chainnet[0]
    [taker_name, taker_addr] = generate_account("ob_noexist_t")
    faucet(taker_addr, amount=1_000_000)
    bogus_id = 9999999
    res = dysond(
        "tx",
        "whaleswap",
        "take-offer",
        "--trades",
        f"offer_id={bogus_id}",
        "--from",
        taker_name,
    )
    assert (
        res.get("code", 0) != 0
    ), f"taking nonexistent offer should fail: {json.dumps(res, indent=2)}"
