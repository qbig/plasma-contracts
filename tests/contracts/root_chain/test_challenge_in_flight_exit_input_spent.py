import pytest
from ethereum.tools.tester import TransactionFailed


def test_challenge_in_flight_exit_input_spent_should_succeed(testlang):
    owner_1, owner_2, amount = testlang.accounts[0], testlang.accounts[1], 100
    deposit_id = testlang.deposit(owner_1, amount)
    spend_id = testlang.spend_utxo([deposit_id], [owner_1.key])
    double_spend_id = testlang.spend_utxo([deposit_id], [owner_1.key], [(owner_1.address, 100)], force_invalid=True)
    testlang.start_in_flight_exit(spend_id)
    testlang.piggyback_in_flight_exit_input(spend_id, 0, owner_1.key)
    testlang.forward_to_period(2)

    testlang.challenge_in_flight_exit_input_spent(spend_id, double_spend_id, owner_2.key)

    in_flight_exit = testlang.get_in_flight_exit(spend_id)
    assert not in_flight_exit.input_piggybacked(0)


def test_challenge_in_flight_exit_input_spent_wrong_period_should_fail(testlang):
    owner_1, owner_2, amount = testlang.accounts[0], testlang.accounts[1], 100
    deposit_id = testlang.deposit(owner_1, amount)
    spend_id = testlang.spend_utxo([deposit_id], [owner_1.key])
    double_spend_id = testlang.spend_utxo([deposit_id], [owner_1.key], [(owner_1.address, 100)], force_invalid=True)
    testlang.start_in_flight_exit(spend_id)
    testlang.piggyback_in_flight_exit_input(spend_id, 0, owner_1.key)
    testlang.forward_to_period(1)

    with pytest.raises(TransactionFailed):
        testlang.challenge_in_flight_exit_input_spent(spend_id, double_spend_id, owner_2.key)


def test_challenge_in_flight_exit_input_spent_not_piggybacked_should_fail(testlang):
    owner_1, owner_2, amount = testlang.accounts[0], testlang.accounts[1], 100
    deposit_id = testlang.deposit(owner_1, amount)
    spend_id = testlang.spend_utxo([deposit_id], [owner_1.key])
    double_spend_id = testlang.spend_utxo([deposit_id], [owner_1.key], [(owner_1.address, 100)], force_invalid=True)
    testlang.start_in_flight_exit(spend_id)
    testlang.forward_to_period(2)

    with pytest.raises(TransactionFailed):
        testlang.challenge_in_flight_exit_input_spent(spend_id, double_spend_id, owner_2.key)


def test_challenge_in_flight_exit_input_spent_same_tx_should_fail(testlang):
    owner_1, owner_2, amount = testlang.accounts[0], testlang.accounts[1], 100
    deposit_id = testlang.deposit(owner_1, amount)
    spend_id = testlang.spend_utxo([deposit_id], [owner_1.key])
    testlang.start_in_flight_exit(spend_id)
    testlang.piggyback_in_flight_exit_input(spend_id, 0, owner_1.key)
    testlang.forward_to_period(2)

    with pytest.raises(TransactionFailed):
        testlang.challenge_in_flight_exit_input_spent(spend_id, spend_id, owner_2.key)


def test_challenge_in_flight_exit_input_spent_unrelated_tx_should_fail(testlang):
    owner_1, owner_2, amount = testlang.accounts[0], testlang.accounts[1], 100
    deposit_id_1 = testlang.deposit(owner_1, amount)
    deposit_id_2 = testlang.deposit(owner_1, amount)
    spend_id = testlang.spend_utxo([deposit_id_1], [owner_1.key])
    unrelated_spend_id = testlang.spend_utxo([deposit_id_2], [owner_1.key], [(owner_1.address, 100)])
    testlang.start_in_flight_exit(spend_id)
    testlang.piggyback_in_flight_exit_input(spend_id, 0, owner_1.key)
    testlang.forward_to_period(2)

    with pytest.raises(TransactionFailed):
        testlang.challenge_in_flight_exit_input_spent(spend_id, unrelated_spend_id, owner_2.key)


def test_challenge_in_flight_exit_input_spent_invalid_signature_should_fail(testlang):
    owner_1, owner_2, amount = testlang.accounts[0], testlang.accounts[1], 100
    deposit_id = testlang.deposit(owner_1, amount)
    spend_id = testlang.spend_utxo([deposit_id], [owner_1.key])
    double_spend_id = testlang.spend_utxo([deposit_id], [owner_2.key], [(owner_1.address, 100)], force_invalid=True)
    testlang.start_in_flight_exit(spend_id)
    testlang.piggyback_in_flight_exit_input(spend_id, 0, owner_1.key)
    testlang.forward_to_period(2)

    with pytest.raises(TransactionFailed):
        testlang.challenge_in_flight_exit_input_spent(spend_id, double_spend_id, owner_2.key)
