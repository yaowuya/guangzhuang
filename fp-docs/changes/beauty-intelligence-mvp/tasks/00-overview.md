# 标题版美妆情报台 Task Plan Overview

状态：用户已确认规范任务计划，进入 `fp-execute` full 模式。此总览只负责两端入口、跨端依赖和派生进度；任务正文与唯一完成标记由各端 manifest 指定的任务分片持有。

## Canonical End Entrypoints

| End | Canonical entrypoint | Mode |
| --- | --- | --- |
| Backend | [tasks/backend/00-index.md](<backend/00-index.md>) | split |
| Frontend | [tasks/frontend/00-index.md](<frontend/00-index.md>) | split |

## Cross-end Dependency Edges

方向为前置任务 → 消费任务。以下 27 条边来自两端任务 owner 的 Depends on；同端依赖不在此复制。

| From task | To task | Shared contract / gate |
| --- | --- | --- |
| [frontend-001](<frontend/10-foundation-tasks.md>) | [backend-039](<backend/70-release-tasks.md>) | 独立前端静态构建供 Caddy 消费，不等待完整 UI 验收 |
| [backend-008](<backend/20-auth-tasks.md>) | [frontend-006](<frontend/20-access-navigation-tasks.md>) | 单人认证、服务端会话与写保护 |
| [backend-039](<backend/70-release-tasks.md>) | [frontend-006](<frontend/20-access-navigation-tasks.md>) | 真实同域 HTTPS 页面与 API 入口 |
| [backend-012](<backend/30-reading-tasks.md>) | [frontend-009](<frontend/30-reading-tasks.md>) | 标题、分页、筛选与详情读取契约 |
| [backend-039](<backend/70-release-tasks.md>) | [frontend-009](<frontend/30-reading-tasks.md>) | 同域页面与真实 API |
| [backend-041](<backend/80-live-acceptance-tasks.md>) | [frontend-009](<frontend/30-reading-tasks.md>) | 已获准来源的真实标题前提，不依赖未来刷新 UI 解锁 |
| [backend-012](<backend/30-reading-tasks.md>) | [frontend-010](<frontend/30-reading-tasks.md>) | 组合筛选、动态选项、日期与分页 |
| [backend-039](<backend/70-release-tasks.md>) | [frontend-010](<frontend/30-reading-tasks.md>) | 真实同域筛选页面 |
| [backend-012](<backend/30-reading-tasks.md>) | [frontend-011](<frontend/40-detail-media-tasks.md>) | 条目详情与出处读取 |
| [backend-039](<backend/70-release-tasks.md>) | [frontend-011](<frontend/40-detail-media-tasks.md>) | 真实详情侧栏与导航环境 |
| [backend-012](<backend/30-reading-tasks.md>) | [frontend-012](<frontend/40-detail-media-tasks.md>) | 允许展示的图片 URL 与原文链接 |
| [backend-039](<backend/70-release-tasks.md>) | [frontend-012](<frontend/40-detail-media-tasks.md>) | 浏览器直连图片与同域业务页面 |
| [backend-014](<backend/30-reading-tasks.md>) | [frontend-013](<frontend/50-bookmark-tasks.md>) | 幂等收藏写入及服务端确认状态 |
| [backend-039](<backend/70-release-tasks.md>) | [frontend-013](<frontend/50-bookmark-tasks.md>) | 真实会话下的页面收藏操作 |
| [backend-014](<backend/30-reading-tasks.md>) | [frontend-014](<frontend/50-bookmark-tasks.md>) | 收藏列表、排序与取消操作 |
| [backend-039](<backend/70-release-tasks.md>) | [frontend-014](<frontend/50-bookmark-tasks.md>) | 同域收藏页与路由返回 |
| [backend-016](<backend/40-source-security-tasks.md>) | [frontend-015](<frontend/60-source-update-tasks.md>) | 五站各入口的只读核验与运行状态 |
| [backend-039](<backend/70-release-tasks.md>) | [frontend-015](<frontend/60-source-update-tasks.md>) | 真实来源状态面板 |
| [backend-025](<backend/50-job-tasks.md>) | [frontend-016](<frontend/60-source-update-tasks.md>) | 提交更新、查询任务和失败入口重试 |
| [backend-039](<backend/70-release-tasks.md>) | [frontend-016](<frontend/60-source-update-tasks.md>) | 真实页面刷新与任务进度 |
| [backend-008](<backend/20-auth-tasks.md>) | [frontend-019](<frontend/80-delivery-tasks.md>) | 正常页面登录、过期和退出 |
| [backend-012](<backend/30-reading-tasks.md>) | [frontend-019](<frontend/80-delivery-tasks.md>) | 真实标题、筛选、分页和出处 |
| [backend-014](<backend/30-reading-tasks.md>) | [frontend-019](<frontend/80-delivery-tasks.md>) | 真实收藏、持久回看、取消与清理 |
| [backend-016](<backend/40-source-security-tasks.md>) | [frontend-019](<frontend/80-delivery-tasks.md>) | 入口许可与启用状态核对 |
| [backend-025](<backend/50-job-tasks.md>) | [frontend-019](<frontend/80-delivery-tasks.md>) | 页面触发真实更新并观察任务结果 |
| [backend-039](<backend/70-release-tasks.md>) | [frontend-019](<frontend/80-delivery-tasks.md>) | 目标 HTTPS、实际构建与同域接口 |
| [backend-041](<backend/80-live-acceptance-tasks.md>) | [frontend-019](<frontend/80-delivery-tasks.md>) | 至少一个来源在目标环境真实更新成功 |

## Progress Totals

以下数值由唯一 owner 的任务 checkbox 派生，只是只读汇总，不是独立完成依据。计划生成和文档校验不计为任务执行完成。

| End | Total | Complete | Remaining |
| --- | ---: | ---: | ---: |
| Backend | 45 | 32 | 13 |
| Frontend | 19 | 6 | 13 |
| Total | 64 | 38 | 26 |
