from langchain_anthropic import ChatAnthropic
from langgraph.graph import StateGraph
from typing import TypedDict

llm = ChatAnthropic(model="claude-sonnet-4-6")

class ReviewState(TypedDict):
    diff: str
    review: str

def reason(state: ReviewState) -> ReviewState:
    review = llm.invoke(  #A
    f"Review: {state['diff']}").content
    return {"review": review}

graph = StateGraph(ReviewState)
graph.add_node("review", reason)
graph.set_entry_point("review")
agent = graph.compile()
