# Nyx — Product direction

Agreed direction · 31 October 2026

## Positioning

**Nyx is a personal AI companion that helps older adults live independently, on their own terms—at home or in senior living.**

A small device that can see, hear, and talk, Nyx is being built to help people find everyday things, remember what happened, manage reminders, and reach people they trust through a simple conversation.

**The promise:** more freedom in everyday life, with a little support when you want it.

**Headline:** Your own space. Your own routine. A little help from Nyx.

This document defines the product direction. Planned capabilities below are not claims about the current release. Implementation status lives in [Milestones](docs/milestones.md).

## Who it is for

Older adults who want practical help remembering everyday details and a natural companion they can talk to. Memory difficulties are one reason to use Nyx; they do not define the person or imply that every older adult has the same needs.

There are two living settings with different support needs:

| Setting | Value for the person | Potential buyer or setup partner |
| --- | --- | --- |
| Living alone at home | Handle more everyday tasks independently, recall things, talk naturally, and reach trusted people when needed. | The person themselves or their family. |
| Senior living or a care home | Keep control over personal routines and get help with small questions without needing to ask staff every time. | A senior-living operator, care home, or family. |

The older adult is the primary user, whoever buys the device. Nyx should support their choices and dignity. Family and staff support should follow their preferences and agreed access controls.

The initial experience is for people who can ask Nyx a question and use its reply. Needs associated with more substantial memory difficulties require separate research and validation; this is not a claim to treat amnesia or another medical condition. The first deployment setting and buyer remain to be validated.

## The problem

Small gaps in everyday recall can interrupt a person's day: where they left their glasses, what they said they would do, or whether someone visited earlier. Repeatedly needing another person to answer these questions can reduce the freedom to follow their own routine.

Nyx makes help available through conversation. The person should not have to search through recordings, learn an interface, or remember exact commands to get a useful answer.

## The product experience

The intended product is a stationary device with a camera, microphone, and speaker. It sits in a chosen room with a useful view of the space. Say “Hey Nyx” and ask naturally; Nyx answers aloud and keeps the conversation going when needed.

The first promise is **“Help me remember what happened around me.”** Start with finding things and recalling useful moments. Build toward a personal concierge that understands the person's surroundings and helps with everyday requests.

Examples of the intended experience:

- “Where did you last see my glasses?” — Recall the last supported sighting and a useful physical location.
- “Where did I say I would keep my phone?” — Recall what the person said, without claiming the planned action happened.
- “Did someone visit this afternoon?” — Search retained events within the device's coverage.
- “Remind me to call my daughter at six.” — Save and deliver a reminder, with clear confirmation.
- “Call my daughter.” — Help reach a trusted contact on request.
- “Hey Nyx, what's up?” — Have a relaxed conversation without forcing every exchange into a search or task.

One device covers what it can observe in its room. Whole-home awareness requires additional coverage; unseen events cannot be reconstructed from missing recordings.

## What we are building toward

| Capability | Product purpose |
| --- | --- |
| Everyday visual recall | Find belongings and recall when and where they were last seen. |
| Lasting personal memory | Remember useful facts, conversations, corrections, and events across days. |
| Natural companionship | Be easy to talk to, whether the person needs help or simply wants a conversation. |
| Reminders | Help people carry out their own plans and routines. |
| Familiar-person recognition | With explicit enrollment and consent, help recall who visited within camera coverage. |
| Requested calls | Reach family, trusted contacts, or a designated emergency contact when asked. |
| Everyday assistance | Answer general questions and, through future integrations, search for information and carry out useful requests. |
| Optional source review | Let the person inspect the moment behind an answer without making recordings the main experience. |

This is a direction, not a promise that Nyx can do everything. Reliable everyday recall is the starting point. Dedicated hardware, dependable long-term memory, scheduled reminders, identity recognition, calling, and broader integrations remain future work. Automatic emergency detection is a separate capability requiring its own scope and validation.

## How Nyx should feel

Calm, relaxed, attentive, and a little witty: a perceptive friend with a dry sense of humor who does not need to fill every silence.

**Easy to talk to, not clever to listen to.** Use very simple spoken language, short answers, and familiar words. The person should understand on first hearing without needing to read or know technology. Never patronize them or joke about forgetting things.

Answer in human terms: “You told me you were going to keep it in the kitchen.” Use local time and natural relative times. Keep uncertainty brief and honest. Do not turn an uncertain match into a confident invention.

## Trust and control

Independence includes control over the device. Recording and listening should be visible, with simple ways to pause, mute, inspect, and delete. Access to personal history should be intentional; buying the device should not automatically grant someone access to everything it captures.

Keep what Nyx saw, what someone told it, and what it inferred distinct. Explain coverage gaps when they affect an answer. Companionship complements human relationships and care.

Lead the product story with independence and everyday support. Explain the camera clearly without making “always watching” the product promise.

## Current foundation

The current product runs as a local browser application and Python service with one camera view. It includes continuous video recording, background indexing, current-view and historical object search, source review, and English/Hindi voice conversation. Conversation transcripts persist, but reliable long-term recall is unfinished. Departure reminders are experimental.

The laptop is the development platform; the intended product is dedicated hardware. This direction does not change existing recording, retention, provider, or implementation permissions. See [Scope](docs/scope.md) and the [README](README.md) for current boundaries.

## Pitch

> Nyx helps older adults live independently, on their own terms. We're building a small companion device that can see, hear, and talk—so someone can find their belongings, recall everyday moments, and get help just by asking. We're starting with everyday recall and natural conversation, and building toward reminders, lasting memory, and easy access to trusted people. At home or in senior living, the goal is the same: more freedom over daily life.
