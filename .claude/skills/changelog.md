# Changelog 规范

## 模板

```markdown
## <branch-name>
**git:** local | pushed
**spec:** `path/to/spec.md` | —

**todo**
- [ ] 子任务 A
- [ ] 子任务 B

**done**
1. ✅🧪 有测试的完成项
2. ✅ 无需测试的完成项
```

符号说明：`✅🧪` = 完成且有测试覆盖，`✅` = 完成无测试（配置/文档/chore 类）

---

## 规则

**文件**
- 每天一个文件：`changelogs/YYYY-MM-DD.md`，文件头一行写 `# YYYY-MM-DD`
- 每个分支在当天文件里只有一个块，多次 commit 追加 done 条目，不新建块
- 第二天同一分支继续开发：在新文件里重新写该分支的块，todo 带入未完成项

**字段**
- `git` — 只有两个值：`local`（committed 未 push）/ `pushed`（已推远端）；commit 后改 local，push 后改 pushed
- `spec` — 对应的 spec 文件路径；无 spec 的 chore/fix 写 `—`
- `todo` — 该分支所有待做子任务，完整列出；完成后从这里删掉、加到 done
- `done` — 已完成项，按完成顺序追加；`✅🧪` 表示有测试覆盖，`✅` 表示无测试

**时机**
- 每次 commit 前：把刚完成的任务从 todo 移到 done，git 改为 `local`，纳入本次 commit
- 每次 push 后：把 git 改为 `pushed`，单独 commit 或合并到下次 commit 均可

**读取**
- 每次会话开始，读最新的 changelog 文件，检查 todo 和当前分支是否一致
- 不需要扫所有 changelog，只读最新一篇
