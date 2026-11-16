"""Frozen household utterances; test data must never be imported by application code."""

CASES = [
    {
        "id": "current-glasses",
        "split": "development",
        "text": "Can you see my glasses right now?",
        "tool": "look_for_object",
        "arguments": {"history": False},
    },
    {
        "id": "latest-keys-report",
        "split": "development",
        "text": "What is the latest place I told you I kept my keys? Search my saved reports, not the camera.",
        "tool": "search_statements",
        "arguments": {"selection": "latest_report"},
    },
    {
        "id": "unfulfilled-plan",
        "split": "development",
        "text": "I'm going to keep my medicine box in the drawer. I haven't put it there yet. Remember that plan.",
        "tool": "remember_statement",
        "arguments": {},
    },
    {
        "id": "shown-pronoun-hi",
        "split": "development",
        "text": "ये कहाँ है? मैं आपको दिखा रही हूँ।",
        "tool": "identify_shown_object",
        "arguments": {},
    },
    {
        "id": "unsupported-clock",
        "split": "development",
        "text": "Remind me in ten minutes to drink water.",
        "tool": None,
    },
    {
        "id": "historical-phone",
        "split": "development",
        "text": "Where did you last see my phone yesterday?",
        "tool": "look_for_object",
        "arguments": {"history": True},
    },
    {
        "id": "current-phone-hinglish",
        "split": "holdout",
        "text": "Mera mobile phone abhi camera mein dikh raha hai kya?",
        "tool": "look_for_object",
        "arguments": {"history": False},
    },
    {
        "id": "latest-glasses-hi",
        "split": "holdout",
        "text": "मेरे चश्मे के बारे में मैंने सबसे आखिर में कौन सी जगह बताई थी? मेरी सेव की हुई बात देखो।",
        "tool": "search_statements",
        "arguments": {"selection": "latest_report"},
    },
    {
        "id": "plan-wallet-hi",
        "split": "holdout",
        "text": "मैं अपना बटुआ अलमारी में रखने वाली हूँ। अभी नहीं रखा है। यह योजना याद रखना।",
        "tool": "remember_statement",
        "arguments": {},
    },
    {
        "id": "shown-pronoun-en",
        "split": "holdout",
        "text": "I'm showing you this. Where did you last see it?",
        "tool": "identify_shown_object",
        "arguments": {},
    },
    {
        "id": "general-question",
        "split": "holdout",
        "text": "Tell me a short joke about the weather.",
        "tool": None,
    },
    {
        "id": "explicit-correction",
        "split": "holdout",
        "text": "Please correct my saved statement about the TV remote: I was wrong about the sofa. It was on the desk.",
        "tool": "search_statements",
        "arguments": {},
    },
]


def score(case, calls):
    if case["tool"] is None:
        return not calls
    return any(
        call["name"] == case["tool"]
        and all(
            call["arguments"].get(key, False if key == "history" else None) == value
            for key, value in case["arguments"].items()
        )
        for call in calls
    ) and not any(
        call["name"] == "remember_statement"
        for call in calls
        if case["tool"] != "remember_statement"
    )
