import json
import math


def _set_destination(dysond_bin, name: str, owner_key: str, dest: str):
    resp = dysond_bin(
        "tx",
        "nameservice",
        "set-destination",
        "--name",
        name,
        "--destination",
        dest,
        "--from",
        owner_key,
    )
    assert resp["code"] == 0, resp.get("raw_log")


def test_destination_signs_save_class_and_mint_coins(
    chainnet, generate_account, faucet, register_name
):
    dysond_bin = chainnet[0]

    owner_name, owner_addr = generate_account("owner_signer", faucet_amount=25000)
    dest_name, dest_addr = generate_account("dest_signer", faucet_amount=25000)

    # Register name to derive class_id/denom
    class_id = register_name(dysond_bin, owner_name, owner_addr)

    # Point name destination to dest_addr
    _set_destination(dysond_bin, class_id, owner_name, dest_addr)

    # Owner attempt should fail (destination is required signer now)
    resp_owner_save = dysond_bin(
        "tx", "nameservice", "save-class", "--class-id", class_id, "--from", owner_name
    )
    assert (
        resp_owner_save["code"] != 0
    ), "owner should not be able to save-class when destination enforced"

    # Destination succeeds
    resp_dest_save = dysond_bin(
        "tx", "nameservice", "save-class", "--class-id", class_id, "--from", dest_name
    )
    assert resp_dest_save["code"] == 0, resp_dest_save.get("raw_log")

    # Mint coins: owner fails, destination succeeds
    amount = 10
    resp_owner_mint = dysond_bin(
        "tx",
        "nameservice",
        "mint-coins",
        "--amount",
        f"{amount}{class_id}",
        "--from",
        owner_name,
        "--mint-fee",
        f"{math.ceil(amount * 0.01)}udys",
    )
    assert (
        resp_owner_mint["code"] != 0
    ), "owner should not be able to mint-coins when destination enforced"

    resp_dest_mint = dysond_bin(
        "tx",
        "nameservice",
        "mint-coins",
        "--amount",
        f"{amount}{class_id}",
        "--from",
        dest_name,
        "--mint-fee",
        f"{math.ceil(amount * 0.01)}udys",
    )
    assert resp_dest_mint["code"] == 0, resp_dest_mint.get("raw_log")


def test_destination_signs_mint_nft_and_set_metadata(
    chainnet, generate_account, faucet, register_name
):
    dysond_bin = chainnet[0]

    owner_name, owner_addr = generate_account("nft_owner")
    dest_name, dest_addr = generate_account("nft_dest")
    faucet(owner_addr, denom="udys", amount="25000")
    faucet(dest_addr, denom="udys", amount="25000")

    class_id = register_name(dysond_bin, owner_name, owner_addr)
    _set_destination(dysond_bin, class_id, owner_name, dest_addr)

    # Save class using destination to set up class
    assert (
        dysond_bin(
            "tx",
            "nameservice",
            "save-class",
            "--class-id",
            class_id,
            "--from",
            dest_name,
        )["code"]
        == 0
    )

    # Mint NFT: owner fails, destination succeeds
    nft_id = "signer-nft-1"
    resp_owner_mint = dysond_bin(
        "tx",
        "nameservice",
        "mint-nft",
        "--class-id",
        class_id,
        "--nft-id",
        nft_id,
        "--from",
        owner_name,
    )
    assert (
        resp_owner_mint["code"] != 0
    ), "owner should not be able to mint-nft when destination enforced"

    resp_dest_mint = dysond_bin(
        "tx",
        "nameservice",
        "mint-nft",
        "--class-id",
        class_id,
        "--nft-id",
        nft_id,
        "--from",
        dest_name,
    )
    assert resp_dest_mint["code"] == 0, resp_dest_mint.get("raw_log")

    # Set metadata: owner fails, destination succeeds
    resp_owner_meta = dysond_bin(
        "tx",
        "nameservice",
        "set-nft-metadata",
        "--class-id",
        class_id,
        "--nft-id",
        nft_id,
        "--metadata",
        "hello",
        "--from",
        owner_name,
    )
    assert (
        resp_owner_meta["code"] != 0
    ), "owner should not be able to set-nft-metadata when destination enforced"

    resp_dest_meta = dysond_bin(
        "tx",
        "nameservice",
        "set-nft-metadata",
        "--class-id",
        class_id,
        "--nft-id",
        nft_id,
        "--metadata",
        "hello",
        "--from",
        dest_name,
    )
    assert resp_dest_meta["code"] == 0, resp_dest_meta.get("raw_log")


def test_owner_only_set_destination_rejects_destination_signer(
    chainnet, generate_account, faucet, register_name
):
    dysond_bin = chainnet[0]

    owner_name, owner_addr = generate_account("owner_only")
    dest_name, dest_addr = generate_account("dest_only")
    faucet(owner_addr, denom="udys", amount="25000")
    faucet(dest_addr, denom="udys", amount="25000")

    name = register_name(dysond_bin, owner_name, owner_addr)

    # Owner can set destination
    ok = dysond_bin(
        "tx",
        "nameservice",
        "set-destination",
        "--name",
        name,
        "--destination",
        dest_addr,
        "--from",
        owner_name,
    )
    assert ok["code"] == 0, ok.get("raw_log")

    # Destination cannot set destination (should remain owner-only)
    fail = dysond_bin(
        "tx",
        "nameservice",
        "set-destination",
        "--name",
        name,
        "--destination",
        owner_addr,
        "--from",
        dest_name,
    )
    assert fail["code"] != 0, "destination signer must not be able to set-destination"
