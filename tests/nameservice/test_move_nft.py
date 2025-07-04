# 6-3 MoveNft tests (success + failure paths)

# (register_name fixture provided via conftest)


def _nft_owner(dysond_bin, class_id: str, nft_id: str) -> str:
    return dysond_bin("query", "nft", "owner", class_id, nft_id).get("owner", "")


# ----------------------------- TESTS -----------------------------------

def test_move_nft_success(chainnet, generate_account, faucet, register_name):
    dysond_bin = chainnet[0]

    # accounts
    owner_name, owner_addr = generate_account("nft_owner")
    recipient_name, recipient_addr = generate_account("nft_recipient")
    faucet(owner_addr, denom="udys", amount="25000")

    # register name & derive NFT class ID
    class_id = register_name(dysond_bin, owner_name, owner_addr)

    # save nft class
    save_resp = dysond_bin(
        "tx",
        "nameservice",
        "save-class",
        "--class-id",
        class_id,
        "--from",
        owner_name,
    )
    assert save_resp["code"] == 0, save_resp.get("raw_log")

    # verify EventClassSaved emitted
    assert any(ev.get("type", "").endswith("EventClassSaved") for ev in save_resp.get("events", [])), "EventClassSaved event missing"

    # mint nft
    nft_id = "nft1"
    mint_resp = dysond_bin(
        "tx",
        "nameservice",
        "mint-nft",
        "--class-id",
        class_id,
        "--nft-id",
        nft_id,
        "--uri",
        "https://example.com/n1",
        "--from",
        owner_name,
    )
    assert mint_resp["code"] == 0, mint_resp.get("raw_log")

    # ensure ownership
    assert _nft_owner(dysond_bin, class_id, nft_id) == owner_addr

    # move nft
    tx_resp = dysond_bin(
        "tx",
        "nameservice",
        "move-nft",
        "--class-id",
        class_id,
        "--nft-id",
        nft_id,
        "--to-address",
        recipient_addr,
        "--from",
        owner_name,
    )
    assert tx_resp["code"] == 0, tx_resp.get("raw_log")

    # verify new owner
    assert _nft_owner(dysond_bin, class_id, nft_id) == recipient_addr


def test_move_nft_non_owner_fails(chainnet, generate_account, faucet, register_name):
    dysond_bin = chainnet[0]

    owner_name, owner_addr = generate_account("nft_owner")
    attacker_name, attacker_addr = generate_account("nft_attacker")
    faucet(owner_addr, denom="udys", amount="25000")
    faucet(attacker_addr, denom="udys", amount="1000")

    class_id = register_name(dysond_bin, owner_name, owner_addr)

    save_resp = dysond_bin(
        "tx",
        "nameservice",
        "save-class",
        "--class-id",
        class_id,
        "--from",
        owner_name,
    )
    assert save_resp["code"] == 0, save_resp.get("raw_log")

    nft_id = "nft1"
    mint_resp = dysond_bin(
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
    assert mint_resp["code"] == 0, mint_resp.get("raw_log")

    # attacker attempts move
    tx_resp = dysond_bin(
        "tx",
        "nameservice",
        "move-nft",
        "--class-id",
        class_id,
        "--nft-id",
        nft_id,
        "--to-address",
        attacker_addr,
        "--from",
        attacker_name,
    )
    assert tx_resp["code"] != 0, "non-owner should not be able to move NFT"


def test_move_nft_module_account_fails(chainnet, generate_account, faucet, register_name):
    dysond_bin = chainnet[0]

    owner_name, owner_addr = generate_account("nft_owner")
    faucet(owner_addr, denom="udys", amount="25000")

    # module account destination
    module_info = dysond_bin("query", "auth", "module-account", "distribution")
    module_addr = module_info["account"]["value"]["address"]

    class_id = register_name(dysond_bin, owner_name, owner_addr)
    save_resp = dysond_bin(
        "tx",
        "nameservice",
        "save-class",
        "--class-id",
        class_id,
        "--from",
        owner_name,
    )
    assert save_resp["code"] == 0, save_resp.get("raw_log")

    nft_id = "nft1"
    mint_resp = dysond_bin(
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
    assert mint_resp["code"] == 0, mint_resp.get("raw_log")

    # attempt move to module account
    tx_resp = dysond_bin(
        "tx",
        "nameservice",
        "move-nft",
        "--class-id",
        class_id,
        "--nft-id",
        nft_id,
        "--to-address",
        module_addr,
        "--from",
        owner_name,
    )
    assert tx_resp["code"] != 0, "move to module account should fail" 