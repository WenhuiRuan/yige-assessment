# Task A - Inventory Reservation Ledger

## 运行

在仓库根目录执行，依赖安装见根 README：

```powershell
Get-Content A/examples/sample.in | .venv/Scripts/python.exe -m A.main
.venv/Scripts/python.exe -m pytest A/tests -q
```

程序从 stdin 读取命令，向 stdout 输出结果。用字典记录每个订单的预留，用集合记录已处理事件，并增量维护总预留。

## 边界情况测试

下列用例在 [test_ledger.py](tests/test_ledger.py) 中实现；输入行数和命令行输出另由 [test_cli.py](tests/test_cli.py) 验证。

| 情况 | 预期结果 |
| --- | --- |
| 库存为 0，预留 1 件 | REJECTED，库存和预留不变 |
| 库存为 4，分别尝试预留 4 件、5 件 | 前者成功且可用库存归零，后者拒绝 |
| 订单预留 2 件，却释放或发货 3 件；或订单不存在 | 拒绝，不能动用其他订单的预留 |
| 部分释放、全部释放；部分发货、全部发货 | 释放只减少预留；发货同时减少在库和预留；归零订单不出现在最终列表中 |
| 数量为 0、负数、小数，或缺少字段 | 拒绝，库存、订单及事件集合均不改变 |
| 单次数量达到 10^12，多次累加超过 10^12 | 单次上限有效，累计库存与预留仍能正确计算 |

另外检查开放订单按 ID 排序，以及输入首行、行数错误时不输出部分结果。

## 重放测试

同样在 [test_ledger.py](tests/test_ledger.py) 中检查以下情况：

- 四种命令成功后，再发送同一事件：返回 DUPLICATE，完整状态与重放前一致。
- 库存为 0 时预留被拒，补货 5 件后重放原事件：仍返回 DUPLICATE，不重新预留。
- 释放或发货因订单预留不足被拒后，使用原 ID 重试：仍视为已处理。
- 已处理 ID 换成其他合法订单、数量或命令：仍返回 DUPLICATE。
- 首次格式错误不登记 ID，修正后可以执行。我采用先校验格式再查重复的顺序，因此已处理 ID 搭配非法数量仍返回 REJECTED。

随机测试逐步与独立参考模型比较，规模测试覆盖 20 万条命令。

## 复杂度与输出约定

N 条命令均摊 O(N)，最后 R 个开放订单排序 O(R log R)，总时间 O(N+R log R)。账本空间 O(E+R)，E 为已登记事件数；输入缓存另占 O(L)，L 为输入长度。哈希操作按定长 ID 和整数计算，长 ID 的字符处理成本另计。

最终输出 `OPEN K`，随后每行 `order_id quantity`。首行或行数错误写入 stderr，退出码为 2；单条坏命令返回 REJECTED，后续继续。ID 使用非空可打印 ASCII。
