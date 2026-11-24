// srv's `sandbox_run` tool for execute-depth reviewer sessions (loaded with `omp -e`).
//
// The reviewer session talks to the model through the relay of its jail (reviewer.py). The code it runs here does
// not: each call starts `sandbox.py`, which copies the head's tracked files into a fresh directory and runs the
// script in a nested bubblewrap namespace with every namespace unshared, the environment cleared, and neither the
// relay socket nor the agent directory mounted. So the change's code never shares a namespace, a network, or a
// process tree with the session that holds the model connection, and every call starts from an unmodified head.
// The user's words (2026-11-24): "실제 실행도 가능해야돼. 에이전트 하네스를 사용하는데 그걸 못할 이유가 없어".
import { spawn } from "node:child_process";
import { mkdtemp, readFile } from "node:fs/promises";

const TAIL = 12000;
const TIMEOUT_S = 120;

async function tail(path: string): Promise<string> {
	try {
		const text = await readFile(path, "utf8");
		return text.length > TAIL ? `[last ${TAIL} of ${text.length} characters]\n` + text.slice(-TAIL) : text;
	} catch {
		return "";
	}
}

export default function sandboxTool(pi) {
	const z = pi.zod;
	const mounts: string[] = JSON.parse(process.env.SRV_SANDBOX_RO || "[]");
	pi.registerTool({
		name: "sandbox_run",
		label: "Run a counterexample",
		description:
			"Run a bash script in a fresh writable copy of the reviewed head at /work, with no network and no " +
			`environment, for at most ${TIMEOUT_S} seconds. Every call starts from the unmodified head, so write the ` +
			"fixture, the fake, and the check in the same script. Prepared dependency directories, if any: " +
			(mounts.length ? mounts.join(", ") : "none") +
			". Returns the exit code, stdout, and stderr.",
		parameters: z.object({
			script: z.string().min(1).max(65536).describe("bash script run with `bash -euo pipefail` in /work"),
		}),
		async execute(_id, params, signal) {
			const out = await mkdtemp("/tmp/srv-run-");
			const args = ["-I", "/opt/srv/sandbox.py", "--repo", "/work", "--files", "/opt/srv/tracked.txt",
				"--out", out, "--timeout", String(TIMEOUT_S)];
			for (const mount of mounts) args.push("--ro", mount);
			args.push("--", "/bin/bash", "--noprofile", "--norc", "-euo", "pipefail", "-c", params.script);
			const code: number | null = await new Promise((resolve, reject) => {
				const child = spawn("/usr/bin/python3", args, { cwd: "/review", env: {}, signal, stdio: "ignore" });
				child.once("error", reject);
				child.once("close", resolve);
			});
			const stdout = await tail(`${out}/stdout.txt`);
			const stderr = await tail(`${out}/stderr.txt`);
			const status = code === 124 ? `timed out after ${TIMEOUT_S} s` : code === 125 ? "the sandbox did not start" : `exit code ${code}`;
			return {
				content: [{ type: "text", text: `${status}\n--- stdout\n${stdout}\n--- stderr\n${stderr}` }],
				details: { exitCode: code, script: params.script },
			};
		},
	});
}
