# Limiting Client Mempools Design Document

Our client tx mempool today grows unbounded. We need to place a limit on how many txs it absorbs.

This addresses how to limit the total number of valid txs. It does **not** address how to protect against DOS attacks that cause the client to validate more txs than it can process.

## Tx validity

A tx in Aztec requires the following checks to be valid. Static checks can be done just once, dynamic ones are done when the tx is received and again when the sequencer is building a block. If the tx fails validation during block building, it gets evicted, unless it failed due to gas fees lower than the block base fee.

### Static

- L1 chain id and L2 version
- Setup function
- Correct public execution requests and logs
- Minimum gas fees (base and priority)
- Reasonable gas limit (currently missing)
- Valid ClientIVC proof

### Dynamic

- Max block number for inclusion
- Double spend (repeated nullifiers)
- Archive root exists (can become invalid after a reorg)
- Fee juice balance for fee payer
- Gas fees over current block base fee
- Gas limit below current block limit

## Geth

What does Geth do? Following is based on geth's [legacy (non-blob) pool implementation](https://github.com/ethereum/go-ethereum/blob/master/core/txpool/legacypool/legacypool.go)

- Geth runs checks by looping over its mempool at regular intervals. This includes evicting txs, and promoting/demoting txs between executable and non-executable.
  - A tx is considered "executable" if it has non nonce gaps and sender has enough balance to pay for its gas.
  - Txs are evicted based on mempool capacity, based on time, and based on the current sender balance (vs the tx max cost) and current max block size in gas (vs tx gas limit).
- Geth enqueues txs per account (sender), and splits txs into executable and non-executable. Geth defines the concept of "slots", where each tx takes up a number of slots depending on its size in bytes. Defaults:
  - `AccountSlots` Number of executable transaction slots guaranteed per account: 16
  - `GlobalSlots` Maximum number of executable transaction slots for all accounts: 4096 + 1024
  - `AccountQueue` Maximum number of non-executable transaction slots permitted per account: 64
  - `GlobalQueue` Maximum number of non-executable transaction slots for all accounts: 1024
  - `Lifetime` Maximum amount of time non-executable transaction are queued: 3 hours
- Geth checks that txs have a minimum gas price before being accepted. For replacements (ie two txs with same sender and nonce), it checks that price bumps are at least of a given %.
  - `PriceLimit` Minimum gas price to enforce for acceptance into the pool: 1
  - `PriceBump` Minimum price bump percentage to replace an already existing transaction by nonce: 10%
- When adding a new tx to the pool, after static validations, geth enqueues the tx as non-executable, and waits for the loop to promote it.
  - [If the tx pool is full](https://github.com/ethereum/go-ethereum/blob/80b8d7a13c20254a9cfb9f7cbca1ab00aa6a3b50/core/txpool/legacypool/legacypool.go#L691-L692), it discards cheaper txs based on gas tip (ie priority fees). Only the global slots seem to be considered here.
- When cleaning up the pool in a loop, loops over pending (executable?) txs for every sender that has gone over AccountSlots, and drops txs (based on nonce) form them. Also loops over future (non-executable?) txs based on **heartbeats**: accounts with the most time without any activity get their txs pruned first.

## Difficulties

In addition to all complications that Ethereum has, we also have the issue that a tx public execution can invalidate an arbitrary number of existing txs just by emitting nullifiers. We have no way of knowing that in advance.

Also, while for Ethereum a "replacement" is just a tx with the same nonce and sender as an existing one, for us any tx that shares a nullifier can technically be a replacement. This also means that tx A may be a replacement for B and C, but B and C may be unrelated to each other.

Also, while our `fee_payer` slightly matches Ethereum's `sender`, it's possible that many users (if not all) use the same very few fee payers (in our case, FPCs), so there is likely no point in setting limits per sender as Ethereum does. Remember that, thanks to privacy, we cannot know the sender of a tx. On the flip side, we know that two txs do come from the same user if they share a private-land nullifier.

## Design

To recap, we need to consider:

- Balance of fee-payers
- Conflicting nullifiers
- Max block number
- Gas fees and limit vs current base fees and limits
- Archive root (only on reorgs)

We propose keeping the following indices for all txs. These indices are implemented as mappings from the given keys to the tx identifier in the backing LMDB store:

- priority fee
- fee-payer
- nullifiers (indexes a tx by all of its nullifiers)
- base fee
- gas limit
- max block number

When adding a tx, we first run the trivial checks:

- Correct L1 chain id and L2 version
- Public setup function is acceptable
- Correct public execution requests and logs
- Gas fees (base and priority) above a given minimum
- Valid ClientIVC proof
- Max block number for inclusion is in the future
- Double spend (repeated nullifiers) against existing state
- Gas limit is below the current block gas limit
- Archive root exists

And then:

- We check if the current balance of the fee payer, minus the max cost of all pending txs for that fee payer, is enough to pay for this tx. If it is not, we try evicting other txs with a lower priority fee. If that works, and all other checks pass, we include the tx dropping the others.
- We check if it shares a nullifier with any existing pending tx (we already checked duplicates against current state at this point). If it pays more than all of the conflicting ones, and it passes all other checks, we include it and drop the other ones.
- We check if the tx fees are above the current base fees. If not, we drop it. Note that we could save it for later in case fees drop in the future, but this means tracking two different pools (executable and non-executable, as geth does).
- We check if we are below a configurable size/number of pending txs. If we are not, start dropping txs with lower priority fee (sorted by priority fee) until we get again below the threshold.
- If we do add the tx, we index its max block number as the minimum of the tx's max-block-number and the current block number plus a configurable number. This allows us to evict txs after they'd been sitting in the pool for a very long time.

When a new block is mined:

- We drop all txs that share nullifiers with nullifiers from the mined blocks
- We update the balance of fee payers and drop txs that can no longer be paid
- We drop all txs with a computed max-block-number equal or lower than the mined one

Note that we should not be dropping them, but rather pushing them to the side to reincorporate them in case of a reorg. But we will dismiss this for now.

When a reorg happens, we crawl through all txs and evict the ones with a no-longer-valid archive root. We could also do this via an index, depending on how frequent we think reorgs will be.

When building a block, for each tx we pick up:

- We re-check nullifiers since public execution of previous txs in the block could invalidate the current one. If we fail validation, we do not drop the tx from the pool immediately; instead, we wait for the block to be mined, and for the p2p sync to evict the tx.
  - Note that, if we check duplicates against existing nullifiers on every block we add, we only need to check against nullifiers emitted during the block being built.
- We check gas fees and limits against the current block base gas fees and limits. If we fail, we just skip the tx.

## Alternative approaches

We can rely heavily on the fact that spamming txs in Aztec is expensive due to the ClientIVC proofs, keep only a global limit on the total number/size of txs, and simply evict based on total mempool size using priority fees, plus re-checking on every block mined. This is much easier to implement than the above.

An attacker can still spam txs with a shared set of nullifiers to flood the pool with just their txs, but if the priority fee is high enough (if it's too low, the attacker's txs get replaced by other txs), one of those txs will be picked up soon enough and invalidate the others; assuming we filter out the invalid ones fast enough, the sequencer eventually get to other valid txs in the pool. The main assumption is that an attacker cannot produce client proofs at a pace that lets them completely fill the mempool before the next block gets built.

This approach still requires rejecting txs with an ineligible base fee or too large a gas limit, otherwise the attacker could flood the tx with non-executable txs. It also requires reviewing all txs on the mempool whenever a block is mined to drop them based on shared nullifiers, insufficient balance, or max-block-age.
