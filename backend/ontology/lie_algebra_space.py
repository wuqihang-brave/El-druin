"""
ontology/lie_algebra_space.py  –  v2 (mathematically corrected)
================================================================
Lie Algebra so(8) Representation for Ontological Relations

数学修正说明 (v2)
──────────────────

问题（v1 的根本数学错误）：
  原版使用 [v_A, v_B] = v_A ⊙ v_B − v_B ⊙ v_A（逐元素积的反对称差）。
  但 ℝⁿ 上的逐元素乘积是交换的：a ⊙ b = b ⊙ a，
  因此这个表达式恒为零向量，不是李括号，
  也无法满足反对称性和 Jacobi 恒等式。

修正方案：反对称矩阵嵌入（hat map）+ 矩阵换位子

  Step 1. 将每个模式向量 v_P ∈ ℝ⁸ 嵌入为 8×8 反对称矩阵 X_P ∈ 𝔰𝔬(8)：

       hat map:  X_P[i,j] = v_P[i] − v_P[j]   (i ≠ j)
                 X_P[i,i] = 0

       等价地：X_P = v_P · 1ᵀ − 1 · v_Pᵀ（外差矩阵）
       显然 X_P^T = (v · 1ᵀ − 1 · vᵀ)^T = 1 · vᵀ − v · 1ᵀ = −X_P  ✓

       X_P 的各行编码该模式向量相对于所有其他维度的相对强度差，
       保留了原始语义向量的全部信息且结构唯一确定。

  Step 2. 李括号定义为矩阵换位子：

       [X_A, X_B] = X_A @ X_B − X_B @ X_A

       验证代数性质：
       (a) 反对称性：[X_A, X_B] = −[X_B, X_A]                           ✓
       (b) 双线性性：[αX+βY, Z] = α[X,Z] + β[Y,Z]                       ✓
       (c) Jacobi：[[X,Y],Z] + [[Y,Z],X] + [[Z,X],Y] = 0                ✓
       (d) 封闭性：若 X,Y ∈ 𝔰𝔬(n) 则 [X,Y] ∈ 𝔰𝔬(n)                   ✓
           证：[X,Y]^T = (XY−YX)^T = Y^T X^T − X^T Y^T
                       = (−Y)(−X) − (−X)(−Y) = YX − XY = −[X,Y] ✓

  Step 3. 换位子 Frobenius 范数 ‖[X_A, X_B]‖_F 作为非交换性度量：

       = 0    ⟺ X_A, X_B 可交换（模式方向平行，作用顺序无关）
       > 0    ⟺ 存在非交换效应（组合顺序不可互换，高阶涌现效应）

  Phase transition 阈值重新标定：
    ℝ⁸ 向量范数 ‖v‖ ~ 1–2；hat(v) 矩阵 Frobenius 范数 ~ √(2n)·‖v‖ ~ 4–8
    换位子强非交换时 ‖[X,Y]‖_F ~ O(‖X‖·‖Y‖) ~ O(16–64)
    将相变阈值设为 1.0（低于此值视为近似可交换）

兼容性说明：
  - _vec() / _PATTERN_VECTORS / SEMANTIC_DIMS 不变（ℝ⁸ 坐标）
  - PCA 投影、lie_sim、cos 相似度仍在 ℝ⁸ 上计算（不变）
  - PatternVector 新增 matrix / matrix_norm 字段
  - LieCompositionResult.lie_bracket 现在是 (8,8) 矩阵（非零）
  - LieCompositionResult 新增 is_commutative 布尔字段
  - 所有对外 API 函数签名与 v1 完全兼容

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
# 核心数学：hat map + 矩阵换位子（v2 修正）
# ===========================================================================

def _hat(v: np.ndarray) -> np.ndarray:
    """
    Hat map: ℝⁿ → 𝔰𝔬(n)（n×n 反对称矩阵）。

    定义：X = v · 1ᵀ − 1 · vᵀ，即 X[i,j] = v[i] − v[j]
    性质：X^T = −X，X[i,i] = 0  ✓

    物理意义：X[i,j] 编码维度 i 相对维度 j 的相对激活强度差。
    """
    return v[:, None] - v[None, :]   # shape (n, n), antisymmetric by construction


def _commutator(X: np.ndarray, Y: np.ndarray) -> np.ndarray:
    """
    矩阵换位子（李括号）：[X, Y] = XY − YX。

    对 X, Y ∈ 𝔰𝔬(n)，[X,Y] ∈ 𝔰𝔬(n)（封闭性证明见模块文档）。
    满足反对称性、双线性性、Jacobi 恒等式。
    """
    return X @ Y - Y @ X


# ===========================================================================
# 核心数据类
# ===========================================================================

@dataclass
class PatternVector:
    """模式在 𝔰𝔬(8) 李代数空间中的表示。"""
    pattern_name:  str
    vector:        np.ndarray          # shape (DIM,)   ℝ⁸ 语义坐标
    matrix:        np.ndarray          # shape (DIM, DIM)  𝔰𝔬(8) 嵌入矩阵
    norm:          float               # ‖v‖₂
    matrix_norm:   float               # ‖X‖_F（Frobenius）
    dominant_dims: List[str]           # 最强的 top-2 语义维度名称
    confidence:    float = 0.72


@dataclass
class LieCompositionResult:
    """两个模式向量组合的结果。"""
    pattern_a:       str
    pattern_b:       str
    composed_vector: np.ndarray        # v_A + v_B  (ℝ⁸)
    nearest_pattern: str               # 最近的已知模式名
    similarity:      float             # cos similarity to nearest
    lie_bracket:     np.ndarray        # [X_A, X_B]  shape (DIM, DIM)  ← v2: 非零矩阵
    bracket_norm:    float             # ‖[X_A, X_B]‖_F                ← v2: 有意义
    phase_transition: Optional[str]    # 若范数超过阈值，标注相变类型
    interpretation:  str               # 人类可读的组合解释
    is_commutative:  bool              # bracket_norm < ε → 可线性叠加


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
    𝔰𝔬(8) 李代数空间。

    每个模式 P 对应：
      v_P ∈ ℝ⁸  （语义坐标，用于 PCA / cos-similarity / lie_sim）
      X_P ∈ 𝔰𝔬(8) （反对称矩阵，用于换位子 / 相变检测）

    李括号 = 矩阵换位子 [X_A, X_B] = X_A @ X_B − X_B @ X_A
    换位子 Frobenius 范数 = 非交换性度量（v1 中恒为 0 的 bug 已修复）
    """

    # 相变阈值（Frobenius 范数，重新标定为矩阵量级）
    # ℝ⁸ 向量范数 ~ 1–2 → hat(v) Frobenius 范数 ~ 4–8
    # 非交换换位子 ~ O(‖X‖·‖Y‖) ~ 16–64；阈值 1.0 = 低端截断
    PHASE_TRANSITION_THRESHOLD: float = 1.0

    # 可交换性判断阈值：bracket_norm < ε 视为近似可交换
    COMMUTATIVITY_EPSILON: float = 0.5

    # 模式组合查找表（与 relation_schema.composition_table 对齐）
    _COMPOSITION_LOOKUP: Dict[Tuple[str, str], str] = {}

    def __init__(self) -> None:
        # 延迟导入，避免循环依赖
        self._all_patterns = list(_PATTERN_VECTORS.keys())
        self._all_vectors  = np.stack(
            [_vec(p) for p in self._all_patterns], axis=0
        )  # shape (N, DIM)
        # 预计算 𝔰𝔬(8) 矩阵缓存
        self._matrices: Dict[str, np.ndarray] = {
            p: _hat(_vec(p)) for p in self._all_patterns
        }
        self._load_composition_lookup()

    def _load_composition_lookup(self) -> None:
        """从 relation_schema 同步 composition_table。"""
        try:
            from ontology.relation_schema import composition_table  # type: ignore
            self._COMPOSITION_LOOKUP = composition_table
        except ImportError:
            logger.debug("LieAlgebraSpace: relation_schema not available, using empty lookup")

    def _get_matrix(self, pattern_name: str) -> np.ndarray:
        """获取模式的 𝔰𝔬(8) 矩阵（缓存 + 按需计算）。"""
        if pattern_name not in self._matrices:
            self._matrices[pattern_name] = _hat(_vec(pattern_name))
        return self._matrices[pattern_name]

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
        𝔰𝔬(8) 矩阵换位子 [X_A, X_B] = X_A @ X_B − X_B @ X_A。

        v1 的实现使用逐元素积的反对称差 v_A ⊙ v_B − v_B ⊙ v_A，
        但 ℝⁿ 上的逐元素乘积满足交换律，因此该式恒为零向量（数学错误）。

        v2 修正：每个模式向量先经 hat map 嵌入为 𝔰𝔬(8) 矩阵，
        再计算矩阵换位子，返回 shape (DIM, DIM) 的反对称矩阵。
        Frobenius 范数 ‖result‖_F = 0 iff 两模式可交换。

        Returns:
            shape (DIM, DIM) ndarray — 换位子矩阵 [X_A, X_B]
        """
        return _commutator(self._get_matrix(pattern_a), self._get_matrix(pattern_b))

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
        检测相变（v2：使用换位子 Frobenius 范数）。

        触发条件（AND）：
          1. ‖[X_P, X_Δ]‖_F > PHASE_TRANSITION_THRESHOLD
          2. project(v_P + Δv) ≠ project(v_P)
        """
        v_current = _vec(pattern)
        v_new     = v_current + delta_vector

        current_proj, _ = self.project(v_current)
        new_proj, _     = self.project(v_new)

        X_current = self._get_matrix(pattern)
        X_delta   = _hat(delta_vector)
        C         = _commutator(X_current, X_delta)
        bracket_n = float(np.linalg.norm(C, "fro"))

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
                f"（换位子 Frobenius 范数={bracket_n:.2f} > {self.PHASE_TRANSITION_THRESHOLD}）"
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
        """构建 PatternVector 数据对象（v2：包含 𝔰𝔬(8) 矩阵）。"""
        v    = _vec(pattern_name)
        X    = self._get_matrix(pattern_name)
        norm = float(np.linalg.norm(v))
        matrix_norm = float(np.linalg.norm(X, "fro"))

        # top-2 语义维度
        top_idx  = np.argsort(np.abs(v))[-2:][::-1]
        dominant = [SEMANTIC_DIMS[i] for i in top_idx]

        return PatternVector(
            pattern_name=pattern_name,
            vector=v,
            matrix=X,
            norm=round(norm, 4),
            matrix_norm=round(matrix_norm, 4),
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
        计算两个模式的 𝔰𝔬(8) 李代数组合（v2）。

        同时查询 composition_table 的确定性结果（来自 relation_schema）
        和向量加法的连续结果（来自 Lie algebra），两者互补：
          - composition_table → 离散代数查找（精确）
          - 向量加法投影     → 连续空间近似（模糊）

        v2 修正：bracket 现在是真实的矩阵换位子 [X_A, X_B]（非零），
        b_norm 是换位子的 Frobenius 范数，用于判断非交换性。
        """
        v_sum   = self.add(pattern_a, pattern_b)
        bracket = self.bracket(pattern_a, pattern_b)
        b_norm  = float(np.linalg.norm(bracket, "fro"))
        is_com  = b_norm < self.COMMUTATIVITY_EPSILON

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
                f"高阶效应激活（换位子 Frobenius 范数={b_norm:.2f}），"
                f"组合顺序不可互换，存在非线性涌现效应"
            )

        # 人类可读解释
        dominant_sum_idx = int(np.argmax(np.abs(v_sum)))
        dominant_sum_dim = SEMANTIC_DIMS[dominant_sum_idx]
        comm_note = "（近似可交换）" if is_com else f"（非交换，‖[X_A,X_B]‖_F={b_norm:.2f}）"
        interp = (
            f"「{pattern_a}」⊕「{pattern_b}」→ 向量叠加主导维度：{dominant_sum_dim}，"
            f"最近模式：「{final_nearest}」（相似度={final_sim:.2f}）{comm_note}"
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
            is_commutative=is_com,
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

        # SVD（numpy built-in）– guard against < 2 patterns
        try:
            if len(names) < 2:
                coords_2d = np.hstack([X[:, :1], np.zeros((len(names), 1))])
            else:
                _, _, Vt = np.linalg.svd(X, full_matrices=False)
                n_components = min(2, Vt.shape[0])
                proj = X @ Vt[:n_components].T  # (M, n_components)
                if proj.shape[1] < 2:
                    coords_2d = np.hstack([proj, np.zeros((len(names), 1))])
                else:
                    coords_2d = proj
        except np.linalg.LinAlgError:
            coords_2d = np.hstack([X[:, :1], np.zeros((len(names), 1))])

        result = []
        for i, name in enumerate(names):
            v           = _vec(name)
            norm        = float(np.linalg.norm(v))
            matrix_norm = float(np.linalg.norm(self._get_matrix(name), "fro"))
            domain      = _infer_domain(name)
            result.append({
                "name":        name,
                "x":           float(coords_2d[i, 0]),
                "y":           float(coords_2d[i, 1]),
                "norm":        round(norm, 3),
                "matrix_norm": round(matrix_norm, 3),
                "domain":      domain,
                "dims":        {SEMANTIC_DIMS[d]: round(float(v[d]), 2) for d in range(DIM)},
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
                "is_commutative":  r.is_commutative,
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
        "algebra": "so(8)",
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
        "dim":           DIM,
        "algebra":       "so(8)",
    }


def get_composition_map() -> List[Dict[str, Any]]:
    """返回 composition_table 的向量化表示（供前端力导向图）。

    v2：bracket_norm 使用矩阵换位子 Frobenius 范数（非零，有意义）。
    """
    result = []
    try:
        from ontology.relation_schema import composition_table  # type: ignore
        for (a, b), c in composition_table.items():
            v_a = _vec(a)
            v_b = _vec(b)
            v_c = _vec(c)
            C   = _commutator(_hat(v_a), _hat(v_b))
            result.append({
                "source":       a,
                "target":       b,
                "result":       c,
                "bracket_norm": round(float(np.linalg.norm(C, "fro")), 3),
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
    lines = ["【𝔰𝔬(8) 李代数空间分析（辅助推演锚定）】"]

    dom_idx = int(np.argmax(np.abs(mean_vec)))
    dom_dim = SEMANTIC_DIMS[dom_idx]
    coerc   = float(mean_vec[0])
    coop    = float(mean_vec[1])

    lines.append(
        f"  整体主导维度: {dom_dim}（强制/合作均值: {coerc:+.2f} / {coop:+.2f}）"
    )

    if compositions:
        top = compositions[0]
        comm_tag = "可交换" if top.is_commutative else f"非交换 ‖[X,Y]‖_F={top.bracket_norm:.2f}"
        lines.append(
            f"  最强组合效应: {top.interpretation}（{comm_tag}）"
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
        c    = compositions[0]
        ct   = "可交换" if c.get("is_commutative") else f"非交换 ‖[X,Y]‖_F={c.get('bracket_norm', 0):.2f}"
        comp_str = (
            f"；主要组合效应: 「{c['pattern_a']}」⊕「{c['pattern_b']}」"
            f"→「{c['composed_result']}」（{ct}）"
        )
    phase_str = ""
    if phase_events:
        phase_str = f"；⚡ 检测到 {len(phase_events)} 个相变点"
    return f"分析了 {len(patterns)} 个模式{comp_str}{phase_str}"