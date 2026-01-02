#!/usr/bin/env python3
# Copyright (C) 2025 PhoneAgent Contributors
# Licensed under AGPL-3.0

"""
应用配置管理模块 - 动态配置管理器

重要说明：
  本模块管理 data/app_config.json 动态配置文件，优先级高于静态配置。

  推荐使用方式：
    1. 前端通过"应用配置"页面手动添加/编辑应用
    2. 系统自动维护 data/app_config.json
    3. 启动时自动加载并与静态配置合并

  设备扫描功能已弃用：
    - scan_device_apps() - 已弃用，不建议使用
    - sync_from_device() - 已弃用，不建议使用
    - 原因：扫描出的包名为英文，用户体验差
    - 替代方案：使用200+预置应用 + 手动添加

职责:
  1. 管理应用配置文件 (data/app_config.json)
  2. 提供完整的CRUD操作
  3. 支持别名、分类、启用状态等高级功能
  4. 与静态配置合并（静态作为兜底）

架构定位:
  - 动态配置: 运行时可修改，无需重启
  - 唯一入口: 所有动态配置操作都通过此模块
  - 优先级: 第一优先（优先于静态配置）

使用方式:
  ```python
  from phone_agent.config.app_manager import get_app_manager

  # 获取全局管理器
  manager = get_app_manager()

  # 查找应用（支持中文、英文、别名）
  app = manager.find_app("微信")
  if app and app.enabled:
      print(f"包名: {app.package_name}")

  # 手动添加应用
  manager.add_app("微信", "com.tencent.mm", category="社交")
  ```

API端点:
  - GET    /api/v1/apps              - 获取应用列表
  - GET    /api/v1/apps/{package}    - 获取应用详情
  - POST   /api/v1/apps              - 创建/更新应用
  - DELETE /api/v1/apps/{package}    - 删除应用
  - POST   /api/v1/apps/search       - 搜索应用

相关文件:
  - phone_agent/config/apps.py - 静态配置（兜底，200+预置应用）
  - server/api/app_config_routes.py - API路由
  - data/app_config.json - 动态配置文件（用户可编辑）
  - web/src/views/AppConfig.vue - 前端管理界面
"""

import json
import logging
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class AppConfig:
    """应用配置数据类"""

    package_name: str  # 包名 (唯一标识)
    display_name: str  # 中文显示名
    display_name_en: Optional[str] = None  # 英文显示名
    aliases: List[str] = None  # 别名列表
    description: Optional[str] = None  # 描述
    enabled: bool = True  # 是否启用
    category: str = "其他"  # 分类
    icon: Optional[str] = None  # 图标路径
    version: Optional[str] = None  # 版本号
    last_updated: Optional[str] = None  # 最后更新时间

    def __post_init__(self):
        if self.aliases is None:
            self.aliases = []
        if self.last_updated is None:
            self.last_updated = datetime.now().isoformat()

    def to_dict(self) -> Dict:
        """转换为字典"""
        data = asdict(self)
        # 移除None值
        return {k: v for k, v in data.items() if v is not None}


class AppConfigManager:
    """
    应用配置管理器

    功能:
      - 加载/保存配置文件 (data/app_config.json)
      - 扫描设备应用
      - 同步设备应用到配置
      - 查询/搜索应用（支持多种匹配方式）
      - 启用/禁用应用

    特性:
      - 全局单例（通过 get_app_manager() 获取）
      - 懒加载（首次调用时才加载配置）
      - 自动保存（修改后自动写入文件）
    """

    def __init__(self, config_path: str = "data/app_config.json"):
        self.config_path = Path(config_path)
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self._apps: Dict[str, AppConfig] = {}
        self._load_static_config()  # 先加载静态配置（兜底）
        self._load_config()  # 再加载动态配置（覆盖）

    def _load_static_config(self):
        """加载静态配置（apps.py）作为兜底"""
        try:
            from phone_agent.config.apps import APP_PACKAGES

            for display_name, package_name in APP_PACKAGES.items():
                # 只添加静态配置中有的应用
                if package_name not in self._apps:
                    app = AppConfig(
                        package_name=package_name,
                        display_name=display_name,
                        display_name_en=None,
                        aliases=[],
                        description=f"预置应用: {display_name}",
                        enabled=True,  # 默认启用
                        category="其他",  # 默认分类
                    )
                    self._apps[package_name] = app

            logger.info(f"从静态配置加载了 {len(APP_PACKAGES)} 个预置应用")
        except Exception as e:
            logger.warning(f"加载静态配置失败: {e}")

    def _load_config(self):
        """加载动态配置文件（覆盖静态配置）"""
        if self.config_path.exists():
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for item in data:
                        app = AppConfig(**item)
                        self._apps[app.package_name] = app  # 覆盖静态配置
                logger.info(f"从动态配置加载了 {len(data)} 个应用（覆盖静态配置）")
            except Exception as e:
                logger.error(f"加载动态配置失败: {e}")
        else:
            logger.info("动态配置文件不存在，使用静态配置")

    def save_config(self):
        """保存配置到文件"""
        try:
            apps_list = [app.to_dict() for app in self._apps.values()]
            # 按包名排序
            apps_list.sort(key=lambda x: x["package_name"])

            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(apps_list, f, ensure_ascii=False, indent=2)

            logger.info(f"保存了 {len(apps_list)} 个应用配置到 {self.config_path}")
            return True
        except Exception as e:
            logger.error(f"保存配置失败: {e}")
            return False

    def scan_device_apps(self, device_id: Optional[str] = None) -> List[Dict]:
        """
        已弃用：扫描设备上已安装的应用

        不建议使用原因：
          - 扫描出的包名为英文（如 "Chrome" 而非 "谷歌浏览器"）
          - 用户体验差，需要手动翻译
          - 建议使用200+预置应用 + 手动添加

        Args:
            device_id: 设备ID

        Returns:
            应用列表 [{"package": "...", "label": "..."}, ...]
        """
        from phone_agent.adb.device import _get_adb_prefix

        adb_prefix = _get_adb_prefix(device_id)
        installed_apps = []

        try:
            # 获取所有第三方应用（排除系统应用）
            logger.info("🔍 扫描设备应用...")

            result = subprocess.run(
                adb_prefix + ["shell", "pm", "list", "packages", "-3"],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode != 0:
                logger.error(f"扫描失败: {result.stderr}")
                return []

            packages = []
            for line in result.stdout.strip().split("\n"):
                if line.startswith("package:"):
                    package = line.replace("package:", "").strip()
                    packages.append(package)

            logger.info(f"找到 {len(packages)} 个第三方应用")

            # 优化：批量获取应用名称，而不是逐个查询
            # 使用 pm list packages -f 一次性获取所有应用信息
            logger.info("正在批量获取应用名称...")

            # 构建包名到标签的映射
            package_labels = {}
            try:
                # 尝试使用更快的方法：pm list packages -U (包含应用uid和label)
                label_result = subprocess.run(
                    adb_prefix + ["shell", "pm", "list", "packages", "-U"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )

                # 解析输出，提取包名
                for line in label_result.stdout.strip().split("\n"):
                    if line.startswith("package:"):
                        parts = line.split()
                        if len(parts) >= 2:
                            package = parts[0].replace("package:", "")
                            # 暂时使用包名最后一段作为标签
                            if package in packages:
                                package_labels[package] = package.split(".")[-1].capitalize()
            except Exception as e:
                logger.warning(f"批量获取失败，使用默认标签: {e}")

            # 构建应用列表
            for package in packages:
                label = package_labels.get(package, package.split(".")[-1].capitalize())
                installed_apps.append({"package": package, "label": label})

            logger.info(f"成功获取 {len(installed_apps)} 个应用信息（优化后）")
            return installed_apps

        except Exception as e:
            logger.error(f"扫描设备应用失败: {e}")
            return []

    def _extract_app_label(self, dump_output: str) -> Optional[str]:
        """从dumpsys输出提取应用标签"""
        for line in dump_output.split("\n"):
            if "label=" in line:
                label = line.split("label=")[-1].strip()
                return label
        return None

    def sync_from_device(
        self,
        device_id: Optional[str] = None,
        auto_enable: bool = False,
        merge_mode: str = "add_new",
    ) -> dict:
        """
        已弃用：从设备同步应用配置

        不建议使用原因：
          - 扫描出的包名为英文，用户体验差
          - 建议使用200+预置应用 + 手动添加
          - 前端"扫描设备应用"按钮已移除

        Args:
            device_id: 设备ID
            auto_enable: 自动启用所有应用（默认False，需要用户手动启用）
            merge_mode: 合并模式
                - "add_new": 只添加新应用，保留现有配置
                - "update_all": 更新所有应用（覆盖现有配置）
                - "replace": 完全替换配置文件

        Returns:
            字典包含: new_apps, removed_apps, kept_apps
        """
        installed_apps = self.scan_device_apps(device_id)

        if not installed_apps:
            logger.warning("未扫描到应用，同步取消")
            return {"new_apps": 0, "removed_apps": 0, "kept_apps": 0}

        # 统计变量
        new_count = 0
        updated_count = 0
        kept_count = 0
        removed_count = 0

        # 获取现有应用包名集合
        existing_packages = set(self._apps.keys())
        {app["package"] for app in installed_apps}

        if merge_mode == "replace":
            # 完全替换模式：记录要删除的应用
            removed_count = len(existing_packages)
            self._apps = {}

        # 处理设备上的应用
        for app_info in installed_apps:
            package = app_info["package"]
            label = app_info["label"]

            if package in self._apps:
                if merge_mode == "update_all":
                    # 更新现有应用
                    self._apps[package].display_name = label
                    self._apps[package].last_updated = datetime.now().isoformat()
                    updated_count += 1
                    logger.debug(f"更新应用: {label} ({package})")
                else:
                    # 保留已存在的
                    kept_count += 1
                    logger.debug(f"保留已有应用: {label} ({package})")
            else:
                # 添加新应用
                new_app = AppConfig(
                    package_name=package,
                    display_name=label,
                    enabled=auto_enable,  # 根据参数决定是否自动启用
                    category=self._guess_category(package),
                )
                self._apps[package] = new_app
                new_count += 1
                logger.info(f"新增应用: {label} ({package})")

        # 保存配置
        total_changes = new_count + updated_count + removed_count
        if total_changes > 0:
            self.save_config()
            logger.info(
                f"同步完成：新增 {new_count}，更新 {updated_count}，删除 {removed_count}，保留 {kept_count}"
            )
        else:
            logger.info("没有应用需要同步")

        return {
            "new_apps": new_count,
            "removed_apps": removed_count,
            "kept_apps": kept_count + updated_count,  # 保留 = 未变动 + 更新
        }

    def _guess_category(self, package_name: str) -> str:
        """根据包名猜测应用分类"""
        package_lower = package_name.lower()

        if any(
            x in package_lower
            for x in ["wechat", "qq", "whatsapp", "telegram", "mm", "slack", "discord"]
        ):
            return "社交"
        elif any(x in package_lower for x in ["taobao", "jd", "shop", "mall", "buy", "pinduoduo"]):
            return "购物"
        elif any(x in package_lower for x in ["alipay", "bank", "pay", "wallet"]):
            return "金融"
        elif any(x in package_lower for x in ["music", "video", "player", "tv", "bili", "douyin"]):
            return "娱乐"
        elif any(x in package_lower for x in ["setting", "launcher", "systemui"]):
            return "系统"
        elif any(x in package_lower for x in ["game"]):
            return "游戏"
        elif any(x in package_lower for x in ["camera", "gallery", "photo"]):
            return "拍照"
        elif any(
            x in package_lower
            for x in ["note", "calculator", "calendar", "clock", "weather", "compass", "scanner"]
        ):
            return "工具"
        else:
            return "其他"

    def get_all_apps(self, enabled_only: bool = False) -> List[AppConfig]:
        """获取所有应用"""
        apps = list(self._apps.values())
        if enabled_only:
            apps = [app for app in apps if app.enabled]
        return apps

    def get_app(self, package_name: str) -> Optional[AppConfig]:
        """根据包名获取应用"""
        return self._apps.get(package_name)

    def find_app(self, name: str) -> Optional[AppConfig]:
        """
        根据名称查找应用（支持多种匹配方式）

        匹配优先级:
        1. 包名完全匹配
        2. 中文显示名匹配
        3. 英文显示名匹配（不区分大小写）
        4. 别名匹配（不区分大小写）
        """
        name_lower = name.lower()

        # 1. 包名匹配
        if name in self._apps:
            return self._apps[name]

        # 2. 显示名/别名匹配
        for app in self._apps.values():
            # 中文显示名
            if app.display_name == name:
                return app

            # 英文显示名
            if app.display_name_en and app.display_name_en.lower() == name_lower:
                return app

            # 别名
            if any(alias.lower() == name_lower for alias in app.aliases):
                return app

        return None

    def set_app_enabled(self, package_name: str, enabled: bool) -> bool:
        """启用/禁用应用"""
        if package_name in self._apps:
            self._apps[package_name].enabled = enabled
            self.save_config()
            return True
        return False

    def add_or_update_app(self, app: AppConfig) -> bool:
        """添加或更新应用配置"""
        self._apps[app.package_name] = app
        return self.save_config()

    def remove_app(self, package_name: str) -> bool:
        """删除应用配置"""
        if package_name in self._apps:
            del self._apps[package_name]
            return self.save_config()
        return False

    def get_stats(self) -> Dict:
        """获取统计信息"""
        total = len(self._apps)
        enabled = sum(1 for app in self._apps.values() if app.enabled)

        # 按分类统计
        categories = {}
        for app in self._apps.values():
            cat = app.category
            categories[cat] = categories.get(cat, 0) + 1

        return {
            "total": total,
            "enabled": enabled,
            "disabled": total - enabled,
            "categories": categories,
        }


# 全局实例
_app_manager = None


def get_app_manager() -> AppConfigManager:
    """
    获取全局应用配置管理器（单例模式）

    Returns:
        全局AppConfigManager实例

    示例:
        >>> manager = get_app_manager()
        >>> app = manager.find_app("微信")
        >>> if app:
        ...     print(app.package_name)
        'com.tencent.mm'
    """
    global _app_manager
    if _app_manager is None:
        _app_manager = AppConfigManager()
    return _app_manager


if __name__ == "__main__":
    # 测试代码
    import sys

    if len(sys.argv) < 2:
        print("用法:")
        print("  python app_manager.py scan [device_id]  - 扫描设备应用")
        print("  python app_manager.py sync [device_id]  - 同步到配置文件")
        print("  python app_manager.py list              - 列出配置的应用")
        print("  python app_manager.py stats             - 显示统计信息")
        sys.exit(1)

    manager = AppConfigManager()
    command = sys.argv[1]

    if command == "scan":
        device_id = sys.argv[2] if len(sys.argv) > 2 else None
        apps = manager.scan_device_apps(device_id)
        print(f"\n扫描到 {len(apps)} 个应用:\n")
        for app in apps:
            print(f"  - {app['label']:<20} ({app['package']})")

    elif command == "sync":
        device_id = sys.argv[2] if len(sys.argv) > 2 else None
        count = manager.sync_from_device(device_id, auto_enable=False)
        print(f"\n同步完成，处理了 {count} 个应用")
        print(f"配置文件: {manager.config_path}")
        print("\n提示: 新应用默认为禁用状态，请到前端界面或手动编辑配置文件启用")

    elif command == "list":
        apps = manager.get_all_apps()
        print(f"\n配置的应用 ({len(apps)} 个):\n")
        for app in apps:
            status = "[ON]" if app.enabled else "[OFF]"
            print(f"  {status} {app.display_name:<20} [{app.category}] ({app.package_name})")

    elif command == "stats":
        stats = manager.get_stats()
        print("\n📊 应用统计:")
        print(f"  总计: {stats['total']}")
        print(f"  启用: {stats['enabled']}")
        print(f"  禁用: {stats['disabled']}")
        print("\n按分类:")
        for cat, count in stats["categories"].items():
            print(f"  {cat}: {count}")

    else:
        print(f"未知命令: {command}")
