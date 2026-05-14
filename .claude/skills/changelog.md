# Changelog 规范

## 模板

每次功能完成或阶段结束时，在 `changelogs/YYYY-MM-DD.md` 追加记录。统一使用以下模板：

```markdown
# YYYY-MM-DD

## <branch-name>
**status:** ✅ done / 🚧 WIP
**todo:** <下一步描述，无则写 none>

**done**
 1. ✅ <完成项>
 2. ✅ <完成项>

**tests** <框架/工具>：<覆盖了什么，简明扼要> · **review** <状态>
```

## 规则

- 每个 `## <branch-name>` 块对应一个分支的工作记录
- 同一文件可包含多个分支的记录
- 字段名统一用英文小写：`status`、`todo`、`done`、`tests`、`review`
- `tests` 需写明测试框架/工具以及覆盖范围，简明扼要，例如：`pytest：27 个单元测试，覆盖 Auth API + Service + 模型`
- 会话开始时读取最新 changelog，检查每个有 `todo` 的记录：若其 `branch` 与当前 git 分支不一致，提醒用户可能需要切换分支
