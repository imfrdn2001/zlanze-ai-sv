from app.schemas import (
    ChatContext,
    ChatData,
    DeveloperMatch,
    ExtractedSlots,
    Intent,
    ProjectOption,
)


def _format_number(value: float) -> str:
    return f"{value:,.0f}" if value.is_integer() else f"{value:,.2f}"


def _format_money(value: float, currency: str) -> str:
    symbol = "$" if currency == "USD" else f"{currency} "
    return f"{symbol}{_format_number(value)}"


def _developer_line(index: int, developer: DeveloperMatch) -> str:
    details = []
    if developer.rating is not None:
        details.append(f"rating {developer.rating:.1f}")
    if developer.matched_tech:
        details.append("matches " + ", ".join(developer.matched_tech))
        details.append(
            f"{len(developer.matched_tech)}/"
            f"{developer.requested_tech_count} stack coverage"
        )
        evidence_parts = [
            f"{term}: {', '.join(sources)}"
            for term, sources in developer.match_evidence.items()
            if sources
        ]
        if evidence_parts:
            details.append("evidence " + " | ".join(evidence_parts))
    details.append(f"{developer.gig_count} gig(s)")
    if developer.advertised_price_low is not None:
        high = developer.advertised_price_high or developer.advertised_price_low
        details.append(
            "advertised gigs "
            f"{_format_money(developer.advertised_price_low, developer.price_currency)}–"
            f"{_format_money(high, developer.price_currency)}"
        )
    elif developer.compensation_label:
        details.append(f"annual compensation {developer.compensation_label}")
        if developer.daily_rate_inr is not None:
            details.append(
                f"calculated rate INR {_format_number(developer.daily_rate_inr)}/day, "
                f"INR {_format_number(developer.hourly_rate_inr or 0)}/hour "
                "(includes INR 150/hour adjustment)"
            )
    return f"{index}. {developer.display_name} — " + "; ".join(details)


def _grouped_developer_lines(
    developers: list[DeveloperMatch],
    technologies: list[str],
) -> list[str]:
    complete = [developer for developer in developers if developer.coverage_percent == 100]
    partial = [
        developer
        for developer in developers
        if 50 <= developer.coverage_percent < 100
    ]
    lines = ["Talent matching for: " + ", ".join(technologies) + "."]
    lines.append("Top recommended — complete stack matches:")
    if complete:
        lines.extend(
            _developer_line(index, developer)
            for index, developer in enumerate(complete, start=1)
        )
    else:
        lines.append("No freelancer matched the complete stack.")

    if partial:
        lines.append("Strong partial matches — at least half of the stack:")
        lines.extend(
            _developer_line(index, developer)
            for index, developer in enumerate(partial, start=1)
        )
    return lines


def build_options_response(options: list[ProjectOption]) -> str:
    sections = [
        "Below is a comparison of all three scopes. The estimates come from "
        "related marketplace gigs."
    ]
    for index, option in enumerate(options, start=1):
        lines = [
            f"{index}. {option.name}",
            option.description,
            "Suggested technology: " + ", ".join(option.technology_used) + ".",
        ]
        if option.developers:
            lines.extend(
                _grouped_developer_lines(
                    option.developers,
                    option.technology_used,
                )
            )
        else:
            lines.append("No strong freelancer match was found for this option.")
        if option.cost:
            lines.append(
                "Estimated price: "
                f"{_format_money(option.cost.low, option.cost.unit)}–"
                f"{_format_money(option.cost.high, option.cost.unit)} "
                f"(median {_format_money(option.cost.median, option.cost.unit)}, "
                f"{option.cost.sample_size} related gigs; "
                f"relevance: {option.cost.relevance})."
            )
        else:
            lines.append("There is not enough related price data for this option.")
        sections.append("\n".join(lines))
    sections.append(
        "These are different project scopes, not three technologies that should "
        "be combined. You can choose one option and I can refine it further."
    )
    return "\n\n".join(sections)


def build_response(slots: ExtractedSlots, context: ChatContext, data: ChatData) -> str:
    if slots.needs_clarification:
        return slots.clarification_question or "Could you describe the project you want to build?"

    sections: list[str] = []
    if Intent.EXPLAIN_PROJECT in slots.intents:
        sections.append(
            slots.advisory_response
            or (
                "I can explain the proposed features and workflow. Tell me which "
                "part you would like to explore in more detail."
            )
        )

    if Intent.SUGGEST_TECHNOLOGY in slots.intents and data.technology_used:
        technology_section = "Suggested technology: " + ", ".join(data.technology_used) + "."
        if slots.technology_rationale:
            technology_section += f"\n{slots.technology_rationale}"
        sections.append(technology_section)

    if Intent.COUNT_TALENT in slots.intents:
        skill_label = ", ".join(data.search_terms) or "those requirements"
        total = data.total_matches or 0
        noun = "freelancer" if total == 1 else "freelancers"
        sections.append(
            f"Marketplace availability: {total} {noun} match {skill_label}."
        )

    if Intent.FIND_DEVELOPER in slots.intents:
        if data.developers:
            lines = _grouped_developer_lines(
                data.developers,
                data.search_terms or data.technology_used,
            )
            sections.append("\n".join(lines))
        else:
            sections.append("I could not find a strong freelancer match for those requirements.")

    if Intent.ESTIMATE_COST in slots.intents:
        if data.cost:
            sections.append(
                "Estimated marketplace price: "
                f"{_format_money(data.cost.low, data.cost.unit)}–"
                f"{_format_money(data.cost.high, data.cost.unit)} "
                f"(median {_format_money(data.cost.median, data.cost.unit)}, "
                f"based on {data.cost.sample_size} related gigs; "
                f"relevance: {data.cost.relevance}, "
                f"data volume: {data.cost.data_volume})."
            )
        else:
            sections.append("There is not enough matching price data for an estimate.")

    if Intent.ESTIMATE_TIME in slots.intents:
        if data.time:
            sections.append(
                "Estimated delivery time: "
                f"{_format_number(data.time.low)}–{_format_number(data.time.high)} days "
                f"(median {_format_number(data.time.median)}, "
                f"based on {data.time.sample_size} related gigs; "
                f"relevance: {data.time.relevance}, "
                f"data volume: {data.time.data_volume})."
            )
        else:
            sections.append("There is not enough matching delivery data for an estimate.")

    if context.budget is not None and data.cost and context.budget < data.cost.low:
        sections.append(
            "Your stated budget is below the lower estimate, so scope or delivery "
            "expectations may need adjustment."
        )
    return "\n\n".join(sections)
