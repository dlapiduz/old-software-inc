# Factory runbook: SuperPlane + Fabro, issue to PR

Label an issue `fabro` and you get a tested pull request that references it,
or a comment explaining why not. A person always reviews and merges.

## Architecture

```
GitHub (dlapiduz/old-software-inc)
  │  issues / issue_comment webhooks
  ▼  Cloudflare Tunnel (webhook paths only; the only public ingress)
SuperPlane  own VM               app "Fabro ticket to PR"  (factory/superplane/canvas.yaml)
  │  HTTP + bearer token, LAN only, every 60 s while a run is open
  ▼
Fabro       own VM, LAN-only API   workflow ticket_to_pr  (factory/fabro/ticket_to_pr)
  │  Docker sandbox per run (python:2.7.18): clone, plan, implement, test
  ├─▶ api.anthropic.com   Haiku 5.5 plans, Sonnet 5.5 writes code
  └─▶ github.com          GitHub App fabro-diego pushes the run branch, opens the PR
```

1. **Start.** `github.onIssue` (action `labeled`) → filter `label == fabro` and
   not a PR → read the issue's comments → `POST /api/v1/runs` with the issue as
   run inputs → `POST /runs/{id}/start` → comment "Fabro picked this up".
2. **Watch.** A loop does `GET /runs/{id}` once a minute (100 iterations,
   6 h hard timeout). That one call returns the status, the pending question
   and the PR.
3. **Questions.** If the run is blocked on a question, the app fetches
   `/runs/{id}/questions` for its id, posts it on the issue once (memory
   namespace `fabro_questions` de-duplicates), and keeps polling.
4. **Answers.** `github.onIssueComment` → filter: created, not a bot, issue
   labelled `fabro` → find the pending question for that issue → `POST
   /runs/{run}/questions/{qid}/answer` `{kind: text}` → mark answered, react 🚀.
5. **Finish.** When the run is terminal, wait 30 s (PR creation trails the run)
   and comment the PR link, or a failure summary with the run page.

### Why polling

- Fabro's only outbound notifications are `run_complete` / `run_failed`
  HTTP hooks. Hooks can't use secrets, so they can't authenticate to
  SuperPlane, and SuperPlane's webhook URLs are public (through the tunnel).
  An unauthenticated public trigger that starts work isn't acceptable.
- Nothing fires when Fabro asks a question, so questions needed polling
  regardless. One mechanism covers both.
- `create-automation-run` takes no request body, so it can't carry the issue.
  The app creates runs from an immutable workflow version instead.

### The workflow (`factory/fabro/ticket_to_pr/workflow.fabro`)

`plan` (Haiku 5.5, routing `Ready`/`Ask`, `max_visits=3`) → optional `clarify`
(human gate, freeform) → `setup` (`pip install`) → `implement` (Sonnet 5.5)
→ `test` (`goal_gate=true`: nose + `coverage report --fail-under=90`, the same
gate CI runs) → on failure `fix` (Sonnet 5.5, `max_visits=3`) → `test` again.
Graph-level `on_failure=exit`, `max_node_visits=10`. `[run.pull_request]`
opens a non-draft PR with `auto_merge = false`.

## Operating it

| Piece | Where | Start / stop / restart | Upgrade |
|---|---|---|---|
| Fabro | Fabro VM, `/opt/fabro`, systemd `fabro` (compose) | `systemctl start\|stop\|restart fabro` | bump `fabro_version` in homelab `vars.yml` (nightly tags, no `v` prefix: `0.403.0-nightly.0`), push; Semaphore applies |
| Fabro config | `/opt/fabro/settings.toml` (rendered by the `fabro` Ansible role) | changes restart the container | edit `roles/fabro/templates/settings.toml.j2` |
| Sandbox env | Fabro SQLite, environment `default` | upserted by the role | edit `fabro_env_spec` in `vars.yml` |
| Workflow | `factory/fabro/ticket_to_pr` | n/a | edit, then run `factory/fabro/register.sh` on the Fabro VM or SuperPlane host. It sets the Fabro variable `TICKET_TO_PR_VERSION`, which the app reads per run, so SuperPlane needs no change |
| SuperPlane app | canvas "Fabro ticket to PR" | pause/resume in the UI | edit `factory/superplane/canvas.yaml`, run `import.sh` (creates a new canvas version) |
| SuperPlane | SuperPlane VM, systemd `superplane` | see homelab `CLAUDE.md` | homelab `superplane_*` vars |

Both VMs come back on boot (`on_boot = true`, systemd units enabled). Fabro's
state is SQLite on `/opt/fabro/storage`; it is not in the Proxmox backup job
(an evaluation box), so a rebuild loses run history but nothing else: config,
secrets and the environment are re-applied by Ansible.

Logs: `sudo docker logs -f fabro` on the Fabro VM; run detail at
`<Fabro web URL>/runs/<id>` (home network only; log in with the dev token).
Issue comments carry the run id, never an internal link.
SuperPlane: the app's run history in the UI.

## Secrets (names only)

| Name | Lives in | Used for |
|---|---|---|
| `fabro_session_secret`, `fabro_dev_token` | homelab Ansible vault → `/opt/fabro/fabro.env` | Fabro web sessions; bearer token for the Fabro API |
| `fabro_anthropic_api_key` | Ansible vault → Fabro vault `ANTHROPIC_API_KEY` | model calls |
| `fabro_github_app_private_key`, `fabro_github_app_client_secret` | Ansible vault → Fabro vault `GITHUB_APP_PRIVATE_KEY`, `GITHUB_APP_CLIENT_SECRET` | GitHub App `fabro-diego` (id 5560452) |
| SuperPlane org secret `fabro`, key `token` | SuperPlane (encrypted) | the canvas's HTTP nodes → Fabro (same value as `fabro_dev_token`) |
| SuperPlane API token | you, at import time only | `import.sh`; not stored |

None of these are in this repository.

## Access and permissions

- **GitHub App `fabro-diego`:** Contents write, Pull requests write, Metadata
  read; installed on `dlapiduz/old-software-inc` only; no webhook. No
  Workflows permission, so agents can't change `.github/workflows/`.
- **Run token:** `workflow.toml` requests `contents` + `pull_requests` write
  so the finalizer can push the run branch and open the PR. Fabro mints it for
  this repo only, and agents in the sandbox see it as `GITHUB_TOKEN`, so an agent
  can push branches. It can't push to or merge into `main` (ruleset).
- **Branch protection:** ruleset "main: PRs only, no agent merges" on `main`:
  PR with 1 approval (stale approvals dismissed, last push must be approved by
  someone else), no force-push, no deletion. Repo admins can bypass.
- **Fabro API exposure:** published on the Fabro VM's LAN address only; `fabro-firewall.service`
  (DOCKER-USER chain `FABRO-API`) admits new connections to 32276 from
  the SuperPlane VM and the reverse proxy (for the web UI) and drops the
  rest. Nothing is exposed to the internet. Loopback is used by the role and
  telegraf.
- **SuperPlane egress:** SuperPlane blocks canvas HTTP to private ranges.
  `BLOCKED_PRIVATE_IP_RANGES` keeps that list with a single /32 hole for
  the Fabro VM, so canvases still can't reach the rest of the homelab.

## Firewall: proposed egress rules for the Fabro VM

The Docker sandbox provider supports only `allow_all` or `block` for network
(`cidr_allow_list` is Daytona-only), and the agent needs the network to clone,
push and install packages. So today **sandboxes have unrestricted egress**.
The intended allowlist:

| Who | Destination | Why |
|---|---|---|
| sandboxes + fabro | the LAN DNS resolver :53 | DNS |
| sandboxes | `github.com`, `api.github.com`, `codeload.github.com`, `objects.githubusercontent.com` :443 | clone, push the run branch |
| sandboxes | `pypi.org`, `files.pythonhosted.org` :443 | `pip install` |
| sandboxes | `deb.debian.org`, `security.debian.org` :80/443 | only if an agent installs OS packages |
| fabro container | `api.anthropic.com` :443 | model calls are made by the server, not the sandbox |
| fabro container | `api.github.com`, `github.com` :443 | installation tokens, PR creation |
| fabro container | `ghcr.io`, `registry-1.docker.io` :443 | image pulls at deploy time |
| everything | 10.0.0.0/8 except the two above | **deny**; a prompt-injected agent must not reach the homelab |

Hostname rules can't be enforced with plain iptables (these hosts sit behind
large, changing CDNs). The workable design is an egress proxy:

1. Put sandboxes on a dedicated bridge (`fabro-sandbox`) and add, in
   `DOCKER-USER`: allow established, allow DNS to the LAN resolver, allow the bridge
   to the proxy, drop everything else from that bridge.
2. Run a forward proxy (squid or tinyproxy) on the VM with a domain allowlist
   (the hosts above, CONNECT to :443 only).
3. Set `HTTPS_PROXY`/`HTTP_PROXY`/`NO_PROXY` in the sandbox environment's
   `env` (`fabro_env_spec.env`); git, pip and curl honour them.
4. Block RFC 1918 destinations except the resolver's :53 at the VM, and (defence in
   depth) a router rule from the Fabro VM to the other VLANs.

Until then the mitigations are: the VM is its own kernel, the GitHub token in
the sandbox is scoped to this one repo, `main` is protected, and Fabro's API
can't be reached from the internet.

## Known limits

- **Polling latency and horizon.** Status is seen within ~60 s. A run, or an
  unanswered question, is watched for at most 100 minutes, after which the app
  posts a failure summary ("Polling stopped because: max_iterations") while
  the Fabro run carries on. Answer late on the Fabro run page instead.
- **One question at a time.** The relay answers the oldest pending question
  per issue; parallel human gates aren't supported.
- **Any non-bot comment on a `fabro` issue counts as the answer** while a
  question is pending.
- **Failure summaries are thin.** Fabro leaves `lifecycle.error` empty for
  most failures; the reason is in the run's event stream and on the run page.
- **Fabro is nightly-only**, so pin a tag and expect behaviour to change
  between bumps. Its built-in model catalog lagged the current models;
  `claude-sonnet-5-5` / `claude-haiku-5-5` are registered in `settings.toml`.
- **The GitHub App can merge an approved PR** (Pull requests write). On a
  personal repo, rulesets can't exclude a specific app from merging. Fabro is
  configured with `auto_merge = false` and nothing in the workflow merges.
- **This repo also runs SuperPlane's own factory.** Old Software Inc's "GitHub
  issues" app turns every opened issue into a work order, so a `fabro` issue
  is also refined by that factory's Backlog agent.
- **Single replica.** Fabro owns `/storage` exclusively; `max_concurrent_runs = 2`.
- **`/fabro` PR revisions (stretch goal) are not built.**
