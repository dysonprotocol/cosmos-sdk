import pytest


def test_delete_empty_class(chainnet, generate_account, faucet, register_name):
    dysond_bin = chainnet[0]

    [alice_name, alice_address] = generate_account('alice')
    faucet(alice_address, denom="udys", amount="10000000")

    root = register_name(dysond_bin, alice_name, alice_address)

    # Create class under the root
    resp = dysond_bin(
        "tx",
        "nameservice",
        "save-class",
        "--class-id",
        root,
        "--from",
        alice_name,
    )
    assert resp["code"] == 0, resp.get("raw_log", "")

    # Verify it appears in reverse index
    out_before = dysond_bin("query", "nameservice", "nftclasses-by-name", "--name", root)
    assert root in out_before.get("class_ids", []), out_before

    # Delete the empty class
    del_resp = dysond_bin(
        "tx",
        "nameservice",
        "delete-class",
        "--class-id",
        root,
        "--from",
        alice_name,
    )
    assert del_resp["code"] == 0, del_resp.get("raw_log", "")

    # Ensure reverse index no longer includes the class
    out_after = dysond_bin("query", "nameservice", "nftclasses-by-name", "--name", root)
    assert root not in out_after.get("class_ids", []), out_after


