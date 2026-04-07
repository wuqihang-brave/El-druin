# PHILOSOPHICAL FOUNDATION OF EL'DRUIN

## A Formal Account of the Project's Motivating Philosophy

---

> *"The moving cause is the first whence the change or rest proceeds. The final cause is that
> for the sake of which a thing is done — as health is the cause of walking. For why does one
> walk? We say 'in order to be healthy', and, having said this, we think we have assigned the cause."*
>
> — Aristotle, *Physics*, Book II, Chapter 3 [Aristotle, 350 BCE]

> *"The blade of El'druin cannot harm those holding righteous intent."*
>
> — Project epigraph

---

## 1. The Foundational Problem: On the Accountability of Inference Systems

Modern prediction systems have undergone a remarkable transformation. Where classical
statistical forecasting demanded explicit model specification — requiring the analyst to
commit, in advance, to a set of causal assumptions that could subsequently be tested —
large language models (LLMs) have introduced a regime in which prediction emerges from
the interpolation of vast corpora rather than from principled structural hypotheses.
This shift carries underappreciated epistemic consequences.

Kahneman distinguishes between "System 1" cognition — fast, associative, and opaque —
and "System 2" cognition — slow, deliberate, and auditable [Kahneman, 2011]. Contemporary
LLM inference architectures instantiate a sophisticated form of System 1: they produce
confident-sounding outputs through pattern interpolation without exposing a traceable
inference path that could be examined, challenged, or corrected. The result is an inference
apparatus that is, in a structurally important sense, unable to criticise its own outputs.

This concern is not merely technical. Taleb's analysis of "Black Swan" events demonstrates
that precisely the events most consequential for human welfare — financial crises,
pandemics, geopolitical ruptures — are those least well-captured by models calibrated
on historical frequency distributions [Taleb, 2007]. When an LLM confidently interpolates
toward a plausible-sounding prediction in a domain with sparse historical precedent,
it may produce a systematically misleading confidence signal with no mechanism for
self-correction.

Miranda Fricker's account of epistemic injustice provides a complementary lens
[Fricker, 2007]. Fricker identifies "testimonial injustice" as the systematic
deflation of a speaker's credibility due to identity prejudice, and "hermeneutical
injustice" as the gap in collective interpretive resources that prevents a group from
making sense of their own experience. Applied to inference systems, a closely analogous
harm arises when opaque prediction outputs are deployed in consequential decisions —
asylum determinations, credit scoring, resource allocation — and the affected individuals
lack both the technical vocabulary and the institutional standing to challenge them.
A system that cannot expose its reasoning cannot be held accountable; a system that
cannot be held accountable will disproportionately harm those with the least power to
resist its verdicts.

The thesis of this document is the following: **a prediction system whose core inference
chain is mathematically deterministic and algebraically traceable offers a structural
solution to the accountability problem**. Not because determinism is epistemically superior
in every domain — stochastic systems have irreplaceable value — but because determinism
enables auditability, and auditability enables accountability. El'druin is designed
from its foundations to make every intermediate inference inspectable.

---

## 2. From Aristotle's Four Causes to Ontological Logical Edges

Aristotle's metaphysics distinguishes four types of explanatory cause [Aristotle, 350 BCE]:

- **Material cause** (*hyle*): the substrate from which a thing is made.
- **Formal cause** (*morphe*): the pattern, structure, or definition that makes the thing
  what it is.
- **Efficient cause** (*arche tes kineseos*): the proximate agent or mechanism that
  brings the change about.
- **Final cause** (*telos*): the end or purpose toward which the change is oriented.

This fourfold structure, developed in the context of natural philosophy, anticipates the
structure of modern causal modelling. Efficient causation corresponds to the structural
equations of a causal Bayesian network [Pearl, 2000]. Formal causation maps naturally
onto ontological type hierarchies — the abstract schema constraining which entities can
stand in which relations. Final causation prefigures attractor-state reasoning in
dynamical systems: a system evolves toward a stable configuration because the structure
of the state space biases trajectories in that direction.

El'druin operationalises this Aristotelian framework through the concept of the
**ontological logical edge**: a directed, typed connection between two ontological states
(entities, relations, or structural configurations) that encodes an efficient-causal
dependency. A logical edge is not a probabilistic correlation — it is a structural
claim: *if state A obtains and conditions C are met, then the transition to state B is
permitted by the formal structure of the domain*.

The accumulation (serial composition) of logical edges constitutes the mechanism of
event development. Where a single logical edge encodes a local causal step — an actor
imposes an export control, a state responds with domestic substitution — a composed
chain of edges encodes a historical trajectory: sanction → decoupling → domestic
acceleration → technology gap. The formal structure of this chain is not asserted by
an LLM interpolating from surface patterns; it is derived from an explicit ontological
schema [McGuinness & van Harmelen, 2004] in which entity types, relation types, and
their permitted compositions are specified in advance.

This approach connects naturally to the traditions of knowledge graph reasoning
[Hogan et al., 2021] and ontology engineering [Noy & McGuinness, 2001]. Unlike purely
statistical knowledge graph completion methods (e.g., TransE, RotatE), which learn
embeddings from link co-occurrence without structural commitments, El'druin's ontological
edges carry explicit formal semantics. Each edge activation has a derivation traceable
to the underlying schema — the formal cause, in Aristotle's vocabulary.

---

## 3. The Dimensional Ascent: From Logical Edges to Lie Algebra

The key theoretical insight underlying El'druin's mathematical engine is the following
**dimensional ascent principle**: the accumulation of logical edges in ontological space
can be modelled as vector addition in a higher-dimensional abstract space, and the
geometry of that space captures constraints on valid compositions that cannot be
expressed at the object level.

More precisely: if each ontological pattern (a cluster of co-occurring logical edges
representing a recognisable structural configuration — "hegemonic sanctions", "military
coercion", "technology decoupling") is represented as a vector in an eight-dimensional
state space, then the composition of two co-active patterns can be approximated by
their vector sum. The dimensionality eight is not arbitrary: it corresponds to eight
orthogonal semantic dimensions of geopolitical state space identified through domain
analysis — coercion intensity, alliance consolidation, information asymmetry, resource
dependency, technological capability gap, normative legitimacy, economic interdependence,
and domestic consolidation pressure. These dimensions span the observable outcomes
documented in the system's outcome catalogue.

Standard vector addition, however, is commutative: *A + B = B + A*. Historical causation
is not commutative. The sequence "sanctions → domestic substitution" has materially
different consequences from the sequence "domestic substitution → sanctions", because the
first sequence triggers a defensive industrial policy that pre-empts the second sequence's
counterfactual impact. This irreversibility of historical processes is a fundamental
structural feature that any adequate formal model must capture.

Lie algebra provides the natural algebraic structure for non-commutative composition
[Humphreys, 1972]. The **Lie bracket** [X, Y] = XY − YX captures precisely the
*failure of commutativity*: it measures the extent to which applying X then Y differs
from applying Y then X. In El'druin's implementation, patterns are embedded as
antisymmetric matrices in *so*(8) — the Lie algebra of the special orthogonal group
*SO*(8) — via the hat map that maps each eight-dimensional pattern vector to a skew-
symmetric matrix. The Lie bracket [X, Y] = X·Y − Y·X (matrix commutator) then yields
a new matrix whose Frobenius norm measures the degree of non-commutativity of the
composition, and whose direction encodes the differential effect of ordering.

A large Lie bracket norm (exceeding the phase transition threshold) signals a
**phase transition** in the system's trajectory: the order of pattern activation matters
enough that the two possible orderings produce qualitatively distinct outcomes. This
signal is surfaced to the analyst as a flag on the probability tree, indicating that
the prediction is sensitive to the temporal ordering of causal factors — an epistemic
warning that is structurally impossible to generate from a purely statistical model.

The algebraic structure is further constrained by the requirement of **partial
semigroup closure**: not all pairs of patterns are composable. If two patterns are
ontologically incompatible — if their formal causes are contradictory — their composition
is undefined, and the system declines to produce an output rather than producing a
spurious one. This "honest incompleteness" — following Gödel's insight that a sufficiently
expressive formal system cannot be both complete and consistent [Gödel, 1931] — is a
deliberate design choice. A system that produces a confident output for every input is
not more capable than one that refuses to answer when its assumptions are violated; it
is simply less honest.

---

## 4. The Role of LLM as Translator, Not Reasoner

The architecture of El'druin enforces a **strict functional separation** between
the mathematical inference engine and the natural language interface. LLMs participate
in exactly three stages, each carefully bounded:

1. **Stage 1 — Information extraction**: The LLM reads a natural-language news fragment
   and extracts structured events — entity types, relation types, claim confidence, and
   temporal ordering. This is a *translation* task: converting human language into the
   formal vocabulary of the ontological schema. The LLM does not reason about geopolitical
   consequences at this stage; it performs syntactic and semantic parsing into a
   pre-specified type system.

2. **Final rendering — Language output**: After all numerical inference is complete and
   all probability values are locked, the LLM performs a second translation: converting
   the deterministic output of the inference engine (outcome labels, confidence intervals,
   driving factor rankings) into professional intelligence prose. Guardrails prevent the
   LLM from modifying numerical values, introducing unanchored entities, or using internal
   jargon. If the guardrails are triggered, the system falls back to a deterministic
   template.

3. **Backtesting calibration advisory — Qualitative feedback**: When the backtesting
   framework detects a prediction error, the LLM is invited to provide a *qualitative*
   advisory on whether the confidence prior for the mis-fired pattern should be increased,
   decreased, or maintained. The LLM is explicitly prohibited from outputting numbers.
   Its role is to provide human-interpretable natural-language rationale for a calibration
   decision that a human analyst must then make.

The **core inference** — Stages 2a through 2d and the Stage 3 Bayesian posterior
computation — is entirely deterministic and algebraic. No LLM token probabilities enter
the inference chain. The confidence values that appear in the final output are derived
from: the ontological pattern confidence priors (hand-calibrated domain parameters),
the Lie bracket composition results, the Bayesian posterior weighting across transition
edges, and the composite credibility assessment. Each of these quantities has a closed-
form derivation traceable to its inputs.

This separation resolves the foundational accountability problem. The LLM components
operate in bounded, auditable roles — translation and rendering — where their known
weaknesses (hallucination, overconfidence, self-consistency failures) have limited
impact on the epistemic integrity of the output. The mathematical engine, operating
independently of LLM stochasticity, produces results that are reproducible, inspectable,
and in principle formally verifiable.

The analogy is precise: the LLM functions as the **interface layer** between human
language and formal mathematical structure, in the same way that a compiler translates
human-readable source code into machine instructions without participating in the
logical structure of the program it compiles. The compiler can make syntactic errors;
it does not introduce new logical dependencies. Similarly, El'druin's LLM can make
phrasing errors; it cannot modify the algebraic derivation of the confidence values
it is asked to describe.

---

## 5. Justice Through Auditability: The Ethical Dimension

The connection between formal auditability and justice is not merely rhetorical.
It has a precise structural form.

A decision is *contestable* if and only if the basis for that decision can be examined
by the party affected. Contestability is a necessary condition for meaningful recourse:
an individual cannot challenge a conclusion whose derivation is inaccessible to them.
Opaque inference systems — whether LLM-based or otherwise — systematically undermine
contestability by producing conclusions without traceable derivations.

The asymmetry of impact is structural. Those with institutional power can commission
independent technical audits, retain expert witnesses, and navigate judicial processes
designed for adversarial technical fact-finding. Those without such resources cannot.
An inference system that cannot be examined therefore harms the powerful and the
powerless unequally — not because of any explicit bias in its outputs, but because
the structural inaccessibility of its reasoning converts raw predictive error into
systematic injustice for those least equipped to challenge it.

El'druin's design commits to the following principle: **every confidence value in the
output has a traceable derivation; no number is asserted without algebraic grounding**.
The probability tree audit log records every intermediate computation. The driving
factor ranking exposes which ontological edges contributed most to the final posterior.
The credibility assessment decomposes into verifiability score, knowledge graph
consistency score, and hypothesis ratio — each independently interpretable.

This is not mere transparency theatre. The goal is to make the system's reasoning
available for meaningful challenge. A domain expert who disagrees with a confidence
value can trace its derivation to the specific pattern prior and composition result
from which it was computed, and can propose a specific correction — not a vague
objection to the "black box", but a targeted argument about a particular algebraic
parameter.

The blade metaphor that names this project captures the ethical commitment precisely.
A blade that cannot harm those holding righteous intent is a blade whose application
is constrained by the formal properties of its target, not merely by the intent of
its wielder. El'druin's formal constraints — the ontological schema, the algebraic
composition rules, the Bayesian prior structure — function as moral commitments
embedded in the mathematical architecture of the system. They constrain what the
system can assert, independently of the downstream uses to which its outputs are put.

---

## 6. Generalisability Beyond Geopolitics

The mathematical framework underlying El'druin is domain-agnostic. The specific
choice of geopolitical ontology — the eight semantic dimensions, the pattern catalogue,
the outcome vocabulary — reflects the domain of initial application, not any constraint
of the underlying formalism.

The universal structure is the following:

1. **Domain ontology**: a typed schema of entities, relations, and their permitted
   compositions, encoding the formal-causal structure of the domain.
2. **Pattern activation**: mapping observed events to ontological patterns with
   associated confidence priors.
3. **Lie algebra composition**: computing the Lie bracket structure of co-active
   patterns to identify non-commutative dynamics and phase transitions.
4. **Bayesian posterior**: weighting outcome predictions by the posterior probability
   of each transition path given the evidence.
5. **Outcome prediction**: mapping the posterior-weighted composition result to the
   outcome catalogue of the domain.

This structure is applicable wherever three conditions hold: (a) the domain admits
a formal ontological schema with typed entities and relations; (b) observed events
can be reliably parsed into instances of this schema; and (c) the composition of
causal patterns is not always commutative.

These conditions are met in a wide range of domains beyond geopolitics. In
**epidemiology**, the composition of transmission pathways, population immunity states,
and non-pharmaceutical intervention patterns is non-commutative: the sequence "mask
mandate → vaccination" has different population-level dynamics than "vaccination →
mask mandate" [Anderson & May, 1991]. In **market microstructure**, the ordering of
liquidity shocks and regulatory interventions determines qualitatively different
equilibrium paths [Kyle, 1985]. In **legal reasoning**, the sequence of precedent
citation and statutory interpretation is formally non-commutative in appellate courts
with stare decisis obligations [Dworkin, 1986]. In **social movement dynamics**,
the ordering of repression and grievance articulation determines whether movements
consolidate or fragment [Tarrow, 2011].

The claim is not that El'druin's current implementation is immediately applicable
to these domains — domain-specific ontological engineering would be required in each
case. The claim is that the mathematical engine is domain-general, and that the
effort required to apply it to a new domain is the effort of ontological specification,
not of fundamental architectural redesign.

---

## 7. Limitations and Future Work

The current system has two principal limitations that are acknowledged explicitly
rather than obscured.

**Limitation 1: Hand-calibrated confidence priors.** The confidence prior values
assigned to each ontological pattern in the current implementation are calibrated
by domain expertise rather than derived empirically from historical backtesting.
This means the system's outputs reflect the calibrator's judgements, and systematic
biases in those judgements will propagate into the posterior. The backtesting
framework developed alongside this document is the first step toward empirical
grounding: by comparing predicted outcomes against realised historical outcomes,
the framework generates evidence that can inform calibration adjustments. The
LLM calibration advisory function provides a qualitative bridge between backtesting
evidence and calibration decisions, while preserving the constraint that no numerical
value is modified by LLM fiat.

**Limitation 2: No formal convergence proof for partial semigroup composition.**
The system's mathematical claims — that the Lie bracket composition and Bayesian
posterior weighting converge to a well-defined result under partial information —
rest on empirical observation and domain reasoning rather than formal proof.
A rigorous convergence analysis, likely requiring conditions on the coverage of
the activation schema and the regularity of the prior distribution, remains future
work. Initial exploration suggests that convergence conditions can be stated in
terms of the spectral gap of the transition matrix induced by the composition
table — a connection to the theory of Markov chains on semigroups [Lalley, 1984]
that merits formal development.

A third avenue for future work, more speculative but potentially consequential, is
the formal connection between El'druin's partial semigroup structure and the theory
of **causal abstraction** [Beckers & Halpern, 2019]. Causal abstraction studies the
conditions under which a coarse-grained causal model is a faithful abstraction of a
fine-grained one. El'druin's ontological patterns are explicitly coarse-grained
abstractions of the fine-grained event structure extracted from news text. A formal
account of when this abstraction is faithful — when predictions at the pattern level
reliably track ground truth at the event level — would substantially strengthen the
system's epistemic standing.

---

## References

[Anderson & May, 1991] Anderson, R. M., & May, R. M. (1991). *Infectious Diseases of
Humans: Dynamics and Control*. Oxford University Press.

[Aristotle, 350 BCE] Aristotle. *Physics*, Book II; *Metaphysics*, Book V.
(Translated by R. P. Hardie and R. K. Gaye.)

[Beckers & Halpern, 2019] Beckers, S., & Halpern, J. Y. (2019). Abstracting causal
models. *Proceedings of the AAAI Conference on Artificial Intelligence*, 33, 2678–2685.

[Dworkin, 1986] Dworkin, R. (1986). *Law's Empire*. Harvard University Press.

[Fricker, 2007] Fricker, M. (2007). *Epistemic Injustice: Power and the Ethics of
Knowing*. Oxford University Press.

[Gödel, 1931] Gödel, K. (1931). Über formal unentscheidbare Sätze der Principia
Mathematica und verwandter Systeme. *Monatshefte für Mathematik und Physik*, 38,
173–198.

[Hogan et al., 2021] Hogan, A., Blomqvist, E., Cochez, M., et al. (2021).
Knowledge Graphs. *ACM Computing Surveys*, 54(4), 1–37.

[Humphreys, 1972] Humphreys, J. E. (1972). *Introduction to Lie Algebras and
Representation Theory*. Springer.

[Kahneman, 2011] Kahneman, D. (2011). *Thinking, Fast and Slow*. Farrar, Straus
and Giroux.

[Kyle, 1985] Kyle, A. S. (1985). Continuous auctions and insider trading.
*Econometrica*, 53(6), 1315–1335.

[Lalley, 1984] Lalley, S. P. (1984). Probability theory on semigroups.
*Transactions of the American Mathematical Society*, 284(2), 657–675.

[McGuinness & van Harmelen, 2004] McGuinness, D. L., & van Harmelen, F. (Eds.)
(2004). *OWL Web Ontology Language Overview*. W3C Recommendation.

[Noy & McGuinness, 2001] Noy, N. F., & McGuinness, D. L. (2001).
*Ontology Development 101: A Guide to Creating Your First Ontology*. Stanford
Knowledge Systems Laboratory Technical Report KSL-01-05.

[Pearl, 2000] Pearl, J. (2000). *Causality: Models, Reasoning, and Inference*.
Cambridge University Press.

[Taleb, 2007] Taleb, N. N. (2007). *The Black Swan: The Impact of the Highly
Improbable*. Random House.

[Tarrow, 2011] Tarrow, S. (2011). *Power in Movement: Social Movements and
Contentious Politics* (3rd ed.). Cambridge University Press.
