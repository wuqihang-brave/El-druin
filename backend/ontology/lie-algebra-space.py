"""
ontology/lie_algebra_space.py
==============================
Lie Algebra Vector Space for Ontological Relations

设计目标（基础闭环版本）：
  1. 把每个「本体关系模式」(DynamicPattern) 看成高维空间中的一个向量
  2. 关系的组合对应向量加法（在李代数空间里）
  3. 连续强度变化 → 不连续模式转换（相变检测）
  4. 提供与现有 relation_schema.py / deduction_engine.py 的闭环集成接口

数学基础：
  李代数 g 是一个带有李括号 [·,·] 的向量空间
  本文件的离散近似：
    • 向量空间 V = ℝ^d，d = 语义维度数（当前 d=8）
    • 加法 v_A + v_B ≈ compose_patterns(A, B) 的向量表示
    • 逆元 -v_A ≈ inverse_table[A] 的向量表示
    • 李括号 [v_A, v_B] = v_A × v_B（反对称部分）→ 高阶效应检测
    • 范数 ||v|| = confidence_prior × strength 权重

语义维度（8维）：
  dim 0: coercion       — 强制/对抗强度
  dim 1: cooperation    — 合作/协调强度
  dim 2: dependency     — 依赖/流通强度
  dim 3: information    — 信息/认知维度
  dim 4: regulation     — 结构/制度维度
  dim 5: military       — 军事/暴力维度
  dim 6: economic       — 经济/金融维度
  dim 7: technology     — 技术/创新维度

集成方式（闭环）：
  A. deduction_engine.py 调用 enrich_with_lie_algebra()
     → 为 MechanismLabel 附加向量表示和相变分析
  B. evented_pipeline.py 调用 compute_pattern_trajectory()
     → 为 active_patterns 计算演化轨迹
  C. 前端 Cartesian 诊断视图调用 get_vector_analysis()
     → 返回向量可视化数据（用于散点图）
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

# ===========================================================================
# 语义维度定义
# ===========================================================================

SEMANTIC_DIMS = [
    "coercion",     # 0 强制/对抗
    "cooperation",  # 1 合作/协调
    "dependency",   # 2 依赖/流通
    "information",  # 3 信息/认知
    "regulation",   # 4 结构/制度
    "military",     # 5 军事/暴力
    "economic",     # 6 经济/金融
    "technology",   # 7 技术/创新
]
DIM = len(SEMANTIC_DIMS)  # 8


# ===========================================================================
# 模式向量库
# 每个已命名模式在 8 维语义空间中的坐标
# 坐标值 ∈ [-1.0, 1.0]，正 = 该维度激活，负 = 该维度被抑制
# ===========================================================================

_PATTERN_VECTORS: Dict[str, List[float]] = {
    # ── 地缘政治模式 ──────────────────────────────────────────────────
    #                        coerc  coop  dep   info  reg   mil   econ  tech
    "霸权制裁模式":         [ 0.90,  -0.30,  0.10, 0.20,  0.40, 0.20,  0.70, 0.30],
    "实体清单技术封锁模式":  [ 0.80,  -0.20,  0.30, 0.10,  0.50, 0.10,  0.50, 0.90],
    "国家间武力冲突模式":   [ 0.70,  -0.70,  0.00, 0.20,  0.10, 0.95,  0.30, 0.10],
    "大国脅迫/威懾模式":    [ 0.85,  -0.50,  0.10, 0.40,  0.20, 0.60,  0.20, 0.20],
    "多邊聯盟制裁模式":     [ 0.75,  -0.20,  0.10, 0.30,  0.60, 0.15,  0.65, 0.25],
    "非國家武裝代理衝突模式":[ 0.60,  -0.60,  0.00, 0.30,  0.05, 0.90,  0.10, 0.05],
    "正式軍事同盟模式":     [ 0.20,   0.70,  0.40, 0.20,  0.70, 0.60,  0.20, 0.15],
    "國際規範建構模式":     [ 0.10,   0.60,  0.20, 0.50,  0.90, 0.05,  0.10, 0.30],

    # ── 经济/金融模式 ─────────────────────────────────────────────────
    "雙邊貿易依存模式":     [-0.20,   0.70,  0.90, 0.10,  0.30, 0.00,  0.85, 0.25],
    "央行貨幣政策傳導模式":  [ 0.10,   0.20,  0.60, 0.20,  0.80, 0.00,  0.90, 0.10],
    "金融孤立/SWIFT切斷模式":[ 0.85,  -0.40,  0.20, 0.10,  0.50, 0.15,  0.85, 0.20],
    "企業供應鏈單點依賴模式":[ 0.10,   0.30,  0.90, 0.10,  0.30, 0.00,  0.70, 0.60],
    "資源依賴/能源武器化模式":[ 0.70,   0.00,  0.80, 0.20,  0.25, 0.30,  0.75, 0.15],

    # ── 技术模式 ──────────────────────────────────────────────────────
    "技術標準主導模式":     [ 0.30,   0.30,  0.50, 0.30,  0.75, 0.00,  0.40, 0.90],
    "關鍵零部件寡頭供應模式":[ 0.40,   0.10,  0.70, 0.10,  0.40, 0.00,  0.55, 0.85],
    "科技脫鉤/技術鐵幕模式": [ 0.70,  -0.50,  0.20, 0.20,  0.50, 0.10,  0.40, 0.90],

    # ── 信息/制度模式 ─────────────────────────────────────────────────
    "信息戰/敘事操控模式":  [ 0.60,  -0.30,  0.10, 0.95,  0.20, 0.25,  0.10, 0.30],
    "跨國監管/合規約束模式": [ 0.30,   0.20,  0.40, 0.30,  0.90, 0.05,  0.40, 0.50],

    # ── 逆模式（仅向量，不在注册表中，供计算用）─────────────────────
    "制裁解除/正常化模式":  [-0.70,   0.60, -0.10, 0.20,  0.30, 0.10, -0.50, 0.10],
    "技術許可/解禁模式":    [-0.60,   0.50, -0.20, 0.10,  0.30, 0.05, -0.30, 0.60],
    "停火/和平協議模式":    [-0.50,   0.80, -0.10, 0.30,  0.60,-0.80, -0.10, 0.05],
    "外交讓步/去升級模式":  [-0.70,   0.75, -0.05, 0.30,  0.50,-0.50, -0.10, 0.10],
    "貿易戰/脫鉤模式":      [ 0.65,  -0.60,  0.10, 0.20,  0.30, 0.10,  0.70, 0.30],
    "技術合作再融合模式":   [-0.50,   0.60, -0.10, 0.20,  0.40, 0.00, -0.20, 0.80],
    "信息環境修復模式":     [-0.40,   0.50, -0.05, 0.70,  0.40,-0.15,  0.10, 0.20],
}


def _vec(pattern_name: str) -> np.ndarray:
    """获取模式向量，未知模式返回零向量。"""
    v = _PATTERN_VECTORS.get(pattern_name)
    if v is None:
        logger.debug("LieAlgebraSpace: unknown pattern '%s', using zero vector", pattern_name)
        return np.zeros(DIM)
    return np.array(v, dtype=float)


# ===========================================================================
# 核心数据类
# ===========================================================================

@dataclass
class PatternVector:
    """模式在李代数空间中的向量表示。"""
    pattern_name:  str
    vector:        np.ndarray          # shape (DIM,)
    norm:          float               # ||v||₂
    dominant_dims: List[str]           # 最强的 top-2 语义维度名称
    confidence:    float = 0.72


@dataclass
class LieCompositionResult:
    """两个模式向量组合的结果。"""
    pattern_a:       str
    pattern_b:       str
    composed_vector: np.ndarray        # v_A + v_B
    nearest_pattern: str               # 最近的已知模式名
    similarity:      float             # cos similarity to nearest
    lie_bracket:     np.ndarray        # [v_A, v_B] = 反对称部分
    bracket_norm:    float             # ||[v_A, v_B]||
    phase_transition: Optional[str]    # 若范数超过阈值，标注相变类型
    interpretation:  str               # 人类可读的组合解释


@dataclass
class PhaseTransitionEvent:
    """相变事件：连续强度变化触发的不连续模式转换。"""
    from_pattern:   str
    to_pattern:     str
    trigger_dim:    str               # 触发相变的维度
    threshold:      float             # 触发阈值
    delta:          float             # 强度变化量
    description:    str


@dataclass
class LieAlgebraAnalysis:
    """
    完整的李代数空间分析结果。
    由 enrich_with_lie_algebra() 或 compute_pattern_trajectory() 生成。
    """
    patterns:            List[PatternVector]
    compositions:        List[LieCompositionResult]
    phase_transitions:   List[PhaseTransitionEvent]
    trajectory_summary:  str
    # 供前端散点图使用的 2D 投影（PCA to ℝ²）
    pca_coords:          List[Dict[str, Any]]   # [{name, x, y, norm}]
    # 代数度量
    total_coercion:      float
    total_cooperation:   float
    dominant_domain:     str


# ===========================================================================
# 李代数空间核心计算
# ===========================================================================

class LieAlgebraSpace:
    """
    离散李代数空间实现。

    核心操作：
      add(A, B)       → 向量加法，等价于关系组合
      bracket(A, B)   → 李括号，测量非交换性（高阶效应）
      project(v)      → 将任意向量投影到最近的已知模式
      phase(v, dv)    → 检测是否发生相变（超过阈值跃迁）
    """

    # 相变阈值：当李括号范数超过此值时，认为发生高阶相变
    PHASE_TRANSITION_THRESHOLD = 0.45

    # 模式组合查找表（与 relation_schema.composition_table 对齐）
    _COMPOSITION_LOOKUP: Dict[Tuple[str, str], str] = {}

    def __init__(self) -> None:
        # 延迟导入，避免循环依赖
        self._all_patterns = list(_PATTERN_VECTORS.keys())
        self._all_vectors  = np.stack(
            [_vec(p) for p in self._all_patterns], axis=0
        )  # shape (N, DIM)
        self._load_composition_lookup()

    def _load_composition_lookup(self) -> None:
        """从 relation_schema 同步 composition_table。"""
        try:
            from ontology.relation_schema import composition_table  # type: ignore
            self._COMPOSITION_LOOKUP = composition_table
        except ImportError:
            logger.debug("LieAlgebraSpace: relation_schema not available, using empty lookup")

    # ------------------------------------------------------------------
    # 基本向量运算
    # ------------------------------------------------------------------

    def add(self, pattern_a: str, pattern_b: str) -> np.ndarray:
        """
        向量加法：v_A + v_B。
        对应李代数 g 中的线性叠加。
        """
        return _vec(pattern_a) + _vec(pattern_b)

    def bracket(self, pattern_a: str, pattern_b: str) -> np.ndarray:
        """
        李括号 [v_A, v_B]：
        离散近似 = 反对称部分，即 (v_A ⊗ v_B - v_B ⊗ v_A) 的对角投影。

        物理含义：
          bracket_norm 大 → A 和 B 的作用顺序不可互换 → 高阶非线性效应
          bracket_norm ≈ 0 → A 和 B 近似交换 → 可线性叠加
        """
        v_a = _vec(pattern_a)
        v_b = _vec(pattern_b)
        # 元素级反对称：近似 [A,B] = A*B - B*A（对角元素）
        return v_a * v_b - v_b * v_a

    def project(self, vector: np.ndarray) -> Tuple[str, float]:
        """
        将向量投影到最近的已知模式（余弦相似度）。

        Returns:
            (pattern_name, cosine_similarity)
        """
        v_norm = np.linalg.norm(vector)
        if v_norm < 1e-9:
            return ("零向量（无模式激活）", 0.0)

        # 计算与所有已知模式向量的余弦相似度
        norms = np.linalg.norm(self._all_vectors, axis=1, keepdims=True)
        norms = np.where(norms < 1e-9, 1.0, norms)
        all_normed = self._all_vectors / norms

        v_normed = vector / v_norm
        similarities = all_normed @ v_normed  # shape (N,)

        best_idx  = int(np.argmax(similarities))
        best_sim  = float(similarities[best_idx])
        best_name = self._all_patterns[best_idx]

        return (best_name, best_sim)

    def phase_detect(
        self,
        pattern: str,
        delta_vector: np.ndarray,
    ) -> Optional[PhaseTransitionEvent]:
        """
        检测相变：若强度变化 delta_vector 导致模式跃迁，返回 PhaseTransitionEvent。

        相变条件：
          1. ||v + dv|| > THRESHOLD（组合范数超过阈值）
          2. project(v + dv) ≠ project(v)（投影到不同模式）
        """
        v_current = _vec(pattern)
        v_new     = v_current + delta_vector

        current_proj, _ = self.project(v_current)
        new_proj, sim   = self.project(v_new)

        bracket_v = v_current * delta_vector - delta_vector * v_current
        bracket_n = float(np.linalg.norm(bracket_v))

        if new_proj == current_proj or bracket_n < self.PHASE_TRANSITION_THRESHOLD:
            return None

        # 找触发相变的主要维度
        trigger_idx = int(np.argmax(np.abs(delta_vector)))
        trigger_dim = SEMANTIC_DIMS[trigger_idx]

        return PhaseTransitionEvent(
            from_pattern=current_proj,
            to_pattern=new_proj,
            trigger_dim=trigger_dim,
            threshold=self.PHASE_TRANSITION_THRESHOLD,
            delta=float(delta_vector[trigger_idx]),
            description=(
                f"在 {trigger_dim} 维度发生强度跃迁（Δ={delta_vector[trigger_idx]:+.2f}），"
                f"模式从「{current_proj}」相变为「{new_proj}」"
                f"（李括号范数={bracket_n:.2f}）"
            ),
        )

    # ------------------------------------------------------------------
    # 模式向量构建
    # ------------------------------------------------------------------

    def make_pattern_vector(
        self,
        pattern_name: str,
        confidence: float = 0.72,
    ) -> PatternVector:
        """构建 PatternVector 数据对象。"""
        v    = _vec(pattern_name)
        norm = float(np.linalg.norm(v))

        # top-2 语义维度
        top_idx = np.argsort(np.abs(v))[-2:][::-1]
        dominant = [SEMANTIC_DIMS[i] for i in top_idx]

        return PatternVector(
            pattern_name=pattern_name,
            vector=v,
            norm=norm,
            dominant_dims=dominant,
            confidence=confidence,
        )

    # ------------------------------------------------------------------
    # 组合分析
    # ------------------------------------------------------------------

    def compose(
        self,
        pattern_a: str,
        pattern_b: str,
        confidence_a: float = 0.72,
        confidence_b: float = 0.72,
    ) -> LieCompositionResult:
        """
        计算两个模式的李代数组合。

        同时查询 composition_table 的确定性结果（来自 relation_schema）
        和向量加法的连续结果（来自 Lie algebra），两者互补：
          - composition_table → 离散代数查找（精确）
          - 向量加法投影     → 连续空间近似（模糊）
        """
        v_sum    = self.add(pattern_a, pattern_b)
        bracket  = self.bracket(pattern_a, pattern_b)
        b_norm   = float(np.linalg.norm(bracket))

        # 先查 composition_table
        exact = self._COMPOSITION_LOOKUP.get((pattern_a, pattern_b))

        # 再查向量投影
        nearest, similarity = self.project(v_sum)

        # 合并：优先使用 composition_table
        final_nearest = exact if exact else nearest
        final_sim     = 1.0   if exact else similarity

        # 相变检测
        phase: Optional[str] = None
        if b_norm >= self.PHASE_TRANSITION_THRESHOLD:
            phase = (
                f"高阶效应激活（李括号范数={b_norm:.2f}），"
                f"A×B 的顺序不可互换，存在非线性涌现效应"
            )

        # 人类可读解释
        v_a = _vec(pattern_a)
        v_b = _vec(pattern_b)
        dominant_sum_idx = int(np.argmax(np.abs(v_sum)))
        dominant_sum_dim = SEMANTIC_DIMS[dominant_sum_idx]
        interp = (
            f"「{pattern_a}」⊕「{pattern_b}」→ 向量叠加主导维度：{dominant_sum_dim}，"
            f"最近模式：「{final_nearest}」（相似度={final_sim:.2f}）"
        )
        if exact:
            interp += f"。代数精确解：「{exact}」"
        if phase:
            interp += f"。⚡ {phase}"

        return LieCompositionResult(
            pattern_a=pattern_a,
            pattern_b=pattern_b,
            composed_vector=v_sum,
            nearest_pattern=final_nearest,
            similarity=final_sim,
            lie_bracket=bracket,
            bracket_norm=b_norm,
            phase_transition=phase,
            interpretation=interp,
        )

    # ------------------------------------------------------------------
    # PCA 投影（用于前端 2D 散点图）
    # ------------------------------------------------------------------

    def pca_project(
        self,
        pattern_names: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        将模式向量 PCA 投影到 ℝ²，用于前端可视化。

        不引入 sklearn 依赖：使用手工 SVD（numpy.linalg.svd）。
        """
        names = pattern_names or self._all_patterns
        vecs  = np.stack([_vec(n) for n in names], axis=0)  # (M, DIM)

        # 中心化
        center = vecs.mean(axis=0)
        X      = vecs - center

        # SVD（numpy built-in）
        try:
            _, _, Vt = np.linalg.svd(X, full_matrices=False)
            coords_2d = X @ Vt[:2].T  # (M, 2)
        except np.linalg.LinAlgError:
            coords_2d = X[:, :2]  # fallback: first 2 dims

        result = []
        for i, name in enumerate(names):
            v      = _vec(name)
            norm   = float(np.linalg.norm(v))
            domain = _infer_domain(name)
            result.append({
                "name":   name,
                "x":      float(coords_2d[i, 0]),
                "y":      float(coords_2d[i, 1]),
                "norm":   round(norm, 3),
                "domain": domain,
                "dims":   {SEMANTIC_DIMS[d]: round(float(v[d]), 2) for d in range(DIM)},
            })
        return result


# ===========================================================================
# 辅助函数：模式 → 领域推断
# ===========================================================================

def _infer_domain(pattern_name: str) -> str:
    geo  = ["霸权", "脅迫", "联盟", "武力", "规范", "代理", "制裁", "多边"]
    econ = ["贸易", "央行", "金融", "供应链", "资源"]
    tech = ["技术", "标准", "零部件", "脱钩"]
    info = ["信息", "叙事", "监管"]
    for kw in geo:
        if kw in pattern_name:
            return "geopolitics"
    for kw in econ:
        if kw in pattern_name:
            return "economics"
    for kw in tech:
        if kw in pattern_name:
            return "technology"
    for kw in info:
        if kw in pattern_name:
            return "information"
    return "general"


# ===========================================================================
# 集成接口 A：为 MechanismLabel 列表附加向量分析
# （供 deduction_engine.py 调用）
# ===========================================================================

_space = LieAlgebraSpace()  # 模块级单例


def enrich_with_lie_algebra(
    mechanism_labels: list,
) -> LieAlgebraAnalysis:
    """
    为 deduction_engine.MechanismLabel 列表计算李代数空间分析。

    调用方式（在 DeductionEngine.deduce_from_ontological_paths 中）：
        from ontology.lie_algebra_space import enrich_with_lie_algebra
        lie_analysis = enrich_with_lie_algebra(mechanisms)
        # lie_analysis.trajectory_summary 注入 prompt
        # lie_analysis.dominant_domain 用于 domain 校验

    Returns:
        LieAlgebraAnalysis 对象
    """
    from ontology.relation_schema import CARTESIAN_PATTERN_REGISTRY  # type: ignore

    # 从 MechanismLabel 中提取模式名称
    pattern_names: List[str] = []
    for lbl in mechanism_labels:
        rel   = getattr(lbl, "relation", "")
        src_t = getattr(lbl, "source", "")
        tgt_t = getattr(lbl, "target", "")
        # 查找最匹配的注册模式名
        matched = _find_matching_pattern_name(rel, src_t, tgt_t)
        if matched:
            pattern_names.append(matched)

    if not pattern_names:
        # 无机制标签时，返回空分析
        return LieAlgebraAnalysis(
            patterns=[], compositions=[], phase_transitions=[],
            trajectory_summary="无机制标签，李代数分析未激活",
            pca_coords=[],
            total_coercion=0.0, total_cooperation=0.0, dominant_domain="unknown",
        )

    # 构建模式向量列表
    pat_vectors = [_space.make_pattern_vector(n) for n in pattern_names]

    # 成对组合分析（对前 3 个模式做两两组合）
    compositions: List[LieCompositionResult] = []
    for i in range(min(3, len(pattern_names))):
        for j in range(i + 1, min(3, len(pattern_names))):
            comp = _space.compose(pattern_names[i], pattern_names[j])
            compositions.append(comp)

    # 相变检测（对相邻模式对）
    phase_events: List[PhaseTransitionEvent] = []
    for i in range(len(pattern_names) - 1):
        v_cur  = _vec(pattern_names[i])
        v_next = _vec(pattern_names[i + 1])
        delta  = v_next - v_cur
        evt    = _space.phase_detect(pattern_names[i], delta)
        if evt:
            phase_events.append(evt)

    # 整体代数度量
    all_vecs     = np.stack([_vec(n) for n in pattern_names], axis=0)
    mean_vec     = all_vecs.mean(axis=0)
    total_coerc  = float(mean_vec[0])
    total_coop   = float(mean_vec[1])
    dom_idx      = int(np.argmax(np.abs(mean_vec)))
    dom_dim      = SEMANTIC_DIMS[dom_idx]

    # PCA 投影（只投影涉及的模式 + 它们的组合结果）
    pca_names = list(dict.fromkeys(
        pattern_names
        + [c.nearest_pattern for c in compositions if c.nearest_pattern]
    ))
    pca_coords = _space.pca_project(pca_names)

    # 轨迹摘要（注入推演 prompt 用）
    trajectory_summary = _build_trajectory_summary(
        pattern_names, compositions, phase_events, mean_vec
    )

    return LieAlgebraAnalysis(
        patterns=pat_vectors,
        compositions=compositions,
        phase_transitions=phase_events,
        trajectory_summary=trajectory_summary,
        pca_coords=pca_coords,
        total_coercion=round(total_coerc, 3),
        total_cooperation=round(total_coop, 3),
        dominant_domain=dom_dim,
    )


# ===========================================================================
# 集成接口 B：为 evented_pipeline 的 active_patterns 计算轨迹
# （供 evented_pipeline.py 或 analysis.py 调用）
# ===========================================================================

def compute_pattern_trajectory(
    active_pattern_names: List[str],
    derived_pattern_names: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    为 active_patterns + derived_patterns 计算李代数演化轨迹。

    供 analysis.py evented/deduce 端点在响应中附加向量分析字段。

    Returns:
        dict，可直接序列化进 API 响应的 "lie_algebra" 字段。
    """
    all_names   = active_pattern_names + (derived_pattern_names or [])
    if not all_names:
        return {"enabled": False, "reason": "no_patterns"}

    compositions:  List[Dict[str, Any]] = []
    phase_events:  List[Dict[str, Any]] = []

    # 主动模式两两组合
    for i in range(min(3, len(active_pattern_names))):
        for j in range(i + 1, min(3, len(active_pattern_names))):
            r = _space.compose(active_pattern_names[i], active_pattern_names[j])
            compositions.append({
                "pattern_a":       r.pattern_a,
                "pattern_b":       r.pattern_b,
                "composed_result": r.nearest_pattern,
                "similarity":      round(r.similarity, 3),
                "bracket_norm":    round(r.bracket_norm, 3),
                "phase_transition": r.phase_transition,
                "interpretation":  r.interpretation,
            })

    # 相变检测
    for i in range(len(active_pattern_names) - 1):
        v_a = _vec(active_pattern_names[i])
        v_b = _vec(active_pattern_names[i + 1])
        evt = _space.phase_detect(active_pattern_names[i], v_b - v_a)
        if evt:
            phase_events.append({
                "from_pattern":  evt.from_pattern,
                "to_pattern":    evt.to_pattern,
                "trigger_dim":   evt.trigger_dim,
                "delta":         round(evt.delta, 3),
                "description":   evt.description,
            })

    # PCA coords
    pca_coords = _space.pca_project(all_names)

    # 整体向量
    mean_v     = np.mean([_vec(n) for n in all_names], axis=0)
    dom_idx    = int(np.argmax(np.abs(mean_v)))
    dim_values = {SEMANTIC_DIMS[d]: round(float(mean_v[d]), 3) for d in range(DIM)}

    return {
        "enabled":          True,
        "active_patterns":  active_pattern_names,
        "derived_patterns": derived_pattern_names or [],
        "compositions":     compositions,
        "phase_transitions": phase_events,
        "pca_coords":       pca_coords,
        "mean_vector": {
            "dominant_dim":   SEMANTIC_DIMS[dom_idx],
            "coercion":       round(float(mean_v[0]), 3),
            "cooperation":    round(float(mean_v[1]), 3),
            "dim_values":     dim_values,
        },
        "summary": _build_simple_summary(all_names, compositions, phase_events),
    }


# ===========================================================================
# 集成接口 C：供前端 Cartesian 诊断视图调用
# （供 analysis.py 新增的 GET /analysis/lie-algebra/vectors 端点使用）
# ===========================================================================

def get_full_vector_space() -> Dict[str, Any]:
    """返回完整的模式向量空间数据，用于前端散点图可视化。"""
    pca_all = _space.pca_project()
    return {
        "semantic_dims": SEMANTIC_DIMS,
        "n_patterns":    len(_PATTERN_VECTORS),
        "pca_coords":    pca_all,
        "dim": DIM,
    }


def get_composition_map() -> List[Dict[str, Any]]:
    """返回 composition_table 的向量化表示（供前端力导向图）。"""
    result = []
    try:
        from ontology.relation_schema import composition_table  # type: ignore
        for (a, b), c in composition_table.items():
            v_a = _vec(a)
            v_b = _vec(b)
            v_c = _vec(c)
            result.append({
                "source":  a,
                "target":  b,
                "result":  c,
                "bracket_norm": round(float(np.linalg.norm(v_a * v_b - v_b * v_a)), 3),
                "additive_sim": round(float(
                    np.dot(v_a + v_b, v_c) /
                    max(1e-9, np.linalg.norm(v_a + v_b) * np.linalg.norm(v_c))
                ), 3),
            })
    except ImportError:
        pass
    return result


# ===========================================================================
# 内部工具
# ===========================================================================

def _find_matching_pattern_name(
    relation: str,
    source: str,
    target: str,
) -> Optional[str]:
    """
    从 MechanismLabel 的 relation / source / target 推断对应的模式名称。
    优先从 CARTESIAN_PATTERN_REGISTRY 查，其次模糊匹配 _PATTERN_VECTORS。
    """
    try:
        from ontology.relation_schema import (  # type: ignore
            CARTESIAN_PATTERN_REGISTRY,
            _infer_entity_type,
        )
        for (e_src, r, e_tgt), pat in CARTESIAN_PATTERN_REGISTRY.items():
            if r.value.lower() in relation.lower():
                return pat.pattern_name
    except ImportError:
        pass

    # 模糊匹配：关系动词 → 模式向量库键名
    rel_lower = relation.lower()
    for name in _PATTERN_VECTORS:
        kws = name.replace("模式", "").replace("/", " ").replace("·", " ").split()
        for kw in kws:
            if kw and kw in rel_lower:
                return name
    return None


def _build_trajectory_summary(
    patterns: List[str],
    compositions: List[LieCompositionResult],
    phase_events: List[PhaseTransitionEvent],
    mean_vec: np.ndarray,
) -> str:
    """构建供 LLM prompt 注入的轨迹摘要（中文）。"""
    lines = ["【李代数空间分析（辅助推演锚定）】"]

    dom_idx = int(np.argmax(np.abs(mean_vec)))
    dom_dim = SEMANTIC_DIMS[dom_idx]
    coerc   = float(mean_vec[0])
    coop    = float(mean_vec[1])

    lines.append(
        f"  整体主导维度: {dom_dim}（强制/合作均值: {coerc:+.2f} / {coop:+.2f}）"
    )

    if compositions:
        top = compositions[0]
        lines.append(
            f"  最强组合效应: {top.interpretation}"
        )

    if phase_events:
        for evt in phase_events[:2]:
            lines.append(f"  ⚡ 相变: {evt.description}")

    lines.append(
        "  提示：以上向量分析仅用于辅助推演方向判断，不替代原文证据。"
    )
    return "\n".join(lines)


def _build_simple_summary(
    patterns: List[str],
    compositions: List[Dict[str, Any]],
    phase_events: List[Dict[str, Any]],
) -> str:
    if not patterns:
        return "无模式激活"
    comp_str = ""
    if compositions:
        comp_str = f"；主要组合效应: 「{compositions[0]['pattern_a']}」⊕「{compositions[0]['pattern_b']}」→「{compositions[0]['composed_result']}」"
    phase_str = ""
    if phase_events:
        phase_str = f"；⚡ 检测到 {len(phase_events)} 个相变点"
    return f"分析了 {len(patterns)} 个模式{comp_str}{phase_str}"