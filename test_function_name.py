#!/usr/bin/env python3
"""检查函数名是否匹配"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

print("检查 ontology.py 中的函数名:")
print("-" * 80)

try:
    import backend.config.ontology as ont_module
    
    # 列出所有公开函数
    functions = [name for name in dir(ont_module) if not name.startswith('_')]
    print(f"✅ 导出的函数和变量: {functions}")
    
    # 检查是否有特定函数
    if hasattr(ont_module, 'generate_extraction_system_prompt'):
        print("✅ generate_extraction_system_prompt 存在")
    else:
        print("❌ generate_extraction_system_prompt 不存在")
    
    if hasattr(ont_module, 'generate_ontology_system_prompt'):
        print("✅ generate_ontology_system_prompt 存在")
    else:
        print("❌ generate_ontology_system_prompt 不存在")
    
    if hasattr(ont_module, 'build_validation_report'):
        print("✅ build_validation_report 存在")
    else:
        print("❌ build_validation_report 不存在")
    
except Exception as e:
    print(f"❌ 导入失败: {e}")
    import traceback
    traceback.print_exc()
