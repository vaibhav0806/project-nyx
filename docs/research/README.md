# Research board

Status: R3/R4/R6/R8 contain local prototype findings, with independent household/user evaluation pending. R7 has an initial public-source Instinct review; its broader comparison remains open. No interviews were conducted or external messages sent. Research assignments are prepared for people to accept.

Research should answer a bounded question that changes a decision. Keep product evidence, source-reported capabilities, local measurements, and interpretation separate.

## Questions and assignments

| ID | Question | Assignment | Output | Owner / status |
| --- | --- | --- | --- | --- |
| R1 | Which recurring situations most affect everyday independence? | Interview roughly five older adults about recent concrete incidents, consequences, frequency, workarounds and help received. Gather relatives' views separately. | Three ranked workflows, anonymized evidence, and disconfirming findings | Unassigned / proposed |
| R2 | Where can Nyx fit physically and conversationally? | Explore camera coverage/blind spots, recording expectations, preferred language, clarification and reminder interaction. Role-play the selected tasks. | Two or three placement sketches, interaction examples, accepted controls and unresolved concerns | Unassigned / proposed |
| R3 | Can a light encoder retrieve useful household moments? | Compare a small aligned image/text encoder on the same labelled images/clips, including small/hidden objects and negatives. | Reproducible recall@k, latency, memory, throughput and failure cases; recommended baseline | In progress / local baseline measured; household evaluation pending |
| R4 | How reliably can a VLM verify candidates and give grounded guidance? | Compare a small number of local VLMs on identical retrieved/fresh frames; score correct, wrong and uncertain answers. | Quality/resource comparison and evidence-grounding failures | [First local findings](R4-local-verification.md) / in progress |
| R5 | What useful role can JEPA play, including prediction? | Start with pretrained feature extraction and Mac compatibility. Compare event selection to motion detection; define any prediction task, required head/alignment/data, and evaluation separately. | Runnable experiment, measured event recall/false triggers/resource use, and an explicit integrate/defer recommendation | Unassigned / proposed; teammate expressed interest |
| R6 | Which cloud voice path works for the chosen user/language? | Trial comprehension, follow-ups, interruptions, echo and backend tool calls. | Short recordings where permitted, latency breakdown, observed limitations and usage | [Initial hands-free findings](R6-handsfree-voice.md) / in progress |
| R7 | What alternatives and adoption constraints matter? | Compare about five relevant products/current workarounds from primary sources and actual user evidence. Explore who chooses, installs, maintains and pays. | Dated capability/pricing matrix, user objections, buyer/adoption hypothesis and gaps | [Initial Instinct UX findings](R7-instinct-ux.md); broader comparison/adoption work open |
| R8 | Can conversation-aware local tools and continuous observation support useful next-departure assistance? | Exercise contextual query construction, adaptive selection, local sequence judgments and durable event delivery. | [Measured prototype findings](R8-companion-loop.md), failures and remaining gates | In progress / inline implementation |

R1/R2 can run alongside early technical feasibility work once separately authorized. R5 does not block the initial R3 retrieval baseline. Do not assign a person or deadline without their agreement.

## Ready-to-share product brief

We’re exploring Nyx, a voice-based home companion intended to support older adults’ independence. Before showing the concept, ask about recent moments when the person needed help finding something, remembering something, following a routine, or recalling an earlier event. Capture what happened, frequency, consequences, current workarounds and who helped. Then explore the proposed interaction and what recording/controls would be acceptable.

Return three promising workflows with evidence and anything that argues against building them. Separate older adults' answers from relatives' expectations. Use anonymized findings; get permission for recordings and retain raw material privately.

## Ready-to-share technical brief

Determine whether a lightweight visual representation improves Nyx's ability to retrieve relevant moments or select meaningful events from recorded household scenes. Use identical permitted clips and explicit labels for comparisons. Test aligned image/text retrieval separately from JEPA/motion event selection; these tasks have different outputs and success criteria.

For JEPA prediction, name exactly what is predicted, over what horizon, how the latent output is evaluated, and what extra head, text alignment, or training data is required. Demonstrate a pretrained feature-extraction run before making performance or deployment claims. Record the actual Mac/device/runtime path and compatibility problems. LeRobot is a possible future robotics integration topic, not a prerequisite for this task.

## Findings format

Create `docs/research/<question-id>-<topic>.md` when a person begins work:

```markdown
# Rn — Research question

Owner: <accepted owner>
Status: proposed / in progress / findings ready / closed
Date: YYYY-MM-DD
Decision affected: <decision or milestone ID>

## Question and hypothesis
What do we need to learn, and what result would change our approach?

## Method and inputs
Participants or permitted dataset, procedure, labels, comparison baseline.
For technical work: hardware, model ID/revision, runtime versions,
preprocessing, exact command, and raw-result location.

## Findings
Separate measured/observed facts, source-reported claims, and inference.
Include anonymized quotes or metrics and representative failures.

## Limitations and counterevidence
What did this not establish? Which examples contradicted the hypothesis?

## Recommendation
Integrate, revise, defer, or run a specified follow-up. Name the decision owner.

## Sources and artifacts
Dated primary links, permitted fixtures, commands, and private-artifact references.
```

## Evaluation rules

- Record accuracy and failure examples as well as speed. A fast wrong answer is still wrong.
- Use time/object/event ground truth for video retrieval. Similarity scores are not calibrated correctness probabilities.
- A JEPA feature-change score is not itself proof of a meaningful household event.
- Avoid asking only “would you use this?” Ask about actual incidents and observe interaction.
- Keep benchmark inputs, versions, and evaluation method stable across model comparisons.
- Findings become decisions through review in [Decisions](../decisions.md); promising research is not shipped capability.
