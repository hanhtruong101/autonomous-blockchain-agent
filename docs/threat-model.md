# Threat model

This prototype protects fake assets on local Anvil. It is not an audited wallet and must never be deployed with real funds. Mainnet and all public testnets are rejected by application configuration; contract constructors require chain 31337.

| Threat | Risk | Mitigation | Remaining limitation |
|---|---|---|---|
| Prompt injection | Agent asks to override permissions | Interpreter only emits drafts; extra fields rejected; no signing capability; owner activation | A user can approve a misleading draft; review remains necessary |
| LLM hallucination | Invalid assets, protocols or values | Validated typed schema; deterministic rules; fixed deployed allowlist; risk checks | Pluggable provider needs its own privacy and availability review |
| Backend compromise | Malicious requests signed with agent identity | Independent on-chain limit, token and target restrictions; owner revocation/pause | Attacker can consume the remaining on-chain budget and may ignore stricter off-chain cadence/targets |
| Malicious contract | Reentrancy, theft or fake output | Explicit owner allowlist; no generic calldata; exact temporary allowance; balance-delta check; limited assets | Owner can whitelist bad code; these mocks are not production AMMs |
| Excessive approval | Unlimited token withdrawal | Approval proposals blocked; wallet approves exact input and clears afterward | Malicious approved target may consume the exact allowance, subject to output check |
| Policy bypass | Agent bypasses backend | On-chain daily budget and restricted operations tested by direct calls | Contract does not independently enforce every portfolio policy field |
| Key compromise | Attacker controls signer | No real keys stored; only disposable unlocked Anvil identities; loopback published RPC | Anyone reaching local RPC can impersonate development owner; Docker network and host are trusted |
| Unsafe destination | Redirect outputs | App destination must equal smart account; swap contract always sends output to itself | Owner-controlled direct transfers to whitelisted recipients exist only for the contract demonstration |
| Slippage attack | Bad exchange output | Policy tolerance, risk checks, RPC simulation, on-chain minimum output and balance check | No real oracle, MEV, dynamic liquidity or market pricing modeled |
| Incorrect chain | Real asset execution | Configuration accepts 31337 only; RPC chain/client guard before reads and calls; local host allowlist; contract guard | Malicious RPC can lie; chain ID alone is not proof of locality |
| Replay/double execution | Same action executes twice | Digest-bound approval, row locks, durable busy flag, unique execution record, on-chain operation ID | Crash before recording RPC hash requires manual reconciliation |
| Race between approval and execution | Stale budget or policy | Revalidate all gates immediately before submission; version match; wallet reservation | State can change before mining; on-chain checks remain authoritative |
| Audit tampering | Hide unauthorized actions | Append-only application API, chronological events, chain hashes and events | DB administrator can alter off-chain rows; no cryptographic external audit sink |
| Owner token theft | Attacker approves changes | Explicit bearer token, constant-time check, browser memory only; no token in URLs or logs | Local HTTP assumes a trusted machine; not suitable for network exposure |
| Unsafe restart | DB state refers to a different chain | Fresh stack resets both database and chain; adapter verifies deployed code exists | Local operators must reset both together; retaining one side is unsupported |
| Denial of service | Expensive proposals or RPC failure freeze work | Bounded inputs, allowlist, local owner authentication; fail-closed uncertain state | No distributed rate limiter; a trusted owner can cause many local runs |

## Trust boundaries

The browser, interpreter and agent are not authorization authorities. Owner review grants an application policy. The policy and risk engines run ordinary deterministic Python. The signer adapter consumes a validated internal proposal after the coordinator authorizes it. The EVM independently enforces account limits. PostgreSQL and the local host are trusted infrastructure.

No API receives arbitrary calldata or a private key. Never log private keys, mnemonic phrases, tokens or full provider exceptions. Anvil's well-known unlocked accounts are deliberately unsafe and have no real-world security value. The deployment script writes only public addresses.

## Recovery

Do not retry an uncertain submission. If a hash exists, use the receipt reconciliation endpoint. If it does not, inspect the account's `Executed` events for the proposal digest and verify the receipt manually. The prototype intentionally has no generic force-unlock endpoint. For a disposable demonstration, reset the entire stack after preserving any audit data you want to study.

## Scheduled execution additions

| Threat | Mitigation | Remaining limitation |
|---|---|---|
| AI proposes a swap away from the user's target | Deterministic integer-only comparison of current versus simulated post-swap allocation; reject non-improvement | Valuation assumes equal-price local mock tokens |
| Overlapping ticks or replay after restart | Wallet row lock, durable unique schedule claim, generation reservation and final authorization check | Interrupted claims require owner freeze and inspection; no automatic crash recovery |
| Owner stops/freezes while model responds | No database lock during generation; invalidate reservation/claim and recheck before durable execution intent | Stop/freeze cannot cancel a transaction already committed for submission |
| Repeated malformed proposals or unavailable provider/RPC | Three consecutive failures disable scheduling and freeze execution; request on-chain pause | Backend compromise can bypass local freeze; on-chain budget/target restrictions still apply |
| Ambiguous send result | Preserve reservation, disable schedule immediately, require reconciliation before resume | No durable hash requires operator chain/event investigation |
| Pause RPC fails | Persist local freeze first, record uncertainty, never auto-resume | Contract pause may remain unconfirmed; direct chain access still needs independent contract restrictions |
| Replacement policy silently inherits automation | Schedule binds version; policy approval disables schedule and invalidates stale pending proposals | Owner must explicitly enable the new version |
| Wrong server timezone extends approval validity | Normalize aware timestamps to UTC; treat SQLite naive timestamps as UTC | Correct host/chain clocks remain operational requirements |

The local owner token authorizes pause/resume endpoints. The agent does not receive that token or the owner control interface. Anvil exposes public unlocked identities, so this prototype does not model private owner-key custody or defend a local RPC from other local processes.

## Exact sizing and explicit minimums

| Threat | Mitigation | Remaining limitation |
|---|---|---|
| Model repeats an arbitrary amount or calculates incorrectly | AI amounts remain untrusted; independent daily/per-trade rules, simulated goal improvement and minimum allocation checks can block them. No automatic clipping or replacement | AI reasoning can still be misleading; calculated facts and actual checks are displayed separately |
| Approximate target is mistaken for a hard reserve | Explicit minimum share in the reviewed version; simulated post-trade integer-ratio check repeats before signing | Minimum is enforced off-chain; mock 1:1 valuation is unsuitable for real markets |
| Parser misinterprets a natural-language minimum | Structured validation, explicit minimum form field and owner review before activation | Natural language is not a formal specification; owners must verify the draft |
| Benchmark is mistaken for live trading or proof of savings | Separate synthetic evaluator with no RPC/signing and visible caveats | Small scenario suite and one model run do not establish general reliability or human time saved |
| AI repeatedly chooses HOLD despite an eligible portfolio | Preserve reasons in Check history; show an advisory after three consecutive AI HOLDs in the history window | Safe inaction can delay goal completion; no automatic fallback or claim of guaranteed progress |
| AI proposes a trade despite no permitted plan | Shared preflight skips ineligible model calls, and execution independently checks every proposed amount through policy/simulation/risk | The synthetic benchmark deliberately calls the model even on skipped snapshots to expose decision errors |
