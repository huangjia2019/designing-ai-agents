class AgentRuntime:
    """Simplified Runtime VM — the infrastructure layer."""
    def __init__(self, config: RuntimeConfig):
        self.sandbox = Sandbox(  #A
        config.isolation_level)
        self.state = StateManager(  #B
        config.persistence)
        self.mcp_host = MCPHost(  #C
        config.tool_servers)
        self.skills = SkillRegistry(  #D
        config.skill_dir)
        self.monitor = ObservabilityLayer(  #E
        config.metrics)

    def execute_action(self, action: AgentAction) -> ActionResult:
        self.monitor.log_action_start(action)

        risk = self.classify_risk(action)  #F
        if risk.requires_approval:
            approval = self.request_human_approval(action)
            if not approval.granted:
                return ActionResult.blocked(approval.reason)

        with self.sandbox.isolated_context():  #G
            tool = self.mcp_host.resolve_tool(action.tool_name)
            result = tool.invoke(action.parameters)

        self.state.checkpoint(action, result)  #H
        self.monitor.log_action_complete(action, result)
        return result
