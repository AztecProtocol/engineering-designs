import marimo

__generated_with = "0.19.4"
app = marimo.App(width="medium", app_title="Fee Model")


@app.cell
def _():
    from ape import networks
    import matplotlib.pyplot as plt
    import math

    from typing import List, Optional, ClassVar
    import random
    import numpy as np
    import pickle
    import os

    import json

    from pydantic import StrictInt, field_validator, Field
    from pydantic.dataclasses import dataclass
    from dataclasses import fields
    from copy import deepcopy
    import marimo as mo

    return (
        Field,
        List,
        Optional,
        StrictInt,
        dataclass,
        deepcopy,
        field_validator,
        fields,
        json,
        math,
        mo,
        networks,
        os,
        pickle,
        plt,
        random,
    )


@app.cell
def _(deepcopy, fields):
    def json_serializable(cls):
        """Decorator to make a dataclass JSON serializable and copyable."""

        def copy(self):
            return deepcopy(self)

        cls.copy = copy

        def to_dict(self):
            def convert_value(obj):
                if hasattr(obj, "to_dict"):
                    return obj.to_dict()
                elif isinstance(obj, (list, tuple)):
                    return [convert_value(x) for x in obj]
                elif isinstance(obj, dict):
                    return {k: convert_value(v) for k, v in obj.items()}
                return obj

            # Convert each field using our custom converter and sort keys
            return dict(
                sorted(
                    (field.name, convert_value(getattr(self, field.name)))
                    for field in fields(self)
                )
            )

        cls.to_dict = to_dict
        return cls

    return (json_serializable,)


@app.cell
def _(StrictInt, dataclass, field_validator):
    def bounded_int(min_value: int, max_value: int):
        """
        Decorator for creating bounded integer types with validation
        Inclusive of min_value, exclusive of max_value
        """

        def decorator(cls):
            @dataclass
            class BoundedInt:
                value: StrictInt

                @field_validator("value")
                def check_range(cls, v):
                    if not (min_value <= v < max_value):
                        raise ValueError(
                            f"Value don't satisfy {min_value} <= {v} <= {max_value}"
                        )
                    return v

                def to_dict(self) -> int:
                    # Custom serialization to return just the integer value
                    return self.value

                def __eq__(self, other):
                    if isinstance(other, BoundedInt):
                        return self.value == other.value
                    return False

                def __ne__(self, other):
                    return not self.__eq__(other)

                def __gt__(self, other):
                    return self.value > other.value

                def __ge__(self, other):
                    return self.value >= other.value

                def __lt__(self, other):
                    return self.value < other.value

                def __le__(self, other):
                    return self.value <= other.value

                def __abs__(self):
                    return BoundedInt(value=abs(self.value))

                def __neg__(self):
                    return BoundedInt(value=-self.value)

                def __add__(self, other):
                    if isinstance(other, BoundedInt):
                        result = self.value + other.value
                        if result > max_value:
                            raise OverflowError("Integer overflow")
                        return BoundedInt(value=result)
                    else:
                        raise TypeError(
                            f"Unsupported operand type for +: '{cls.__name__}' and '{type(other)}'"
                        )

                def __sub__(self, other):
                    if isinstance(other, BoundedInt):
                        result = self.value - other.value
                        if result < min_value:
                            raise ValueError("Integer underflow")
                        return BoundedInt(value=result)
                    else:
                        raise TypeError(
                            f"Unsupported operand type for -: '{cls.__name__}' and '{type(other)}'"
                        )

                def __mul__(self, other):
                    if isinstance(other, BoundedInt):
                        result = self.value * other.value
                        if result > max_value:
                            raise OverflowError("Integer overflow")
                        return BoundedInt(value=result)
                    else:
                        raise TypeError(
                            f"Unsupported operand type for *: '{cls.__name__}' and '{type(other)}'"
                        )

                def __truediv__(self, other):
                    if isinstance(other, BoundedInt):
                        if other.value == 0:
                            raise ZeroDivisionError("Division by zero")
                        return BoundedInt(value=self.value // other.value)
                    else:
                        raise TypeError(
                            f"Unsupported operand type for /: '{cls.__name__}' and '{type(other)}'"
                        )

                def mul_div(self, other, denominator, round_up=False):
                    temp = self.value * other.value
                    result = temp // denominator.value
                    if round_up and temp % denominator.value != 0:
                        result += 1
                    return BoundedInt(value=result)

            # Copy the class name and update annotations
            BoundedInt.__name__ = cls.__name__
            BoundedInt.__qualname__ = cls.__qualname__
            return BoundedInt

        return decorator

    @bounded_int(min_value=0, max_value=2**256 - 1)
    class Uint256:
        pass

    @bounded_int(min_value=-(2**255), max_value=2**255 - 1)
    class Int256:
        pass

    return Int256, Uint256


@app.cell
def _(Uint256):
    MIN_BASE_FEE_PER_BLOB_GAS = Uint256(1)
    BLOB_BASE_FEE_UPDATE_FRACTION = Uint256(3338477)
    BLOB_SIZE_IN_FIELDS = Uint256(4096)
    GAS_PER_BLOB = Uint256(2**17)

    def fake_exponential(
        factor: Uint256, numerator: Uint256, denominator: Uint256
    ) -> Uint256:
        """
        An approximation of the exponential function: factor * e ** (numerator / denominator)
        Approximated using a taylor series.
        For shorthand below, let `a = factor`, `x = numerator`, `d = denominator`

        f(x) =  a
             + (a * x) / d
             + (a * x ** 2) / (2 * d ** 2)
             + (a * x ** 3) / (6 * d ** 3)
             + (a * x ** 4) / (24 * d ** 4)
             + (a * x ** 5) / (120 * d ** 5)
             + ...

        For integer precision purposes, we will multiply by the denominator for intermediary steps and then finally do a division by it.
        The notation below might look slightly strange, but it is to try to convey the program flow below.

        e(x) = (       a * d
             +         a * d * x / d
             +       ((a * d * x / d) * x) / (2 * d)
             +     ((((a * d * x / d) * x) / (2 * d)) * x) / (3 * d)
             +   ((((((a * d * x / d) * x) / (2 * d)) * x) / (3 * d)) * x) / (4 * d)
             + ((((((((a * d * x / d) * x) / (2 * d)) * x) / (3 * d)) * x) / (4 * d)) * x) / (5 * d)
             + ...
               ) / d

        While the notation might make it a bit of a pain to look at. f(x) and e(x) are the same, gotta lover integer math.
        """
        i = Uint256(1)
        output = Uint256(0)
        numerator_accum = factor * denominator
        while numerator_accum > Uint256(0):
            output += numerator_accum
            numerator_accum = (numerator_accum * numerator) / (denominator * i)
            i += Uint256(1)
        return output / denominator

    # Small check to see if the fake exponential is working as intended
    a = Uint256(5415357955)
    b = Uint256(2611772262)
    c = Uint256(100000000000)
    d = fake_exponential(a, b, c)
    e = Uint256(5558657961)
    assert d == e, f"Expected {d} to be {e}"
    return (
        BLOB_BASE_FEE_UPDATE_FRACTION,
        MIN_BASE_FEE_PER_BLOB_GAS,
        fake_exponential,
    )


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # Collecting data

    In the following section we will be collecting data from an Etheruem node. If it is the same range as we last collected we will simply load it from a pickle file.

    Note that we only keep track of minimal information related to the L1 block.
    """)
    return


@app.cell
def _(
    BLOB_BASE_FEE_UPDATE_FRACTION,
    MIN_BASE_FEE_PER_BLOB_GAS,
    Uint256,
    dataclass,
    fake_exponential,
    json_serializable,
    mo,
    networks,
    os,
    pickle,
):
    @json_serializable
    @dataclass
    class L1BlockSub:
        number: Uint256
        timestamp: Uint256
        blob_fee: Uint256
        base_fee: Uint256
        excess_blob_gas: Uint256

    def get_l1_block_sub(block_number: int) -> L1BlockSub:
        block = networks.provider.web3.eth.get_block(block_number)
        blob_fee = fake_exponential(
            MIN_BASE_FEE_PER_BLOB_GAS,
            Uint256(block.excessBlobGas),
            BLOB_BASE_FEE_UPDATE_FRACTION,
        )
        return L1BlockSub(
            number=Uint256(block.number),
            blob_fee=blob_fee,
            base_fee=Uint256(block.baseFeePerGas),
            excess_blob_gas=Uint256(block.excessBlobGas),
            timestamp=Uint256(block.timestamp),
        )

    @mo.cache
    def get_blocks(start_number: int, number_of_blocks: int):
        if os.path.exists("blocks.pkl"):
            with open("blocks.pkl", "rb") as f:
                candidated_blocks = pickle.load(f)
                if (
                    candidated_blocks[0].number.value == start_number
                    and candidated_blocks[-1].number.value
                    == start_number + number_of_blocks
                ):
                    return candidated_blocks
        networks.parse_network_choice("ethereum:mainnet:node").__enter__()
        blocks = [
            get_l1_block_sub(i)
            for i in range(start_number, start_number + number_of_blocks + 1)
        ]
        with open("blocks.pkl", "wb") as f:
            pickle.dump(blocks, f)
        return blocks

    # You should not change these unless you have access to the endpoint in the `ape-config.yaml` file.
    # This is because we are using the `ape` library to fetch the data from the Ethereum node, or just
    # fetching the data from a pickle file otherwise if we already have it.

    block_start_number = 20973664 - 500
    blocks_to_pull = 2000

    blocks = get_blocks(block_start_number, blocks_to_pull)
    return (blocks,)


@app.cell
def _(blocks, plt):
    block_numbers = [b.number.value for b in blocks]
    plt.figure(figsize=(12, 6))
    plt.plot(
        block_numbers,
        [b.blob_fee.value for b in blocks],
        label="Blob Gas Price (wei)",
    )
    plt.plot(block_numbers, [b.base_fee.value for b in blocks], label="Base Fee (wei)")
    plt.xlabel("Block Number")
    plt.ylabel("Fee (wei)")
    plt.title("Blob Gas Price and Base Fee over Recent Blocks")
    plt.legend()
    plt.grid(True)
    return (block_numbers,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # Model

    We want a model where the `mana` that a transaction requires is **constant** and independent of the l1 cost, but with the base fee fluctuating.
    This is slightly different from the previously specified model, where the `mana` amount itself could also fluctuate, but it is simpler for the users if we have a fixed amount.
    Also it will avoid landing in an issue where your tx is now out of gas because the l1 cost increased.
    """)
    return


@app.cell
def _(
    Field,
    Int256,
    List,
    Optional,
    Uint256,
    dataclass,
    fake_exponential,
    json_serializable,
    math,
):
    @dataclass
    class Tx:
        mana_spent: Uint256

        nullifiers: Uint256 = Field(default_factory=lambda: Uint256(1))
        notes: Uint256 = Field(default_factory=lambda: Uint256(0))
        public_state_diffs: Uint256 = Field(
            default_factory=lambda: Uint256(1 + 2 + 2 + 2)
        )
        encrypted_logs_size: Uint256 = Field(default_factory=lambda: Uint256(256))

        def size_in_bytes(self) -> Uint256:
            return (
                Uint256(32) * self.nullifiers
                + Uint256(64) * self.public_state_diffs
                + self.notes * (Uint256(32) + self.encrypted_logs_size)
            )

        def size_in_fields(self) -> Uint256:
            return Uint256(math.ceil(self.size_in_bytes().value / 32))

    @json_serializable
    @dataclass
    class BlockHeader:
        l1_block_number: Uint256
        block_number: Uint256
        slot_number: Uint256
        timestamp: Uint256
        mana_spent: Uint256
        blobs_needed: Uint256
        size_in_fields: Uint256

    @dataclass
    class Block:
        l1_block_number: Uint256
        block_number: Uint256
        slot_number: Uint256
        timestamp: Uint256
        txs: list[Tx]

        def size_in_fields(self) -> Uint256:
            return sum((tx.size_in_fields() for tx in self.txs), start=Uint256(0))

        def mana_spent(self) -> Uint256:
            return sum((tx.mana_spent for tx in self.txs), start=Uint256(0))

        def blobs_needed(self) -> Uint256:
            # Note that we cast this slightly different as we want the ceiling of the division
            return Uint256(math.ceil(self.size_in_fields().value / 4096))

        def compute_header(self) -> BlockHeader:
            return BlockHeader(
                l1_block_number=self.l1_block_number,
                block_number=self.block_number,
                slot_number=self.slot_number,
                timestamp=self.timestamp,
                mana_spent=self.mana_spent(),
                blobs_needed=self.blobs_needed(),
                size_in_fields=self.size_in_fields(),
            )

    @json_serializable
    @dataclass
    class L1Fees:
        blob_fee: Uint256
        base_fee: Uint256

    @json_serializable
    @dataclass
    class L1GasOracle:
        LIFETIME = Uint256(5)
        LATENCY = Uint256(2)

        pre: L1Fees
        post: L1Fees
        slot_of_change: Uint256

        def value_at(self, slot_number: Uint256) -> L1Fees:
            if slot_number < self.slot_of_change:
                return self.pre
            return self.post

        def queue_change(self, slot_number: Uint256, fees: L1Fees):
            # If the value have been active `self.LIFETIME - self.LATENCY` we can queue the next
            if slot_number >= self.slot_of_change + (self.LIFETIME - self.LATENCY):
                self.pre = self.post
                self.post = fees
                # This value should at the earliest be equal to the slot_of_change + LIFETIME.
                assert slot_number + self.LATENCY <= self.slot_of_change + self.LIFETIME
                self.slot_of_change = slot_number + self.LATENCY

    # New fee asset pricing constants
    ETH_PER_FEE_ASSET_PRECISION = Uint256(int(1e12))
    MIN_ETH_PER_FEE_ASSET = Uint256(
        100
    )  # 1e-10 ETH/AZTEC (avoids rounding issues with 1% changes)
    MAX_ETH_PER_FEE_ASSET = Uint256(int(1e11))  # 0.1 ETH/AZTEC
    MAX_FEE_ASSET_PRICE_MODIFIER_BPS = Int256(100)  # ±1% max change per checkpoint
    INITIAL_ETH_PER_FEE_ASSET = Uint256(
        int(1e7)
    )  # 1e-5 ETH/AZTEC (~$0.03 at $3000 ETH)

    @json_serializable
    @dataclass
    class FeeHeader:
        excess_mana: Uint256 = Field(default_factory=lambda: Uint256(0))
        mana_used: Uint256 = Field(default_factory=lambda: Uint256(0))
        eth_per_fee_asset: Uint256 = Field(
            default_factory=lambda: INITIAL_ETH_PER_FEE_ASSET
        )

    @json_serializable
    @dataclass
    class ManaBaseFeeComponents:
        sequencer_cost: Uint256
        prover_cost: Uint256
        congestion_cost: Uint256
        congestion_multiplier: Uint256

    @json_serializable
    @dataclass
    class OracleInput:
        fee_asset_price_modifier: Int256

    @dataclass
    class FeeModel:
        """
        The fee model here will not be perfect, it does not take into account for example that there might be slots with no txs, in reality
        it should be possible for the model, to take this into account mainly impact the `calc_excess_mana` function.
        """

        AZTEC_SLOT_DURATION = Uint256(36)
        AZTEC_EPOCH_DURATION = Uint256(32)
        CONGESTION_MULTIPLIER_DIVISOR = Uint256(int(1e9))
        GAS_PER_BLOB = Uint256(2**17)

        mana_target: Uint256
        l1_gas_per_block_proposed: Uint256
        l1_gas_per_epoch_verified: Uint256
        proving_cost_per_mana: Uint256

        genesis_timestamp: Uint256

        # Below is mutable
        current_timestamp: Uint256
        l1_gas_oracle: L1GasOracle
        fee_headers: List[FeeHeader] = Field(default_factory=lambda: [FeeHeader()])

        def set_timestamp(self, timestamp: Uint256):
            self.current_timestamp = timestamp

        def current_slot_number(self) -> Uint256:
            return (
                self.current_timestamp - self.genesis_timestamp
            ) / FeeModel.AZTEC_SLOT_DURATION

        def photograph(self, l1_fees: L1Fees):
            self.l1_gas_oracle.queue_change(self.current_slot_number(), l1_fees)

        def current_l1_fees(self) -> L1Fees:
            return self.l1_gas_oracle.value_at(self.current_slot_number())

        def fee_update_fraction(self) -> Uint256:
            """
            A bit of magic for the fake exponential and integer math. Computing the divisor this way should ensure
            that the multiplier will increase by at most a factor of ~ 1.125 every block.
            """
            return Uint256((self.mana_target.value * 854_700_854) // 100_000_000)

        def compute_sequencer_costs(
            self, block: Optional[Block], real=False
        ) -> Uint256:
            l1_fees = self.current_l1_fees()

            l1_gas = self.l1_gas_per_block_proposed
            execution = l1_gas * l1_fees.base_fee

            blob_gas = (
                (block.blobs_needed() if block else Uint256(3)) * FeeModel.GAS_PER_BLOB
                if real
                else (
                    block.size_in_fields() * Uint256(32)
                    if block
                    else Uint256(3) * FeeModel.GAS_PER_BLOB
                )
            )
            data = blob_gas * l1_fees.blob_fee

            return (execution + data).mul_div(
                Uint256(1), self.mana_target, round_up=True
            )

        def compute_prover_costs(self):
            l1_fees = self.current_l1_fees()
            l1_gas = self.l1_gas_per_epoch_verified
            execution = l1_gas.mul_div(
                l1_fees.base_fee, FeeModel.AZTEC_EPOCH_DURATION, round_up=True
            ).mul_div(Uint256(1), self.mana_target, round_up=True)

            return execution + self.proving_cost_per_mana

        def eth_per_fee_asset(self) -> Uint256:
            """
            Returns the ETH per fee asset price with 1e12 precision.
            Higher value = more expensive fee asset (more ETH needed per unit of fee asset).
            Example: 1e7 means 1e-5 ETH per fee asset (~$0.03 at $3000 ETH).
            """
            return self.fee_headers[-1].eth_per_fee_asset

        def mana_base_fee_components(
            self, block: Optional[Block], in_fee_asset: bool = False
        ) -> ManaBaseFeeComponents:
            sequencer_cost = self.compute_sequencer_costs(block, real=True)
            prover_cost = self.compute_prover_costs()

            congestion_multiplier = fake_exponential(
                Uint256(int(1e9)),
                self.calc_excess_mana(),
                self.fee_update_fraction(),
            )

            total = sequencer_cost + prover_cost

            congestion_cost = (
                total * congestion_multiplier / FeeModel.CONGESTION_MULTIPLIER_DIVISOR
            ) - total

            if in_fee_asset:
                # Convert from wei (ETH) to fee asset using ETH/AZTEC ratio
                # fee_asset = wei * ETH_PER_FEE_ASSET_PRECISION / eth_per_fee_asset
                # We round up to ensure the fee is always enough
                eth_price = self.eth_per_fee_asset()
                return ManaBaseFeeComponents(
                    sequencer_cost=sequencer_cost.mul_div(
                        ETH_PER_FEE_ASSET_PRECISION, eth_price, round_up=True
                    ),
                    prover_cost=prover_cost.mul_div(
                        ETH_PER_FEE_ASSET_PRECISION, eth_price, round_up=True
                    ),
                    congestion_cost=congestion_cost.mul_div(
                        ETH_PER_FEE_ASSET_PRECISION, eth_price, round_up=True
                    ),
                    congestion_multiplier=congestion_multiplier,
                )
            else:
                # Return costs in wei (no conversion needed)
                return ManaBaseFeeComponents(
                    sequencer_cost=sequencer_cost,
                    prover_cost=prover_cost,
                    congestion_cost=congestion_cost,
                    congestion_multiplier=congestion_multiplier,
                )

        def mana_base_fee(
            self,
            block: Optional[Block],
            apply_congestion_multiplier=False,
            in_fee_asset: bool = False,
        ) -> Uint256:
            """
            Return the base fee of mana in wei.
            We assume that there is a minimum amount of mana spent per block, to the sequencer to manipulate the fee completely.
            """
            components = self.mana_base_fee_components(block, in_fee_asset)

            if apply_congestion_multiplier:
                return (
                    components.sequencer_cost
                    + components.prover_cost
                    + components.congestion_cost
                )
            return components.sequencer_cost + components.prover_cost

        def calc_excess_mana(self) -> Uint256:
            """
            Calculate the excess mana in the last block.
            Should be updated to take into account that there might be slots with no txs.
            """
            spent = self.fee_headers[-1].mana_used
            excess = self.fee_headers[-1].excess_mana
            if excess + spent < self.mana_target:
                return Uint256(0)
            return excess + spent - self.mana_target

        def add_slot(
            self, block: Optional[Block], oracle_input: Optional[OracleInput] = None
        ):
            """
            Potentially add a block for a slot, if there is one.
            """
            assert block is None or block.slot_number == self.current_slot_number(), (
                f"invalid slot number {block.slot_number} != {self.current_slot_number()}"
            )

            assert block is None or block.mana_spent() <= self.mana_target * Uint256(
                2
            ), "invalid block size"

            # fee_asset_price_modifier is now in basis points (-100 to +100, representing -1% to +1%)
            modifier_bps = (
                oracle_input.fee_asset_price_modifier if oracle_input else Int256(0)
            )
            assert modifier_bps is None or (
                abs(modifier_bps) <= MAX_FEE_ASSET_PRICE_MODIFIER_BPS
            ), "invalid fee asset price modifier (must be within ±100 bps)"

            parent_fee_header = self.fee_headers[-1]

            # Apply percentage modifier and clamp: new_price = current_price * (10000 + modifier_bps) / 10000
            new_price = Uint256(
                max(
                    MIN_ETH_PER_FEE_ASSET.value,
                    min(
                        parent_fee_header.eth_per_fee_asset.mul_div(
                            Uint256(10000 + modifier_bps.value), Uint256(10000)
                        ).value,
                        MAX_ETH_PER_FEE_ASSET.value,
                    ),
                )
            )

            new_header = FeeHeader(
                excess_mana=self.calc_excess_mana(),
                mana_used=block.mana_spent() if block else Uint256(0),
                eth_per_fee_asset=new_price,
            )
            self.fee_headers.append(new_header)

    return (
        Block,
        BlockHeader,
        INITIAL_ETH_PER_FEE_ASSET,
        ETH_PER_FEE_ASSET_PRECISION,
        FeeHeader,
        FeeModel,
        L1Fees,
        L1GasOracle,
        MAX_ETH_PER_FEE_ASSET,
        MAX_FEE_ASSET_PRICE_MODIFIER_BPS,
        MIN_ETH_PER_FEE_ASSET,
        ManaBaseFeeComponents,
        OracleInput,
        Tx,
    )


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Simulating some blocks

    In the following, we will be simulating a bunch of blocks and then plotting our results.

    For the simulation of a block, we will be generating a random block, with mana spent being a random number between 0 and 2 \* mana_target.
    We will keep collecting transactions from a "randomized" mempool until we have either reached the mana target, or the mempool size limit.
    We only collect transactions find the fee acceptable (another sampling) and don't force us beyond the limit.
    The size of the transactions are also drawn from a distribution.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    > This is probably the place where it would make good sense to get someone that know thier stuff in.
    > We have a setup that could work, but at the same time, it does not seem to work perfectly well.
    """)
    return


@app.cell
def _(Uint256):
    USD_PER_ETH = 2638
    USD_PER_WEI = USD_PER_ETH / 1e18
    MANA_PER_BASE_TX = Uint256(21000)
    USD_PER_BASE_TX = 0.01  # 0.3 is the real value, this is me messing around # a value kinda pulled out the ass as of now, expecting big reductions

    USD_PER_MANA = USD_PER_BASE_TX / MANA_PER_BASE_TX.value

    WEI_PER_MANA = USD_PER_MANA / USD_PER_WEI

    print(f"WEI PER MANA: {WEI_PER_MANA:.2f}")
    print(f"GWEI PER MANA / 1e9: {WEI_PER_MANA / 1e9:.2f} gwei")

    print(f"The cost: {2638 * MANA_PER_BASE_TX.value * WEI_PER_MANA / 1e18:.2f} USD")
    return MANA_PER_BASE_TX, WEI_PER_MANA


@app.cell
def _(
    BlockHeader,
    FeeHeader,
    L1Fees,
    L1GasOracle,
    ManaBaseFeeComponents,
    OracleInput,
    Uint256,
    dataclass,
    json_serializable,
):
    @json_serializable
    @dataclass
    class TestPointOutputs:
        eth_per_fee_asset_at_execution: (
            Uint256  # Price used for this checkpoint's fee calculation
        )
        mana_base_fee_components_in_wei: ManaBaseFeeComponents
        mana_base_fee_components_in_fee_asset: ManaBaseFeeComponents
        l1_fee_oracle_output: L1Fees  # value_at(now)
        l1_gas_oracle_values: L1GasOracle

    @json_serializable
    @dataclass
    class TestPoint:
        block_header: BlockHeader
        parent_fee_header: FeeHeader
        fee_header: FeeHeader
        oracle_input: OracleInput
        outputs: TestPointOutputs

    return TestPoint, TestPointOutputs


@app.cell
def _(
    Block,
    FeeModel,
    Int256,
    L1Fees,
    L1GasOracle,
    MANA_PER_BASE_TX,
    OracleInput,
    TestPoint,
    TestPointOutputs,
    Tx,
    Uint256,
    WEI_PER_MANA,
    blocks,
    random,
):
    fee_model = FeeModel(
        mana_target=Uint256(int(75_000_000)),
        l1_gas_per_block_proposed=Uint256(int(300_000)),
        l1_gas_per_epoch_verified=Uint256(int(3_600_000)),
        proving_cost_per_mana=Uint256(int(WEI_PER_MANA)),
        l1_gas_oracle=L1GasOracle(
            pre=L1Fees(blob_fee=Uint256(1), base_fee=Uint256(int(1e9))),
            post=L1Fees(
                blob_fee=blocks[0].blob_fee,
                base_fee=blocks[0].base_fee,
            ),
            slot_of_change=L1GasOracle.LIFETIME,
        ),
        genesis_timestamp=blocks[0].timestamp - FeeModel.AZTEC_SLOT_DURATION,
        current_timestamp=blocks[0].timestamp,
    )

    def generate_random_with_min(
        mean: Uint256, std_dev: Uint256, min_value: Uint256
    ) -> Uint256:
        while True:
            value = int(random.gauss(mean.value, std_dev.value))
            if value >= min_value.value:
                return Uint256(value)

    MEMPOOL_SIZE = 5000

    l2_blocks = []
    test_points = []

    last_slot = Uint256(0)

    for l1_block in blocks:
        fee_model.set_timestamp(l1_block.timestamp)
        # We try to photograph the l1 fees at every l1 block
        fee_model.photograph(
            L1Fees(blob_fee=l1_block.blob_fee, base_fee=l1_block.base_fee)
        )

        slot_number = fee_model.current_slot_number()

        # We are in the next slot, let us create a block!
        if slot_number > last_slot:
            last_slot = slot_number

            cost = fee_model.mana_base_fee_components(None)
            cost_in_fee_asset = fee_model.mana_base_fee_components(
                None, in_fee_asset=True
            )

            real_cost = cost.sequencer_cost + cost.prover_cost
            mana_base_fee = real_cost + cost.congestion_cost

            mana_spent_block = Uint256(0)
            mana_planned_for_block = min(
                generate_random_with_min(
                    fee_model.mana_target,
                    fee_model.mana_target,
                    Uint256(0),
                ),
                fee_model.mana_target * Uint256(2),
            )

            txs = []
            count = 0

            while (
                abs(mana_planned_for_block.value - mana_spent_block.value)
                >= MANA_PER_BASE_TX.value
                and count < MEMPOOL_SIZE
            ):
                count += 1
                mana_spent_tx = generate_random_with_min(
                    MANA_PER_BASE_TX * Uint256(2),
                    Uint256(500_000),
                    MANA_PER_BASE_TX,
                )
                within_bounds = (
                    mana_spent_tx + mana_spent_block
                    <= fee_model.mana_target * Uint256(2)
                )
                acceptable_mana_base_fee = generate_random_with_min(
                    real_cost, Uint256(2) * real_cost, Uint256(0)
                )

                is_fee_acceptable = acceptable_mana_base_fee >= mana_base_fee

                if within_bounds and is_fee_acceptable:
                    txs.append(Tx(mana_spent=mana_spent_tx))
                    mana_spent_block += mana_spent_tx

            block = Block(
                l1_block_number=l1_block.number,
                timestamp=l1_block.timestamp,
                slot_number=slot_number,
                block_number=Uint256(len(l2_blocks) + 1),
                txs=txs,
            )

            # Deciding oracle movements. Modifier is in basis points (-100 to +100, representing -1% to +1%)
            # Using a Gaussian distribution centered slightly above 0 to simulate typical price movement
            oracle_input = OracleInput(
                fee_asset_price_modifier=Int256(
                    int(max(-100, min(100, random.gauss(1, 50))))
                ),
            )

            eth_per_fee_asset_at_execution = fee_model.eth_per_fee_asset()
            fee_model.add_slot(block, oracle_input)

            test_points.append(
                TestPoint(
                    block_header=block.compute_header(),
                    fee_header=fee_model.fee_headers[-1],
                    parent_fee_header=fee_model.fee_headers[-2],
                    oracle_input=oracle_input,
                    outputs=TestPointOutputs(
                        eth_per_fee_asset_at_execution=eth_per_fee_asset_at_execution,
                        mana_base_fee_components_in_wei=cost,
                        mana_base_fee_components_in_fee_asset=cost_in_fee_asset,
                        l1_fee_oracle_output=fee_model.current_l1_fees(),
                        l1_gas_oracle_values=fee_model.l1_gas_oracle.copy(),
                    ),
                )
            )

            l2_blocks.append(block)
    return fee_model, l2_blocks, test_points


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### Plotting the results
    """)
    return


@app.cell
def _(block_numbers, blocks, l2_blocks, plt, test_points):
    def create_plots():
        fig, (ax1, ax2, ax3, ax4, ax5, ax6) = plt.subplots(
            6, 1, figsize=(12, 14), sharex=True
        )

        # For this, if we took our oracle, that would probably also be pretty cool he.

        aztec_l1_block_numbers = [
            l2_block.l1_block_number.value for l2_block in l2_blocks
        ]

        act = ax1
        act.plot(
            block_numbers,
            [l1_block.base_fee.value for l1_block in blocks],
            label="L1 BaseFee (wei)",
        )
        act.plot(
            aztec_l1_block_numbers,
            [x.outputs.l1_fee_oracle_output.base_fee.value for x in test_points],
            label="L1 BaseFee Oracle (wei)",
        )
        act.set_ylabel("Gas BaseFee (wei)")
        act.set_title("Gas base fees over Recent Blocks")
        act.legend()
        act.grid(True)

        # I need to load the different components of the cost from my test points

        costs = [x.outputs.mana_base_fee_components_in_wei for x in test_points]
        costs_fee_asset = [
            x.outputs.mana_base_fee_components_in_fee_asset for x in test_points
        ]

        sequencer_costs = [cost.sequencer_cost.value for cost in costs]
        prover_costs = [cost.prover_cost.value for cost in costs]
        congestion_costs = [cost.congestion_cost.value for cost in costs]

        act = ax2

        act.plot(aztec_l1_block_numbers, sequencer_costs, label="Sequencer cost (wei)")
        act.plot(aztec_l1_block_numbers, prover_costs, label="Prover cost (wei)")

        act.set_ylabel("Mana BaseFee (wei)")
        act.set_title("Mana Base Fee Components over Recent Blocks")
        act.legend()
        act.grid(True)

        real_costs = [
            sequencer_costs[i] + prover_costs[i] for i in range(len(sequencer_costs))
        ]
        total_costs = [
            real_costs[i] + congestion_costs[i] for i in range(len(sequencer_costs))
        ]

        act = ax3
        act.fill_between(aztec_l1_block_numbers, 0, real_costs, label="Real cost (wei)")
        act.fill_between(
            aztec_l1_block_numbers,
            real_costs,
            total_costs,
            label="Congestion cost (wei)",
        )
        act.set_ylabel("Mana BaseFee (wei)")
        act.set_title("Fee over the recent blocks (Ether)")
        act.legend()
        act.grid(True)

        real_costs = [
            c.sequencer_cost.value + c.prover_cost.value for c in costs_fee_asset
        ]
        total_costs = [
            real_costs[i] + costs_fee_asset[i].congestion_cost.value
            for i in range(len(real_costs))
        ]
        act = ax4
        act.fill_between(aztec_l1_block_numbers, 0, real_costs, label="Real cost (wei)")
        act.fill_between(
            aztec_l1_block_numbers,
            real_costs,
            total_costs,
            label="Congestion cost (wei)",
        )
        act.set_ylabel("Mana BaseFee (wei)")
        act.set_title("Fee over the recent blocks (fee asset)")
        act.legend()
        act.grid(True)

        act = ax5

        t_0 = [len(b.txs) for b in l2_blocks]
        t_1 = [b.mana_spent().value for b in l2_blocks]
        flem_2 = act.twinx()
        (l1,) = act.plot(
            aztec_l1_block_numbers,
            t_0,
            label="L2 number of transactions",
            color="green",
            linewidth=0.5,
        )
        (l2,) = flem_2.plot(
            aztec_l1_block_numbers,
            t_1,
            label="L2 mana spent",
            color="blue",
            linewidth=0.5,
        )
        act.set_ylabel("Number of transactions")
        flem_2.set_ylabel("Mana Spent")
        act.set_title("Number of transactions and Mana Spent per Block")
        act.legend([l1, l2], ["L2 number of transactions", "L2 mana spent"])
        act.grid(True)

        # Plot 6: ETH per Fee Asset price over time
        act = ax6
        eth_per_fee_asset_values = [
            x.outputs.eth_per_fee_asset_at_execution.value / 1e12 for x in test_points
        ]
        act.plot(
            aztec_l1_block_numbers,
            eth_per_fee_asset_values,
            label="ETH per Fee Asset",
            color="purple",
        )
        act.set_xlabel("Block Number")
        act.set_ylabel("ETH per Fee Asset (1e12 precision)")
        act.set_title("Fee Asset Price over Recent Blocks")
        act.legend()
        act.grid(True)

        plt.tight_layout()

        return ax1, ax2, ax3, ax4, ax5, ax6

    create_plots()
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Points of interest

    - The multiplier makes the base fee more unstable, it might be better to consider a different function to see if we can stabilize it.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## To test with sol
    """)
    return


@app.cell
def _(
    INITIAL_ETH_PER_FEE_ASSET,
    ETH_PER_FEE_ASSET_PRECISION,
    MAX_ETH_PER_FEE_ASSET,
    MAX_FEE_ASSET_PRICE_MODIFIER_BPS,
    MIN_ETH_PER_FEE_ASSET,
    fee_model,
):
    # Constants for the fee maths!
    def get_solidity_code():
        return f"""
        uint256 internal constant PROVING_COST_PER_MANA = {fee_model.proving_cost_per_mana.to_dict()};

        // Fee asset pricing constants (ETH/AZTEC ratio with 1e12 precision)
        uint256 internal constant ETH_PER_FEE_ASSET_PRECISION = {ETH_PER_FEE_ASSET_PRECISION.to_dict()};
        uint256 internal constant MIN_ETH_PER_FEE_ASSET = {MIN_ETH_PER_FEE_ASSET.to_dict()};
        uint256 internal constant MAX_ETH_PER_FEE_ASSET = {MAX_ETH_PER_FEE_ASSET.to_dict()};
        int256 internal constant MAX_FEE_ASSET_PRICE_MODIFIER_BPS = {MAX_FEE_ASSET_PRICE_MODIFIER_BPS.to_dict()};
        uint256 internal constant INITIAL_ETH_PER_FEE_ASSET = {INITIAL_ETH_PER_FEE_ASSET.to_dict()};
        """

    get_solidity_code()
    return


@app.cell
def _(
    Uint256,
    blocks,
    dataclass,
    fee_model,
    json,
    json_serializable,
    test_points,
):
    @json_serializable
    @dataclass
    class L1Metadata:
        block_number: Uint256
        timestamp: Uint256
        blob_fee: Uint256
        base_fee: Uint256

    def get_json():
        return {
            "l1_metadata": [
                L1Metadata(
                    block_number=x.number,
                    timestamp=x.timestamp,
                    blob_fee=x.blob_fee,
                    base_fee=x.base_fee,
                ).to_dict()
                for x in blocks
            ],
            "points": [x.to_dict() for x in test_points],
            "proving_cost": fee_model.proving_cost_per_mana.to_dict(),
        }

    def get_dump():
        return json.dumps(get_json())

    # Create a json object that we can throw at foundry tests
    get_dump()
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # Bandwidth

    In Etheruem, the bandwidth consumed by a validator as noted in the Eth 2.0 book is ~3.5mb/s.

    If we follow the assumption that Ethereum transactions are 700 bytes, and have 15 txs per second, the 180 transaction per block will "require" 0.01mb/s, so there is a good chunk of overhead etc.
    """)
    return


@app.cell
def _():
    ETH_TX_BANDWIDTH = 700
    ETH_BLOCK_BANDWIDTH = ETH_TX_BANDWIDTH * 15

    ETH_MB_PER_SEC = ETH_BLOCK_BANDWIDTH / 1024 / 1024
    print(f"Tx Bandwidth: {ETH_MB_PER_SEC:.2f} MB/s -> {ETH_MB_PER_SEC * 8:.2f} mbit/s")

    ETH_FACTOR = 3.5 / ETH_MB_PER_SEC

    print(f"ETH_FACTOR: {ETH_FACTOR:.2f}")
    return (ETH_FACTOR,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    We call this overhead for the `ETH_FACTOR`. The overhead is due to the gossiping across the nodes, the transactions that might not actually make it, the block headers etc.

    We don't expect to have as big of an overhead, for the simple reason that we do not expect to have as many nodes. Nevertheless, it is a good thing to keep in mind when thinking about the bandwidth requirements.
    """)
    return


@app.cell
def _(ETH_FACTOR):
    AZTEC_TX_BANDWIDTH = 80 * 1024
    AZTEC_BLOCK_BANDWIDTH = AZTEC_TX_BANDWIDTH * 10
    AZTEC_MB_PER_SEC = AZTEC_BLOCK_BANDWIDTH / 1024 / 1024
    print(
        f"Bandwidth: {AZTEC_MB_PER_SEC:.2f} MB/s -> {AZTEC_MB_PER_SEC * 8:.2f} mbit/s"
    )

    ASSUMED_AZTEC_FACTOR = max(1, ETH_FACTOR / 32)

    print(f"ASSUMED_AZTEC_FACTOR: {ASSUMED_AZTEC_FACTOR:.2f}")

    print(
        f"Bandwidth with assumed AZTEC_FACTOR: {AZTEC_MB_PER_SEC * 8 * ASSUMED_AZTEC_FACTOR:.2f} mbit/s"
    )
    return


if __name__ == "__main__":
    app.run()
