#!/usr/bin/env python3
"""完整的分析管道测试"""

import os
import sys
import json
import asyncio

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

async def test_full_pipeline():
    print("=" * 100)
    print("🧪 完整分析管道测试 - 本体系统诊断")
    print("=" * 100)
    
    test_news = "Google is launching Search Live globally. This AI-powered search enables real-time assistance via phone camera."
    
    print(f"\n📰 输入新闻:\n{test_news}\n")
    
    # ════════════════════════════════════════════════════════════
    # 第 1 步：检查本体系统
    # ════════════════════════════════════════════════════════════
    print("\n" + "=" * 100)
    print("【第 1 步】检查本体系统是否已加载")
    print("=" * 100)
    
    try:
        from backend.config.ontology import (
            CORE_ONTOLOGY,
            generate_ontology_system_prompt,
            build_validation_report,
            validate_node_type,
        )
        
        print(f"✅ 本体系统已加载")
        print(f"   - 实体类型数: {len(CORE_ONTOLOGY['NODES'])}")
        print(f"   - 关系类型数: {len(CORE_ONTOLOGY['EDGES'])}")
        print(f"   - 实体类型列表: {list(CORE_ONTOLOGY['NODES'].keys())}")
        
        # 测试提示词生成
        system_prompt = generate_ontology_system_prompt()
        print(f"✅ 系统提示词已生成 ({len(system_prompt)} 字符)")
        
        if "Organization" in system_prompt and "mentions" in system_prompt:
            print(f"✅ 提示词包含本体定义")
        else:
            print(f"❌ 提示词不包含本体定义！")
        
    except Exception as e:
        print(f"❌ 本体系统加载失败: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # ════════════════════════════════════════════════════════════
    # 第 2 步：测试实体提取
    # ════════════════════════════════════════════════════════════
    print("\n" + "=" * 100)
    print("【第 2 步】测试实体提取（OntologyConstrainedExtractor）")
    print("=" * 100)
    
    try:
        from app.knowledge.entity_extractor import OntologyConstrainedExtractor
        
        extractor = OntologyConstrainedExtractor()
        print(f"✅ OntologyConstrainedExtractor 已加载")
        
        extraction_result = extractor.extract(test_news)
        
        entities = extraction_result.get("entities", [])
        relations = extraction_result.get("relations", [])
        validation_report = extraction_result.get("validation_report", {})
        
        print(f"✅ 提取完成")
        print(f"   - 提取的实体数: {len(entities)}")
        print(f"   - 提取的关系数: {len(relations)}")
        print(f"   - 合规率: {validation_report.get('compliance_pct', 'N/A')}%")
        
        if entities:
            print(f"\n   示例实体:")
            for e in entities[:3]:
                print(f"     • {e.get('name')} ({e.get('type')})")
        
        if relations:
            print(f"\n   示例关系:")
            for r in relations[:3]:
                print(f"     • {r.get('from')} --{r.get('relation')}--> {r.get('to')}")
        
        if validation_report.get('invalid_entities'):
            print(f"\n   ⚠️ 无效实体 ({len(validation_report['invalid_entities'])}):")
            for invalid in validation_report['invalid_entities'][:3]:
                print(f"     • {invalid}")
        
    except Exception as e:
        print(f"❌ 实体提取失败: {e}")
        import traceback
        traceback.print_exc()
        entities = []
        relations = []
    
    # ════════════════════════════════════════════════════════════
    # 第 3 步：检查 KuzuDB 图谱
    # ════════════════════════════════════════════════════════════
    print("\n" + "=" * 100)
    print("【第 3 步】检查 KuzuDB 图谱")
    print("=" * 100)
    
    try:
        from app.core.kuzu_connection import get_kuzu_connection
        
        kuzu_conn = get_kuzu_connection()
        print(f"✅ KuzuDB 连接成功")
        
        # 检查数据量
        result = kuzu_conn.execute("MATCH (n) RETURN COUNT(*) as count")
        count = 0
        if result.has_next():
            count = result.get_next()[0]
        
        print(f"✅ 图谱中的实体数: {count}")
        
        if count == 0:
            print(f"⚠️ KuzuDB 为空！")
            print(f"   需要运行: python -m backend.knowledge_layer.seed_ontology")
        else:
            print(f"✅ 图谱已初始化")
    
    except Exception as e:
        print(f"❌ KuzuDB 连接失败: {e}")
        import traceback
        traceback.print_exc()
    
    # ════════════════════════════════════════════════════════════
    # 第 4 步：测试完整分析流程
    # ════════════════════════════════════════════════════════════
    print("\n" + "=" * 100)
    print("【第 4 步】测试完整分析流程")
    print("=" * 100)
    
    try:
        from app.services.analysis_service import perform_deduction
        
        print(f"⏳ 调用 perform_deduction...")
        analysis_result = await perform_deduction(test_news, kuzu_conn)
        
        driving_factor = analysis_result.get('driving_factor', 'N/A')
        confidence = analysis_result.get('confidence', 'N/A')
        
        print(f"✅ 分析完成")
        print(f"\n🎯 核心驱动因素: {driving_factor}")
        print(f"📈 信心度: {confidence}")
        
        # 判断结果
        if driving_factor in ['Unable to determine from LLM response', 'Unknown', 'N/A', None]:
            print(f"\n❌ 结果仍然是 Unknown！")
            print(f"\n🔍 可能的原因:")
            
            if count == 0:
                print(f"   1. ✅ KuzuDB 为空 → 无图谱上下文")
            elif not entities:
                print(f"   2. ✅ 实体提取失败 → 无法查询图谱")
            else:
                print(f"   3. ✅ LLM 限制死了 → 提示词约束过强或 LLM 服务问题")
                print(f"   4. ✅ 解析失败 → LLM 输出格式不符合预期")
        else:
            print(f"\n✅ 成功！已生成具体分析")
            
            alpha = analysis_result.get('scenario_alpha', {})
            beta = analysis_result.get('scenario_beta', {})
            
            print(f"\n【情景 Alpha】")
            print(f"  名称: {alpha.get('name')}")
            print(f"  概率: {alpha.get('probability')}")
            
            print(f"\n【情景 Beta】")
            print(f"  名称: {beta.get('name')}")
            print(f"  概率: {beta.get('probability')}")
        
        print(f"\n📋 完整结果:")
        print(json.dumps(analysis_result, indent=2, ensure_ascii=False))
    
    except Exception as e:
        print(f"❌ 分析失败: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 100)
    print("✅ 诊断完成")
    print("=" * 100)

# 运行
asyncio.run(test_full_pipeline())
