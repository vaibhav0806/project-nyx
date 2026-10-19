# R7 — Instinct: interaction and memory lessons

Owner: inline product/implementation session
Status: initial desk findings; broader alternatives/adoption research remains open
Date: 2026-10-20
Decision affected: companion conversation, continuing requests and interruption behavior

## Question and method

The user asked how Instinct handles personal-assistant UX and memory, as inspiration for Nyx's product behavior. Review public first-party pages and one reported hands-on account. No account was created, service exercised, personal account connected, purchase made or message sent. This is source review, not measured usability or a reconstruction of its implementation.

## Source-reported findings

Instinct's public homepage presents a personal assistant reached through text or calls, able to operate a phone/computer and complete ordinary errands. Its examples describe outcomes such as travel and grocery tasks. The product proposition reduces the need to learn a separate tool interface. This establishes its positioning, not successful execution rates. [Official homepage](https://instinct.com/), accessed 2026-10-20.

The privacy policy describes using accessible information to understand requests, plan tasks and personalize suggestions using earlier interactions. Connected communications and documents can provide context, depending on permissions. Disconnecting an integration does not automatically delete information collected from it; a separate deletion route is described. These statements support retained context as a product capability, but reveal no retrieval architecture, consolidation algorithm, memory schema, context budget, or correctness benchmark. [Official privacy policy](https://instinct.com/privacy-policy), revised 2026-08-26, accessed 2026-10-20.

The terms distinguish generated output from actions and describe indexing connected information. They grant broad action authority; they do **not** establish a universal ask-before-every-action guarantee. Avoid repeating third-party descriptions of approval behavior as a verified product invariant. [Official terms](https://instinct.com/terms), revised 2026-08-26, accessed 2026-10-20.

A reporter's hands-on account describes lightweight message reactions, typing/read indicators and periods of silence while work proceeds. This suggests acknowledgement and completion can happen separately in a familiar conversation. It is one person's experience, not independent evidence about long-term memory quality or older-adult usability. [The Atlantic, 2026-09-13](https://www.theatlantic.com/technology/2026/09/instinct-ai-personal-assistant-credit-card/688607/).

## Inferred lessons for Nyx

These are product interpretations, not claims about Instinct's internal system:

1. **Accept the task in the user's language.** “Find the reading ones” should use conversational context to choose and refine tools. Requiring the person to write an embedding query is unnecessary interaction work.
2. **Separate acknowledgement, work and outcome.** “Checking the recent recording” is progress; “I saw them beside the chair at 10:12” needs evidence. A fluent acknowledgement must not imply the task succeeded.
3. **Represent continuing requests outside chat prose.** A departure reminder needs a durable condition, active/cancelled state and a delivery attempt. Merely retaining its sentence in a prompt does not make it dependable.
4. **Speak when there is a useful result or decision.** Background image changes should usually stay quiet. A user-requested reminder is a reason to interrupt, subject to fresh evidence and current playback state. One event should not generate repeated announcements.
5. **Make remembered context correctable and inspectable.** User statements, assistant hypotheses and observed scenes need different attribution. Retention, source deletion and cancellation should have visible effects. Nyx currently has bounded conversation history and event requests; general personal memory remains unimplemented.

The current slice implements portions of these lessons through shared typed/voice tools, visible progress, source-linked answers and separate event/delivery records. It does not establish that the interface is easy for intended users. The page still exposes developer-oriented controls; reducing that surface should follow observed user tasks.

## Recommendation and open evidence

Keep two narrow product demonstrations: contextual object finding, and a next-departure reminder. Define their success by the user's outcome, including how often Nyx speaks incorrectly, interrupts unnecessarily, fails silently, or needs repair. For each, observe whether a person can understand the answer and cancel/correct it without learning the implementation.

Do not add WhatsApp, general errands or an elaborate memory framework solely to resemble Instinct. No public source reviewed establishes its memory engineering or a suitable architecture for continuous household vision. R1/R2 intended-user work and R8's independent event evaluation remain the next evidence needed. The broader five-alternative R7 comparison, buyer/installer questions and actual adoption research are still open.
