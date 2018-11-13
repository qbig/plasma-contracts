import rlp
from plasma_core.child_chain import ChildChain
from plasma_core.account import EthereumAccount
from plasma_core.block import Block
from plasma_core.transaction import Transaction, TransactionOutput, UnsignedTransaction
from plasma_core.constants import WEEK, NULL_SIGNATURE, NULL_ADDRESS
from plasma_core.utils.transactions import decode_utxo_id, encode_utxo_id
from plasma_core.utils.address import address_to_hex
from plasma_core.utils.merkle.fixed_merkle import FixedMerkle
import conftest


MIN_EXIT_PERIOD = 1 * WEEK
IN_FLIGHT_PERIOD = MIN_EXIT_PERIOD // 2


def get_accounts(ethtester):
    """Converts ethereum.tools.tester accounts into a list.

    Args:
        ethtester (ethereum.tools.tester): Ethereum tester instance.

    Returns:
        EthereumAccount[]: A list of EthereumAccounts.
    """

    accounts = []
    for i in range(10):
        address = getattr(ethtester, 'a{0}'.format(i))
        key = getattr(ethtester, 'k{0}'.format(i))
        accounts.append(EthereumAccount(address_to_hex(address), key))
    return accounts


class StandardExit(object):
    """Represents a Plasma exit.

    Attributes:
        owner (str): Address of the exit's owner.
        token (str): Address of the token being exited.
        amount (int): How much value is being exited.
    """

    def __init__(self, owner, amount):
        self.owner = owner
        self.amount = amount


class PlasmaBlock(object):
    """Represents a Plasma block.

    Attributes:
        root (str): Root hash of the block.
        timestamp (int): Time when the block was created.
    """

    def __init__(self, root, timestamp):
        self.root = root
        self.timestamp = timestamp


class InFlightExit(object):

    def __init__(self, root_chain, in_flight_tx, exit_start_timestamp, exit_map, bond_owner, oldest_competitor):
        self.root_chain = root_chain
        self.in_flight_tx = in_flight_tx
        self.exit_start_timestamp = exit_start_timestamp
        self.exit_map = exit_map
        self.bond_owner = bond_owner
        self.oldest_competitor = oldest_competitor
        self.inputs = {}
        self.outputs = {}

    @property
    def challenge_flag_set(self):
        return self.root_chain.flagSet(self.exit_start_timestamp)

    def get_input(self, index):
        input_info = self.inputs.get(index)
        if not input_info:
            input_info = TransactionOutput(*self.root_chain.getInFlightExitOutput(self.in_flight_tx.encoded, index))
            input_info.owner = address_to_hex(input_info.owner)
            self.inputs[index] = input_info
        return input_info

    def get_output(self, index):
        return self.get_input(index + 4)

    def input_piggybacked(self, index):
        return (self.exit_map >> index & 1) == 1

    def output_piggybacked(self, index):
        return self.input_piggybacked(index + 4)


class TestingLanguage(object):
    """Represents the testing language.

    Attributes:
        root_chain (ABIContract): Root chain contract instance.
        eththester (tester): Ethereum tester instance.
        accounts (EthereumAccount[]): List of available accounts.
        operator (EthereumAccount): The operator's account.
        child_chain (ChildChain): Child chain instance.
        confirmations (dict): A mapping from transaction IDs to confirmation signatures.
    """

    def __init__(self, root_chain, ethtester):
        self.root_chain = root_chain
        self.ethtester = ethtester
        self.accounts = get_accounts(ethtester)
        self.operator = self.accounts[0]
        self.child_chain = ChildChain(operator=self.operator.address)

    def submit_block(self, transactions, signer=None, force_invalid=False):
        signer = signer or self.operator
        blknum = self.root_chain.nextChildBlock()
        block = Block(transactions, number=blknum)
        block.sign(signer.key)
        self.root_chain.submitBlock(block.root, sender=signer.key)
        if force_invalid:
            self.child_chain.blocks[self.child_chain.next_child_block] = block
            self.child_chain.next_deposit_block = self.child_chain.next_child_block + 1
            self.child_chain.next_child_block += self.child_chain.child_block_interval
        else:
            assert self.child_chain.add_block(block)
        return blknum

    @property
    def timestamp(self):
        """Current chain timestamp"""
        return self.ethtester.chain.head_state.timestamp

    def deposit(self, owner, amount):
        deposit_tx = Transaction(outputs=[(owner.address, NULL_ADDRESS, amount)])
        blknum = self.root_chain.getDepositBlockNumber()
        self.root_chain.deposit(deposit_tx.encoded, value=amount)
        deposit_id = encode_utxo_id(blknum, 0, 0)
        block = Block([deposit_tx], number=blknum)
        self.child_chain.add_block(block)
        return deposit_id

    def deposit_token(self, owner, token, amount):
        """Mints, approves and deposits token for given owner and amount

        Args:
            owner (EthereumAccount): Account to own the deposit.
            token (Contract: ERC20, MintableToken): Token to be deposited.
            amount (int): Deposit amount.

        Returns:
            int: Unique identifier of the deposit.
        """

        deposit_tx = Transaction(outputs=[(owner.address, token.address, amount)])
        token.mint(owner.address, amount)
        self.ethtester.chain.mine()
        token.approve(self.root_chain.address, amount, sender=owner.key)
        self.ethtester.chain.mine()
        blknum = self.root_chain.getDepositBlockNumber()
        pre_balance = self.get_balance(self.root_chain, token)
        self.root_chain.depositFrom(deposit_tx.encoded, sender=owner.key)
        balance = self.get_balance(self.root_chain, token)
        assert balance == pre_balance + amount
        block = Block(transactions=[deposit_tx], number=blknum)
        self.child_chain.add_block(block)
        return encode_utxo_id(blknum, 0, 0)

    def spend_utxo(self, input_ids, keys, outputs=[], force_invalid=False):
        inputs = [decode_utxo_id(input_id) for input_id in input_ids]
        spend_tx = Transaction(inputs=inputs, outputs=outputs)
        for i in range(0, len(inputs)):
            spend_tx.sign(i, keys[i])
        blknum = self.submit_block([spend_tx], force_invalid=force_invalid)
        spend_id = encode_utxo_id(blknum, 0, 0)
        return spend_id

    def start_standard_exit(self, output_id, key, bond=None, sender=None):
        if sender is None:
            sender = key
        output_tx = self.child_chain.get_transaction(output_id)
        merkle = FixedMerkle(16, [output_tx.encoded])
        proof = merkle.create_membership_proof(output_tx.encoded)
        bond = bond if bond is not None else self.root_chain.standardExitBond()
        self.root_chain.startStandardExit(output_id, output_tx.encoded, proof, value=bond, sender=sender)

    def challenge_standard_exit(self, output_id, spend_id):
        spend_tx = self.child_chain.get_transaction(spend_id)
        input_index = None
        signature = NULL_SIGNATURE
        for i in range(0, 4):
            input_index = i
            signature = spend_tx.signatures[i]
            if (spend_tx.inputs[i].identifier == output_id and signature != NULL_SIGNATURE):
                break
        self.root_chain.challengeStandardExit(output_id, spend_tx.encoded, input_index, signature)

    def start_in_flight_exit(self, tx_id, bond=None):
        (encoded_spend, encoded_inputs, proofs, signatures) = self.get_in_flight_exit_info(tx_id)
        bond = bond if bond is not None else self.root_chain.inFlightExitBond()
        self.root_chain.startInFlightExit(encoded_spend, encoded_inputs, proofs, signatures, value=bond)

    def create_utxo(self, token=NULL_ADDRESS):
        class Utxo(object):
            def __init__(self, deposit_id, owner, token, amount, spend, spend_id):
                self.deposit_id = deposit_id
                self.owner = owner
                self.amount = amount
                self.token = token
                self.spend_id = spend_id
                self.spend = spend

        owner, amount = self.accounts[0], 100
        if token == NULL_ADDRESS:
            deposit_id = self.deposit(owner, amount)
            token_address = NULL_ADDRESS
        else:
            deposit_id = self.deposit_token(owner, token, amount)
            token_address = token.address
        spend_id = self.spend_utxo([deposit_id], [owner.key], [(owner.address, token_address, 100)])
        spend = self.child_chain.get_transaction(spend_id)
        return Utxo(deposit_id, owner, token_address, amount, spend, spend_id)

    def start_deposit_exit(self, owner, deposit_id, amount, token_addr=NULL_ADDRESS):
        """Starts an exit for a deposit.

        Args:
            owner (EthereumAccount): Account that owns this deposit.
            blknum (int): Deposit block number.
            amount (int): Deposit amount.
        """

        self.root_chain.startDepositExit(deposit_id, token_addr, amount, sender=owner.key)

    def start_fee_exit(self, operator, amount):
        """Starts a fee exit.

        Args:
            operator (EthereumAccount): Account to attempt the fee exit.
            amount (int): Amount to exit.

        Returns:
            int: Unique identifier of the exit.
        """

        fee_exit_id = self.root_chain.currentFeeExit()
        self.root_chain.startFeeExit(NULL_ADDRESS, amount, sender=operator.key)
        return fee_exit_id

    def finalize_exits(self, token, utxo_id, count, **kwargs):
        """Finalizes exits that have completed the exit period.

        Args:
            token (address): Address of the token to be processed.
            utxo_id (int): Identifier of the UTXO being exited.
            count (int): Maximum number of exits to be processed.
        """

        self.root_chain.processExits(token, utxo_id, count, **kwargs)

    def get_challenge_proof(self, utxo_id, spend_id):
        """Returns information required to submit a challenge.

        Args:
            utxo_id (int): Identifier of the UTXO being exited.
            spend_id (int): Identifier of the transaction that spent the UTXO.

        Returns:
            int, bytes, bytes, bytes: Information necessary to create a challenge proof.
        """

        spend_tx = self.child_chain.get_transaction(spend_id)
        inputs = [(spend_tx.blknum1, spend_tx.txindex1, spend_tx.oindex1), (spend_tx.blknum2, spend_tx.txindex2, spend_tx.oindex2)]
        try:
            input_index = inputs.index(decode_utxo_id(utxo_id))
        except ValueError:
            input_index = 0
        (blknum, _, _) = decode_utxo_id(spend_id)
        block = self.child_chain.blocks[blknum]
        proof = block.merklized_transaction_set.create_membership_proof(spend_tx.merkle_hash)
        sigs = spend_tx.sig1 + spend_tx.sig2
        return (input_index, spend_tx.encoded, proof, sigs)

    def get_plasma_block(self, blknum):
        """Queries a plasma block by its number.

        Args:
            blknum (int): Plasma block number to query.

        Returns:
            PlasmaBlock: Formatted plasma block information.
        """

        block_info = self.root_chain.blocks(blknum)
        return PlasmaBlock(*block_info)

    def get_standard_exit(self, exit_id):
        """Queries a plasma exit by its ID.

        Args:
            exit_id (int): Identifier of the exit to query.

        Returns:
            StandardExit: Formatted plasma exit information.
        """

        exit_info = self.root_chain.exits(exit_id)
        return StandardExit(*exit_info)

    def get_balance(self, account, token=NULL_ADDRESS):
        """Queries ETH or token balance of an account.

        Args:
            account (EthereumAccount): Account to query,
            token (str OR ABIContract OR NULL_ADDRESS):
                MintableToken contract: its address or ABIContract representation.

        Returns:
            int: The account's balance.
        """
        if token == NULL_ADDRESS:
            return self.ethtester.chain.head_state.get_balance(account.address)
        if hasattr(token, "balanceOf"):
            return token.balanceOf(account.address)
        else:
            token_contract = conftest.watch_contract(self.ethtester, 'MintableToken', token)
            return token_contract.balanceOf(account.address)

    def forward_timestamp(self, amount):
        """Forwards the chain's timestamp.

        Args:
            amount (int): Number of seconds to move forward time.
        """

        self.ethtester.chain.head_state.timestamp += amount

    def get_in_flight_exit_info(self, tx_id):
        spend_tx = self.child_chain.get_transaction(tx_id)
        input_txs = []
        proofs = b''
        signatures = b''
        for i in range(0, len(spend_tx.inputs)):
            tx_input = spend_tx.inputs[i]
            (blknum, _, _) = decode_utxo_id(tx_input.identifier)
            if (blknum == 0):
                continue
            input_tx = self.child_chain.get_transaction(tx_input.identifier)
            input_txs.append(input_tx)
            proofs += self.get_merkle_proof(tx_input.identifier)
            signatures += spend_tx.signatures[i]
        encoded_inputs = rlp.encode(input_txs, rlp.sedes.CountableList(UnsignedTransaction, 4))
        return (spend_tx.encoded, encoded_inputs, proofs, signatures)

    def get_merkle_proof(self, tx_id):
        tx = self.child_chain.get_transaction(tx_id)
        (blknum, _, _) = decode_utxo_id(tx_id)
        block = self.child_chain.get_block(blknum)
        merkle = block.merklized_transaction_set
        return merkle.create_membership_proof(tx.encoded)

    def piggyback_in_flight_exit_input(self, tx_id, input_index, key, bond=None):
        spend_tx = self.child_chain.get_transaction(tx_id)
        bond = bond if bond is not None else self.root_chain.piggybackBond()
        self.root_chain.piggybackInFlightExit(spend_tx.encoded, input_index, sender=key, value=bond)

    def piggyback_in_flight_exit_output(self, tx_id, output_index, key, bond=None):
        return self.piggyback_in_flight_exit_input(tx_id, output_index + 4, key, bond)

    def find_shared_input(self, tx_a, tx_b):
        tx_a_input_index = 0
        tx_b_input_index = 0
        for i in range(0, 4):
            for j in range(0, 4):
                tx_a_input = tx_a.inputs[i].identifier
                tx_b_input = tx_b.inputs[j].identifier
                if (tx_a_input == tx_b_input and tx_a_input != 0):
                    tx_a_input_index = i
                    tx_b_input_index = j
        return (tx_a_input_index, tx_b_input_index)

    def find_input_index(self, output_id, tx_b):
        tx_b_input_index = 0
        for i in range(0, 4):
            tx_b_input = tx_b.inputs[i].identifier
            if tx_b_input == output_id:
                tx_b_input_index = i
        return tx_b_input_index

    def challenge_in_flight_exit_not_canonical(self, in_flight_tx_id, competing_tx_id, key):
        in_flight_tx = self.child_chain.get_transaction(in_flight_tx_id)
        competing_tx = self.child_chain.get_transaction(competing_tx_id)
        (in_flight_tx_input_index, competing_tx_input_index) = self.find_shared_input(in_flight_tx, competing_tx)
        proof = self.get_merkle_proof(competing_tx_id)
        signature = competing_tx.signatures[competing_tx_input_index]
        self.root_chain.challengeInFlightExitNotCanonical(in_flight_tx.encoded, in_flight_tx_input_index, competing_tx.encoded, competing_tx_input_index, competing_tx_id, proof, signature, sender=key)

    def respond_to_non_canonical_challenge(self, in_flight_tx_id, key):
        in_flight_tx = self.child_chain.get_transaction(in_flight_tx_id)
        proof = self.get_merkle_proof(in_flight_tx_id)
        self.root_chain.respondToNonCanonicalChallenge(in_flight_tx.encoded, in_flight_tx_id, proof)

    def forward_to_period(self, period):
        self.forward_timestamp((period - 1) * IN_FLIGHT_PERIOD)

    def challenge_in_flight_exit_input_spent(self, in_flight_tx_id, spend_tx_id, key):
        in_flight_tx = self.child_chain.get_transaction(in_flight_tx_id)
        spend_tx = self.child_chain.get_transaction(spend_tx_id)
        (in_flight_tx_input_index, spend_tx_input_index) = self.find_shared_input(in_flight_tx, spend_tx)
        signature = spend_tx.signatures[spend_tx_input_index]
        self.root_chain.challengeInFlightExitInputSpent(in_flight_tx.encoded, in_flight_tx_input_index, spend_tx.encoded, spend_tx_input_index, signature, sender=key)

    def challenge_in_flight_exit_output_spent(self, in_flight_tx_id, spending_tx_id, output_index, key):
        in_flight_tx = self.child_chain.get_transaction(in_flight_tx_id)
        spending_tx = self.child_chain.get_transaction(spending_tx_id)
        in_flight_tx_output_id = in_flight_tx_id + output_index
        spending_tx_input_index = self.find_input_index(in_flight_tx_output_id, spending_tx)
        in_flight_tx_inclusion_proof = self.get_merkle_proof(in_flight_tx_id)
        spending_tx_sig = spending_tx.signatures[spending_tx_input_index]
        self.root_chain.challengeInFlightExitOutputSpent(in_flight_tx.encoded, in_flight_tx_output_id, in_flight_tx_inclusion_proof, spending_tx.encoded, spending_tx_input_index, spending_tx_sig, sender=key)

    def process_exits(self):
        self.root_chain.processExits()

    def get_in_flight_exit(self, in_flight_tx_id):
        in_flight_tx = self.child_chain.get_transaction(in_flight_tx_id)
        unique_id = self.root_chain.getUniqueId(in_flight_tx.encoded)
        exit_info = self.root_chain.inFlightExits(unique_id)
        return InFlightExit(self.root_chain, in_flight_tx, *exit_info)
