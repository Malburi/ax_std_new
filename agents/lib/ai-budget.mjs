#!/usr/bin/env node
/*
 * AX-Harness AI 호출 예산 게이트
 *
 * 출처: upstream AX-Harness(Malburi/harness-sm) scripts/ai-budget.mjs, 2026-08-12 이식.
 * 로직은 무수정 — root/session/role/kind/reason만 다루는 완전 범용 스크립트라 이 저장소의
 * Tier·agent 이름을 가정하지 않는다. harness-init SKILL.md의 claim 호출 지점·예산 수치만
 * 이 저장소 컨벤션(Lite 폐지로 initial 3, Phase 4가 analyzer+writer 동시 재시도 가능해 retries 2)에
 * 맞춰 배선한다.
 *
 * initial claim은 역할당 평생 1회만 허용된다(호출 횟수가 아니라 "이미 한 번 썼는가" 규칙).
 * retry claim은 validator 실패 사유(--reason) 없이는 거부된다. 예산 소진 시 exit 1 — 조용히
 * 넘어가지 않는다.
 */
import { existsSync, mkdirSync, readFileSync, renameSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";

function parseArgs(argv) {
  const args = { command: argv[0] || "status", root: process.cwd(), kind: "initial", initial: 2, retries: 1 };
  for (let i = 1; i < argv.length; i += 1) {
    if (argv[i] === "--root") args.root = argv[++i];
    else if (argv[i] === "--session") args.session = argv[++i];
    else if (argv[i] === "--role") args.role = argv[++i];
    else if (argv[i] === "--kind") args.kind = argv[++i];
    else if (argv[i] === "--reason") args.reason = argv[++i];
    else if (argv[i] === "--initial") args.initial = Number(argv[++i]);
    else if (argv[i] === "--retries") args.retries = Number(argv[++i]);
    else throw new Error(`알 수 없는 인자: ${argv[i]}`);
  }
  args.root = resolve(args.root);
  if (!new Set(["init", "claim", "status"]).has(args.command)) throw new Error(`지원하지 않는 명령: ${args.command}`);
  return args;
}

function budgetPath(root) { return join(root, "_workspace", "ai-budget.json"); }
function readBudget(root) {
  const path = budgetPath(root);
  if (!existsSync(path)) throw new Error(`AI 예산이 초기화되지 않았습니다: ${path}`);
  return JSON.parse(readFileSync(path, "utf8"));
}

function atomicJson(path, value) {
  mkdirSync(dirname(path), { recursive: true });
  const temp = `${path}.tmp-${process.pid}`;
  writeFileSync(temp, `${JSON.stringify(value, null, 2)}\n`, "utf8");
  renameSync(temp, path);
}

export function initBudget({ root, session, initial = 2, retries = 1 }) {
  if (!session) throw new Error("init에는 --session이 필요합니다.");
  if (!Number.isInteger(initial) || initial < 0 || !Number.isInteger(retries) || retries < 0) throw new Error("예산은 0 이상의 정수여야 합니다.");
  const path = budgetPath(root);
  if (existsSync(path)) {
    const current = JSON.parse(readFileSync(path, "utf8"));
    if (current.session === session) return current;
  }
  const value = { version: 1, session, limits: { initial, retries }, used: { initial: 0, retries: 0 }, claims: [] };
  atomicJson(path, value);
  return value;
}

export function claimBudget({ root, session, role, kind = "initial", reason = "" }) {
  if (!role) throw new Error("claim에는 --role이 필요합니다.");
  if (!new Set(["initial", "retry"]).has(kind)) throw new Error("kind는 initial 또는 retry여야 합니다.");
  const value = readBudget(root);
  if (session && value.session !== session) throw new Error(`AI 예산 session 불일치: expected ${value.session}, got ${session}`);
  const bucket = kind === "retry" ? "retries" : "initial";
  if (kind === "initial" && value.claims.some((item) => item.kind === "initial" && item.role === role)) {
    throw new Error(`동일 role의 initial 호출은 한 번만 허용됩니다: ${role}`);
  }
  if (value.used[bucket] >= value.limits[bucket]) throw new Error(`${bucket} AI 호출 예산 초과: ${value.used[bucket]}/${value.limits[bucket]}`);
  if (kind === "retry" && !reason.trim()) throw new Error("retry claim에는 validator 실패 --reason이 필요합니다.");
  const claim = { sequence: value.claims.length + 1, role, kind, reason: reason || undefined };
  value.claims.push(claim);
  value.used[bucket] += 1;
  atomicJson(budgetPath(root), value);
  return { allowed: true, claim, remaining: { initial: value.limits.initial - value.used.initial, retries: value.limits.retries - value.used.retries } };
}

export function budgetStatus(root) { return readBudget(root); }

function main() {
  try {
    const args = parseArgs(process.argv.slice(2));
    const result = args.command === "init" ? initBudget(args) : args.command === "claim" ? claimBudget(args) : budgetStatus(args.root);
    process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);
  } catch (error) {
    process.stderr.write(`AI 예산 거부: ${error.message}\n`);
    process.exitCode = 1;
  }
}

const isMain = process.argv[1] && resolve(process.argv[1]) === resolve(new URL(import.meta.url).pathname.replace(/^\/(\w:)/, "$1"));
if (isMain) main();
