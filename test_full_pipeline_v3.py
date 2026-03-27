#!/usr/bin/env python3
"""修复版本 v3 - 使用正确的导入路径"""

import os
import sys
import json
import asyncio

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

async def test_full_pipeline():
    print("=" * 100)
    print("🧪 完整分析管道测试 v3 - 使用正确的导入")
    print("=" * 100)
    
    test_news = "Google is launching Search Live globally. This AI-powered search enables real-time assistance."
    
    print(f"\n📰 输入新闻:\n{test_news}\n")
    
    # ════════════════════════════════════════════════════════════
    # 第 1 步：本体系统
    # ════════════════════════════════════════════════════════════
    print("\n" + "=" * 100)
    print("【第 1 步】本体系统")
    print("=" * 100)
    
    try:
        from backend.config.ontology import CORE_ONTOLOGY, generate_ontology_system_prompt
        print(f"✅ 本体系统已加载: {len(CORE_ONTOLOGY['NODES'])} 实体类型, {len(CORE_ONTOLOGY['EDGES'])} 关系类型")
    except Exception as e:
        print(f"❌ 本体系统加载失败: {e}")
        return
    
    # ════════════════════════════════════════════════════════════
    # 第 2 步：实体提取
    # ════════════════════════════════════════════════════════════
    print("\n" + "=" * 100)
    print("【第 2 步】实体提取")
    print("=" * 100)
    
    try:
        from app.knowledge.entity_extractor import OntologyConstrainedExtractor
        
        extractor = OntologyConstrainedExtractor()
        extraction_result = extractor.extract(test_news)
        
        entities = extraction_result.get("entities", [])
        relations = extraction_result.get("relations", [])
        
        print(f"✅ 提取完成: {len(entities)} 实体, {len(relations)} 关系")
        print(f"\n   实体:")
        for e in entities:
            print(f"     • {e.get('name')} ({e.get('type')})")
    
    except Exception as e:
        print(f"❌ 实体提取失败: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # ════════════════════════════════════════════════════════════
    # 第 3 步：KuzuDB 连接
    # ══════════���═════════════════════════════════════════════════
    print("\n" + "=" * 100)
    print("【第 3 步】KuzuDB 连接")
    print("=" * 100)
    
    kuzu_conn = None
    
    # 尝试不同的导入方式
    try:
        print("   尝试: from app.knowledge.kuzu_graph import ...")
        from app.knowledge.kuzu_graph import KuzuGraph
        kg = KuzuGraph()
        kuzu_conn = kg.conn
        print(f"✅ 使用 KuzuGraph 成功")
    except Exception as e:
        print(f"   ❌ KuzuGraph: {type(e).__name__}")
    
    if not kuzu_conn:
        try:
            print("   尝试: from backend.knowledge_layer.kuzu_store import ...")
            from backend.knowledge_layer.kuzu_store import KuzuStore
            store = KuzuStore()
            kuzu_conn = store.conn
            print(f"✅ 使用 KuzuStore 成功")
        except Exception as e:
            print(f"   ❌ KuzuStore: {type(e).__name__}")
    
    if not kuzu_conn:
        try:
            print("   尝试: 手动创建连接")
            import kuzu
            db = kuzu.Database("./data/kuzu_db")
            kuzu_conn = kuzu.Connection(db)
            print(f"✅ 手动连接成功")
        except Exception as e:
            print(f"   ❌ 手动连接: {e}")
    
    if kuzu_conn:
        try:
            result = kuzu_conn.execute("MATCH (n) RETURN COUNT(*) as count")
            count = 0
            if result.has_next():
                count = result.get_next()[0]
            print(f"✅ KuzuDB 数据: {count} 实体")
            
            if count == 0:
                print(f"⚠️ 数据库为空！")
        except Exception as e:
            print(f"❌ 查询失败: {e}")
    else:
        print(f"❌ 无法建立 KuzuDB 连接")
    
    # ════════════════════════════════════════════════════════════
    # 第 4 步：完整分析流程
    # ════════════════════════════════════════════════════════════
    print("\n" + "=" * 100)
    print("【第 4 步】完整分析流程")
    print("=" * 100)
    
    if kuzu_conn:
        try:
            from app.services.analysis_service import perform_deduction
            
            print(f"⏳ 调用 perform_deduction...")
            analysis_result = await perform_deduction(test_news, kuzu_conn)
            
            driving_factor = analysis_result.get('driving_factor', 'N/A')
            confidence = analysis_result.get('confidence', 'N/A')
            
            print(f"✅ 分析完成")
            print(f"\n🎯 核心驱动因素: {driving_factor}")
            print(f"📈 信心度: {confidence}")
            
            if driving_factor in ['Unable to determine', 'Unknown', 'N/A', None]:
                print(f"\n❌ 仍然是 Unknown!")
                print(f"\n📊 诊断总结:")
                print(f"   • 本体系统: ✅ 已加载")
                print(f"   • 实体提取: ✅ {len(entities)} 个实体")
                print(f"   • KuzuDB: {'✅ 有数据' if kuzu_conn else '❌ 无连接'}")
                print(f"   • LLM 推理: ❌ 失败")
                print(f"\n💡 可能的根本原因:")
                print(f"   1. ❌ LLM 被本体约束限制死了")
                print(f"   2. ❌ LLM API 配置有问题")
                print(f"   3. ❌ 提示词没有被正确使用")
            else:
                print(f"\n✅ 成功！")
            
            print(f"\n📋 结果:")
            print(json.dumps({
                "driving_factor": driving_factor,
                "confidence": confidence,
                "scenario_alpha": analysis_result.get('scenario_alpha'),
                "scenario_beta": analysis_result.get('scenario_beta'),
            }, indent=2, ensure_ascii=False))
        
        except Exception as e:
            print(f"❌ 分析失败: {e}")
            import traceback
            traceback.print_exc()
    else:
        print(f"⚠️ KuzuDB 连接失败，跳过分析")
    
    print("\n" + "=" * 100)

asyncio.run(test_full_pipeline())
