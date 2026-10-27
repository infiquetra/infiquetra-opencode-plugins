import assert from "node:assert/strict"
import { readFile } from "node:fs/promises"
import { pathToFileURL } from "node:url"

const bridge = (await import(pathToFileURL(process.argv[2]).href)).default
const cwd = process.cwd()
const marker = process.env.SAGA_TEST_MARKER!
const readEvents = async () => (await readFile(marker, "utf8")).trim().split("\n")
const waitFor = async (expected: string) => {
  for (let i = 0; i < 100; i++) {
    try { if ((await readEvents()).includes(expected)) return } catch { /* hook not finished */ }
    await Bun.sleep(10)
  }
  throw new Error(`hook did not produce ${expected}`)
}

// OpenCode 1 loads server(), and it must retain veto and shell behavior.
const v1 = await bridge.server({ directory: cwd })
const v1env = { env: {} as Record<string, string> }
await v1["shell.env"]({}, v1env)
assert.equal(v1env.env.SAGA_PLUGIN_ROOT, process.env.SAGA_TEST_ROOT)
await assert.rejects(
  () => v1["tool.execute.before"]({ tool: "bash", sessionID: "v1" }, { args: { command: "unsafe" } }),
  /blocked by/,
)

// OpenCode 2 registers callbacks with domain hooks. Exercise the public event
// shapes, including simultaneous first activity and failed tool calls.
const hooks: Record<string, (event: any) => any> = {}
const domain = (name: string) => ({
  hook: async (event: string, callback: (event: any) => any) => { hooks[`${name}.${event}`] = callback },
})
const controller = await bridge.setup({
  location: { directory: cwd },
  session: domain("session"), shell: domain("shell"), tool: domain("tool"),
  event: { subscribe: async function* () {} },
})
const env = { env: {} as Record<string, string> }
await hooks["shell.create.before"](env)
assert.equal(env.env.SAGA_PLUGIN_ROOT, process.env.SAGA_TEST_ROOT)
await Promise.all([
  hooks["session.prompt"]({ sessionID: "v2" }),
  hooks["session.prompt"]({ sessionID: "v2" }),
])
assert.deepEqual(await readEvents(), ["start"])
await assert.rejects(
  () => hooks["tool.execute.before"]({ tool: "bash", sessionID: "v2", input: { command: "unsafe" } }),
  /blocked by/,
)
await hooks["tool.execute.after"]({ tool: "bash", sessionID: "v2", input: {}, status: "error" })
await hooks["tool.execute.after"]({ tool: "bash", sessionID: "v2", input: {}, status: "completed" })
await waitFor("post")
assert.equal((await readEvents()).filter((event) => event === "post").length, 1)
await hooks["session.compaction"]({ sessionID: "v2" })
await waitFor("compact")
controller()
