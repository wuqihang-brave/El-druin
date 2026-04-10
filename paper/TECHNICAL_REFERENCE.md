# EL'druin: Ontology-Driven Structural Intelligence — Mathematical and Algorithmic Framework

*A technical reference for internal discussion. Covers the core algebraic machinery, probabilistic inference pipeline, and structural analysis engines as implemented in the codebase.*

---

## 1. Ontological State Space and Semantic Embedding

### 1.1 The 8-Dimensional Lie Algebra Representation

The system models every geopolitical dynamic pattern as a vector in an 8-dimensional real vector space. The eight semantic dimensions are:

$$\mathcal{D} = \{\text{coercion}, \text{cooperation}, \text{dependency}, \text{information}, \text{regulation}, \text{military}, \text{economic}, \text{technology}\}$$

Each pattern $P$ is assigned an embedding $\mathbf{v}_P \in \mathbb{R}^8$ encoding its activation intensity across these dimensions. The embedding function is:

$$\phi: \mathcal{P} \longrightarrow \mathbb{R}^8, \quad P \mapsto \mathbf{v}_P$$

where $\mathcal{P}$ is the finite pattern library. The aggregate ontological state at any moment is the weighted mean vector:

$$\bar{\mathbf{v}} = \sum_{i} w_i \cdot \mathbf{v}_{P_i}, \quad w_i = \pi(P_i)$$

where $\pi(P_i)$ is the confidence prior of the $i$-th active pattern.

### 1.2 The Hat Map and Matrix Lifting

Each pattern vector $\mathbf{v} \in \mathbb{R}^8$ is lifted to an $8 \times 8$ antisymmetric matrix $\hat{X} \in \mathfrak{so}(8)$ via the *hat map*:

$$\hat{\cdot}: \mathbb{R}^8 \longrightarrow \mathfrak{so}(8), \quad v \mapsto X = \hat{v}$$

Explicitly, $X[i,j] = v[i] - v[j]$ for $i \neq j$, and $X[i,i] = 0$. This is antisymmetric by construction ($X = -X^\top$). The hat map's kernel is $\mathrm{span}\{\mathbf{1}\}$, giving an image of dimension 7 within the full 28-dimensional $\mathfrak{so}(8)$.

**Remark on image dimensionality.** The commutator $[X_A, X_B] = X_A X_B - X_B X_A$ lies in $\mathfrak{so}(8)$ (closed under the bracket) but generically does *not* lie in the 7-dimensional image of the hat map. This is a mathematically significant feature: the commutator can activate directions in $\mathfrak{so}(8)$ that no single pattern vector in $\mathbb{R}^8$ can represent. Consequently, the row-norm vector $\boldsymbol{\eta}$ (§3.3) captures interaction effects genuinely absent from any individual $\mathbf{v}_P$ — this is the deepest structural justification for the dual-path architecture (§3).

This lifting embeds the pattern into the Lie algebra $\mathfrak{so}(8)$ of the special orthogonal group $\mathrm{SO}(8)$, enabling the use of bracket structure to measure non-linear interactions.

### 1.3 Phase Transition Detection

A phase transition is flagged when the aggregate state vector changes discontinuously between successive reasoning steps:

$$\|\mathbf{v}_t - \mathbf{v}_{t-1}\|_2 > \delta_{\text{threshold}} = 0.25$$

This threshold is calibrated on the **unit-normalised** embedding. For unnormalised vectors the effective angular displacement varies with $\|\mathbf{v}\|$: pattern vectors in the library have norms ranging roughly 0.5 to 2.0; for a typical norm of 1.5, $\delta = 0.25$ corresponds to approximately 9.6°, not 14°. The threshold is therefore best interpreted as a Euclidean distance criterion in $\mathbb{R}^8$ rather than as a fixed angular displacement.

---

## 2. Cartesian Pattern Library and Composition Semi-Group

### 2.1 Triple Projection and the Pattern Registry

The pattern library defines a finite mapping from entity-relation-entity triples to named dynamic patterns:

$$\Phi: \mathcal{E} \times \mathcal{R} \times \mathcal{E} \longrightarrow \mathcal{P}$$

where $\mathcal{E}$ is the set of ontological entity types (e.g., `state`, `alliance`, `firm`, `resource`) and $\mathcal{R}$ is the set of relation types (e.g., `sanction`, `ally`, `supply`, `coerce`). Each registered triple $(e_1, r, e_2)$ projects to a named pattern carrying a domain label, a mechanism class, a prior confidence $\pi \in [0,1]$, and a list of typical outcomes.

### 2.2 Composition Table

A binary composition law is defined over the pattern set:

$$\circ: \mathcal{P} \times \mathcal{P} \longrightarrow \mathcal{P}$$

encoded as a finite lookup table `composition_table`. This makes $(\mathcal{P}, \circ)$ a *finite composition semi-group*. The composition rule is:

$$P_A \circ P_B = P_C \iff (P_A, P_B) \in \text{composition\_table}$$

**Idempotent elements** (attractors) satisfy $P \circ P = P$, representing terminal stable states of the system. The attractor-finding algorithm iterates over the composition table to enumerate all such fixed points by domain.

### 2.3 Additive Similarity for Transition Probability

Given two simultaneously active patterns $A$ and $B$, the *additive vector sum* $\mathbf{v}_A + \mathbf{v}_B$ serves as the query vector. The cosine similarity between this sum and a candidate target $C$ defines the structural plausibility of the transition:

$$\text{cos\_sim}(A, B \to C) = \frac{(\mathbf{v}_A + \mathbf{v}_B) \cdot \mathbf{v}_C}{\|\mathbf{v}_A + \mathbf{v}_B\|_2 \cdot \|\mathbf{v}_C\|_2}$$

Negative cosine similarities are clipped to zero: $\max(0, \text{cos\_sim})$, ensuring only directionally consistent transitions contribute positive weight.

---

## 3. Dual Inference Engine

The core inference problem is decomposed into two **structurally independent** sub-problems, solved in parallel and integrated by a consistency layer.

### 3.1 Problem Decomposition

| Path | Question | Output space |
|---|---|---|
| **Bayesian** | Which pattern $C$ is most likely activated next by $A \oplus B$? | Discrete probability distribution over $\mathcal{P}$ |
| **Lie Algebra** | In which semantic dimensions does the $A \oplus B$ interaction produce non-linear emergence? | Emergence intensity vector $\boldsymbol{\eta} \in \mathbb{R}^8$ |

These answer fundamentally different questions. Multiplying the bracket norm by the Bayesian probability, or using the row-norm vector to select a "nearest pattern", are both category errors that lose information in both directions.

### 3.2 Bayesian Path: Posterior Weight Computation

The unnormalized posterior weight for a transition $A, B \to C$ is:

$$w(A, B \to C) = \pi(A) \cdot \pi(B) \cdot \max\!\Big(0,\; \frac{(\mathbf{v}_A + \mathbf{v}_B) \cdot \mathbf{v}_C}{\|\mathbf{v}_A + \mathbf{v}_B\|_2 \cdot \|\mathbf{v}_C\|_2}\Big)$$

where $\pi(A), \pi(B)$ are the confidence priors of the active patterns. The global partition function aggregates across all active transition pairs:

$$Z = \sum_{(A,B,C)} w(A, B \to C)$$

The globally normalized probability is:

$$P_{\text{Bayes}}(C \mid A, B) = \frac{w(A, B \to C)}{Z}$$

Global normalization (rather than per-pair) is deliberate: it prevents the degenerate case where $P_{\text{Bayes}} = 1.0$ when the composition table contains exactly one entry for a given $(A, B)$ pair, and ensures probabilities displayed in the UI are consistent with those in the probability tree.

### 3.3 Lie Algebra Path: Non-Linear Emergence Detection

Given patterns $A$ and $B$ lifted to $\mathfrak{so}(8)$ matrices $X_A, X_B$, the Lie bracket (commutator) is:

$$C = [X_A, X_B] = X_A X_B - X_B X_A \in \mathbb{R}^{8 \times 8}$$

The entry $C[i, j]$ measures the non-linear interference intensity of dimension $i$ on dimension $j$. The *row-norm vector* extracts the total non-linear activation of each semantic dimension:

$$\boldsymbol{\eta}[i] = \|C[i, :]\|_2, \quad i = 1, \ldots, 8$$

This is a diagnostic signal — not a probability. A large $\boldsymbol{\eta}[i]$ means dimension $i$ is strongly activated by the non-linear $A \oplus B$ interaction in ways that the additive $\mathbf{v}_A + \mathbf{v}_B$ representation cannot capture.

The Frobenius norm and first singular value serve as scalar summaries of overall structural intensity:

$$\|C\|_F = \sqrt{\sum_{i,j} C[i,j]^2}, \qquad \sigma_1 = \lambda_{\max}(C^\top C)^{1/2}$$

The superlinear threshold is $\boldsymbol{\eta}[i] > 2.5$ (empirically calibrated), above which a dimension is classified as exhibiting superlinear emergence.

### 3.4 Path Independence Verification

The two paths are structurally independent inputs: the Bayesian path uses $\mathbf{v}_A + \mathbf{v}_B$ (linear sum), while the Lie algebra path uses $\boldsymbol{\eta} = \text{row\_norms}([X_A, X_B])$ (non-linear bracket). The independence diagnostic is:

$$\delta_{\text{independence}} = 1 - \left|\cos\!\left(\frac{\mathbf{v}_A + \mathbf{v}_B}{\|\mathbf{v}_A + \mathbf{v}_B\|}, \frac{\boldsymbol{\eta}}{\|\boldsymbol{\eta}\|}\right)\right| \in [0, 1]$$

**Structural interpretation.** $\delta \approx 0$ indicates the Lie bracket interaction reinforces the same semantic direction as the additive sum (linear regime — the two paths are redundant). $\delta \approx 1$ indicates the bracket activates orthogonal dimensions not present in $\mathbf{v}_A + \mathbf{v}_B$ (nonlinear emergence regime). This diagnostic is the operational definition of *structural novelty* beyond additive inference: a high $\delta$ is precisely when the Lie algebra path contributes genuinely new information that the Bayesian path cannot recover.

For example, for the Sanctions $\oplus$ Tech Blockade pair, $\delta \approx 0.289$ — the paths are moderately independent, indicating partial nonlinear emergence alongside a dominant additive component.

The mathematical grounding for why $\delta > 0$ is structurally guaranteed in the non-commutative case is the remark in §1.2: the commutator lives in a 28-dimensional space whereas $\boldsymbol{\eta}$ is projected back to $\mathbb{R}^8$, so whenever the commutator has components outside the hat map image, $\boldsymbol{\eta}$ captures directions absent from any $\mathbf{v}_P$.

### 3.5 Integration Layer

The consistency between the two paths is measured by the cosine angle between the emergence vector $\boldsymbol{\eta}$ and the target pattern's semantic vector $\mathbf{v}_C$:

$$\text{consistency}(A, B, C) = \cos(\boldsymbol{\eta},\, \mathbf{v}_C) = \frac{\boldsymbol{\eta} \cdot \mathbf{v}_C}{\|\boldsymbol{\eta}\|_2 \cdot \|\mathbf{v}_C\|_2} \in [-1, 1]$$

Interpretation:
- $+1$: both paths fully aligned — high confidence
- $0$: paths orthogonal — complementary rather than contradictory
- $-1$: paths opposed — bifurcation signal, confidence reduced

The integrated confidence combines both paths via:

$$\hat{p}(C) = P_{\text{Bayes}}(C) \cdot \frac{1 + \alpha \cdot \max(0,\;\text{consistency})}{1 + \alpha}, \quad \alpha = 0.30$$

**Important structural property of the denominator.** The denominator is always $1 + \alpha = 1.3$, regardless of consistency. This means:

- At `consistency = +1`: $\hat{p} = P_{\text{Bayes}} \cdot \frac{1.3}{1.3} = P_{\text{Bayes}}$, boosted by at most $\alpha/(1+\alpha) = 0.3/1.3 \approx 23\%$ relative to the baseline without the boost term.
- At `consistency = 0`: $\hat{p} = P_{\text{Bayes}} \cdot \frac{1}{1.3} \approx 0.77 \cdot P_{\text{Bayes}}$, a **guaranteed 23% structural discount**. This is not merely "no boost" — the formula actively reduces confidence whenever the two paths are orthogonal.
- At `consistency < 0`: the `max(0, ·)` clips the numerator's bonus term to zero, so $\hat{p} = P_{\text{Bayes}} / 1.3$ — the same 23% discount as the orthogonal case, not a further reduction beyond it.

This is intentional: the denominator encodes a prior skepticism that resolves *only* when the Lie algebra path confirms the Bayesian path's direction. When they are orthogonal or opposed, the denominator's discount stands as a structural penalty.

The verdict taxonomy is:

$$\text{verdict} = \begin{cases} \text{convergent} & \text{consistency} \geq 0.5 \\ \text{divergent} & \text{consistency} \leq -0.20 \\ \text{emergent} & \|\boldsymbol{\eta}\|_2 > 2.5 \\ \text{neutral} & \text{otherwise} \end{cases}$$

---

## 4. Structural Regime Classification

### 4.1 Regime Taxonomy

The system maps the normalized *structural activation score* $s \in [0,1]$ to a six-state regime taxonomy:

$$\mathcal{R} = \{\text{Linear},\;\text{Stress Accumulation},\;\text{Nonlinear Escalation},\;\text{Cascade Risk},\;\text{Attractor Lock-in},\;\text{Dissipating}\}$$

with boundaries:

| Regime | Score range |
|---|---|
| Linear | $[0, 0.20)$ |
| Stress Accumulation | $[0.20, 0.40)$ |
| Nonlinear Escalation | $[0.40, 0.60)$ |
| Cascade Risk | $[0.60, 0.75)$ |
| Attractor Lock-in | $[0.75, 0.90)$ |
| Dissipating | $[0.90, 1.00]$ |

### 4.2 Structural Score Composition

The scalar structural score is computed as a weighted combination of three signals:

$$s = 0.5 \cdot p_\beta + 0.3 \cdot \bar{\mu} + 0.2 \cdot \rho_b$$

where:
- $p_\beta$ = the *beta path* (structural break) probability from the deduction engine
- $\bar{\mu}$ = mean mechanism strength across active `MechanismLabel` objects
- $\rho_b = \min(1, n_b / 5)$ = bifurcation density, where $n_b$ is the number of detected phase transitions

The frontend uses a simplified parallel classifier over $\sigma_1$ and $\|C\|_F$ directly:

$$\text{regime} = \begin{cases} \text{Nonlinear Escalation} & \sigma_1 \geq 6 \;\vee\; \|C\|_F \geq 2 \;\vee\; n_{\text{trans}} \geq 2 \\ \text{Cascade Risk} & \sigma_1 \geq 5 \;\wedge\; \|C\|_F \geq 1.5 \\ \text{Stress Accumulation} & \sigma_1 \geq 3.5 \;\vee\; \|C\|_F \geq 1.0 \;\vee\; n_{\text{trans}} = 1 \\ \text{Linear} & \text{otherwise} \end{cases}$$

### 4.3 Derived Structural Metrics

**Threshold Distance** — normalized proximity to the next regime boundary. Let $u_r$ be the upper boundary of the current regime:

$$d_{\text{thresh}} = \text{clamp}\!\left(\frac{u_r - s}{0.25},\; 0, 1\right)$$

A value near 0 means the system is close to a regime transition.

**Coupling Asymmetry** — measured via the Herfindahl–Hirschman Index (HHI) over the domain distribution of active mechanisms. Let $\{c_k\}$ be the counts of mechanisms per domain, $n_d = 8$ (the fixed total number of semantic domains in the ontology, not the count of domains with active mechanisms), and total $= \sum_k c_k$:

$$\text{HHI} = \sum_k \left(\frac{c_k}{\text{total}}\right)^2, \qquad \text{baseline} = \frac{1}{n_d} = \frac{1}{8}$$

$$\text{coupling\_asymmetry} = \text{clamp}\!\left(\frac{\text{HHI} - \text{baseline}}{1 - \text{baseline}},\; 0, 1\right)$$

Using the fixed $n_d = 8$ prevents division by zero when mechanisms are concentrated in fewer than all domains. A perfectly symmetric system (equal distribution across all 8 domains) scores 0; a system concentrated entirely in one domain scores 1.

**Damping Capacity** — resistance to perturbation amplification:

$$d_{\text{damping}} = \text{clamp}\!\left(0.6 \cdot p_\alpha + 0.4 \cdot c_{\text{sword}} - 0.08 \cdot n_b,\; 0, 1\right)$$

where $p_\alpha$ is the alpha (continuation) path probability and $c_{\text{sword}}$ is a separate confidence score from the SacredSword analyzer.

**Reversibility Index** — how easily the system can return to a lower-risk regime:

$$r = \text{clamp}\!\left(p_\alpha - 0.08 \cdot n_{\text{attractors}},\; 0, 1\right)$$

**Transition Volatility** — rate of structural change, proxied by mean $\|\Delta\mathbf{v}\|_2$ across simulation steps, normalized against the 0.4 empirical ceiling, boosted by bifurcation count:

$$v_{\text{trans}} = \text{clamp}\!\left(\frac{\overline{\|\Delta\mathbf{v}\|}}{0.4} + 0.1 \cdot n_b,\; 0, 1\right)$$

---

## 5. Forward Simulation and Attractor Dynamics

### 5.1 Algebraic Iteration

The ontology forecaster implements a discrete dynamical system over the composition semi-group. Starting from an initial pattern set $S_0 \subseteq \mathcal{P}$, each iteration applies the composition law to generate the next state:

$$S_{t+1} = \{P_A \circ P_B \mid P_A, P_B \in S_t,\; (P_A, P_B) \in \text{composition\_table}\} \cup S_t$$

The simulation terminates when $S_{t+1} = S_t$ (convergence to an attractor basin) or when the horizon $T$ steps is reached. Confidence decays geometrically:

$$\pi_t(P) = \pi_0(P) \cdot 0.85^t$$

**Bifurcation points** are steps $t$ where $|S_{t+1} \setminus S_t| > 0$ (using $|\cdot|$ for set cardinality) combined with $\|\Delta\bar{\mathbf{v}}\|_2 > 0.25$.

### 5.2 Attractor Lock-in and Pull Strength

An element $P^* \in \mathcal{P}$ is an attractor (idempotent fixed point) if:

$$P^* \circ P^* = P^*$$

The *pull strength* toward a candidate attractor is derived from the scenario branch probability $p_{\text{branch}}$ and the *structural alignment* $\alpha_s$, which measures how well the current state vector points toward the attractor:

$$\alpha_s = \min\!\left(1,\; \hat{p}_0 \cdot (1 - 0.4 \cdot v_{\text{event}})\right)$$

$$\text{pull\_strength} = \text{clamp}\!\left(p_{\text{branch}} \cdot (0.5 + 0.5 \cdot \alpha_s),\; 0.05, 0.95\right)$$

where $v_{\text{event}} = \overline{\|\Delta\mathbf{v}\|} / 0.25$ is the normalized event velocity derived from simulation step delta norms.

---

## 6. Knowledge Graph Grounding and Context Extraction

### 6.1 Ontological Path Structure

The Knowledge Graph (stored in KuzuDB) encodes entities and relations as a property graph. For a seed entity $e$, the extractor retrieves:

- **1-hop paths**: $e \xrightarrow{r_1} e'$ — direct causal relationships
- **2-hop paths**: $e \xrightarrow{r_1} e' \xrightarrow{r_2} e''$ — second-order structural dependencies

The strength of a path is the minimum edge confidence along the path:

$$\text{strength}(e \to e' \to e'') = \min\!\left(\text{conf}(r_1),\; \text{conf}(r_2)\right)$$

These paths are serialized into a structured natural-language context block and prepended as absolute premises to the LLM reasoning prompt, grounding the inference in graph-verified facts before any generative step.

### 6.2 Schema.org Fallback

When an entity has no edges in the main KG, the system falls back to a schema.org type-hierarchy path: the entity type is mapped via a fixed vocabulary (e.g., `state` → `Country`, `alliance` → `Organization`) and `SUBTYPE_OF` edges in the `SchemaType` table are retrieved to provide minimal type-level ontological grounding.

---

## 7. Cross-Domain Propagation Engine

The propagation engine models how a structural event in one domain transfers energy to adjacent domains through a canonical directed coupling graph $G = (V, E, w)$ where:

- $V$ = domain set $\{\text{military}, \text{diplomatic}, \text{sanctions}, \text{energy}, \text{finance}, \text{trade}, \text{insurance}, \text{logistics}, \text{political}, \text{market}\}$
- $E$ = canonical directed coupling edges with default time buckets and weights $w: E \to [0,1]$

Selected coupling weights from the implementation:

| Source | Target | Time bucket | $w$ |
|---|---|---|---|
| military | diplomatic | T+24h | 0.82 |
| diplomatic | sanctions | T+72h | 0.71 |
| sanctions | energy | T+72h | 0.78 |
| energy | insurance | T+24h | 0.74 |
| insurance | market | T+7d | 0.67 |
| trade | political | T+2–6w | 0.53 |

Starting from seed domains $S_0$, a BFS traversal over $G$ orders by coupling weight to produce a causal chain of length at most 8. Time bucket assignments are adjusted by event *velocity* $v \in [0,1]$ (derived from $1 - d_{\text{damping}}$): high velocity ($v \geq 0.7$) promotes steps one bucket earlier; low velocity ($v \leq 0.2$) demotes by one.

Structural *bottlenecks* are identified as nodes with in-degree $\geq 2$ in $G$ (multiple upstream coupling paths converge), producing temporal concentration points where cascade energy accumulates before the next domain transfer.

---

## 8. Trigger Amplification Scoring

The amplification factor $a \in [0,1]$ is the central ranking criterion, derived from the causal relationship branch weight of the probability tree (not media frequency or source count):

$$a = \text{clamp}\!\left(0.6 \cdot w_{\text{causal}} + 0.4 \cdot w_{\text{KG}} + \Delta_{\text{domain}},\; 0, 1\right)$$

where:
- $w_{\text{causal}}$ = causal branch weight from the probability tree, scaled by source reliability
- $w_{\text{KG}}$ = externally supplied KG-derived causal weight (blended only when $> 0$)
- $\Delta_{\text{domain}} \in \{0.15, 0.10, 0.08, 0.05, 0\}$ = small structural boost for high-amplification domains (military, sanctions, energy, finance, other)

**Behaviour when KG evidence is absent.** The formula is intentionally non-normalizing when $w_{\text{KG}} = 0$. In that case, the 0.4 weight disappears and the formula reduces to:

$$a = \text{clamp}\!\left(w_{\text{causal}} + \Delta_{\text{domain}},\; 0, 1\right)$$

with $w_{\text{causal}}$ receiving full (unit) weight. This reflects the design choice that $w_{\text{causal}}$ is the primary structural signal; the KG weight provides a grounding correction when available, not a mandatory second opinion.

Jump potential is categorized:

$$\text{jump\_potential}(a) = \begin{cases} \text{Critical} & a > 0.75 \\ \text{High} & a \in [0.50, 0.75] \\ \text{Medium} & a \in [0.30, 0.50) \\ \text{Low} & a < 0.30 \end{cases}$$

---

## 9. Assessment Delta Tracking

Between successive runs, the delta engine computes a machine-readable diff over the following structural dimensions:

| Field | Materiality threshold |
|---|---|
| Regime label | Any label change |
| Threshold distance | $> 0.02$ (directional: narrowing / widening / stable) |
| Trigger amplification factor | $\Delta > 0.05$ |
| Attractor pull strength | $\Delta > 0.05$ |
| Damping capacity | $\Delta > 0.05$ |
| Confidence | $\Delta > 0.05$ |

The threshold direction signal is particularly useful for early warning: *narrowing* indicates the system is approaching a regime transition boundary, even if the regime label has not yet changed.

---

## 10. Summary of Mathematical Dependencies

The following diagram captures the data-flow dependencies between the algebraic components:

```
Pattern embedding  φ: P → v ∈ ℝ⁸
         │
         ├─── Additive sum v_A + v_B ──────► cosine similarity ──► w(A,B→C) ──► P_Bayes
         │
         └─── Hat map v ↦ X̂ ∈ 𝔰𝔬(8) ──► [X_A, X_B] ──► row-norms η ──► emergence
                                                            │
                                                            └──► σ₁, ‖C‖_F ──► regime
                                                                              classification

P_Bayes + η ──► consistency = cos(η, v_C) ──► p̂ = P_Bayes·(1+α·max(0,consistency))/(1+α)
                                                   [denominator always 1+α=1.3; 23% discount
                                                    applies at consistency ≤ 0]

p̂ ──► probability tree ──► trigger amplification ──► attractor pull ──► delta
```

The separation between the Bayesian and Lie-algebraic branches ensures that linear ontological priors and non-linear structural emergence signals contribute independent information channels, whose agreement or disagreement is itself a first-class observable (the `verdict` and `divergence_dims` fields). The independence is not merely architectural — it is mathematically guaranteed by the fact that the commutator $[X_A, X_B]$ lives in dimensions of $\mathfrak{so}(8)$ unreachable by any single pattern vector in $\mathbb{R}^8$.
