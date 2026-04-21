# Argus method: integrated into review flow
def review_with_reasoning(self, diff: str) -> ReviewResult:
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

# Argus method: routing in the review pipeline
def review(self, diff: str) -> ReviewResult:
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
