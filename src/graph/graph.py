"""Build and compile the LangGraph state graph."""

from langgraph.graph import END, START, StateGraph

from src.graph.nodes.ask_search_info import ask_search_info
from src.graph.nodes.classify_intent import classify_intent
from src.graph.nodes.confirm_listing import confirm_listing
from src.graph.nodes.extract_listing import extract_listing
from src.graph.nodes.follow_up import follow_up
from src.graph.nodes.handle_opt_in import handle_opt_in
from src.graph.nodes.identify_user import identify_user
from src.graph.nodes.onboard_user import onboard_user
from src.graph.nodes.respond import respond
from src.graph.nodes.respond_help import respond_help
from src.graph.nodes.respond_unknown import respond_unknown
from src.graph.nodes.search_and_match import search_and_match
from src.graph.state import FyndState


def build_graph(checkpointer, store):
    """Build the conversation state graph.

    Nodes use Command(goto=...) for routing, so most edges are implicit.
    Only START -> identify_user and respond -> END are explicit edges.
    """
    builder = StateGraph(FyndState)

    # Core flow
    builder.add_node("identify_user", identify_user)
    builder.add_node("classify_intent", classify_intent)
    builder.add_node("onboard_user", onboard_user)
    builder.add_node("respond_help", respond_help)
    builder.add_node("respond_unknown", respond_unknown)
    builder.add_node("respond", respond)

    # Listing flow: extract → follow_up (loop) → confirm → respond
    builder.add_node("extract_listing", extract_listing)
    builder.add_node("follow_up", follow_up)
    builder.add_node("confirm_listing", confirm_listing)

    # Search flow: search → ask_search_info (loop) → respond
    builder.add_node("search_and_match", search_and_match)
    builder.add_node("ask_search_info", ask_search_info)

    # Opt-in flow
    builder.add_node("handle_opt_in", handle_opt_in)

    # Explicit edges
    builder.add_edge(START, "identify_user")
    builder.add_edge("respond", END)

    return builder.compile(
        checkpointer=checkpointer,
        store=store,
    )
