"""
测试小世界模型 - 意图驱动的主权智能体

演示：人输入意图 → 小世界模型解析意图 → World Model 自己产生 Δ → Agent 自发行动
"""

import asyncio
import json
from xingtu import XingTuService
from xingtu.config import XingTuConfig


async def test_intent_processing():
    """测试意图处理流程"""

    # 1. 初始化服务
    print("=" * 60)
    print("初始化星图服务...")
    print("=" * 60)

    config = XingTuConfig.default()
    service = XingTuService(config)
    service.initialize()

    # 2. 查看当前世界模型
    print("\n当前世界模型状态：")
    world = service.get_world_model()
    print(json.dumps(world, indent=2, ensure_ascii=False))

    # 3. 输入意图
    print("\n" + "=" * 60)
    print("测试意图处理")
    print("=" * 60)

    intent_text = "创建一个名为'客户数据'的集合，用于存储客户信息"

    print(f"\n用户意图: {intent_text}")
    print("\n处理中...")

    # 4. 处理意图
    result = await service.universe.process_intent(
        intent_text=intent_text,
        user_id="test_user",
        auto_execute=True,
    )

    # 5. 显示结果
    print("\n处理结果：")
    print(f"- 成功: {result['success']}")

    if result['success']:
        goal = result['goal']
        print(f"\n目标信息：")
        print(f"  - ID: {goal['id']}")
        print(f"  - 意图: {goal['intent_text']}")
        print(f"  - 置信度: {goal['confidence']}")
        print(f"  - 推理: {goal['reasoning']}")

        print(f"\n生成的差分数量: {result['delta_count']}")

        for i, delta in enumerate(result['deltas'], 1):
            print(f"\n差分 #{i}:")
            print(f"  - 类型: {delta['delta_type']}")
            print(f"  - 目标: {delta['target_type']}")
            print(f"  - 优先级: {delta['priority']}")
            print(f"  - 行技: {delta['xingji_id']}")
            print(f"  - 已执行: {delta['is_executed']}")
            if delta['error_message']:
                print(f"  - 错误: {delta['error_message']}")

        if result['auto_executed']:
            print(f"\n执行结果:")
            for i, exec_result in enumerate(result['execution_results'], 1):
                print(f"  差分 #{i}: {'成功' if exec_result.get('success') else '失败'}")
                if not exec_result.get('success'):
                    print(f"    错误: {exec_result.get('error')}")
    else:
        print(f"错误: {result.get('error')}")

    # 6. 查看更新后的世界模型
    print("\n" + "=" * 60)
    print("更新后的世界模型：")
    print("=" * 60)

    world_after = service.get_world_model()
    print(f"集合数量: {world_after['collection_count']}")
    print(f"文档数量: {world_after['document_count']}")

    if world_after['collections']:
        print("\n集合列表:")
        for col in world_after['collections']:
            print(f"  - {col['name']} ({col['collection_type']}): {col['status']}")


async def test_complex_intent():
    """测试复杂意图"""

    print("\n" + "=" * 60)
    print("测试复杂意图")
    print("=" * 60)

    config = XingTuConfig.default()
    service = XingTuService(config)
    service.initialize()

    # 复杂意图：创建集合 + 添加文档 + 建立关系
    intent_text = """
    创建两个集合：'产品目录' 和 '销售记录'，
    然后在产品目录中添加几个产品信息，
    最后建立产品和销售记录之间的关联关系
    """

    print(f"\n用户意图: {intent_text.strip()}")
    print("\n处理中...")

    result = await service.universe.process_intent(
        intent_text=intent_text,
        user_id="test_user",
        auto_execute=True,
    )

    print(f"\n结果: {'成功' if result['success'] else '失败'}")
    print(f"生成差分数: {result.get('delta_count', 0)}")

    if result['success']:
        goal = result['goal']
        print(f"置信度: {goal['confidence']}")
        print(f"\n预期状态:")
        print(f"  - 集合: {len(goal['expected_collections'])} 个")
        print(f"  - 文档: {len(goal['expected_documents'])} 个")
        print(f"  - 关系: {len(goal['expected_relations'])} 个")


def main():
    """主函数"""
    print("星图小世界模型测试")
    print("=" * 60)
    print("核心理念：差分即行动指南")
    print("流程：意图 → 目标 → 差分 → 执行")
    print("=" * 60)

    # 运行测试
    asyncio.run(test_intent_processing())

    # 运行复杂测试
    # asyncio.run(test_complex_intent())


if __name__ == "__main__":
    main()
