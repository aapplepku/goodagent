# Backup And Recovery

This experimental alpha supports **cold backups of a standard local self-hosted
Docker installation**. It pauses that installation briefly. Native legacy-demo,
hosted, distributed Qdrant, custom mounts and shared-volume deployments are not
supported by this helper. Schedule a maintenance window and stop any tools that
write directly to its database/cache. Do not run concurrent setup, upgrades or
other Docker administration during backup or restore.

The backup covers PostgreSQL, Redis, Qdrant and catalog images together. It also
contains resolved configuration, including the encryption key and credentials.
Never upload it to GitHub, attach it to an issue, send it to an agent, or store it
in a public/export directory. Use an encrypted disk or encrypted backup service;
the helper's owner-only file permissions **are not encryption at rest**.

## Capture

Use the same checkout, local Docker context and private environment that started
the installation. Find its `COMPOSE_PROJECT_NAME` in the private environment; do
not print or share the whole file. Create the private parent directory first;
Docker-first setup does not create `.opencommerce` on the host. Choose a new output
directory every time, and leave that final directory absent so the helper can
create it privately:

```sh
mkdir -p -m 700 .opencommerce
python3 scripts/backup_self_hosted.py backup \
  --env-file .env \
  --confirm-project YOUR_PROJECT \
  --output .opencommerce/backup-YYYYMMDD
```

For a different output path, create its parent privately before running the helper.
The helper never creates missing ancestors or overwrites an existing destination.

The helper validates service ownership, mounts, encryption keys and configuration
drift before stopping anything. It stops clients, API and worker, saves Redis,
then stops the three data services. All must stop cleanly before copying begins.
It preserves file bytes, numeric ownership, permissions and hidden files.
Previously running services are restarted using their existing containers; no
build, migration or volume reset is part of backup.

`manifest.json` exists only after all four copies have passed inspection and have
recorded checksums. The initial `INCOMPLETE.json` is an attempt receipt and remains
for audit; it is not a completion marker. A missing manifest means the backup is
not usable. Failed attempts are retained, never overwritten. If restarting fails,
the completed backup can still be valid, but service recovery needs attention.

Keep the **exact source checkout and exact local container images** with the
backup. Image IDs are recorded in the manifest; rebuilding identical source is
not guaranteed to produce identical images because distribution security packages
can change. The helper refuses to pull or build replacements during recovery.
Archive the recorded images separately with `docker image save` onto private
storage, and restore them with `docker image load` on a compatible Linux-container
engine and CPU architecture. A data backup without retained source/images is not
a complete machine-loss recovery kit. Monitor disk capacity before copying.

Checksums detect changes relative to the manifest; they do not authenticate a
malicious backup. Restore only your own trusted backup. Preserve its manifest
hash in a separate trusted record. Never modify database files inside an archive.

## Restore Into An Isolated Copy

Keep the original installation intact. Choose an unused project name and a new
private output directory:

```sh
python3 scripts/backup_self_hosted.py restore \
  --backup .opencommerce/backup-YYYYMMDD \
  --project recovery-check \
  --output .opencommerce/recovery-check
```

Existing containers, networks or target volumes, including orphaned/unlabelled
volumes, cause refusal. The target gets new loopback ports and independent volumes.
The helper verifies copied file bytes and ownership **before starting anything**;
it cannot claim success by silently rebuilding a missing search index.

The restored containers remain stopped. The recovery configuration removes live
model credentials, uses deterministic test conversation, and puts services on an
internal Docker network without outbound connectivity. The encryption key and
database password are preserved. No new owner is bootstrapped, and original store,
account, catalog, conversation and order identities remain unchanged.

After checking the completed `restore.json` receipt, explicitly start the copy:

```sh
python3 scripts/backup_self_hosted.py start \
  --directory .opencommerce/recovery-check \
  --confirm-project recovery-check
```

This starts the recorded images and their normal migration/job recovery logic;
it does not rebuild images. The restored migration revision must already match
those images. Default offline recovery has no host port forwarding: verify it
through `docker exec` and service-local requests, not invented localhost links.

For an interactive browser drill, choose a new project/output and add
`--local-preview` to the **restore** command. This explicitly permits outbound
networking and loopback app ports after the separate start command. Model
credentials stay disabled. Do not choose this mode for an untrusted backup or
while its pending jobs could perform unwanted external work. The completed
receipt records the choice; start verifies actual network ownership/attachments.
Use the printed app URLs in a **separate browser profile or private window**:
cookies are scoped by host/store, not by port, so two localhost copies can
otherwise overwrite each other's sessions.

## Verify Before Cutover

- Sign in as the existing owner; do not create another owner.
- Check the published catalog ID, active versus staged versions, store slug and
  sharing state. Review an unconfirmed upload to verify the encryption key works.
- Verify images and raw search contents before invoking any index rebuild. Then
  browse and run a known search through the application.
- Sign in as a test shopper. Check conversations, saved memory, memory opt-out,
  cart variants and quantities, demo orders and replay of an idempotent test action.
- Verify another store's identifiers cannot grant access. Preview grants must
  still be narrower than merchant permission.
- Confirm fresh worker activity after startup, not merely a copied heartbeat key.
  Check pending/cancelled jobs and duplicate-delivery behavior with synthetic data.
- Check elapsed-time effects. Guest/session/import expiry, checkout reservations,
  worker leases and run budgets are not reset to make an old backup seem current.

An older backup can resurrect sessions or recovery codes revoked after it was
taken, and can restore data that someone subsequently deleted. Before real cutover,
keep the old installation stopped, revoke affected sessions, rotate recovery codes,
apply post-backup deletion requests, and reconcile work performed after the backup.
Provider requests cannot be undone by restoring a database. Do not allow two copies
to process the same real work. Re-enable model credentials only after deliberate
configuration review. Keep external exposure disabled: internet-hosting qualification
is a separate gate.

To recover owner access, run the existing console recovery operation inside the
restored API container in your own terminal. It revokes that owner's sessions and
issues a new single-use recovery code. Never put the resulting code in logs or
screenshots. Shopper session controls and data deletion remain explicit app actions.

Do not use `make setup` against the restored copy until you have intentionally
prepared matching private environment settings and planned the upgrade. Its
private `configuration.json` is the authoritative frozen recovery configuration;
the ordinary root `.env` may still identify the original installation.

## Failure And Scope

There is no in-place overwrite, automatic destructive rollback, or volume deletion.
An interrupted restore leaves a stopped partial project; retain it for diagnosis
and retry into another unused project. Do not start it without a complete receipt.
Remove test resources only after verifying their exact project and volume labels.

This is an offline same-version recovery path, not online point-in-time recovery,
cross-version PostgreSQL migration, backup scheduling or a hosted disaster-recovery
SLA. Database/queue copies contain sensitive account and conversation state.
Retain backups according to your privacy obligations and test recovery periodically.

## Verification Scope

An October 16, 2026 disposable same-machine ARM64 Linux-container drill on macOS
verified all four restored volumes before startup, including file hashes, numeric
ownership and modes. It then verified existing owner/shopper sign-in, publication
identity, encrypted staged-import review, stored images, search, memory,
conversations, cart, demo-order idempotency, denied merchant access from a shopper,
and a fresh worker task with duplicate-command handling. The owner and shopper
browser checks passed at 1440x1000 and 390x844; images and layout were inspected.
Model calls were disabled. This was explicitly selected sample data with synthetic
accounts, prices and demo orders, not a backup of a real merchant's customer data.

The tests also exposed and corrected an unclean Qdrant wrapper shutdown and
Docker-copy root ownership differences. Unsafe/incomplete attempts are retained.
Independent code review covered configuration drift, isolation and resource
replacement races. That bounded review is not a release security approval.

Not demonstrated by this drill: recovery on a lost/replaced host, a different CPU
architecture, older snapshots with expired pending work, two live stores during
cutover, or real external-provider side effects. These require separate evidence.

The approach uses Docker's supported stopped-container archive copy and a
shutdown barrier consistent with PostgreSQL's filesystem backup requirements:
[Docker copy semantics](https://docs.docker.com/reference/cli/docker/container/cp/),
[PostgreSQL filesystem backups](https://www.postgresql.org/docs/16/backup-file.html).
For online/distributed vector deployments, use the appropriate
[Qdrant snapshot procedure](https://qdrant.tech/documentation/operations/snapshots/)
instead of this local cold-copy helper.
