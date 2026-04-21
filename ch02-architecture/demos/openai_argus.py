from agents import Agent, Runner

argus = Agent(
    name="Argus",
    instructions="You are an expert code reviewer. Analyze diffs for bugs.",
    model="gpt-4.1",
)

if __name__ == "__main__":
    diff = open("sample.diff").read()
    result = Runner.run_sync(argus, f"Review this diff:\n{diff}")
    print(result.final_output)
