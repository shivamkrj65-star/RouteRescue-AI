"""ASI:One Conversational Travel Recovery Service.

Integrates with ASI:One (Fetch.ai's LLM API) to provide conversational,
natural-language travel recovery interactions:
1. Translates conversational user travel requests into validated, structured RecoveryRequest objects.
2. Invokes the core recovery planning workflow (modal search, constraint validation, multimodal routing).
3. Generates clear, empathetic, and grounded explanations strictly verified against actual planner results.
4. Enforces strict anti-hallucination guardrails: NEVER invents transport services, fares, availability, or bookings.
5. Provides a resilient deterministic rule-based NLP fallback when ASI:One is unconfigured or temporarily offline.
"""

import json
import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import httpx

from config.settings import IST, settings
from schemas.agent_messages import (
    RankedAlternative,
    RecoveryRequest,
    RecoveryResponse,
    ScoringWeights,
)

logger = logging.getLogger("routerescue.asione")


class AsiOneService:
    """Service for conversational travel recovery powered by ASI:One with deterministic fallback."""

    KNOWN_CITIES = {
        "delhi": "Delhi",
        "new delhi": "Delhi",
        "ndls": "Delhi",
        "dli": "Delhi",
        "jaipur": "Jaipur",
        "jp": "Jaipur",
        "chandigarh": "Chandigarh",
        "cdg": "Chandigarh",
        "agra": "Agra",
        "agc": "Agra",
        "mathura": "Mathura",
        "mtj": "Mathura",
        "ambala": "Ambala",
        "umb": "Ambala",
        "gurugram": "Gurugram",
        "gurgaon": "Gurugram",
        "ggn": "Gurugram",
        "noida": "Noida",
        "noi": "Noida",
    }

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout_seconds: float = 12.0,
    ):
        self.api_key = api_key or settings.asione_api_key
        self.base_url = (base_url or settings.asione_base_url).rstrip("/")
        self.model = model or settings.asione_model
        self.timeout_seconds = timeout_seconds

    @property
    def is_configured(self) -> bool:
        """True if ASI:One API key is present."""
        return bool(self.api_key and self.api_key.strip() and self.api_key != "your_asi1_api_key_here")

    # -------------------------------------------------------------------------
    # 1. Natural Language Instruction to Structured RecoveryRequest
    # -------------------------------------------------------------------------

    async def parse_instruction_to_request(self, user_instruction: str) -> Tuple[RecoveryRequest, bool]:
        """Converts user conversational text into a structured RecoveryRequest.

        Returns (request, used_llm).
        Attempts ASI:One structured completion first; on error or missing API key,
        falls back seamlessly to deterministic rule-based extraction.
        """
        if self.is_configured:
            try:
                request = await self._parse_with_asione(user_instruction)
                return request, True
            except Exception as e:
                logger.warning(
                    f"ASI:One API call failed ({e}). Gracefully falling back to deterministic extractor."
                )

        request = self.parse_with_deterministic_rules(user_instruction)
        return request, False

    async def _parse_with_asione(self, text: str) -> RecoveryRequest:
        """Invokes ASI:One OpenAI-compatible chat completion endpoint to extract travel parameters."""
        endpoint = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        system_prompt = (
            "You are RouteRescue AI's travel query parser. Extract travel recovery parameters "
            "from the user's message into JSON with the following schema:\n"
            "{\n"
            '  "origin": string (city name e.g. "Delhi", "Jaipur", "Chandigarh", "Agra", "Gurugram", "Ambala", "Mathura"),\n'
            '  "destination": string (city name),\n'
            '  "earliest_departure": string in "HH:MM:SS" format or null,\n'
            '  "latest_acceptable_arrival": string in "HH:MM:SS" format or null,\n'
            '  "max_budget": float (in INR) or null,\n'
            '  "max_transfers": integer (default 1),\n'
            '  "preferred_modes": array of strings (e.g. ["TRAIN", "BUS", "CAB"]) or null\n'
            "}\n"
            "Return ONLY a valid JSON object. Do not include markdown code blocks or explanations."
        )

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text},
            ],
            "temperature": 0.0,
            "max_tokens": 512,
        }

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            resp = await client.post(endpoint, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        content = data["choices"][0]["message"]["content"].strip()
        # Clean potential markdown fences
        if content.startswith("```"):
            lines = content.split("\n")
            content = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

        parsed = json.loads(content)

        req_id = f"REQ-ASI1-{int(datetime.now(IST).timestamp() * 1000)}"
        return RecoveryRequest(
            request_id=req_id,
            origin=parsed.get("origin") or "Delhi",
            destination=parsed.get("destination") or "Jaipur",
            earliest_departure=parsed.get("earliest_departure"),
            latest_acceptable_arrival=parsed.get("latest_acceptable_arrival"),
            max_budget=float(parsed["max_budget"]) if parsed.get("max_budget") is not None else None,
            max_transfers=int(parsed.get("max_transfers", 1)),
            preferred_modes=parsed.get("preferred_modes"),
        )

    def parse_with_deterministic_rules(self, text: str) -> RecoveryRequest:
        """Deterministic regex and keyword-based NLP extractor for zero-downtime fallback.

        Extracts:
        - Origin and Destination from phrases like:
          "from <city> to <city>", "stuck in <city> need to go to <city>", "<city> to <city>"
        - Budget: "under 1500", "budget 1500", "1500 inr", "rs 1500", "rs. 1500", "max 2000"
        - Latest Arrival: "before 18:00", "by 6 PM", "before 9pm", "reach by 21:00"
        - Earliest Departure: "after 06:00", "leave after 7 am"
        - Max Transfers: "direct only" (0), "1 transfer" (1)
        """
        text_lower = text.lower()

        # 1. Extract Cities
        origin = None
        destination = None

        # Pattern: from X to Y
        from_to_match = re.search(r"from\s+([a-zA-Z\s]+?)\s+to\s+([a-zA-Z\s]+?)(?:[\.,;]|\s+before|\s+by|\s+under|\s+with|$)", text, re.IGNORECASE)
        if from_to_match:
            cand_orig = from_to_match.group(1).strip().lower()
            cand_dest = from_to_match.group(2).strip().lower()
            origin = self.KNOWN_CITIES.get(cand_orig)
            destination = self.KNOWN_CITIES.get(cand_dest)

        # Pattern: stuck in X ... reach / go to Y
        if not (origin and destination):
            stuck_match = re.search(r"(?:stuck in|at|in)\s+([a-zA-Z\s]+?)(?:,|\s+need to go to|\s+going to|\s+travel to|\s+to)\s+([a-zA-Z\s]+?)(?:[\.,;]|\s+before|\s+by|\s+under|\s+with|$)", text, re.IGNORECASE)
            if stuck_match:
                cand_orig = stuck_match.group(1).strip().lower()
                cand_dest = stuck_match.group(2).strip().lower()
                origin = origin or self.KNOWN_CITIES.get(cand_orig)
                destination = destination or self.KNOWN_CITIES.get(cand_dest)

        # Pattern: direct "X to Y"
        if not (origin and destination):
            simple_match = re.search(r"\b([a-zA-Z]+)\s+to\s+([a-zA-Z]+)\b", text, re.IGNORECASE)
            if simple_match:
                cand_orig = simple_match.group(1).strip().lower()
                cand_dest = simple_match.group(2).strip().lower()
                origin = origin or self.KNOWN_CITIES.get(cand_orig)
                destination = destination or self.KNOWN_CITIES.get(cand_dest)

        # Keyword scan fallback if still missing
        if not origin or not destination:
            found_cities = []
            for token, canon in self.KNOWN_CITIES.items():
                if re.search(rf"\b{re.escape(token)}\b", text_lower):
                    if canon not in found_cities:
                        found_cities.append(canon)
            if len(found_cities) >= 2:
                origin = origin or found_cities[0]
                destination = destination or found_cities[1]
            elif len(found_cities) == 1:
                if not origin:
                    origin = found_cities[0]
                elif not destination and found_cities[0] != origin:
                    destination = found_cities[0]

        # Defaults if unspecified
        origin = origin or "Delhi"
        destination = destination or "Jaipur"

        # 2. Extract Budget
        max_budget = None
        budget_match = re.search(
            r"(?:under|budget|max|below|less than|within|rs\.?|inr)\s*(?:of\s*)?(\d{2,5})|(\d{2,5})\s*(?:inr|rs|rupees|budget)",
            text,
            re.IGNORECASE,
        )
        if budget_match:
            b_val = budget_match.group(1) or budget_match.group(2)
            if b_val:
                max_budget = float(b_val)

        # 3. Extract Arrival Deadline
        latest_arrival = None
        arr_match = re.search(
            r"(?:before|by|reach by|arrive by)\s*(\d{1,2})(?::(\d{2}))?\s*(am|pm)?",
            text,
            re.IGNORECASE,
        )
        if arr_match:
            hour = int(arr_match.group(1))
            minute = int(arr_match.group(2) or 0)
            ampm = (arr_match.group(3) or "").lower()
            if ampm == "pm" and hour < 12:
                hour += 12
            elif ampm == "am" and hour == 12:
                hour = 0
            latest_arrival = f"{hour:02d}:{minute:02d}:00"

        # 4. Extract Earliest Departure
        earliest_departure = None
        dep_match = re.search(
            r"(?:after|leave after|depart after)\s*(\d{1,2})(?::(\d{2}))?\s*(am|pm)?",
            text,
            re.IGNORECASE,
        )
        if dep_match:
            hour = int(dep_match.group(1))
            minute = int(dep_match.group(2) or 0)
            ampm = (dep_match.group(3) or "").lower()
            if ampm == "pm" and hour < 12:
                hour += 12
            elif ampm == "am" and hour == 12:
                hour = 0
            earliest_departure = f"{hour:02d}:{minute:02d}:00"

        # 5. Extract Transfers Preference
        max_transfers = 1
        if "direct only" in text_lower or "no transfer" in text_lower or "non-stop" in text_lower or "non stop" in text_lower:
            max_transfers = 0

        req_id = f"REQ-NLP-{int(datetime.now(IST).timestamp() * 1000)}"
        return RecoveryRequest(
            request_id=req_id,
            origin=origin,
            destination=destination,
            earliest_departure=earliest_departure,
            latest_acceptable_arrival=latest_arrival,
            max_budget=max_budget,
            max_transfers=max_transfers,
        )

    # -------------------------------------------------------------------------
    # 2. Grounded Natural-Language Response Synthesis
    # -------------------------------------------------------------------------

    async def generate_grounded_response(
        self,
        request: RecoveryRequest,
        response: RecoveryResponse,
        user_message: str,
    ) -> Tuple[str, bool]:
        """Synthesizes a conversational response strictly grounded in verified recovery results.

        Returns (response_text, used_llm).
        Follows strict anti-hallucination rules: NEVER invents options, timings, or prices.
        """
        if self.is_configured:
            try:
                reply = await self._generate_with_asione(request, response, user_message)
                return reply, True
            except Exception as e:
                logger.warning(
                    f"ASI:One synthesis failed ({e}). Falling back to deterministic generator."
                )

        reply = self.generate_deterministic_explanation(request, response)
        return reply, False

    async def _generate_with_asione(
        self,
        request: RecoveryRequest,
        response: RecoveryResponse,
        user_message: str,
    ) -> str:
        """Invokes ASI:One to generate an empathetic, grounded reply based on verified results."""
        endpoint = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        # Format verified facts for grounding
        options_summary = []
        for i, opt in enumerate(response.top_3_options, start=1):
            alt = opt.alternative
            options_summary.append(
                f"Option #{i} ({alt.mode}): {alt.service_number} ({alt.provider}) | "
                f"Departs: {alt.departure_time} from {alt.origin_name} | "
                f"Arrives: {alt.arrival_time} at {alt.destination_name} | "
                f"Fare: INR {alt.fare_inr:.0f} ({'Estimated cab fare' if alt.has_estimated_costs else 'Scheduled ticket'}) | "
                f"Duration: {alt.duration_minutes}m | Transfers: {alt.transfers_count} | Status: {alt.seat_availability} | "
                f"Tradeoffs: {alt.tradeoffs}"
            )

        grounded_facts = {
            "origin": request.origin,
            "destination": request.destination,
            "total_options_evaluated": response.total_options_evaluated,
            "valid_options_count": response.valid_options_count,
            "rejections": response.rejection_reasons,
            "options": options_summary,
            "best_explanation": response.best_option_explanation,
            "data_label": "DEMONSTRATION SYNTHETIC DATASET (Fetch-A-Thon 3.0)",
        }

        system_prompt = (
            "You are RouteRescue AI, an autonomous multimodal travel disruption recovery assistant. "
            "Your task is to respond to the passenger's inquiry based STRICTLY on the verified facts provided below.\n\n"
            "CRITICAL INTEGRITY RULES:\n"
            "1. NEVER invent, hallucinate, or assume transport options, providers, departure/arrival times, "
            "ticket prices, seat availability, or booking confirmations not in the facts.\n"
            "2. If no valid options are available, explain the constraints clearly and truthfully without making up alternatives.\n"
            "3. Explicitly state that all options are from the Fetch-A-Thon 3.0 demonstration dataset.\n"
            "4. Remind the user that booking any recovery alternative requires their explicit confirmation.\n"
            "5. Be concise, empathetic, and professional."
        )

        user_prompt = (
            f"Passenger Message: \"{user_message}\"\n\n"
            f"Verified Planner Results:\n{json.dumps(grounded_facts, indent=2)}\n\n"
            "Please formulate the conversational response for the passenger."
        )

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.1,
            "max_tokens": 700,
        }

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            resp = await client.post(endpoint, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        return data["choices"][0]["message"]["content"].strip()

    def generate_deterministic_explanation(
        self,
        request: RecoveryRequest,
        response: RecoveryResponse,
    ) -> str:
        """Pure Python deterministic natural-language response grounded in verified planner output."""
        if not response.top_3_options:
            active_rejections = [
                f"{k.replace('_', ' ')}: {v}"
                for k, v in response.rejection_reasons.items()
                if v > 0
            ]
            rejection_details = "; ".join(active_rejections) if active_rejections else "no matching services found"
            budget_note = f" under INR {request.max_budget:,.0f}" if request.max_budget else ""
            deadline_note = f" arriving by {request.latest_acceptable_arrival}" if request.latest_acceptable_arrival else ""

            return (
                f"I reviewed available recovery routes from **{request.origin}** to **{request.destination}**"
                f"{budget_note}{deadline_note}, but unfortunately no travel options could satisfy all your constraints.\n\n"
                f"**Evaluation Summary:** Evaluated {response.total_options_evaluated} services across rail, bus, and road networks. "
                f"Rejections occurred due to: {rejection_details}.\n\n"
                f"*(Note: All data evaluated from RouteRescue AI demonstration network. Please consider widening budget or arrival constraints.)*"
            )

        best = response.top_3_options[0]
        alt = best.alternative
        dur_h = alt.duration_minutes // 60
        dur_m = alt.duration_minutes % 60
        dur_str = f"{dur_h}h {dur_m}m" if dur_h > 0 else f"{dur_m}m"

        try:
            dep_time_str = datetime.fromisoformat(alt.departure_time).strftime("%H:%M")
            arr_time_str = datetime.fromisoformat(alt.arrival_time).strftime("%H:%M")
        except Exception:
            dep_time_str = alt.departure_time
            arr_time_str = alt.arrival_time

        fare_desc = "estimated road fare" if alt.has_estimated_costs else "scheduled ticket fare"
        transfer_desc = "Direct service (0 transfers)" if alt.transfers_count == 0 else f"{alt.transfers_count} transfer ({alt.journey_pattern})"

        lines = [
            f"Here are the best verified recovery options from **{request.origin}** to **{request.destination}**:\n",
            f"### 🏆 Option 1 (Top Recommendation): {alt.mode} — {alt.service_number}",
            f"- **Provider:** {alt.provider}",
            f"- **Schedule:** Departs **{dep_time_str}** ({alt.origin_name}) $\\rightarrow$ Arrives **{arr_time_str}** ({alt.destination_name})",
            f"- **Duration & Fare:** {dur_str} | **INR {alt.fare_inr:,.0f}** ({fare_desc})",
            f"- **Routing:** {transfer_desc}",
            f"- **Seat Availability:** `{alt.seat_availability}`",
            f"- **Selection Rationale:** {response.best_option_explanation}\n",
        ]

        if len(response.top_3_options) > 1:
            lines.append("### 📋 Alternative Options:")
            for i, opt in enumerate(response.top_3_options[1:], start=2):
                o_alt = opt.alternative
                try:
                    o_dep = datetime.fromisoformat(o_alt.departure_time).strftime("%H:%M")
                    o_arr = datetime.fromisoformat(o_alt.arrival_time).strftime("%H:%M")
                except Exception:
                    o_dep = o_alt.departure_time
                    o_arr = o_alt.arrival_time
                o_dur = f"{o_alt.duration_minutes // 60}h {o_alt.duration_minutes % 60}m"
                o_fare_desc = "estimated" if o_alt.has_estimated_costs else "verified"
                lines.append(
                    f"- **Option #{i} ({o_alt.mode})**: {o_alt.service_number} ({o_alt.provider}) — "
                    f"{o_dep} to {o_arr} ({o_dur}), INR {o_alt.fare_inr:,.0f} ({o_fare_desc}), Status: `{o_alt.seat_availability}`."
                )
            lines.append("")

        lines.extend([
            "> **Disclaimer:** Demonstration dataset for Fetch-A-Thon 3.0.",
            "> **User Authorization:** In accordance with RouteRescue AI safety protocols, no booking has been initiated. "
            "Please provide explicit approval before proceeding with any ticket purchase or cab dispatch.",
        ])

        return "\n".join(lines)
