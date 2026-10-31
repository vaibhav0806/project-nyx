# Nyx — Product direction

Agreed direction · 31 October 2026

## Positioning

**Nyx is a personal AI companion that helps older adults live independently at home, on their own terms.**

**Your own space. Your own routine. A little help from Nyx.**

We are starting with older adults living at home, especially those living alone who want help remembering everyday details and a natural companion to talk to. The person themselves or their family may buy and set up Nyx; the older adult remains the primary user.

## The product

Nyx is being built as a small, stationary device with a camera, microphone, and speaker. Place it in a room and say “Hey Nyx.” Ask naturally, get a simple spoken answer, and continue the conversation.

The starting promise is **“Help me remember what happened around me.”** Find belongings, recall useful moments, and spend less time searching or asking someone else for help.

One device can only answer from the room and moments it captured. Source recordings should be available when wanted, without becoming the main experience.

## Features

The full product should help you **find things, remember people and moments, get answers, and follow through on plans.** These are intended capabilities; current availability is described below.

| Feature | What you can ask |
| --- | --- |
| Find your belongings | “Where did I keep my glasses?” |
| Remember people and visits | “Who came by today?” Recognize familiar people with their consent and enrollment, within camera coverage. |
| Recall what happened | “What happened in this room this morning?” |
| Remember what you said | “Where did I say I would keep my phone?” or “Was there anything else I asked you to remember?” |
| Answer everyday questions | “Can you explain how this works?” |
| Keep reminders | “Remind me to call my daughter at six.” |
| Reach trusted people | “Call my daughter.” |
| Be there for a conversation | “Hey Nyx, what's up?” |

## Security and privacy

**The intended product keeps your recordings and personal memory on the device.** Core recall and conversation should use local vision models, local language models, and local speech recognition and generation, so private images, audio, and conversations do not need to leave the device for processing.

- **Stored on your device:** recordings and personal history stay under your control, with no automatic cloud upload.
- **Processed on your device:** the target is fully local core assistance, including seeing, understanding, listening, and speaking.
- **Connected only when needed:** calls and online searches require external services. Make that clear and send only the information needed for the requested action.
- **Control and protection:** simple pause, mute, and deletion controls, restricted access to history, encrypted storage, and secure updates are product requirements. Family access should follow the person's choices.

Local processing reduces exposure to cloud services; device security and access controls still matter. Hardware performance, response quality, and these protections need validation before we promise them as delivered features.

**Today:** the prototype saves full video recordings locally but uses cloud services for selected images, activated speech, and relevant conversation context. It is not yet fully local. This section defines the target product architecture, not a completed migration; see the [current data flow](README.md#privacy-and-control).

## Direction

Start with everyday recall and natural conversation. Build toward lasting memory, reminders, recognition of enrolled familiar people, and requested calls to family or trusted contacts. Over time, Nyx can become a personal concierge that understands its surroundings and helps with everyday requests.

Dedicated hardware and these broader capabilities are planned work. The current browser-based product supports visual search, recorded history, source review, and English/Hindi voice conversation. Reliable long-term recall is unfinished; departure reminders are experimental. [Milestones](docs/milestones.md) tracks implementation status.

## Personality and trust

Calm, relaxed, attentive, and a little witty—a perceptive friend with a dry sense of humor who does not need to fill every silence. **Easy to talk to, not clever to listen to.** Use short sentences and familiar spoken words. Never patronize someone or joke about forgetting things.

Keep what Nyx saw distinct from what someone told it. Say “You told me you were going to keep it in the kitchen” when that is the evidence. Be honest about uncertainty and missing coverage.

Independence includes control: clear recording indicators, simple pause and mute controls, and intentional access to personal history. Family involvement should respect the person's choices. Existing [scope and data boundaries](docs/scope.md) remain unchanged.

## Pitch

> Nyx helps older adults live independently at home. We're building a small companion device that can see, hear, and talk, so someone can find their belongings, recall everyday moments, and get help just by asking. We're starting with everyday recall and natural conversation, then building toward reminders, lasting memory, and easy access to trusted people—all to give people more freedom over daily life.
