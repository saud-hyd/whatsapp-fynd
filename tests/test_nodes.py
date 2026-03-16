"""Tests for individual graph nodes with fake data.

Each node is tested in isolation with mocked external dependencies
(DB, Gemini LLM, WhatsApp API, embeddings).
"""

import uuid
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage

# -- Helpers --


def make_config(conn=None):
    """Build a minimal RunnableConfig dict with a mock DB connection."""
    if conn is None:
        conn = AsyncMock()
    return {"configurable": {"thread_id": "wa_test", "conn": conn}}


def make_state(**overrides):
    """Build a minimal FyndState dict."""
    base = {
        "messages": [HumanMessage(content="Hello")],
        "wa_id": "4917600000001",
        "user_id": None,
        "user_role": None,
        "intent": None,
        "extracted_listing": None,
        "extracted_preferences": None,
        "match_results": None,
        "current_match_index": None,
        "response_type": None,
        "response_payload": None,
    }
    base.update(overrides)
    return base


# -- identify_user tests --


class TestIdentifyUserNode:
    @pytest.mark.asyncio
    async def test_existing_user(self):
        from src.graph.nodes.identify_user import identify_user

        conn = AsyncMock()
        user_id = str(uuid.uuid4())
        conn.fetchrow.return_value = {"id": user_id, "wa_id": "491760", "role": "lister"}
        conn.fetch.return_value = []  # no pending notifications

        store = MagicMock()
        state = make_state(wa_id="491760")

        with (
            patch(
                "src.graph.nodes.identify_user.get_user_by_wa_id", new_callable=AsyncMock
            ) as mock_get,
            patch("src.graph.nodes.identify_user.create_user", new_callable=AsyncMock),
            patch(
                "src.graph.nodes.identify_user.update_last_active", new_callable=AsyncMock
            ) as mock_active,
            patch(
                "src.graph.nodes.identify_user.flush_pending_notifications", new_callable=AsyncMock
            ) as mock_flush,
        ):
            mock_get.return_value = {"id": user_id, "wa_id": "491760", "role": "lister"}

            result = await identify_user(state, make_config(conn), store=store)

        assert result.goto == "classify_intent"
        assert result.update["user_id"] == user_id
        assert result.update["user_role"] == "lister"
        mock_active.assert_called_once_with(conn, user_id)
        mock_flush.assert_called_once_with(conn, user_id, "491760")

    @pytest.mark.asyncio
    async def test_new_user_created(self):
        from src.graph.nodes.identify_user import identify_user

        conn = AsyncMock()
        new_id = str(uuid.uuid4())

        store = MagicMock()
        state = make_state(wa_id="491760NEW")

        with (
            patch(
                "src.graph.nodes.identify_user.get_user_by_wa_id", new_callable=AsyncMock
            ) as mock_get,
            patch(
                "src.graph.nodes.identify_user.create_user", new_callable=AsyncMock
            ) as mock_create,
            patch("src.graph.nodes.identify_user.update_last_active", new_callable=AsyncMock),
            patch(
                "src.graph.nodes.identify_user.flush_pending_notifications", new_callable=AsyncMock
            ),
        ):
            mock_get.return_value = None
            mock_create.return_value = {"id": new_id, "wa_id": "491760NEW"}

            result = await identify_user(state, make_config(conn), store=store)

        assert result.goto == "classify_intent"
        assert result.update["user_id"] == new_id
        assert result.update["user_role"] is None
        mock_create.assert_called_once_with(conn, "491760NEW")


# -- classify_intent tests --


class TestClassifyIntentNode:
    @pytest.mark.asyncio
    async def test_routes_list_place(self):
        from src.graph.nodes.classify_intent import classify_intent
        from src.models.intent import ClassifiedIntent

        mock_classifier = AsyncMock()
        mock_classifier.ainvoke.return_value = ClassifiedIntent(
            intent="list_place", confidence=0.95
        )

        mock_llm = MagicMock()
        mock_llm.with_structured_output.return_value = mock_classifier

        state = make_state(
            messages=[HumanMessage(content="I have a 2BR in Kreuzberg for 800/month")]
        )

        with patch("src.graph.nodes.classify_intent.get_llm", return_value=mock_llm):
            result = await classify_intent(state, make_config())

        assert result.goto == "extract_listing"
        assert result.update["intent"] == "list_place"

    @pytest.mark.asyncio
    async def test_routes_search_place(self):
        from src.graph.nodes.classify_intent import classify_intent
        from src.models.intent import ClassifiedIntent

        mock_classifier = AsyncMock()
        mock_classifier.ainvoke.return_value = ClassifiedIntent(
            intent="search_place", confidence=0.92
        )

        mock_llm = MagicMock()
        mock_llm.with_structured_output.return_value = mock_classifier

        state = make_state(
            messages=[HumanMessage(content="Looking for a room in Munich under 600")]
        )

        with patch("src.graph.nodes.classify_intent.get_llm", return_value=mock_llm):
            result = await classify_intent(state, make_config())

        assert result.goto == "search_and_match"
        assert result.update["intent"] == "search_place"

    @pytest.mark.asyncio
    async def test_routes_onboard(self):
        from src.graph.nodes.classify_intent import classify_intent
        from src.models.intent import ClassifiedIntent

        mock_classifier = AsyncMock()
        mock_classifier.ainvoke.return_value = ClassifiedIntent(intent="onboard", confidence=0.88)

        mock_llm = MagicMock()
        mock_llm.with_structured_output.return_value = mock_classifier

        state = make_state(messages=[HumanMessage(content="Hi!")])

        with patch("src.graph.nodes.classify_intent.get_llm", return_value=mock_llm):
            result = await classify_intent(state, make_config())

        assert result.goto == "onboard_user"

    @pytest.mark.asyncio
    async def test_routes_opt_in(self):
        from src.graph.nodes.classify_intent import classify_intent
        from src.models.intent import ClassifiedIntent

        mock_classifier = AsyncMock()
        mock_classifier.ainvoke.return_value = ClassifiedIntent(
            intent="opt_in_response", confidence=0.99
        )

        mock_llm = MagicMock()
        mock_llm.with_structured_output.return_value = mock_classifier

        state = make_state(messages=[HumanMessage(content="match_interested_0")])

        with patch("src.graph.nodes.classify_intent.get_llm", return_value=mock_llm):
            result = await classify_intent(state, make_config())

        assert result.goto == "handle_opt_in"

    @pytest.mark.asyncio
    async def test_routes_help(self):
        from src.graph.nodes.classify_intent import classify_intent
        from src.models.intent import ClassifiedIntent

        mock_classifier = AsyncMock()
        mock_classifier.ainvoke.return_value = ClassifiedIntent(intent="help", confidence=0.9)

        mock_llm = MagicMock()
        mock_llm.with_structured_output.return_value = mock_classifier

        state = make_state(messages=[HumanMessage(content="How does this work?")])

        with patch("src.graph.nodes.classify_intent.get_llm", return_value=mock_llm):
            result = await classify_intent(state, make_config())

        assert result.goto == "respond_help"

    @pytest.mark.asyncio
    async def test_routes_unknown(self):
        from src.graph.nodes.classify_intent import classify_intent
        from src.models.intent import ClassifiedIntent

        mock_classifier = AsyncMock()
        mock_classifier.ainvoke.return_value = ClassifiedIntent(intent="unknown", confidence=0.3)

        mock_llm = MagicMock()
        mock_llm.with_structured_output.return_value = mock_classifier

        state = make_state(messages=[HumanMessage(content="What's the weather like?")])

        with patch("src.graph.nodes.classify_intent.get_llm", return_value=mock_llm):
            result = await classify_intent(state, make_config())

        assert result.goto == "respond_unknown"


# -- onboard_user tests --


class TestOnboardUserNode:
    @pytest.mark.asyncio
    async def test_returns_buttons(self):
        from src.graph.nodes.onboard_user import onboard_user

        state = make_state()
        result = await onboard_user(state, make_config())

        assert result.goto == "respond"
        assert result.update["response_type"] == "interactive_buttons"
        buttons = result.update["response_payload"]["buttons"]
        assert len(buttons) == 2
        assert buttons[0]["id"] == "action_list"
        assert buttons[1]["id"] == "action_search"


# -- extract_listing tests --


class TestExtractListingNode:
    @pytest.mark.asyncio
    async def test_complete_listing_goes_to_confirm(self):
        from src.graph.nodes.extract_listing import extract_listing
        from src.models.listing import ExtractedListing

        complete = ExtractedListing(
            city="Berlin",
            neighborhood="Kreuzberg",
            rent_amount=800,
            rooms=2,
            available_from=date(2026, 4, 1),
            listing_type="sublet",
            summary="Sunny 2BR in Kreuzberg, available from April.",
        )

        mock_extractor = AsyncMock()
        mock_extractor.ainvoke.return_value = complete

        mock_llm = MagicMock()
        mock_llm.with_structured_output.return_value = mock_extractor

        state = make_state(
            messages=[
                HumanMessage(
                    content="I have a 2BR in Kreuzberg Berlin, 800/month, from April 1st, sublet"
                )
            ]
        )

        with patch("src.graph.nodes.extract_listing.get_llm", return_value=mock_llm):
            result = await extract_listing(state, make_config())

        assert result.goto == "confirm_listing"
        assert result.update["extracted_listing"]["city"] == "Berlin"
        assert result.update["extracted_listing"]["rent_amount"] == 800

    @pytest.mark.asyncio
    async def test_incomplete_listing_goes_to_follow_up(self):
        from src.graph.nodes.extract_listing import extract_listing
        from src.models.listing import ExtractedListing

        incomplete = ExtractedListing(
            city="Berlin",
            rent_amount=None,
            rooms=2,
            available_from=None,
            summary="A 2BR apartment in Berlin.",
        )

        mock_extractor = AsyncMock()
        mock_extractor.ainvoke.return_value = incomplete

        mock_llm = MagicMock()
        mock_llm.with_structured_output.return_value = mock_extractor

        state = make_state(messages=[HumanMessage(content="I have a 2BR in Berlin")])

        with patch("src.graph.nodes.extract_listing.get_llm", return_value=mock_llm):
            result = await extract_listing(state, make_config())

        assert result.goto == "follow_up"
        assert result.update["extracted_listing"]["city"] == "Berlin"
        assert result.update["extracted_listing"]["rent_amount"] is None

    @pytest.mark.asyncio
    async def test_merges_with_existing_extraction(self):
        from src.graph.nodes.extract_listing import extract_listing
        from src.models.listing import ExtractedListing

        # New extraction only has the missing rent
        new_extraction = ExtractedListing(
            rent_amount=900,
            summary="Updated summary.",
        )

        mock_extractor = AsyncMock()
        mock_extractor.ainvoke.return_value = new_extraction

        mock_llm = MagicMock()
        mock_llm.with_structured_output.return_value = mock_extractor

        state = make_state(
            messages=[
                HumanMessage(content="I have a 2BR in Berlin"),
                HumanMessage(content="900 per month"),
            ],
            extracted_listing={
                "city": "Berlin",
                "neighborhood": None,
                "rent_amount": None,
                "rooms": 2.0,
                "available_from": "2026-04-01",
                "available_to": None,
                "listing_type": None,
                "amenities": [],
                "summary": "A 2BR in Berlin.",
            },
        )

        with patch("src.graph.nodes.extract_listing.get_llm", return_value=mock_llm):
            result = await extract_listing(state, make_config())

        # Should merge: keep city and rooms from existing, add rent from new
        listing = result.update["extracted_listing"]
        assert listing["city"] == "Berlin"
        assert listing["rent_amount"] == 900
        assert listing["rooms"] == 2.0


# -- confirm_listing tests --


class TestConfirmListingNode:
    @pytest.mark.asyncio
    async def test_confirm_saves_and_responds(self):
        from src.graph.nodes.confirm_listing import confirm_listing

        conn = AsyncMock()
        listing_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())
        conn.fetchrow.return_value = {"id": listing_id}

        state = make_state(
            user_id=user_id,
            user_role=None,
            messages=[HumanMessage(content="I have a place in Berlin")],
            extracted_listing={
                "city": "Berlin",
                "neighborhood": "Kreuzberg",
                "rent_amount": 800,
                "rooms": 2.0,
                "available_from": "2026-04-01",
                "available_to": None,
                "listing_type": "sublet",
                "amenities": ["furnished"],
                "summary": "Sunny 2BR in Kreuzberg.",
            },
        )

        fake_embedding = [0.1] * 768

        with (
            patch("src.graph.nodes.confirm_listing.interrupt", return_value="action_confirm"),
            patch(
                "src.graph.nodes.confirm_listing.generate_embedding",
                new_callable=AsyncMock,
                return_value=fake_embedding,
            ),
            patch(
                "src.graph.nodes.confirm_listing.insert_listing",
                new_callable=AsyncMock,
                return_value={"id": listing_id},
            ),
            patch(
                "src.graph.nodes.confirm_listing.update_user_role", new_callable=AsyncMock
            ) as mock_role,
        ):
            result = await confirm_listing(state, make_config(conn))

        assert result.goto == "respond"
        assert result.update["response_type"] == "text"
        assert "live" in result.update["response_payload"]["body"].lower()
        assert result.update["user_role"] == "lister"
        mock_role.assert_called_once_with(conn, user_id, "lister")

    @pytest.mark.asyncio
    async def test_edit_goes_back_to_extract(self):
        from src.graph.nodes.confirm_listing import confirm_listing

        state = make_state(
            user_id=str(uuid.uuid4()),
            extracted_listing={
                "city": "Berlin",
                "neighborhood": None,
                "rent_amount": 800,
                "rooms": 2.0,
                "available_from": "2026-04-01",
                "available_to": None,
                "listing_type": None,
                "amenities": [],
                "summary": "2BR in Berlin.",
            },
        )

        with patch(
            "src.graph.nodes.confirm_listing.interrupt", return_value="Actually the rent is 750"
        ):
            result = await confirm_listing(state, make_config())

        assert result.goto == "extract_listing"
        # Should add the edit message to state
        assert any("750" in str(m) for m in result.update["messages"])


# -- search_and_match tests --


class TestSearchAndMatchNode:
    @pytest.mark.asyncio
    async def test_no_matches_found(self):
        from src.graph.nodes.search_and_match import search_and_match
        from src.models.search import SeekingPreferences

        prefs = SeekingPreferences(
            city="Munich",
            max_rent=600,
            min_rooms=1.0,
            seeker_intro="I'm a student looking for a quiet place.",
            summary="Student looking for 1+ room in Munich under 600.",
        )

        mock_extractor = AsyncMock()
        mock_extractor.ainvoke.return_value = prefs

        mock_llm = MagicMock()
        mock_llm.with_structured_output.return_value = mock_extractor

        conn = AsyncMock()
        fake_embedding = [0.2] * 768

        state = make_state(
            user_id=str(uuid.uuid4()),
            messages=[HumanMessage(content="Looking for a room in Munich under 600")],
        )

        with (
            patch("src.graph.nodes.search_and_match.get_llm", return_value=mock_llm),
            patch(
                "src.graph.nodes.search_and_match.generate_embedding",
                new_callable=AsyncMock,
                return_value=fake_embedding,
            ),
            patch(
                "src.graph.nodes.search_and_match.find_matches",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch("src.graph.nodes.search_and_match.update_user_role", new_callable=AsyncMock),
        ):
            result = await search_and_match(state, make_config(conn))

        assert result.goto == "respond"
        assert "no matches" in result.update["response_payload"]["body"].lower()

    @pytest.mark.asyncio
    async def test_matches_found_presents_first(self):
        from src.graph.nodes.search_and_match import search_and_match
        from src.models.search import SeekingPreferences

        prefs = SeekingPreferences(
            city="Berlin",
            max_rent=900,
            seeker_intro="Software dev, quiet, non-smoker.",
            summary="Looking for a quiet room in Berlin under 900.",
        )

        mock_extractor = AsyncMock()
        mock_extractor.ainvoke.return_value = prefs

        mock_llm = MagicMock()
        mock_llm.with_structured_output.return_value = mock_extractor
        # For match reason generation
        mock_llm.ainvoke = AsyncMock(
            return_value=AIMessage(content="Great fit — quiet neighborhood, within budget.")
        )

        conn = AsyncMock()
        fake_embedding = [0.2] * 768

        matches = [
            {
                "id": str(uuid.uuid4()),
                "user_id": str(uuid.uuid4()),
                "summary": "Sunny 2BR in Kreuzberg",
                "city": "Berlin",
                "neighborhood": "Kreuzberg",
                "rent_amount": 800,
                "rooms": 2.0,
                "similarity": 0.89,
                "wa_id": "4917600000002",
                "lister_name": "Alice",
            },
        ]

        state = make_state(
            user_id=str(uuid.uuid4()),
            messages=[HumanMessage(content="Looking for something in Berlin")],
        )

        with (
            patch("src.graph.nodes.search_and_match.get_llm", return_value=mock_llm),
            patch(
                "src.graph.nodes.search_and_match.generate_embedding",
                new_callable=AsyncMock,
                return_value=fake_embedding,
            ),
            patch(
                "src.graph.nodes.search_and_match.find_matches",
                new_callable=AsyncMock,
                return_value=matches,
            ),
            patch("src.graph.nodes.search_and_match.update_user_role", new_callable=AsyncMock),
        ):
            result = await search_and_match(state, make_config(conn))

        assert result.goto == "respond"
        assert result.update["response_type"] == "interactive_buttons"
        body = result.update["response_payload"]["body"]
        assert "Kreuzberg" in body
        assert "800" in body
        buttons = result.update["response_payload"]["buttons"]
        button_ids = [b["id"] for b in buttons]
        assert "match_interested_0" in button_ids
        assert "match_skip_all" in button_ids

    @pytest.mark.asyncio
    async def test_missing_city_asks_for_it(self):
        from src.graph.nodes.search_and_match import search_and_match
        from src.models.search import SeekingPreferences

        prefs = SeekingPreferences(
            city=None,
            max_rent=700,
            seeker_intro="Student",
            summary="Looking for a room under 700.",
        )

        mock_extractor = AsyncMock()
        mock_extractor.ainvoke.return_value = prefs

        mock_llm = MagicMock()
        mock_llm.with_structured_output.return_value = mock_extractor

        state = make_state(messages=[HumanMessage(content="I need a room under 700")])

        with patch("src.graph.nodes.search_and_match.get_llm", return_value=mock_llm):
            result = await search_and_match(state, make_config())

        assert result.goto == "ask_search_info"
        assert "city" in result.update["response_payload"]["body"].lower()

    @pytest.mark.asyncio
    async def test_missing_seeker_intro_asks_for_it(self):
        from src.graph.nodes.search_and_match import search_and_match
        from src.models.search import SeekingPreferences

        prefs = SeekingPreferences(
            city="Berlin",
            max_rent=700,
            seeker_intro=None,
            summary="Looking for a room in Berlin.",
        )

        mock_extractor = AsyncMock()
        mock_extractor.ainvoke.return_value = prefs

        mock_llm = MagicMock()
        mock_llm.with_structured_output.return_value = mock_extractor

        state = make_state(messages=[HumanMessage(content="I need a room in Berlin under 700")])

        with patch("src.graph.nodes.search_and_match.get_llm", return_value=mock_llm):
            result = await search_and_match(state, make_config())

        assert result.goto == "ask_search_info"
        assert "about yourself" in result.update["response_payload"]["body"].lower()


# -- handle_opt_in tests --


class TestHandleOptInNode:
    @pytest.mark.asyncio
    async def test_seeker_interested_creates_match(self):
        from src.graph.nodes.handle_opt_in import handle_opt_in

        conn = AsyncMock()
        match_id = str(uuid.uuid4())
        lister_id = str(uuid.uuid4())
        seeker_id = str(uuid.uuid4())
        listing_id = str(uuid.uuid4())

        state = make_state(
            user_id=seeker_id,
            messages=[HumanMessage(content="match_interested_0")],
            match_results=[
                {
                    "id": listing_id,
                    "user_id": lister_id,
                    "summary": "2BR Kreuzberg",
                    "similarity": 0.89,
                    "wa_id": "4917600000002",
                },
            ],
            extracted_preferences={"seeker_intro": "I'm a student."},
        )

        with (
            patch(
                "src.graph.nodes.handle_opt_in.create_match", new_callable=AsyncMock
            ) as mock_create,
            patch(
                "src.graph.nodes.handle_opt_in.deliver_or_queue", new_callable=AsyncMock
            ) as mock_notify,
        ):
            mock_create.return_value = {
                "id": match_id,
                "listing_id": listing_id,
                "seeker_id": seeker_id,
                "lister_id": lister_id,
                "seeker_status": "accepted",
                "lister_status": "pending",
            }

            result = await handle_opt_in(state, make_config(conn))

        assert result.goto == "respond"
        assert "interested" in result.update["response_payload"]["body"].lower()
        mock_create.assert_called_once()
        mock_notify.assert_called_once()
        # Verify notification type
        notify_args = mock_notify.call_args
        assert notify_args[0][3] == "match_interest"

    @pytest.mark.asyncio
    async def test_seeker_next_shows_next_match(self):
        from src.graph.nodes.handle_opt_in import handle_opt_in

        match1_id = str(uuid.uuid4())
        match2_id = str(uuid.uuid4())

        state = make_state(
            messages=[HumanMessage(content="match_next_0")],
            match_results=[
                {
                    "id": match1_id,
                    "summary": "Match 1",
                    "city": "Berlin",
                    "rent_amount": 800,
                    "rooms": 2,
                },
                {
                    "id": match2_id,
                    "summary": "Match 2",
                    "city": "Berlin",
                    "rent_amount": 700,
                    "rooms": 1,
                },
            ],
            current_match_index=0,
        )

        result = await handle_opt_in(state, make_config())

        assert result.goto == "respond"
        assert result.update["current_match_index"] == 1
        assert result.update["response_type"] == "interactive_buttons"
        assert "Match 2" in result.update["response_payload"]["body"]

    @pytest.mark.asyncio
    async def test_seeker_skip_all(self):
        from src.graph.nodes.handle_opt_in import handle_opt_in

        state = make_state(messages=[HumanMessage(content="match_skip_all")])

        result = await handle_opt_in(state, make_config())

        assert result.goto == "respond"
        assert result.update["response_type"] == "text"
        assert "saved" in result.update["response_payload"]["body"].lower()

    @pytest.mark.asyncio
    async def test_lister_accept_mutual_match(self):
        from src.graph.nodes.handle_opt_in import handle_opt_in

        conn = AsyncMock()
        match_id = str(uuid.uuid4())

        state = make_state(
            messages=[HumanMessage(content=f"opt_accept_{match_id}")],
        )

        with (
            patch("src.graph.nodes.handle_opt_in.update_match_status", new_callable=AsyncMock),
            patch(
                "src.graph.nodes.handle_opt_in.get_match_by_id", new_callable=AsyncMock
            ) as mock_get,
            patch("src.graph.nodes.handle_opt_in.deliver_or_queue", new_callable=AsyncMock),
        ):
            mock_get.return_value = {
                "id": match_id,
                "seeker_status": "accepted",
                "lister_status": "accepted",
                "seeker_wa_id": "4917600000003",
                "lister_wa_id": "4917600000004",
                "seeker_id": str(uuid.uuid4()),
                "lister_id": str(uuid.uuid4()),
                "seeker_name": "Bob",
                "lister_name": "Alice",
                "listing_summary": "2BR Kreuzberg",
            }

            result = await handle_opt_in(state, make_config(conn))

        assert result.goto == "respond"
        body = result.update["response_payload"]["body"]
        assert "match" in body.lower()
        assert "wa.me/" in body

    @pytest.mark.asyncio
    async def test_lister_reject(self):
        from src.graph.nodes.handle_opt_in import handle_opt_in

        conn = AsyncMock()
        match_id = str(uuid.uuid4())

        state = make_state(
            messages=[HumanMessage(content=f"opt_reject_{match_id}")],
        )

        with (
            patch("src.graph.nodes.handle_opt_in.update_match_status", new_callable=AsyncMock),
            patch(
                "src.graph.nodes.handle_opt_in.get_match_by_id", new_callable=AsyncMock
            ) as mock_get,
        ):
            mock_get.return_value = {
                "id": match_id,
                "seeker_status": "accepted",
                "lister_status": "rejected",
                "seeker_wa_id": "4917600000003",
                "lister_wa_id": "4917600000004",
                "seeker_id": str(uuid.uuid4()),
                "lister_id": str(uuid.uuid4()),
                "seeker_name": "Bob",
                "lister_name": "Alice",
                "listing_summary": "2BR Kreuzberg",
            }

            result = await handle_opt_in(state, make_config(conn))

        assert result.goto == "respond"
        assert "won't share" in result.update["response_payload"]["body"].lower()

    @pytest.mark.asyncio
    async def test_invalid_match_index(self):
        from src.graph.nodes.handle_opt_in import handle_opt_in

        conn = AsyncMock()
        state = make_state(
            messages=[HumanMessage(content="match_interested_5")],
            match_results=[],
        )

        with patch("src.graph.nodes.handle_opt_in.create_match", new_callable=AsyncMock):
            result = await handle_opt_in(state, make_config(conn))

        assert result.goto == "respond"
        assert "no longer available" in result.update["response_payload"]["body"].lower()

    @pytest.mark.asyncio
    async def test_no_more_matches(self):
        from src.graph.nodes.handle_opt_in import handle_opt_in

        state = make_state(
            messages=[HumanMessage(content="match_next_0")],
            match_results=[
                {"id": "only-one", "summary": "Only match", "city": "Berlin"},
            ],
            current_match_index=0,
        )

        result = await handle_opt_in(state, make_config())

        assert result.goto == "respond"
        assert result.update["response_type"] == "text"
        assert "all the matches" in result.update["response_payload"]["body"].lower()


# -- respond node tests --


class TestRespondNode:
    @pytest.mark.asyncio
    async def test_sends_text(self):
        from src.graph.nodes.respond import respond

        state = make_state(
            response_type="text",
            response_payload={"body": "Hello there!"},
        )

        with patch("src.graph.nodes.respond.send_text", new_callable=AsyncMock) as mock_send:
            await respond(state, make_config())

        mock_send.assert_called_once_with("4917600000001", "Hello there!")

    @pytest.mark.asyncio
    async def test_sends_buttons(self):
        from src.graph.nodes.respond import respond

        buttons = [{"id": "a", "title": "Option A"}, {"id": "b", "title": "Option B"}]
        state = make_state(
            response_type="interactive_buttons",
            response_payload={"body": "Choose:", "buttons": buttons},
        )

        with patch("src.graph.nodes.respond.send_buttons", new_callable=AsyncMock) as mock_send:
            await respond(state, make_config())

        mock_send.assert_called_once_with("4917600000001", "Choose:", buttons)

    @pytest.mark.asyncio
    async def test_sends_list(self):
        from src.graph.nodes.respond import respond

        sections = [{"title": "Results", "rows": [{"id": "r1", "title": "Room 1"}]}]
        state = make_state(
            response_type="interactive_list",
            response_payload={
                "body": "Here are your options:",
                "button_text": "View",
                "sections": sections,
            },
        )

        with patch("src.graph.nodes.respond.send_list", new_callable=AsyncMock) as mock_send:
            await respond(state, make_config())

        mock_send.assert_called_once_with(
            "4917600000001", "Here are your options:", "View", sections
        )

    @pytest.mark.asyncio
    async def test_handles_send_failure(self):
        from src.graph.nodes.respond import respond

        state = make_state(
            response_type="text",
            response_payload={"body": "Test"},
        )

        with patch(
            "src.graph.nodes.respond.send_text",
            new_callable=AsyncMock,
            side_effect=Exception("API Error"),
        ):
            # Should not raise — errors are logged
            result = await respond(state, make_config())

        assert result == {}


# -- respond_help tests --


class TestRespondHelpNode:
    @pytest.mark.asyncio
    async def test_returns_help_text(self):
        from src.graph.nodes.respond_help import respond_help

        result = await respond_help(make_state(), make_config())

        assert result.goto == "respond"
        assert result.update["response_type"] == "text"
        assert "how i work" in result.update["response_payload"]["body"].lower()


# -- respond_unknown tests --


class TestRespondUnknownNode:
    @pytest.mark.asyncio
    async def test_returns_redirect(self):
        from src.graph.nodes.respond_unknown import respond_unknown

        result = await respond_unknown(make_state(), make_config())

        assert result.goto == "respond"
        assert result.update["response_type"] == "text"
        body = result.update["response_payload"]["body"]
        assert "fynd" in body.lower()
        # Should NOT mention Berlin
        assert "berlin" not in body.lower()
