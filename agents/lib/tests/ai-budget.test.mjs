import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { initBudget, claimBudget, budgetStatus } from "../ai-budget.mjs";

function withTempRoot(fn) {
  const root = mkdtempSync(join(tmpdir(), "ax-budget-"));
  try {
    return fn(root);
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
}

export async function test(register, assert) {
  register("ai-budget init은 동일 session 재호출 시 멱등하다", () => {
    withTempRoot((root) => {
      const first = initBudget({ root, session: "s1", initial: 3, retries: 2 });
      const second = initBudget({ root, session: "s1", initial: 99, retries: 99 });
      assert.equal(second.limits.initial, 3, "재init이 기존 한도를 덮어쓰면 안 됨");
      assert.equal(first.used.initial, 0);
    });
  });

  register("initial claim은 role마다 정확히 1회 허용된다", () => {
    withTempRoot((root) => {
      initBudget({ root, session: "s1", initial: 3, retries: 2 });
      const claim = claimBudget({ root, session: "s1", role: "analyzer", kind: "initial" });
      assert.equal(claim.allowed, true);
      assert.equal(budgetStatus(root).used.initial, 1);

      let threw = false;
      try {
        claimBudget({ root, session: "s1", role: "analyzer", kind: "initial" });
      } catch (e) {
        threw = true;
        assert.ok(/한 번만 허용/.test(e.message), `동일 role 재claim 오류 메시지: ${e.message}`);
      }
      assert.ok(threw, "동일 role의 두 번째 initial claim은 거부돼야 함");
    });
  });

  register("initial 예산은 role 3개(analyzer/writer/pattern-extractor)까지만 허용된다", () => {
    withTempRoot((root) => {
      initBudget({ root, session: "s1", initial: 3, retries: 2 });
      claimBudget({ root, session: "s1", role: "analyzer", kind: "initial" });
      claimBudget({ root, session: "s1", role: "writer", kind: "initial" });
      claimBudget({ root, session: "s1", role: "pattern-extractor", kind: "initial" });
      let threw = false;
      try {
        claimBudget({ root, session: "s1", role: "extra-role", kind: "initial" });
      } catch (e) {
        threw = true;
        assert.ok(/예산 초과/.test(e.message), `예산 초과 메시지: ${e.message}`);
      }
      assert.ok(threw, "initial 예산 소진 후 새 role claim은 거부돼야 함");
    });
  });

  register("retry claim은 --reason 없이 거부된다", () => {
    withTempRoot((root) => {
      initBudget({ root, session: "s1", initial: 3, retries: 2 });
      let threw = false;
      try {
        claimBudget({ root, session: "s1", role: "analyzer", kind: "retry", reason: "" });
      } catch (e) {
        threw = true;
        assert.ok(/reason이 필요/.test(e.message));
      }
      assert.ok(threw, "reason 없는 retry claim은 거부돼야 함");
    });
  });

  register("retry 예산은 2회까지 허용되고 초과 시 거부된다", () => {
    withTempRoot((root) => {
      initBudget({ root, session: "s1", initial: 3, retries: 2 });
      claimBudget({ root, session: "s1", role: "analyzer", kind: "retry", reason: "T-A-RETRY test" });
      claimBudget({ root, session: "s1", role: "writer", kind: "retry", reason: "T-W-RETRY test" });
      let threw = false;
      try {
        claimBudget({ root, session: "s1", role: "writer", kind: "retry", reason: "third retry" });
      } catch (e) {
        threw = true;
        assert.ok(/retries AI 호출 예산 초과: 2\/2/.test(e.message), `예산 초과 메시지: ${e.message}`);
      }
      assert.ok(threw, "retries 예산 소진 후 세 번째 claim은 거부돼야 함");
    });
  });
}
