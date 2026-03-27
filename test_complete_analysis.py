#!/usr/bin/env python3
"""完整分析流程测试 - 现在有数据了"""

import os
import sys
import json
import asyncio

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

async def main():
    print("=" * 100)
    print("🧪 完整分析流程测试 - KuzuDB 已初始化")
    print("=" * 100)
    
    test_news = "Google is launching Search Live globally. This AI-powered search enables real-time assistance via phone camera."
    
    print(f"\n📰 新闻: {test_news}\n")
    
    # ════════════════════════════════════════════════════════════
    # 第 1 步：验证 KuzuDB 数据
    # ════════════════════════════════════════════════════════════
    print("【第 1 步】验证 KuzuDB 数据")
    print("=" * 100)
    
    try:
        import kuzu
        db = kuzu.Database("./data/kuzu_db.db")
        conn = kuzu.Connection(db)
        
        result = conn.execute("MATCH (n) RETURN COUNT(*) as count")
        entity_count = 0
        if result.has_next():
            entity_count = result.get_next()[0]
        
        result = conn.execute("MATCH ()-[r]->() RETURN COUNT(*) as count")
        rel_count = 0
        if result.has_next():
            rel_count = result.get_next()[0]
        
        print(f"✅ KuzuDB 连接成功")
        print(f"   - 实体数: {entity_count}")
        print(f"   - 关系数: {rel_count}")
        
    except Exception as e:
        print(f"❌ KuzuDB 连接失败: {e}")
        return
    
    # ════════════════════════════════════════════════════════════
    # 第 2 步：实体提取
    # ════════════════════════════════════════════════════════════
    print("\n【第 2 步】实体提取")
    print("=" * 100)
    
    try:
        from app.knowledge.entity_extractor import OntologyConstrainedExtractor
        
        extractor = OntologyConstrainedExtractor()
        result = extractor.extract(test_news)
        
        entities = result.get("entities", [])
        relations = result.get("relations", [])
        report = result.get("validation_report", {})
        
        print(f"✅ 提取完成")
        print(f"   - 实体: {len(entities)} 个")
        print(f"   - 关系: {len(relations)} 个")
        print(f"   - 合规率: {report.get('compliance_pct')}%")
        
        print(f"\n   提取的实体:")
        for e in entities:
            print(f"     • {e['name']} ({e['type']})")
        
        if relations:
            print(f"\n   提取的关系:")
            for r in relations:
                print(f"     • {r['from']} --{r['relation']}--> {r['to']}")
        
    except Exception as e:
        print(f"❌ 实体提取失败: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # ════════════════════════════════════════════════════════════
    # 第 3 步：完整分析推演
    # ════════════════════════════════════════════════════════════
    print("\n【第 3 步】完整分析推演")
    print("=" * 100)
    
    try:
        from app.services.analysis_service import perform_deduction
        
        print(f"⏳ 调用 perform_deduction...")
        analysis_result = await perform_deduction(test_news, conn)
        
        driving_factor = analysis_result.get('driving_factor')
        confidence = analysis_result.get('confidence')
        
        print(f"✅ 分析完成")
        print(f"\n🎯 核���驱动因素: {driving_factor}")
        print(f"📈 信心度: {confidence}")
        
        if driving_factor in ['Unable to determine', 'Unknown', None, 'N/A']:
            print(f"\n❌ 仍然是 Unknown!")
            print(f"\n📊 诊断:")
            print(f"   • 本体系统: ✅ 已加载")
            print(f"   • 实体提取: ✅ {len(entities)} 个实体")
            print(f"   • KuzuDB: ✅ {entity_count} 个实体，{rel_count} 个关系")
            print(f"   • LLM 推理: ❌ 失败")
            print(f"\n💡 可能的原因:")
            print(f"   1. LLM 被提示词约束限制死了")
            print(f"   2. LLM API 配置问题")
            print(f"   3. LLM 输出解析失败")
        else:
            print(f"\n✅ 成功！已生成具体分析")
            
            alpha = analysis_result.get('scenario_alpha', {})
            beta = analysis_result.get('scenario_beta', {})
            
            if alpha:
                print(f"\n【情景 Alpha】")
                print(f"  • 名称: {alpha.get('name')}")
                print(f"  • 概率: {alpha.get('probability')}")
                print(f"  • 描述: {alpha.get('description', 'N/A')[:100]}")
            
            if beta:
                print(f"\n【情景 Beta】")
                print(f"  • 名称: {beta.get('name')}")
                print(f"  • 概率: {beta.get('probability')}")
                print(f"  • 描述: {beta.get('description', 'N/A')[:100]}")
        
        print(f"\n📋 完整结果（前 500 字符）:")
        result_str = json.dumps(analysis_result, indent=2, ensure_ascii=False)
        print(result_str[:500])
        
    except Exception as e:
        print(f"❌ 分析失败: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 100)
    print("✅ 测试完成")
    print("=" * 100)

asyncio.run(main())
