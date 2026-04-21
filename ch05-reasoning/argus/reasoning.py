"""Chapter 5 — Argus reasoning integration (conceptual snippets).

Listings 5.2b, 5.3b, 5.5c show how the reasoning patterns compose into
Argus as methods on the Argus class. They reference:

    self.client                          — an anthropic.Anthropic instance
    reason_with_cot, verify_chain        — from patterns.chain_of_thought
    classify_complexity, Complexity      — from patterns.complexity_routing
    HypothesisTester, run_in_sandbox     — from patterns.hypothesis_testing
    ReviewResult                         — a domain type (not defined here)

These fragments are not runnable on their own. For the runnable reasoning
pattern implementations see the `patterns/` sibling directory.
"""


# Listing 5.2b — integrated into review flow
def review_with_reasoning(self, diff: str) -> "ReviewResult":
    chain = reason_with_cot(self.client,  #A
        f"Review this code diff for bugs, security issues, "
        f"and style problems:\n{diff}")

    if chain.weakest_step:  #B
        issues = verify_chain(self.client, chain)
        if issues:
            chain = self.revise_chain(chain, issues)  #C

    return ReviewResult(
        verdict=chain.final_answer,
        reasoning_steps=chain.steps,
        confidence=min(s.confidence for s in chain.steps),
    )

# Listing 5.3b — routing in the review pipeline
def review(self, diff: str) -> "ReviewResult":
    complexity = classify_complexity(  #A
        self.client,
        f"Code review task:\n{diff[:500]}"
    )

    if complexity == Complexity.SIMPLE:
        return self.quick_review(diff)       #B
    elif complexity == Complexity.MODERATE:
        return self.review_with_reasoning(diff)  #C
    else:
        return self.deep_review(diff)        #D

# Listing 5.5c — hypothesis testing for bug verification
def verify_bug(self, suspicion: str, repo_path: str):
    tester = HypothesisTester(
        client=self.client,
        execute_fn=lambda cmd: run_in_sandbox(  #A
            cmd, repo_path),
        max_iterations=5,  #B
    )
    return tester.investigate(  #C
        f"Verify whether this is a real bug: {suspicion}"
    )
