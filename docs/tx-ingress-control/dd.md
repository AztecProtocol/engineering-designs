# Intro

For the first release of the network where we permit transactions, we want to retain some ability to moderate the rate of transaction ingress. This is difficult with a decentralised system and no solution can be perfect.

But assuming the majority of nodes respect default implementation and behaviour there is some control that can be achieved.

## Current Architecture

Today, when an RPC node receives a transaction, after successful validation it immediately broadcasts the transaction onto the P2P network. The issue here is that we could end up with a flood of transactions and nodes could be overwhelmed.

The knock on effect here could be nodes can't keep up with verifying ClientIVC proofs and/or transactions could be dropped causing diverging mempools.

## Proposed Changes

The only way to moderate the flow of transactions around the network is to control their ingress at source. Once a tx is being propagated it can't be impeded, to do so would exacerbate the problem of divergent mempools.

So the proposed changes are to track the average rate of transaction delivery at the p2p network, say over the last `N` seconds where `N` is configurable. If this goes beyond a configured threshold, transactions will be rejected at the RPC layer until it reduces.