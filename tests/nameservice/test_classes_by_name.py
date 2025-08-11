import pytest


def test_query_classes_by_name_single(chainnet, generate_account, faucet, register_name):
    dysond_bin = chainnet[0]

    [alice_name, alice_address] = generate_account('alice')
    faucet(alice_address, denom="udys", amount="10000000")

    root = register_name(dysond_bin, alice_name, alice_address)

    # Save a class under the root
    resp = dysond_bin("tx", "nameservice", "save-class",
                      "--class-id", root,
                      "--name", "Main",
                      "--symbol", "MAIN",
                      "--description", "Main collection",
                      "--uri", "https://example.com",
                      "--from", alice_name)
    assert resp["code"] == 0, resp.get("raw_log", "")

    out = dysond_bin("query", "nameservice", "nftclasses-by-name", "--name", root)
    assert "class_ids" in out
    assert root in out["class_ids"], out


def test_query_classes_by_name_multiple(chainnet, generate_account, faucet, register_name):
    dysond_bin = chainnet[0]

    [alice_name, alice_address] = generate_account('alice')
    faucet(alice_address, denom="udys", amount="10000000")

    root = register_name(dysond_bin, alice_name, alice_address)

    sub1 = f"{root}/a"
    sub2 = f"{root}/b"

    for cid in [root, sub1, sub2]:
        resp = dysond_bin("tx", "nameservice", "save-class",
                          "--class-id", cid,
                          "--name", "C",
                          "--symbol", "C",
                          "--description", "C",
                          "--uri", "https://example.com",
                          "--from", alice_name)
        assert resp["code"] == 0, resp.get("raw_log", "")

    out = dysond_bin("query", "nameservice", "nftclasses-by-name", "--name", root)
    assert set([root, sub1, sub2]).issubset(set(out.get("class_ids", []))), out


def test_query_classes_by_name_not_found(chainnet):
    dysond_bin = chainnet[0]
    out = dysond_bin("query", "nameservice", "nftclasses-by-name", "--name", "doesnotexist.dys")
    # Expect error info in response or proper non-zero in CLI layer; here assert structure contains error
    assert "error" in out or out.get("code", 0) != 0


