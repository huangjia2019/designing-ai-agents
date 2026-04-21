"""Chapter 1 illustration — traditional pipeline vs. agent loop.

Two minimal pedagogical snippets contrasting deterministic software
with the probabilistic, tool-using agent paradigm introduced in Ch1.
Not meant to run end-to-end; included as reference.
"""

# Traditional: deterministic pipeline
class CheckoutService:
    """Every branch enumerated ahead of time."""

    def process_order(self, order):
        if order.total > self.limit:
            return self.reject(order, "over limit")
        if not self.inventory.has(order.items):
            return self.reject(order, "out of stock")
        return self.fulfill(order)


# Agent-based: probabilistic reasoning loop
class AgentCheckout:
    """Given tools + a goal, decide what to do next."""

    def process_order(self, order):
        context = self.perceive(order)
        while not self.done(context):
            action = self.reason(context)
            result = self.act(action)
            context = self.update(context, result)
        return context.outcome
