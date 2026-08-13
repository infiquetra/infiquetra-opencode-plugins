/**
 * Saga hook bridge: runs the ported Claude Code hooks on matching opencode
 * events, feeding them the Claude hook JSON protocol on stdin.
 *
 * Contract (see plugins/saga/PORTABILITY.md and manifest.json):
 * - Reads hooks.json from this repo (realpath, so the installer's symlink
 *   into ~/.config/opencode/plugins/ is transparent).
 * - Exports SAGA_PLUGIN_ROOT through shell.env so ported skill/command bodies
 *   that reference ${SAGA_PLUGIN_ROOT}/scripts/... resolve.
 * - Exit codes follow the Claude protocol: 0 continue, 1 feedback (treated as
 *   block with the hook message, since opencode plugins cannot prompt),
 *   2 block. A JSON stdout body with continue:false also blocks.
 * - PreToolUse hooks are awaited and a veto throws, which denies the tool
 *   call. Lifecycle hooks (SessionStart/End, PreCompact, PostToolUse) run
 *   asynchronously and only log.
 * - Deferred hooks are listed in DEFERRED_HOOKS and must match the manifest's
 *   hooks.deferred list (enforced by scripts/validate_opencode_plugins.py).
 */

import { realpathSync, readFileSync } from "node:fs"
import { spawn } from "node:child_process"
import type { Plugin } from "@opencode-ai/plugin"

const DEFERRED_HOOKS = ["delegation_stop_audit_hook.py"]

type HookEntry = { type: string; command: string; timeout?: number }
type HookMatcher = { matcher?: string; hooks: HookEntry[] }
type HooksJson = { hooks?: Record<string, HookMatcher[]> }

const here = realpathSync(new URL(".", import.meta.url).pathname)
const pluginRoot = realpathSync(`${here}/..`)
const hooksJson: HooksJson = JSON.parse(
  readFileSync(`${pluginRoot}/hooks/hooks.json`, "utf8"),
)

const TOOL_NAME_MAP: Record<string, string> = {
  bash: "Bash",
  edit: "Edit",
  write: "Write",
  patch: "Edit",
  apply_patch: "Edit",
  multiedit: "MultiEdit",
  task: "Agent",
}

const inFlight = new Set<string>()

function entryDeferred(entry: HookEntry): boolean {
  return DEFERRED_HOOKS.some((name) => entry.command.includes(name))
}

function buildToolInput(tool: string, args: any): Record<string, any> {
  if (tool === "bash") {
    return { command: args?.command ?? "", description: args?.description ?? "" }
  }
  if (tool === "task") {
    return {
      subagent_type: args?.subagent_type ?? args?.agent ?? "",
      description: args?.description ?? "",
      prompt: args?.prompt ?? "",
    }
  }
  return {
    file_path: args?.filePath ?? "",
    content: args?.content ?? "",
    old_string: args?.oldString ?? "",
    new_string: args?.newString ?? "",
    replace_all: args?.replaceAll ?? false,
  }
}

function matchingEntries(eventName: string, selector?: string): HookEntry[] {
  const matchers = hooksJson.hooks?.[eventName] ?? []
  const entries: HookEntry[] = []
  for (const group of matchers) {
    if (group.matcher && (!selector || !new RegExp(group.matcher).test(selector))) {
      continue
    }
    for (const entry of group.hooks) {
      if (!entryDeferred(entry)) entries.push(entry)
    }
  }
  return entries
}

/** Run one hook and resolve with a block reason, or "" if it allowed. */
function runOne(entry: HookEntry, payload: Record<string, any>): Promise<string> {
  const command = entry.command.replaceAll("${CLAUDE_PLUGIN_ROOT}", pluginRoot)
  const key = `${command}:${payload.session_id ?? ""}`
  if (inFlight.has(key)) return Promise.resolve("")
  inFlight.add(key)

  return new Promise((resolve) => {
    const child = spawn("bash", ["-c", command], {
      cwd: (payload.cwd as string) ?? process.cwd(),
      env: { ...process.env, CLAUDE_PLUGIN_ROOT: pluginRoot, SAGA_PLUGIN_ROOT: pluginRoot },
    })
    let stdout = ""
    let stderr = ""
    child.stdout.on("data", (chunk) => (stdout += chunk))
    child.stderr.on("data", (chunk) => (stderr += chunk))
    const timer = setTimeout(
      () => child.kill("SIGKILL"),
      (entry.timeout ?? 60) * 1000,
    )

    child.on("exit", (code) => {
      clearTimeout(timer)
      inFlight.delete(key)
      let stopReason = ""
      try {
        const parsed = JSON.parse(stdout)
        if (parsed.continue === false) stopReason = parsed.stopReason ?? "hook veto"
      } catch {
        /* stdout is prose, not protocol */
      }
      const message = stderr.trim() || stdout.trim() || `exit ${code}`
      if (code === 2 || code === 1 || stopReason) {
        resolve(message)
      } else if (code !== 0 && code !== null) {
        console.error(`[saga-hooks] ${command} failed (exit ${code}):\n${message}`)
        resolve("")
      } else {
        resolve("")
      }
    })

    child.stdin.write(JSON.stringify(payload))
    child.stdin.end()
  })
}

async function runHooks(
  eventName: string,
  payload: Record<string, any>,
  toolName?: string,
  blocking = false,
): Promise<void> {
  const selector =
    toolName ??
    (payload.source as string | undefined) ??
    (payload.trigger as string | undefined)
  const entries = matchingEntries(eventName, selector)
  for (const entry of entries) {
    const reason = await runOne(entry, payload)
    if (reason && blocking) {
      throw new Error(`[saga-hooks] blocked by ${entry.command}:\n${reason}`)
    }
    if (reason && !blocking) {
      console.error(`[saga-hooks] blocked by ${entry.command}:\n${reason}`)
    }
  }
}

const sagaHooks: Plugin = async ({ directory }) => {
  return {
    "shell.env": (_input, output) => {
      output.env.SAGA_PLUGIN_ROOT = pluginRoot
    },
    event: ({ event }) => {
      const props = (event as any).properties ?? {}
      const sessionId = props.sessionID ?? props.info?.id ?? ""
      if (event.type === "session.created") {
        void runHooks(
          "SessionStart",
          { session_id: sessionId, cwd: directory, source: "startup" },
        )
      } else if (event.type === "session.compacted") {
        void runHooks(
          "SessionStart",
          { session_id: sessionId, cwd: directory, source: "compact" },
        )
      } else if (event.type === "session.deleted") {
        void runHooks(
          "SessionEnd",
          { session_id: sessionId, cwd: directory },
        )
      }
    },
    "experimental.session.compacting": ({ sessionID }) => {
      void runHooks(
        "PreCompact",
        { session_id: sessionID, cwd: directory, trigger: "auto" },
      )
    },
    "tool.execute.before": async ({ tool, sessionID }, output) => {
      const claudeTool = TOOL_NAME_MAP[tool]
      if (!claudeTool) return
      await runHooks(
        "PreToolUse",
        {
          session_id: sessionID,
          cwd: directory,
          hook_event_name: "PreToolUse",
          tool_name: claudeTool,
          tool_input: buildToolInput(tool, output.args),
        },
        claudeTool,
        true,
      )
    },
    "tool.execute.after": ({ tool, sessionID, args }) => {
      const claudeTool = TOOL_NAME_MAP[tool]
      if (!claudeTool) return
      void runHooks(
        "PostToolUse",
        {
          session_id: sessionID,
          cwd: directory,
          hook_event_name: "PostToolUse",
          tool_name: claudeTool,
          tool_input: buildToolInput(tool, args),
        },
        claudeTool,
      )
    },
  }
}

export default sagaHooks
