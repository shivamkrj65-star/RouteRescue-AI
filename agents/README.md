# Fetch.ai uAgents - RouteRescue AI (Phase 3 Roadmap)

*Note: As per Phase 1 instructions, agent implementations will be added in Phase 3.*

## Planned uAgents Architecture

1. **Disruption Monitor Agent (`disruption_monitor_agent`)**
   - Polls transport incident feeds and broadcasts `DisruptionAlertMessage` to the Recovery Planner.
   - Address & seed configured in `config/settings.py`.

2. **Rail Search Agent (`rail_search_agent`)**
   - Responds to `ModalSearchRequest` with mode `TRAIN`.
   - Discovers alternative train itineraries across Indian Railways / IRCTC network.

3. **Bus Search Agent (`bus_search_agent`)**
   - Responds to `ModalSearchRequest` with mode `BUS`.
   - Discovers intercity coach alternatives (Zingbus, IntrCity SmartBus, NueGo, RSRTC).

4. **Cab & Road Agent (`cab_road_agent`)**
   - Responds to `ModalSearchRequest` with mode `CAB` / `ROAD`.
   - Evaluates expressway outstation cabs and terminal-to-terminal connections.

5. **Recovery Planner Agent (`recovery_planner_agent`)**
   - Central coordinator orchestrating the agent mesh.
   - Combines modal alternatives, ranks them using multimodal optimization, and requests user approval.
