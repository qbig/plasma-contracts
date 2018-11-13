import pytest
from ethereum.tools.tester import TransactionFailed


def test_challenge_in_flight_exit_not_canonical_should_succeed(testlang):
    owner_1, owner_2, amount = testlang.accounts[0], testlang.accounts[1], 100
    deposit_id = testlang.deposit(owner_1, amount)
    spend_id = testlang.spend_utxo([deposit_id], [owner_1.key])
    double_spend_id = testlang.spend_utxo([deposit_id], [owner_1.key], [(owner_1.address, 100)], force_invalid=True)

    testlang.start_in_flight_exit(spend_id)

    testlang.challenge_in_flight_exit_not_canonical(spend_id, double_spend_id, key=owner_2.key)

    in_flight_exit = testlang.get_in_flight_exit(spend_id)
    assert in_flight_exit.bond_owner == owner_2.address
    assert in_flight_exit.oldest_competitor == double_spend_id
    assert in_flight_exit.challenge_flag_set


def test_challenge_in_flight_exit_not_canonical_wrong_period_should_fail(testlang):
    owner_1, owner_2, amount = testlang.accounts[0], testlang.accounts[1], 100
    deposit_id = testlang.deposit(owner_1, amount)
    spend_id = testlang.spend_utxo([deposit_id], [owner_1.key])
    double_spend_id = testlang.spend_utxo([deposit_id], [owner_1.key], [(owner_1.address, 100)], force_invalid=True)

    testlang.start_in_flight_exit(spend_id)
    testlang.forward_to_period(2)

    with pytest.raises(TransactionFailed):
        testlang.challenge_in_flight_exit_not_canonical(spend_id, double_spend_id, key=owner_2.key)


def test_challenge_in_flight_exit_not_canonical_same_tx_should_fail(testlang):
    owner_1, owner_2, amount = testlang.accounts[0], testlang.accounts[1], 100
    deposit_id = testlang.deposit(owner_1, amount)
    spend_id = testlang.spend_utxo([deposit_id], [owner_1.key])
    double_spend_id = testlang.spend_utxo([deposit_id], [owner_1.key], force_invalid=True)

    testlang.start_in_flight_exit(spend_id)

    with pytest.raises(TransactionFailed):
        testlang.challenge_in_flight_exit_not_canonical(spend_id, double_spend_id, key=owner_2.key)


def test_challenge_in_flight_exit_not_canonical_unrelated_tx_should_fail(testlang):
    owner_1, owner_2, amount = testlang.accounts[0], testlang.accounts[1], 100
    deposit_id_1 = testlang.deposit(owner_1, amount)
    deposit_id_2 = testlang.deposit(owner_1, amount)
    spend_id = testlang.spend_utxo([deposit_id_1], [owner_1.key])
    unrelated_spend_id = testlang.spend_utxo([deposit_id_2], [owner_1.key])
    spend_tx = testlang.child_chain.get_transaction(spend_id)
    unrelated_spend_tx = testlang.child_chain.get_transaction(unrelated_spend_id)

    testlang.start_in_flight_exit(spend_id)

    proof = testlang.get_merkle_proof(unrelated_spend_id)
    signature = unrelated_spend_tx.signatures[0]

    with pytest.raises(TransactionFailed):
        testlang.root_chain.challengeInFlightExitNotCanonical(spend_tx.encoded, 0, unrelated_spend_tx.encoded, 0, unrelated_spend_id, proof, signature, sender=owner_2.key)


def test_challenge_in_flight_exit_not_canonical_wrong_index_should_fail(testlang):
    owner_1, owner_2, amount = testlang.accounts[0], testlang.accounts[1], 100
    deposit_id = testlang.deposit(owner_1, amount)
    spend_id = testlang.spend_utxo([deposit_id], [owner_1.key])
    double_spend_id = testlang.spend_utxo([deposit_id], [owner_1.key], [(owner_1.address, 100)], force_invalid=True)
    spend_tx = testlang.child_chain.get_transaction(spend_id)
    double_spend_tx = testlang.child_chain.get_transaction(double_spend_id)

    testlang.start_in_flight_exit(spend_id)

    proof = testlang.get_merkle_proof(double_spend_id)
    signature = double_spend_tx.signatures[0]

    with pytest.raises(TransactionFailed):
        testlang.root_chain.challengeInFlightExitNotCanonical(spend_tx.encoded, 0, double_spend_tx.encoded, 1, double_spend_id, proof, signature, sender=owner_2.key)


def test_challenge_in_flight_exit_not_canonical_invalid_signature_should_fail(testlang):
    owner_1, owner_2, amount = testlang.accounts[0], testlang.accounts[1], 100
    deposit_id = testlang.deposit(owner_1, amount)
    spend_id = testlang.spend_utxo([deposit_id], [owner_1.key])
    double_spend_id = testlang.spend_utxo([deposit_id], [owner_2.key], [(owner_1.address, 100)], force_invalid=True)

    testlang.start_in_flight_exit(spend_id)

    with pytest.raises(TransactionFailed):
        testlang.challenge_in_flight_exit_not_canonical(spend_id, double_spend_id, key=owner_2.key)


def test_challenge_in_flight_exit_not_canonical_invalid_proof_should_fail(testlang):
    owner_1, owner_2, amount = testlang.accounts[0], testlang.accounts[1], 100
    deposit_id = testlang.deposit(owner_1, amount)
    spend_id = testlang.spend_utxo([deposit_id], [owner_1.key])
    double_spend_id = testlang.spend_utxo([deposit_id], [owner_1.key], [(owner_1.address, 100)], force_invalid=True)
    spend_tx = testlang.child_chain.get_transaction(spend_id)
    double_spend_tx = testlang.child_chain.get_transaction(double_spend_id)

    testlang.start_in_flight_exit(spend_id)

    proof = b''
    signature = double_spend_tx.signatures[0]

    with pytest.raises(TransactionFailed):
        testlang.root_chain.challengeInFlightExitNotCanonical(spend_tx.encoded, 0, double_spend_tx.encoded, 0, double_spend_id, proof, signature, sender=owner_2.key)


def test_challenge_in_flight_exit_not_canonical_same_tx_twice_should_fail(testlang):
    owner_1, owner_2, amount = testlang.accounts[0], testlang.accounts[1], 100
    deposit_id = testlang.deposit(owner_1, amount)
    spend_id = testlang.spend_utxo([deposit_id], [owner_1.key])
    double_spend_id = testlang.spend_utxo([deposit_id], [owner_1.key], [(owner_1.address, 100)], force_invalid=True)

    testlang.start_in_flight_exit(spend_id)

    testlang.challenge_in_flight_exit_not_canonical(spend_id, double_spend_id, key=owner_2.key)

    with pytest.raises(TransactionFailed):
        testlang.challenge_in_flight_exit_not_canonical(spend_id, double_spend_id, key=owner_2.key)


def test_challenge_in_flight_exit_twice_older_position_should_succeed(testlang):
    owner_1, owner_2, owner_3, amount = testlang.accounts[0], testlang.accounts[1], testlang.accounts[2], 100
    deposit_id = testlang.deposit(owner_1, amount)
    spend_id = testlang.spend_utxo([deposit_id], [owner_1.key])
    double_spend_id_1 = testlang.spend_utxo([deposit_id], [owner_1.key], [(owner_1.address, 100)], force_invalid=True)
    double_spend_id_2 = testlang.spend_utxo([deposit_id], [owner_1.key], [(owner_1.address, 50)], force_invalid=True)

    testlang.start_in_flight_exit(spend_id)

    testlang.challenge_in_flight_exit_not_canonical(spend_id, double_spend_id_2, key=owner_2.key)
    testlang.challenge_in_flight_exit_not_canonical(spend_id, double_spend_id_1, key=owner_3.key)

    in_flight_exit = testlang.get_in_flight_exit(spend_id)
    assert in_flight_exit.bond_owner == owner_3.address
    assert in_flight_exit.oldest_competitor == double_spend_id_1
    assert in_flight_exit.challenge_flag_set


def test_challenge_in_flight_exit_twice_younger_position_should_fail(testlang):
    owner_1, owner_2, amount = testlang.accounts[0], testlang.accounts[1], 100
    deposit_id = testlang.deposit(owner_1, amount)
    spend_id = testlang.spend_utxo([deposit_id], [owner_1.key])
    double_spend_id_1 = testlang.spend_utxo([deposit_id], [owner_1.key], [(owner_1.address, 100)], force_invalid=True)
    double_spend_id_2 = testlang.spend_utxo([deposit_id], [owner_1.key], [(owner_1.address, 50)], force_invalid=True)

    testlang.start_in_flight_exit(spend_id)

    testlang.challenge_in_flight_exit_not_canonical(spend_id, double_spend_id_1, key=owner_2.key)

    with pytest.raises(TransactionFailed):
        testlang.challenge_in_flight_exit_not_canonical(spend_id, double_spend_id_2, key=owner_2.key)
