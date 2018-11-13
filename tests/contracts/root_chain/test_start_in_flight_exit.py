import pytest
from ethereum.tools.tester import TransactionFailed
from plasma_core.constants import NULL_ADDRESS, WEEK
from testlang.testlang import address_to_hex


@pytest.mark.parametrize("num_inputs", [1, 2, 3, 4])
def test_start_in_flight_exit_should_succeed(ethtester, testlang, num_inputs):
    amount = 100
    owners = []
    deposit_ids = []
    for i in range(0, num_inputs):
        owners.append(testlang.accounts[i])
        deposit_ids.append(testlang.deposit(owners[i], amount))

    owner_keys = [owner.key for owner in owners]
    spend_id = testlang.spend_utxo(deposit_ids, owner_keys)

    testlang.start_in_flight_exit(spend_id)

    # Exit was created
    in_flight_exit = testlang.get_in_flight_exit(spend_id)
    assert in_flight_exit.exit_start_timestamp == ethtester.chain.head_state.timestamp
    assert in_flight_exit.exit_map == 0
    assert in_flight_exit.bond_owner == owners[0].address
    assert in_flight_exit.oldest_competitor == 0

    # Inputs are correctly set
    for i in range(0, num_inputs):
        input_info = in_flight_exit.get_input(i)
        assert input_info.owner == owners[i].address
        assert input_info.amount == amount

    # Remaining inputs are still unset
    for i in range(num_inputs, 4):
        input_info = in_flight_exit.get_input(i)
        assert input_info.owner == address_to_hex(NULL_ADDRESS)
        assert input_info.amount == 0


def test_start_in_flight_exit_invalid_bond_should_fail(testlang):
    owner, amount = testlang.accounts[0], 100
    deposit_id = testlang.deposit(owner, amount)
    spend_id = testlang.spend_utxo([deposit_id], [owner.key])

    with pytest.raises(TransactionFailed):
        testlang.start_in_flight_exit(spend_id, bond=0)


def test_start_in_flight_exit_invalid_spend_should_fail(testlang):
    owner_1, owner_2, amount = testlang.accounts[0], testlang.accounts[1], 100
    deposit_id = testlang.deposit(owner_1, amount)
    spend_id = testlang.spend_utxo([deposit_id], [owner_2.key], force_invalid=True)

    with pytest.raises(TransactionFailed):
        testlang.start_in_flight_exit(spend_id)


def test_start_in_flight_exit_invalid_proof_should_fail(testlang):
    owner, amount = testlang.accounts[0], 100
    deposit_id = testlang.deposit(owner, amount)
    spend_id = testlang.spend_utxo([deposit_id], [owner.key])

    proofs = b''
    (encoded_spend, encoded_inputs, _, signatures) = testlang.get_in_flight_exit_info(spend_id)
    bond = testlang.root_chain.inFlightExitBond()

    with pytest.raises(TransactionFailed):
        testlang.root_chain.startInFlightExit(encoded_spend, encoded_inputs, proofs, signatures, value=bond)


def test_start_in_flight_exit_twice_should_fail(testlang):
    owner, amount = testlang.accounts[0], 100
    deposit_id = testlang.deposit(owner, amount)
    spend_id = testlang.spend_utxo([deposit_id], [owner.key])

    # First time should succeed
    testlang.start_in_flight_exit(spend_id)

    # Second time should fail
    with pytest.raises(TransactionFailed):
        testlang.start_in_flight_exit(spend_id)


def test_start_in_flight_exit_twice_different_piggybacks_should_succeed(testlang):
    owner, amount = testlang.accounts[0], 100
    deposit_id = testlang.deposit(owner, amount)
    spend_id = testlang.spend_utxo([deposit_id], [owner.key], [(owner.address, 50), (owner.address, 50)])

    # First time should succeed
    testlang.start_in_flight_exit(spend_id)
    testlang.piggyback_in_flight_exit_input(spend_id, 0, owner.key)
    testlang.forward_timestamp(2 * WEEK)
    testlang.process_exits()

    # Second time should also succeed
    testlang.start_in_flight_exit(spend_id)

    # Exit was created
    in_flight_exit = testlang.get_in_flight_exit(spend_id)
    assert in_flight_exit.exit_start_timestamp == testlang.ethtester.chain.head_state.timestamp
    assert in_flight_exit.exit_map == 2 ** 8
    assert in_flight_exit.bond_owner == owner.address
    assert in_flight_exit.oldest_competitor == 0


def test_start_in_flight_exit_invalid_outputs_should_fail(testlang):
    owner_1, owner_2, amount = testlang.accounts[0], testlang.accounts[1], 100
    deposit_id = testlang.deposit(owner_1, amount)

    # Create a transaction with outputs greater than inputs
    output = (owner_2.address, amount * 2)

    spend_id = testlang.spend_utxo([deposit_id], [owner_1.key], [output], force_invalid=True)

    with pytest.raises(TransactionFailed):
        testlang.start_in_flight_exit(spend_id)
