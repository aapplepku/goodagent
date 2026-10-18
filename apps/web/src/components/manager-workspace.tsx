"use client";

import { ChatMarkdown } from "./chat-markdown";
import { RankingPanel } from "./ranking-panel";
import { ShopifyPanel } from "./shopify-panel";
import { ActivityPanel } from "./activity-panel";
import { useStoreNavigation } from "./store-navigation";
import { CatalogIndexProgress } from "./catalog-index-progress";
import { MerchantStoreIdentity } from "./merchant-store-identity";
import { WorkspaceDialog, focusWorkspaceTarget } from "./workspace-dialog";

import type {
  AgentStep,
  CommerceOverview,
  ManagerDataOnboarding,
  ManagerMemory,
  ManagerMessage,
  ManagerRuntimeStatus,
  ManagerRun,
  ManagerRunEvent,
  ManagerThread,
  ManagerThreadDetail,
  ManagerWorkspaceResponse,
  MetaResponse,
  OnboardingPrompt,
} from "@open-commerce/sdk-typescript";
import { OpenCommerceApiError } from "@open-commerce/sdk-typescript";
import {
  Activity,
  Archive,
  ArchiveRestore,
  Bot,
  Brain,
  Check,
  ChevronDown,
  CirclePlus,
  Clock3,
  Database,
  FileText,
  Hash,
  Home,
  Info,
  Menu,
  MessageSquare,
  MoreHorizontal,
  PanelRightOpen,
  Plus,
  RefreshCw,
  Send,
  Settings2,
  ShoppingCart,
  Sparkles,
  Square,
  Trash2,
  User,
  X,
} from "lucide-react";
import {
  type ChangeEvent,
  type FormEvent,
  type KeyboardEvent,
  type ReactNode,
  type RefObject,
  useEffect,
  useLayoutEffect,
  useContext,
  useRef,
  useState,
} from "react";
import { apiErrorMessage, createBrowserClient } from "@/lib/api";
import { MerchantTransportContext, useMerchantClient } from "@/lib/merchant-transport";
import styles from "./manager-workspace.module.css";

type ManagerClient = Pick<
  ReturnType<typeof createBrowserClient>,
  | "bootstrapManagerWorkspace"
  | "clearManagerChannel"
  | "createManagerReplyThread"
  | "createManagerThread"
  | "deleteManagerMemory"
  | "managerReplyThread"
  | "managerThread"
  | "managerStatus"
  | "managerCommerceOverview"
  | "managerWorkspace"
  | "profileManagerDataset"
  | "resetManagerWorkspace"
  | "sendManagerMessage"
  | "updateManagerThread"
> & Partial<Pick<ReturnType<typeof createBrowserClient>,
  "createManagerRun" | "managerRunEvents" | "cancelManagerRun"
>>;

type ManagerWorkspaceProps = {
  initialMeta: MetaResponse | null;
  client?: ManagerClient;
};

type Drawer =
  | {
      kind: "panel";
      panel: "commerce" | "data" | "memory" | "model" | "activity";
    }
  | { kind: "reply"; channelId: string; rootId: string; replyId: string | null }
  | null;

type ChannelModal =
  | { mode: "create"; channel: null }
  | { mode: "rename"; channel: ManagerThread }
  | null;

type ChannelAttempt = {
  key: string;
  body: Readonly<{ title: string; description: string | null }>;
  saved: boolean;
};

function channelIntent(modal: Exclude<ChannelModal, null>) {
  return modal.mode === "create" ? "create" : `rename:${modal.channel.id}`;
}

function mutationRejected(error: unknown) {
  return error instanceof OpenCommerceApiError && [400, 401, 403, 404, 409, 422].includes(error.status);
}

function checkWorkspaceResponse(value: ManagerWorkspaceResponse) {
  if (!Array.isArray(value?.channels) || typeof value?.onboarding?.workspace_status !== "string") {
    throw new Error("The workspace response could not be read. Please retry.");
  }
}

const LAST_SEEN_KEY = "open-commerce-manager-last-seen-v1";
type CatalogIndex = NonNullable<ManagerWorkspaceResponse["catalog_index"]> & {
  status: "not_configured" | "queued" | "running" | "ready" | "failed";
  product_count: number;
  indexed_product_count: number;
};

const EMPTY_CATALOG_INDEX: CatalogIndex = {
  status: "not_configured",
  product_count: 0,
  indexed_product_count: 0,
};

export function ManagerWorkspace({
  initialMeta,
  client: suppliedClient,
}: ManagerWorkspaceProps) {
  const storeNavigation = useStoreNavigation();
  const defaultClient = useMerchantClient();
  const client = suppliedClient ?? defaultClient;
  const [workspace, setWorkspace] = useState<ManagerWorkspaceResponse | null>(
    null,
  );
  const [details, setDetails] = useState<Record<string, ManagerThreadDetail>>(
    {},
  );
  const [selected, setSelected] = useState<string>("home");
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [pendingIds, setPendingIds] = useState<Set<string>>(new Set());
  const [runs, setRuns] = useState<Record<string, ManagerRun>>({});
  const [runEvents, setRunEvents] = useState<Record<string, ManagerRunEvent[]>>({});
  const runCursors = useRef<Record<string, number>>({});
  const runsRef = useRef(runs);
  runsRef.current = runs;
  const [loadingIds, setLoadingIds] = useState<Set<string>>(new Set());
  const [notices, setNotices] = useState<Record<string, string>>({});
  const [workspacePending, setWorkspacePending] = useState(true);
  const [workspaceNotice, setWorkspaceNotice] = useState<string | null>(null);
  const [runtimeStatus, setRuntimeStatus] =
    useState<ManagerRuntimeStatus | null>(null);
  const [statusPending, setStatusPending] = useState(false);
  const [statusNotice, setStatusNotice] = useState<string | null>(null);
  const [statusRefresh, setStatusRefresh] = useState(0);
  const [drawer, setDrawer] = useState<Drawer>(null);
  const [channelMenu, setChannelMenu] = useState(false);
  const [channelModal, setChannelModal] = useState<ChannelModal>(null);
  const [channelPending, setChannelPending] = useState(false);
  const [channelError, setChannelError] = useState<string | null>(null);
  const [channelAttempt, setChannelAttempt] = useState<ChannelAttempt | null>(null);
  const channelAttempts = useRef(new Map<string, ChannelAttempt>());
  const channelInFlight = useRef(false);
  const resetInFlight = useRef(false);
  const resetAttempt = useRef<{ key: string; body: { confirmation: "RESET" }; confirmed: boolean } | null>(null);
  const [resetPhase, setResetPhase] = useState<"idle" | "unknown" | "confirmed">("idle");
  const mutationScope = useRef(0);
  const clearInFlight = useRef(false);
  const [clearTarget, setClearTarget] = useState<ManagerThread | null>(null);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [commerceOverview, setCommerceOverview] =
    useState<CommerceOverview | null>(null);
  const [resetOpen, setResetOpen] = useState(false);
  const [resetPending, setResetPending] = useState(false);
  const [mobileNav, setMobileNav] = useState(false);
  const [showArchived, setShowArchived] = useState(false);
  const [selectedChoices, setSelectedChoices] = useState<string[]>([]);
  const [lastSeen, setLastSeen] = useState<Record<string, string>>({});
  const messageScrollRef = useRef<HTMLDivElement>(null);
  const replyComposerRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [currencyPrompt, setCurrencyPrompt] = useState(false);
  const currencyResolve = useRef<((currency: "USD" | "EUR" | "GBP" | "CAD" | "AUD" | null) => void) | null>(null);
  const uploadRef = useRef<{
    threadId: string;
    kind: "catalog" | "engagement";
  } | null>(null);
  const scrollPositions = useRef<Record<string, number>>({});
  const selectedRef = useRef(selected);
  const workspaceRef = useRef<HTMLElement>(null);
  const dialogOpener = useRef<HTMLElement | null>(null);
  const wasDialogOpen = useRef(false);
  const actionsButton = useRef<HTMLButtonElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const menuEntry = useRef<"first" | "last">("first");
  const menuTabLeaving = useRef(false);
  const [menuItem, setMenuItem] = useState("rename");
  const focusNewView = useRef(false);
  const dialogOpen = !!(channelModal || clearTarget || settingsOpen || resetOpen);

  useLayoutEffect(() => () => { mutationScope.current += 1; }, [client]);

  useLayoutEffect(() => {
    if ((wasDialogOpen.current && !dialogOpen) || focusNewView.current) {
      focusWorkspaceTarget(workspaceRef.current, focusNewView.current ? null : dialogOpener.current);
      dialogOpener.current = null;
      focusNewView.current = false;
    }
    wasDialogOpen.current = dialogOpen;
  }, [dialogOpen, selected]);

  useLayoutEffect(() => {
    if (!channelMenu) return;
    const items = menuRef.current?.querySelectorAll<HTMLButtonElement>("[role=menuitem]:not(:disabled)");
    if (!items?.length) return;
    if (menuRef.current?.contains(document.activeElement) && !document.activeElement?.matches(":disabled")) return;
    items[menuEntry.current === "last" ? items.length - 1 : 0].focus();
  }, [channelMenu, pendingIds]);

  useEffect(() => {
    if (!channelMenu) return;
    function outside(event: PointerEvent) {
      if (event.target instanceof Node && !menuRef.current?.parentElement?.contains(event.target)) {
        setChannelMenu(false);
      }
    }
    document.addEventListener("pointerdown", outside);
    return () => document.removeEventListener("pointerdown", outside);
  }, [channelMenu]);

  function openSettings(opener: HTMLElement) {
    dialogOpener.current = opener;
    setWorkspaceNotice(null);
    setChannelMenu(false);
    setSettingsOpen(true);
  }

  function openChannelDialog(modal: Exclude<ChannelModal, null>, opener: HTMLElement | null) {
    dialogOpener.current = opener;
    setChannelError(null);
    setChannelAttempt(channelAttempts.current.get(channelIntent(modal)) ?? null);
    setChannelMenu(false);
    setChannelModal(modal);
  }

  function menuKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key === "Tab") {
      menuTabLeaving.current = true;
      return;
    }
    if (event.key === "Escape") {
      event.preventDefault();
      event.stopPropagation();
      setChannelMenu(false);
      actionsButton.current?.focus();
      return;
    }
    const items = Array.from(menuRef.current?.querySelectorAll<HTMLButtonElement>("[role=menuitem]:not(:disabled)") ?? []);
    if (!items.length || !["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) return;
    event.preventDefault();
    const current = items.indexOf(document.activeElement as HTMLButtonElement);
    const next = event.key === "Home" ? 0 : event.key === "End" ? items.length - 1
      : (current + (event.key === "ArrowDown" ? 1 : -1) + items.length) % items.length;
    items[next].focus();
  }

  const channels = workspace?.channels ?? [];
  const activeChannels = channels.filter(
    (channel) => channel.status !== "archived",
  );
  const archivedChannels = channels.filter(
    (channel) => channel.status === "archived",
  );
  const selectedChannel =
    channels.find((channel) => channel.id === selected) ?? null;
  const selectedDetail = selectedChannel
    ? (details[selectedChannel.id] ?? null)
    : null;
  const replyDetail =
    drawer?.kind === "reply" && drawer.replyId ? details[drawer.replyId] : null;
  const composerDetail =
    drawer?.kind === "reply" ? replyDetail : selectedDetail;
  const onboarding = workspace?.onboarding ?? null;
  const catalogIndex: CatalogIndex = {
    ...EMPTY_CATALOG_INDEX,
    ...(workspace?.catalog_index ?? {}),
  };
  const statusRefreshMinutes = onboarding?.status_refresh_minutes ?? 5;
  const hasStatusAgent = activeChannels.some(
    (channel) => channel.channel_kind === "status" || channel.slug === "status",
  );
  const workspaceLoaded = workspace !== null;

  useEffect(() => {
    try {
      const stored = window.localStorage.getItem(LAST_SEEN_KEY);
      if (stored) setLastSeen(JSON.parse(stored) as Record<string, string>);
    } catch {
      // Browser-local unread state is expendable when storage is unavailable.
    }
    void bootstrap();
  }, []);

  useEffect(() => {
    setSelectedChoices([]);
  }, [onboarding?.current_prompt?.field]);

  useEffect(() => {
    for (const detail of Object.values(details)) {
      if (detail.active_run && !runsRef.current[detail.thread.id]) {
        const run = detail.active_run;
        setRuns((current) => ({ ...current, [detail.thread.id]: run }));
        setPending(detail.thread.id, true);
      }
    }
  }, [details]);

  useEffect(() => {
    if (!client.managerRunEvents) return;
    let active = true;
    let polling = false;
    async function poll() {
      if (polling) return;
      polling = true;
      try {
        await Promise.all(Object.values(runsRef.current).map(async (run) => {
          try {
            const result = await client.managerRunEvents!(run.id, runCursors.current[run.id] ?? 0);
            if (!active || !runsRef.current[run.thread_id]) return;
            runCursors.current[run.id] = result.next_cursor;
            setRunEvents((events) => ({ ...events, [run.thread_id]: [
              ...(events[run.thread_id] ?? []), ...result.items,
            ].slice(-30) }));
            setNotice(run.thread_id, null);
            if (["completed", "failed", "cancelled"].includes(result.run.status)) {
              const detail = await client.managerThread(run.thread_id);
              if (!active || !runsRef.current[run.thread_id]) return;
              setDetails((items) => ({ ...items, [run.thread_id]: detail }));
              setPending(run.thread_id, false);
              setRuns((current) => {
                const next = { ...current }; delete next[run.thread_id]; return next;
              });
              if (result.run.status !== "completed") setNotice(run.thread_id,
                result.items.at(-1)?.detail ?? "This run stopped. Your message is saved; send a follow-up to continue.");
              await refreshWorkspace();
              setStatusRefresh((value) => value + 1);
            } else {
              setRuns((current) => ({ ...current, [run.thread_id]: result.run }));
            }
          } catch (error) {
            if (active && runsRef.current[run.thread_id]) setNotice(run.thread_id, `Reconnecting to the saved run. ${apiErrorMessage(error)}`);
          }
        }));
      } finally { polling = false; }
    }
    const timer = window.setInterval(() => void poll(), 1000);
    return () => { active = false; window.clearInterval(timer); };
  }, [client]);

  async function stopRun(threadId: string) {
    const run = runsRef.current[threadId];
    if (!run || !client.cancelManagerRun) return;
    try {
      await client.cancelManagerRun(run.id, `stop-${run.id}`);
    } catch (error) { setNotice(threadId, apiErrorMessage(error)); }
  }

  useEffect(() => {
    if (selected !== "home" && details[selected]) markSeen(selected);
  }, [details, selected]);

  useEffect(() => {
    if (drawer?.kind === "reply" && replyDetail)
      replyComposerRef.current?.focus();
  }, [drawer, replyDetail]);

  useEffect(() => {
    if (drawer?.kind !== "panel" || drawer.panel !== "commerce") return;
    let active = true;
    void client
      .managerCommerceOverview()
      .then((result) => active && setCommerceOverview(result))
      .catch(
        (error) =>
          active && setNotice(selectedRef.current, apiErrorMessage(error)),
      );
    return () => {
      active = false;
    };
  }, [client, drawer]);

  useEffect(() => {
    if (!["queued", "running"].includes(catalogIndex.status)) return;
    let active = true;
    let polling = false;
    const timer = window.setInterval(() => {
      if (polling) return;
      polling = true;
      void client
        .managerWorkspace()
        .then((next) => { if (active) setWorkspace(next); })
        .catch(() => undefined)
        .finally(() => { polling = false; });
    }, 1500);
    return () => { active = false; window.clearInterval(timer); };
  }, [catalogIndex.status, client]);

  useEffect(() => {
    if (!workspaceLoaded || !hasStatusAgent) return;
    let active = true;
    async function refreshStatus() {
      setStatusPending(true);
      try {
        const next = await client.managerStatus();
        if (active) {
          setRuntimeStatus(next);
          setStatusNotice(null);
        }
      } catch (error) {
        if (active) setStatusNotice(apiErrorMessage(error));
      } finally {
        if (active) setStatusPending(false);
      }
    }
    void refreshStatus();
    const timer =
      statusRefreshMinutes > 0
        ? window.setInterval(
            () => void refreshStatus(),
            statusRefreshMinutes * 60_000,
          )
        : null;
    return () => {
      active = false;
      if (timer !== null) window.clearInterval(timer);
    };
  }, [client, hasStatusAgent, statusRefresh, statusRefreshMinutes, workspaceLoaded]);

  async function bootstrap() {
    setWorkspacePending(true);
    setWorkspaceNotice(null);
    try {
      const next = await client.bootstrapManagerWorkspace(
        "manager-workspace-bootstrap-v1",
      );
      setWorkspace(next);
      const onboardingChannel = next.channels.find(
        (channel) => channel.channel_kind === "onboarding",
      );
      if (onboardingChannel) {
        const detail = await client.managerThread(onboardingChannel.id);
        setDetails({ [detail.thread.id]: detail });
        if (next.onboarding.workspace_status !== "completed") {
          setSelected(detail.thread.id);
          selectedRef.current = detail.thread.id;
        }
      }
      if (client.managerRunEvents && next.onboarding.workspace_status === "completed") {
        for (const channel of next.channels.filter((item) => item.status !== "archived")) {
          const detail = await client.managerThread(channel.id);
          setDetails((items) => ({ ...items, [channel.id]: detail }));
        }
      }
    } catch (error) {
      setWorkspaceNotice(apiErrorMessage(error));
    } finally {
      setWorkspacePending(false);
    }
  }

  async function refreshWorkspace() {
    const next = await client.managerWorkspace();
    setWorkspace(next);
    return next;
  }

  async function resetWorkspace() {
    if (resetInFlight.current) return;
    const scope = mutationScope.current;
    const attempt = resetAttempt.current ?? {
      key: `manager-workspace-reset-${crypto.randomUUID()}`,
      body: { confirmation: "RESET" as const },
      confirmed: false,
    };
    resetAttempt.current = attempt;
    resetInFlight.current = true;
    setResetPending(true);
    setWorkspaceNotice(null);
    if (!attempt.confirmed) setResetPhase("unknown");
    try {
      if (!attempt.confirmed) {
        const response = await client.resetManagerWorkspace(attempt.body, attempt.key);
        if (scope !== mutationScope.current) return;
        checkWorkspaceResponse(response?.workspace);
        // A confirmed reset is never repeated to recover a subsequent read.
        attempt.confirmed = true;
        setResetPhase("confirmed");
        try {
          window.localStorage.removeItem(LAST_SEEN_KEY);
        } catch {
          // Browser-local unread state is expendable when storage is unavailable.
        }
        setLastSeen({});
        setDetails({});
        setDrafts({});
        scrollPositions.current = {};
        uploadRef.current = null;
        setPendingIds(new Set());
        runsRef.current = {};
        setRuns({});
        setRunEvents({});
        setNotices({});
        setSelectedChoices([]);
        setChannelMenu(false);
        setShowArchived(false);
        setSettingsOpen(false);
        setDrawer(null);
        setRuntimeStatus(null);
        channelAttempts.current.clear();
        setChannelAttempt(null);
        setSelected("home");
        selectedRef.current = "home";
        setWorkspace(response.workspace);
      }
      // A replayed receipt may predate new work; refresh from current server state.
      const next = await client.managerWorkspace();
      if (scope !== mutationScope.current) return;
      checkWorkspaceResponse(next);
      const onboardingChannel = next.channels.find(
        (channel) => channel.channel_kind === "onboarding",
      );
      const nextDetails: Record<string, ManagerThreadDetail> = {};
      if (onboardingChannel) {
        const detail = await client.managerThread(onboardingChannel.id);
        if (scope !== mutationScope.current) return;
        if (detail?.thread?.id !== onboardingChannel.id || !Array.isArray(detail.messages)) {
          throw new Error("The workspace response could not be read. Please retry.");
        }
        nextDetails[onboardingChannel.id] = detail;
      }
      const destination = next.onboarding.workspace_status !== "completed" && onboardingChannel
        ? onboardingChannel.id : "home";
      setSelected(destination);
      selectedRef.current = destination;
      setDetails(nextDetails);
      setWorkspace(next);
      resetAttempt.current = null;
      setResetPhase("idle");
      setResetOpen(false);
    } catch (error) {
      if (scope !== mutationScope.current) return;
      if (!attempt.confirmed && mutationRejected(error)) {
        resetAttempt.current = null;
        setResetPhase("idle");
      }
      setWorkspaceNotice(`${attempt.confirmed ? "Workspace reset. Refresh failed. " : ""}${apiErrorMessage(error)}`);
    } finally {
      resetInFlight.current = false;
      if (scope === mutationScope.current) setResetPending(false);
    }
  }

  async function selectChannel(channelId: string) {
    saveScrollPosition();
    setSelected(channelId);
    selectedRef.current = channelId;
    setMobileNav(false);
    setChannelMenu(false);
    setDrawer(null);
    if (!details[channelId] && !loadingIds.has(channelId)) {
      setLoading(channelId, true);
      try {
        const detail = await client.managerThread(channelId);
        setDetails((items) => ({ ...items, [channelId]: detail }));
      } catch (error) {
        setNotice(channelId, apiErrorMessage(error));
      } finally {
        setLoading(channelId, false);
      }
    }
    window.requestAnimationFrame(() => {
      if (messageScrollRef.current) {
        messageScrollRef.current.scrollTop =
          scrollPositions.current[channelId] ?? 0;
      }
    });
  }

  function selectHome() {
    saveScrollPosition();
    setSelected("home");
    selectedRef.current = "home";
    setDrawer(null);
    setChannelMenu(false);
    setMobileNav(false);
  }

  function saveScrollPosition() {
    const current = selectedRef.current;
    if (current !== "home" && messageScrollRef.current) {
      scrollPositions.current[current] = messageScrollRef.current.scrollTop;
    }
  }

  async function send(content?: string) {
    const detail = composerDetail;
    const cleaned = (
      content ?? (detail ? drafts[detail.thread.id] : "")
    ).trim();
    if (!detail || !cleaned || pendingIds.has(detail.thread.id)) return;
    const threadId = detail.thread.id;
    const optimisticId = `pending-${crypto.randomUUID()}`;
    const optimistic: ManagerMessage = {
      id: optimisticId,
      tenant_id: detail.thread.tenant_id,
      thread_id: threadId,
      role: "user",
      content: cleaned,
      steps: [],
      reply_count: 0,
      created_at: new Date().toISOString(),
    };
    setPending(threadId, true);
    setNotice(threadId, null);
    setDraft(threadId, "");
    setDetails((items) => ({
      ...items,
      [threadId]: {
        ...(items[threadId] ?? detail),
        messages: [...(items[threadId] ?? detail).messages, optimistic],
      },
    }));
    scrollToEnd();
    if (client.createManagerRun && onboarding?.workspace_status === "completed") {
      try {
        const run = await client.createManagerRun(threadId, { content: cleaned },
          `manager-run-${optimisticId}`);
        setRuns((current) => ({ ...current, [threadId]: run }));
        setRunEvents((current) => ({ ...current, [threadId]: [] }));
        setDetails((items) => ({ ...items, [threadId]: {
          ...items[threadId], active_run: run,
          messages: items[threadId].messages.map((message) => message.id === optimisticId
            ? { ...message, id: run.user_message_id } : message),
        } }));
      } catch (error) {
        setNotice(threadId, `Message delivery could not be confirmed. ${apiErrorMessage(error)}`);
        setDraft(threadId, cleaned);
        setPending(threadId, false);
      }
      return;
    }
    try {
      const response = await client.sendManagerMessage(
        threadId,
        { content: cleaned },
        `manager-message-${crypto.randomUUID()}`,
      );
      setDetails((items) => {
        const current = items[threadId] ?? detail;
        const next: ManagerThreadDetail = {
          ...current,
          thread: response.thread,
          messages: [
            ...current.messages.filter(
              (message) => message.id !== optimisticId,
            ),
            response.user_message,
            response.assistant_message,
          ],
          memories: response.memories,
          capabilities: response.capabilities,
          onboarding: response.onboarding,
        };
        return Object.fromEntries(
          Object.entries({ ...items, [threadId]: next }).map(([id, item]) => [
            id,
            { ...item, onboarding: response.onboarding },
          ]),
        );
      });
      setWorkspace((current) =>
        current
          ? {
              ...current,
              onboarding: response.onboarding,
              channels: current.channels.map((channel) =>
                channel.id === response.thread.id ? response.thread : channel,
              ),
            }
          : current,
      );
      if (response.workspace_changed) {
        await refreshWorkspace();
        setSelected("home");
        selectedRef.current = "home";
      }
      if (response.periodic_memory_created) {
        setNotice(threadId, "Periodic memory checkpoint saved.");
      }
      if (drawer?.kind === "reply") {
        const refreshed = await client.managerThread(drawer.channelId);
        setDetails((items) => ({ ...items, [drawer.channelId]: refreshed }));
      }
      scrollToEnd();
    } catch (error) {
      setDetails((items) => {
        const current = items[threadId];
        if (!current) return items;
        return {
          ...items,
          [threadId]: {
            ...current,
            messages: current.messages.filter(
              (message) => message.id !== optimisticId,
            ),
          },
        };
      });
      setDraft(threadId, cleaned);
      setNotice(threadId, apiErrorMessage(error));
    } finally {
      setPending(threadId, false);
    }
  }

  async function openReply(root: ManagerMessage) {
    if (!selectedChannel) return;
    setDrawer({
      kind: "reply",
      channelId: selectedChannel.id,
      rootId: root.id,
      replyId: null,
    });
    setLoading(root.id, true);
    try {
      const detail = await client.createManagerReplyThread(
        selectedChannel.id,
        { root_message_id: root.id },
        `manager-reply-${root.id}`,
      );
      setDetails((items) => ({ ...items, [detail.thread.id]: detail }));
      setDrawer({
        kind: "reply",
        channelId: selectedChannel.id,
        rootId: root.id,
        replyId: detail.thread.id,
      });
    } catch (error) {
      setNotice(selectedChannel.id, apiErrorMessage(error));
      setDrawer(null);
    } finally {
      setLoading(root.id, false);
    }
  }

  function chooseDataset(kind: "catalog" | "engagement", threadId?: string) {
    if (kind === "catalog" && storeNavigation) {
      storeNavigation.openProducts();
      return;
    }
    const target = threadId ?? composerDetail?.thread.id ?? channels.find(
      (channel) => channel.channel_kind === "onboarding" && channel.status !== "archived",
    )?.id;
    if (!target || pendingIds.has(target)) {
      setWorkspaceNotice(target
        ? "The onboarding agent is still working. Try attaching the CSV when it finishes."
        : "Open an agent conversation before attaching this CSV.");
      return;
    }
    uploadRef.current = { threadId: target, kind };
    fileInputRef.current?.click();
  }

  async function profileDataset(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    const target = uploadRef.current;
    event.target.value = "";
    if (!file || !target) return;
    if (!file.name.toLowerCase().endsWith(".csv")) {
      setNotice(target.threadId, "Choose a CSV file.");
      return;
    }
    if (file.size > 524_288) {
      setNotice(target.threadId, "Choose a CSV no larger than 512 KiB.");
      return;
    }
    setPending(target.threadId, true);
    setNotice(target.threadId, null);
    try {
      const csvText = await file.text();
      let catalogCurrency: "USD" | "EUR" | "GBP" | "CAD" | "AUD" | null = null;
      if (target.kind === "catalog" && /(?:Handle|URL handle)/.test(csvText.split(/\r?\n/, 1)[0]) && /(?:Variant Price|Price)/.test(csvText.split(/\r?\n/, 1)[0])) {
        catalogCurrency = await new Promise((resolve) => { currencyResolve.current = resolve; setCurrencyPrompt(true); });
        if (!catalogCurrency) return;
      }
      const response = await client.profileManagerDataset(
        target.threadId,
        {
          dataset_kind: target.kind,
          filename: file.name,
          csv_text: csvText,
          ...(catalogCurrency ? { catalog_currency: catalogCurrency } : {}),
        },
        `manager-dataset-${crypto.randomUUID()}`,
      );
      setDetails((items) => {
        const current = items[target.threadId];
        const next = Object.fromEntries(
          Object.entries(items).map(([id, item]) => [
            id,
            { ...item, onboarding: response.onboarding },
          ]),
        );
        if (current) {
          next[target.threadId] = {
            ...current,
            thread: response.thread,
            messages: [
              ...current.messages,
              response.user_message,
              response.assistant_message,
            ],
            onboarding: response.onboarding,
          };
        }
        return next;
      });
      setWorkspace((current) =>
        current
          ? {
              ...current,
              onboarding: response.onboarding,
              catalog_index: response.catalog_index,
            }
          : current,
      );
      scrollToEnd();
    } catch (error) {
      setNotice(target.threadId, apiErrorMessage(error));
    } finally {
      setPending(target.threadId, false);
    }
  }

  async function saveChannel(name: string, purpose: string) {
    if (channelInFlight.current || !channelModal) return;
    const scope = mutationScope.current;
    const modal = channelModal;
    const intent = channelIntent(modal);
    let attempt = channelAttempts.current.get(intent) ?? {
      key: `manager-channel-${modal.mode === "rename" ? "update-" : ""}${crypto.randomUUID()}`,
      body: { title: name, description: modal.mode === "create" ? purpose || null : purpose },
      saved: false,
    };
    channelAttempts.current.set(intent, attempt);
    setChannelAttempt(attempt);
    channelInFlight.current = true;
    setChannelPending(true);
    setChannelError(null);
    try {
      if (!attempt.saved) {
        const updated = modal.mode === "rename"
          ? await client.updateManagerThread(modal.channel.id, attempt.body, attempt.key)
          : await client.createManagerThread(attempt.body, attempt.key);
        if (scope !== mutationScope.current) return;
        if (typeof updated?.thread?.id !== "string" || !Array.isArray(updated.messages)
          || !Array.isArray(updated.memories)) {
          throw new Error("The save response could not be read. Retry the same save.");
        }
        attempt = { ...attempt, saved: true };
        channelAttempts.current.set(intent, attempt);
        setChannelAttempt(attempt);
        setDetails((items) => ({ ...items, [updated.thread.id]: updated }));
        if (modal.mode === "create") {
          setSelected(updated.thread.id);
          selectedRef.current = updated.thread.id;
        }
      }
      const next = await client.managerWorkspace();
      if (scope !== mutationScope.current) return;
      checkWorkspaceResponse(next);
      setWorkspace(next);
      channelAttempts.current.delete(intent);
      setChannelAttempt(null);
      setChannelModal(null);
    } catch (error) {
      if (scope !== mutationScope.current) return;
      if (!attempt.saved && mutationRejected(error)) {
        channelAttempts.current.delete(intent);
        setChannelAttempt(null);
      }
      setChannelError(`${attempt.saved ? "Saved. Workspace refresh failed. " : ""}${apiErrorMessage(error)}`);
    } finally {
      channelInFlight.current = false;
      if (scope === mutationScope.current) setChannelPending(false);
    }
  }

  async function setChannelStatus(
    channel: ManagerThread,
    status: "active" | "archived",
  ) {
    try {
      const updated = await client.updateManagerThread(
        channel.id,
        { status },
        `manager-channel-status-${crypto.randomUUID()}`,
      );
      setDetails((items) => ({ ...items, [updated.thread.id]: updated }));
      await refreshWorkspace();
      if (status === "archived" && selected === channel.id) {
        focusNewView.current = document.activeElement === actionsButton.current;
        selectHome();
      }
    } catch (error) {
      setNotice(channel.id, apiErrorMessage(error));
    } finally {
      setChannelMenu(false);
    }
  }

  async function clearChannelHistory(channel: ManagerThread) {
    if (clearInFlight.current) return;
    clearInFlight.current = true;
    setLoading(channel.id, true);
    setChannelMenu(false);
    try {
      const cleared = await client.clearManagerChannel(
        channel.id,
        `manager-channel-clear-${crypto.randomUUID()}`,
      );
      const removed = new Set(Object.values(details).filter((item) =>
        item.thread.id === channel.id || item.thread.parent_thread_id === channel.id,
      ).map((item) => item.thread.id));
      const retainedRuns = Object.fromEntries(Object.entries(runsRef.current).filter(([id]) => !removed.has(id)));
      runsRef.current = retainedRuns;
      setRuns(retainedRuns);
      setPendingIds((ids) => new Set([...ids].filter((id) => !removed.has(id))));
      setDetails((items) => ({
        ...Object.fromEntries(Object.entries(items).filter(([id]) => !removed.has(id))),
        [channel.id]: cleared.detail,
      }));
      setWorkspace((current) =>
        current
          ? {
              ...current,
              channels: current.channels.map((item) =>
                item.id === channel.id ? cleared.detail.thread : item,
              ),
            }
          : current,
      );
      scrollPositions.current[channel.id] = 0;
      setDrawer(null);
      setNotice(
        channel.id,
        `${cleared.deleted_message_count} messages and ${cleared.deleted_reply_thread_count} reply threads cleared. Long-term preferences were kept.`,
      );
      scrollToEnd();
    } catch (error) {
      setNotice(channel.id, apiErrorMessage(error));
    } finally {
      clearInFlight.current = false;
      setLoading(channel.id, false);
      setClearTarget(null);
    }
  }

  async function forget(memory: ManagerMemory) {
    const detail = composerDetail;
    if (!detail || memory.layer !== "long_term") return;
    try {
      await client.deleteManagerMemory(
        memory.id,
        `manager-memory-delete-${crypto.randomUUID()}`,
      );
      setDetails((items) =>
        Object.fromEntries(
          Object.entries(items).map(([id, item]) => [
            id,
            {
              ...item,
              memories: item.memories.filter((value) => value.id !== memory.id),
            },
          ]),
        ),
      );
    } catch (error) {
      setNotice(detail.thread.id, apiErrorMessage(error));
    }
  }

  function markSeen(channelId: string) {
    const stamp = new Date().toISOString();
    setLastSeen((current) => {
      const next = { ...current, [channelId]: stamp };
      try {
        window.localStorage.setItem(LAST_SEEN_KEY, JSON.stringify(next));
      } catch {
        // The channel still works when browser storage is unavailable.
      }
      return next;
    });
  }

  function hasUnread(channel: ManagerThread) {
    return (
      selected !== channel.id &&
      channel.updated_at > (lastSeen[channel.id] ?? "")
    );
  }

  function setPending(id: string, value: boolean) {
    setPendingIds((current) => setMembership(current, id, value));
  }

  function setLoading(id: string, value: boolean) {
    setLoadingIds((current) => setMembership(current, id, value));
  }

  function setDraft(id: string, value: string) {
    setDrafts((current) => ({ ...current, [id]: value }));
  }

  function setNotice(id: string, value: string | null) {
    setNotices((current) => {
      const next = { ...current };
      if (value) next[id] = value;
      else delete next[id];
      return next;
    });
  }

  function scrollToEnd() {
    window.requestAnimationFrame(() => {
      const node =
        drawer?.kind === "reply"
          ? document.getElementById("reply-scroll")
          : messageScrollRef.current;
      if (node) node.scrollTop = node.scrollHeight;
    });
  }

  if (!workspace && workspacePending) {
    return <WorkspaceLoading />;
  }

  if (!workspace) {
    return (
      <main className={styles.unavailable}>
        <div className={styles.brandGlyph}>GA</div>
        <h1>Operator workspace unavailable</h1>
        <p>{workspaceNotice ?? "The local runtime did not answer."}</p>
        <button
          className={styles.primaryButton}
          type="button"
          onClick={() => void bootstrap()}
        >
          Try again
        </button>
      </main>
    );
  }

  const onboardingChannel = channels.find(
    (channel) => channel.channel_kind === "onboarding",
  );
  const onboardingDetail = onboardingChannel
    ? (details[onboardingChannel.id] ?? null)
    : null;
  if (onboarding?.workspace_status !== "completed" && onboardingChannel && resetPhase !== "confirmed") {
    return (
      <>
        <OnboardingInterview
          workspaceRef={workspaceRef}
          detail={onboardingDetail}
          onboarding={workspace.onboarding}
          pending={!onboardingDetail || pendingIds.has(onboardingChannel.id)}
          notice={notices[onboardingChannel.id] ?? workspaceNotice}
          selectedChoices={selectedChoices}
          onToggleChoice={(value) =>
            setSelectedChoices((current) =>
              current.includes(value)
                ? current.filter((item) => item !== value)
                : [...current, value],
            )
          }
          onSend={(content) => void send(content)}
          onDraft={(content) => setDraft(onboardingChannel.id, content)}
          draft={drafts[onboardingChannel.id] ?? ""}
          onUpload={(kind) => chooseDataset(kind, onboardingChannel.id)}
        />
        <input
          ref={fileInputRef}
          className={styles.hiddenInput}
          aria-label="Choose dataset CSV"
          hidden
          tabIndex={-1}
          type="file"
          accept=".csv,text/csv"
          onChange={(event) => void profileDataset(event)}
        />
        {currencyPrompt && <CatalogCurrencyDialog onClose={(currency) => { setCurrencyPrompt(false); currencyResolve.current?.(currency); currencyResolve.current = null; }} />}
      </>
    );
  }

  const activeRuns = pendingIds.size;
  const unreadCount = activeChannels.filter(hasUnread).length;

  return (
    <main ref={workspaceRef} className={styles.shell} tabIndex={-1}>
      <header className={styles.topbar}>
        <button
          className={styles.mobileMenu}
          type="button"
          aria-label="Open agent navigation"
          title="Agents"
          onClick={() => setMobileNav(true)}
        >
          <Menu size={18} />
        </button>
        <div className={styles.wordmark}>
          <span className={styles.brandGlyph}>GA</span>
          <strong>
            {onboarding?.workspace_profile?.workspace_name || "GoodAgent"}
          </strong>
        </div>
        <button
          className={styles.searchBox}
          type="button"
          onClick={() => selectHome()}
        >
          <Home size={15} />
          <span>Workspace overview</span>
        </button>
        <div className={styles.topbarActions}>
          <span
            className={styles.connection}
            data-ready={initialMeta?.status === "ready"}
          >
            <span />{" "}
            {initialMeta?.status === "ready"
              ? "Local runtime"
              : "Runtime check"}
          </span>
          <button
            type="button"
            aria-label="Open commerce operations"
            title="Commerce"
            onClick={() => setDrawer({ kind: "panel", panel: "commerce" })}
          >
            <ShoppingCart size={18} />
          </button>
          <button
            type="button"
            aria-label="Workspace settings"
            title="Settings"
            onClick={(event) => openSettings(event.currentTarget)}
          >
            <Settings2 size={18} />
          </button>
          <button
            type="button"
            aria-label="Workspace information"
            title="Workspace information"
          >
            <Info size={18} />
          </button>
        </div>
      </header>

      <div className={styles.workspace}>
        <nav className={styles.workspaceRail} aria-label="Workspace">
          <button
            className={styles.railLogo}
            type="button"
            onClick={selectHome}
            aria-label="Home"
          >
            GA
          </button>
          <button
            className={selected === "home" ? styles.railActive : ""}
            type="button"
            onClick={selectHome}
            aria-label="Workspace Home"
            title="Home"
          >
            <Home size={20} />
          </button>
          <button
            type="button"
            onClick={(event) => openChannelDialog({ mode: "create", channel: null }, event.currentTarget)}
            aria-label="Create agent"
            title="Create agent"
          >
            <Plus size={20} />
          </button>
          <span className={styles.railSpacer} />
        </nav>

        <aside
          className={`${styles.channelSidebar} ${mobileNav ? styles.mobileNavOpen : ""}`}
        >
          <div className={styles.sidebarHeader}>
            <div>
              <strong>
                {onboarding?.workspace_profile?.workspace_name ||
                  "Commerce team"}
              </strong>
              <span>
                <i /> Store operator online
              </span>
            </div>
            <button
              type="button"
              aria-label="Close navigation"
              onClick={() => setMobileNav(false)}
            >
              <X size={18} />
            </button>
          </div>
          <div className={styles.channelScroll}>
            <button
              className={`${styles.homeLink} ${selected === "home" ? styles.navSelected : ""}`}
              type="button"
              onClick={selectHome}
            >
              <Home size={17} />
              <span>Home</span>
              {unreadCount > 0 && <b>{unreadCount}</b>}
            </button>
            <a className={styles.homeLink} href="/manager/catalog">
              <Database size={17} /><span>Browse catalog</span>
            </a>
            <div className={styles.navGroupHeader}>
              <span>Agents</span>
              <button
                type="button"
                aria-label="Create agent"
                title="Create agent"
                onClick={(event) =>
                  openChannelDialog({ mode: "create", channel: null }, event.currentTarget)
                }
              >
                <CirclePlus size={17} />
              </button>
            </div>
            <div className={styles.channelList}>
              {activeChannels.map((channel) => (
                <button
                  key={channel.id}
                  className={selected === channel.id ? styles.navSelected : ""}
                  type="button"
                  onClick={() => void selectChannel(channel.id)}
                  aria-label={`#${channel.slug || channel.title}`}
                >
                  {channel.channel_kind === "status" || channel.slug === "status" ? (
                    <Activity size={16} />
                  ) : (
                    <Hash size={16} />
                  )}
                  <span>{channel.slug || channel.title}</span>
                  {pendingIds.has(channel.id) ? (
                    <i className={styles.pendingDot} title="Agent working" />
                  ) : hasUnread(channel) ? (
                    <b>1</b>
                  ) : null}
                </button>
              ))}
            </div>
            {archivedChannels.length > 0 && (
              <div className={styles.archivedGroup}>
                <button
                  type="button"
                  onClick={() => setShowArchived((value) => !value)}
                >
                  <ChevronDown size={15} data-open={showArchived} />
                  Archived
                </button>
                {showArchived &&
                  archivedChannels.map((channel) => (
                    <div key={channel.id} className={styles.archivedRow}>
                      <span>#{channel.slug}</span>
                      <button
                        type="button"
                        aria-label={`Restore ${channel.title}`}
                        title="Restore agent"
                        onClick={() => void setChannelStatus(channel, "active")}
                      >
                        <ArchiveRestore size={15} />
                      </button>
                    </div>
                  ))}
              </div>
            )}
          </div>
          <div className={styles.sidebarFooter}>
            <button
              type="button"
              aria-label="Settings"
              onClick={(event) => openSettings(event.currentTarget)}
            >
              <span className={styles.userAvatar}>HC</span>
              <div className={styles.operatorCopy}>
                <strong>Store operator</strong>
                <span>Settings</span>
              </div>
              <Settings2 size={17} />
            </button>
          </div>
        </aside>

        <section
          className={styles.mainPane}
          data-status-channel={selectedChannel?.channel_kind === "status" || selectedChannel?.slug === "status"}
        >
          {selected === "home" ? (
            <HomeView
              workspace={workspace}
              activeRuns={activeRuns}
              unreadCount={unreadCount}
              onOpenChannel={(id) => void selectChannel(id)}
              onOpenPanel={(panel) => setDrawer({ kind: "panel", panel })}
            />
          ) : (
            <>
              <header className={styles.channelHeader}>
                <div>
                  <h1 data-workspace-focus tabIndex={-1}>
                    <Bot size={19} />{" "}
                    {selectedChannel?.slug || selectedChannel?.title}
                  </h1>
                  <p>
                    <span className={styles.agentLabel}>Specialist agent</span>
                    {selectedChannel?.description}
                  </p>
                </div>
                <div className={styles.channelActions}>
                  <button
                    type="button"
                    aria-label="Open details panel"
                    title="Details"
                    onClick={() => setDrawer({ kind: "panel", panel: "data" })}
                  >
                    <PanelRightOpen size={18} />
                  </button>
                  <div className={styles.menuAnchor}>
                    <button
                      ref={actionsButton}
                      type="button"
                      aria-label="Agent actions"
                      aria-haspopup="menu"
                      aria-expanded={channelMenu}
                      aria-controls="agent-actions-menu"
                      title="Agent actions"
                      onClick={() => {
                        menuEntry.current = "first";
                        setChannelMenu((value) => !value);
                      }}
                      onKeyDown={(event) => {
                        if (event.key !== "ArrowDown" && event.key !== "ArrowUp") return;
                        event.preventDefault();
                        menuEntry.current = event.key === "ArrowUp" ? "last" : "first";
                        if (channelMenu) {
                          const items = menuRef.current?.querySelectorAll<HTMLButtonElement>("[role=menuitem]:not(:disabled)");
                          items?.[menuEntry.current === "last" ? items.length - 1 : 0]?.focus();
                        } else setChannelMenu(true);
                      }}
                    >
                      <MoreHorizontal size={19} />
                    </button>
                    {channelMenu && selectedChannel && (
                      <div ref={menuRef} id="agent-actions-menu" className={styles.channelMenu} role="menu"
                        aria-label="Agent actions" onKeyDown={menuKeyDown}
                        onBlur={(event) => {
                          const next = event.relatedTarget;
                          if (!event.currentTarget.contains(next)
                            && (next !== actionsButton.current || menuTabLeaving.current)) setChannelMenu(false);
                          menuTabLeaving.current = false;
                        }}>
                        <button
                          type="button"
                          role="menuitem"
                          tabIndex={menuItem === "rename" ? 0 : -1}
                          onFocus={() => setMenuItem("rename")}
                          onClick={() =>
                            openChannelDialog({
                              mode: "rename",
                              channel: selectedChannel,
                            }, actionsButton.current)
                          }
                        >
                          Rename agent
                        </button>
                        <button
                          type="button"
                          role="menuitem"
                          tabIndex={menuItem === "clear" ? 0 : -1}
                          onFocus={() => setMenuItem("clear")}
                          disabled={pendingIds.has(selectedChannel.id)}
                          onClick={() => {
                            dialogOpener.current = actionsButton.current;
                            setChannelMenu(false);
                            setClearTarget(selectedChannel);
                          }}
                        >
                          <Trash2 size={14} /> Clear agent history
                        </button>
                        {selectedChannel.channel_kind !== "onboarding" && (
                          <button
                            type="button"
                            role="menuitem"
                            tabIndex={menuItem === "archive" ? 0 : -1}
                            onFocus={() => setMenuItem("archive")}
                            onClick={() => {
                              setChannelMenu(false);
                              actionsButton.current?.focus();
                              void setChannelStatus(selectedChannel, "archived");
                            }}
                          >
                            <Archive size={14} /> Archive agent
                          </button>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              </header>
              {(selectedChannel?.channel_kind === "status" || selectedChannel?.slug === "status") && (
                <StatusBoard
                  status={runtimeStatus}
                  pending={statusPending}
                  notice={statusNotice}
                  refreshMinutes={statusRefreshMinutes}
                  onRefresh={() => setStatusRefresh((value) => value + 1)}
                />
              )}
              <div
                ref={messageScrollRef}
                className={styles.messageScroll}
                data-testid="message-scroll"
              >
                {loadingIds.has(selected) && !selectedDetail ? (
                  <div className={styles.inlineLoading}>
                    Loading conversation...
                  </div>
                ) : (
                  selectedDetail?.messages.map((message) => (
                    <MessageRow
                      key={message.id}
                      message={message}
                      onReply={() => void openReply(message)}
                      replyLoading={loadingIds.has(message.id)}
                    />
                  ))
                )}
                {pendingIds.has(selected) && (
                  <AgentWorking agentName={selectedChannel?.title}
                    run={runs[selected]} events={runEvents[selected]}
                    onStop={() => void stopRun(selected)} />
                )}
              </div>
              <Composer
                threadId={selected}
                channelSlug={selectedChannel?.slug || "channel"}
                draft={drafts[selected] ?? ""}
                pending={
                  !selectedDetail ||
                  loadingIds.has(selected) ||
                  pendingIds.has(selected)
                }
                notice={notices[selected]}
                onChange={setDraft}
                onSend={() => void send()}
                onUpload={() => chooseDataset("catalog", selected)}
              />
            </>
          )}
        </section>

        {drawer && (
          <WorkspaceDrawer
            drawer={drawer}
            detail={drawer.kind === "reply" ? replyDetail : selectedDetail}
            onboarding={workspace.onboarding}
            catalogIndex={catalogIndex}
            commerceOverview={commerceOverview}
            runtimeStatus={runtimeStatus}
            loading={drawer.kind === "reply" && loadingIds.has(drawer.rootId)}
            draft={replyDetail ? (drafts[replyDetail.thread.id] ?? "") : ""}
            pending={
              replyDetail ? pendingIds.has(replyDetail.thread.id) : false
            }
            notice={replyDetail ? notices[replyDetail.thread.id] : undefined}
            composerRef={replyComposerRef}
            onClose={() => setDrawer(null)}
            onPanel={(panel) => setDrawer({ kind: "panel", panel })}
            onDraft={setDraft}
            onSend={() => void send()}
            onUpload={chooseDataset}
            onForget={(memory) => void forget(memory)}
            run={replyDetail ? runs[replyDetail.thread.id] : undefined}
            events={replyDetail ? runEvents[replyDetail.thread.id] : undefined}
            onStop={() => replyDetail && void stopRun(replyDetail.thread.id)}
          />
        )}
      </div>

      {channelModal && (
        <ChannelDialog
          modal={channelModal}
          pending={channelPending}
          error={channelError}
          attempt={channelAttempt}
          onClose={() => { if (!channelInFlight.current) setChannelModal(null); }}
          onSave={(name, purpose) => void saveChannel(name, purpose)}
        />
      )}
      {clearTarget && (
        <ClearHistoryDialog
          agent={clearTarget}
          pending={loadingIds.has(clearTarget.id)}
          onClose={() => { if (!clearInFlight.current) setClearTarget(null); }}
          onConfirm={() => void clearChannelHistory(clearTarget)}
        />
      )}
      {settingsOpen && (
        <WorkspaceSettingsDialog
          onClose={() => setSettingsOpen(false)}
          onReset={() => {
            setSettingsOpen(false);
            setResetOpen(true);
          }}
        />
      )}
      {resetOpen && (
        <ResetWorkspaceDialog
          pending={resetPending}
          phase={resetPhase}
          error={workspaceNotice}
          onClose={() => { if (!resetInFlight.current) setResetOpen(false); }}
          onConfirm={() => void resetWorkspace()}
        />
      )}
      <input
        ref={fileInputRef}
        className={styles.hiddenInput}
        aria-label="Choose dataset CSV"
        hidden
        tabIndex={-1}
        type="file"
        accept=".csv,text/csv"
        onChange={(event) => void profileDataset(event)}
      />
      {currencyPrompt && <CatalogCurrencyDialog onClose={(currency) => { setCurrencyPrompt(false); currencyResolve.current?.(currency); currencyResolve.current = null; }} />}
    </main>
  );
}

function StatusBoard({
  status,
  pending,
  notice,
  refreshMinutes,
  onRefresh,
}: {
  status: ManagerRuntimeStatus | null;
  pending: boolean;
  notice: string | null;
  refreshMinutes: number;
  onRefresh: () => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const issues = status?.components.filter((component) => component.state !== "green").length;
  return (
    <section className={styles.statusBoard} aria-label="Live service status">
      <div className={styles.statusBoardHeader}>
        <div>
          <strong>Commerce runtime{issues !== undefined ? ` · ${issues === 0 ? "All checks healthy" : `${issues} need attention`}` : ""}</strong>
          <span>
            {status
              ? `Updated ${formatTime(status.generated_at)} · ${refreshMinutes > 0 ? `auto-check every ${refreshMinutes} min` : "auto-check off"}`
              : pending
                ? "Checking services..."
                : "Awaiting status"}
          </span>
        </div>
        <button type="button" aria-label="Toggle service details" aria-expanded={expanded}
          title={expanded ? "Collapse service details" : "Expand service details"}
          onClick={() => setExpanded((value) => !value)}><ChevronDown size={16} /></button>
        <button
          type="button"
          aria-label="Refresh service status"
          title="Refresh status"
          onClick={onRefresh}
          disabled={pending}
        >
          <RefreshCw size={15} data-spinning={pending} />
        </button>
      </div>
      {notice && <p className={styles.statusNotice}>{notice}</p>}
      {expanded && <div className={styles.statusGrid}>
        {(status?.components ?? []).map((component) => (
          <div className={styles.statusComponent} key={component.key}>
            <i data-state={component.state} aria-hidden="true" />
            <div>
              <strong>{component.label}</strong>
              <span>{component.detail}</span>
            </div>
            <b>{{ green: "Healthy", yellow: "Limited", red: "Unreachable", unknown: "Unchecked" }[component.state]}</b>
          </div>
        ))}
      </div>}
    </section>
  );
}

function OnboardingInterview({
  workspaceRef,
  detail,
  onboarding,
  pending,
  notice,
  selectedChoices,
  draft,
  onToggleChoice,
  onSend,
  onDraft,
  onUpload,
}: {
  workspaceRef: RefObject<HTMLElement | null>;
  detail: ManagerThreadDetail | null;
  onboarding: ManagerDataOnboarding;
  pending: boolean;
  notice: string | null;
  selectedChoices: string[];
  draft: string;
  onToggleChoice: (value: string) => void;
  onSend: (value: string) => void;
  onDraft: (value: string) => void;
  onUpload: (kind: "catalog" | "engagement") => void;
}) {
  const prompt = onboarding.current_prompt;
  const recentMessages = (detail?.messages ?? []).slice(-6);
  const promptVisibleInHistory = Boolean(
    prompt &&
      recentMessages.some((message) =>
        message.content.includes(prompt.question),
      ),
  );
  const progress = Math.round(
    ((prompt?.ordinal ?? 1) / (prompt?.total ?? 8)) * 100,
  );
  return (
    <main ref={workspaceRef} className={styles.onboardingShell} tabIndex={-1}>
      <header className={styles.onboardingTopbar}>
        <div className={styles.wordmark}>
          <span className={styles.brandGlyph}>GA</span>
          <strong>GoodAgent</strong>
        </div>
        <span data-workspace-focus tabIndex={-1}>Workspace setup</span>
      </header>
      <div className={styles.onboardingLayout}>
        <aside className={styles.onboardingProgress}>
          <p className={styles.kicker}>Guided setup</p>
          <h1>Set up your operator workspace</h1>
          <div className={styles.progressTrack}>
            <span style={{ width: `${progress}%` }} />
          </div>
          <p>
            {prompt?.ordinal ?? 1} of {prompt?.total ?? 8}
          </p>
          {[
            ["Your business", 1, 3],
            ["Your agents", 4, 4],
            ["Your data", 5, 6],
            ["How we work", 7, 8],
          ].map(([label, start, end]) => {
            const ordinal = prompt?.ordinal ?? 1;
            const done = ordinal > Number(end);
            const active = ordinal >= Number(start) && ordinal <= Number(end);
            return (
              <div
                key={String(label)}
                className={active ? styles.progressActive : ""}
              >
                <span>
                  {done ? <Check size={14} /> : String(start).padStart(2, "0")}
                </span>
                <strong>{label}</strong>
              </div>
            );
          })}
          <small>Draft-only and approval-required modes only.</small>
        </aside>
        <section className={styles.interviewPane}>
          <div className={styles.interviewMessages}>
            {recentMessages.map((message) => (
              <MessageRow key={message.id} message={message} compact />
            ))}
            {pending && <AgentWorking agentName="Onboarding" />}
          </div>
          {prompt && (
            <div className={styles.promptBlock}>
              {!promptVisibleInHistory && (
                <div className={styles.promptHeading}>
                  <p>{prompt.intro}</p>
                  <h2>{prompt.question}</h2>
                </div>
              )}
              <PromptControls
                prompt={prompt}
                onboarding={onboarding}
                selected={selectedChoices}
                draft={draft}
                pending={pending}
                onToggle={onToggleChoice}
                onDraft={onDraft}
                onSend={onSend}
                onUpload={onUpload}
              />
            </div>
          )}
          {notice && <div className={styles.notice}>{notice}</div>}
        </section>
      </div>
    </main>
  );
}

function PromptControls({
  prompt,
  onboarding,
  selected,
  draft,
  pending,
  onToggle,
  onDraft,
  onSend,
  onUpload,
}: {
  prompt: OnboardingPrompt;
  onboarding: ManagerDataOnboarding;
  selected: string[];
  draft: string;
  pending: boolean;
  onToggle: (value: string) => void;
  onDraft: (value: string) => void;
  onSend: (value: string) => void;
  onUpload: (kind: "catalog" | "engagement") => void;
}) {
  const choices = prompt.choices ?? [];
  if (prompt.input_kind === "review") {
    return (
      <div className={styles.reviewPanel}>
        <h2>Review your workspace</h2>
        <ReviewSummary
          onboarding={onboarding}
          onEdit={(field) => onSend(`edit:${field}`)}
        />
        <button
          className={styles.primaryButton}
          type="button"
          disabled={pending}
          onClick={() => onSend("confirm")}
        >
          <Check size={17} /> Open workspace
        </button>
      </div>
    );
  }
  if (prompt.input_kind === "dataset") {
    const catalog = prompt.field === "catalog_decision";
    return (
      <div className={styles.choiceGrid} aria-label={prompt.question}>
        {choices.map((choice) => (
          <button
            key={choice.value}
            type="button"
            disabled={pending}
            onClick={() => {
              if (choice.value === "csv_upload")
                onUpload(catalog ? "catalog" : "engagement");
              else onSend(choice.value);
            }}
          >
            {choice.value === "csv_upload" ? (
              <FileText size={18} />
            ) : (
              <Database size={18} />
            )}
            <span>
              <strong>{choice.label}</strong>
              {choice.description && <small>{choice.description}</small>}
            </span>
          </button>
        ))}
      </div>
    );
  }
  if (prompt.input_kind === "single_select") {
    return (
      <div className={styles.choiceGrid} aria-label={prompt.question}>
        {choices.map((choice) => (
          <button
            key={choice.value}
            type="button"
            disabled={pending}
            onClick={() => onSend(choice.value)}
          >
            <span>
              <strong>{choice.label}</strong>
              {choice.description && <small>{choice.description}</small>}
            </span>
          </button>
        ))}
      </div>
    );
  }
  if (prompt.input_kind === "multi_select") {
    return (
      <div className={styles.multiControls}>
        <div className={styles.choiceGrid} aria-label={prompt.question}>
          {choices.map((choice) => (
            <button
              key={choice.value}
              className={
                selected.includes(choice.value) ? styles.choiceSelected : ""
              }
              type="button"
              aria-pressed={selected.includes(choice.value)}
              disabled={pending}
              onClick={() => onToggle(choice.value)}
            >
              <span>
                <strong>{choice.label}</strong>
              </span>
              {selected.includes(choice.value) && <Check size={17} />}
            </button>
          ))}
        </div>
        <button
          className={styles.primaryButton}
          type="button"
          disabled={pending || selected.length === 0}
          onClick={() => onSend(selected.join(","))}
        >
          Continue <Send size={16} />
        </button>
      </div>
    );
  }
  return (
    <form
      className={styles.onboardingComposer}
      onSubmit={(event) => {
        event.preventDefault();
        onSend(draft);
      }}
    >
      <textarea
        aria-label="Your onboarding answer"
        value={draft}
        disabled={pending}
        autoFocus
        rows={3}
        placeholder="Type your answer..."
        onChange={(event) => onDraft(event.target.value)}
        onKeyDown={(event) => submitWithShortcut(event, () => onSend(draft))}
      />
      <button
        type="submit"
        aria-label="Send answer"
        title="Send"
        disabled={pending || !draft.trim()}
      >
        <Send size={18} />
      </button>
    </form>
  );
}

function ReviewSummary({
  onboarding,
  onEdit,
}: {
  onboarding: ManagerDataOnboarding;
  onEdit: (field: string) => void;
}) {
  const profile = onboarding.workspace_profile;
  const rows: [string, string, string | null | undefined][] = [
    ["workspace_name", "Workspace", profile?.workspace_name],
    ["business_summary", "Business", profile?.business_summary],
    ["manager_role", "Role", profile?.manager_role],
    ["primary_goal", "Primary goal", profile?.primary_goal],
    ["starter_agents", "Agents", profile?.starter_agents?.join(", ")],
    [
      "catalog_decision",
      "Catalog",
      onboarding.catalog?.profile?.filename ||
        (onboarding.catalog_decision === "defer"
          ? "No data yet"
          : onboarding.catalog?.source_kind),
    ],
    [
      "engagement_decision",
      "Engagement",
      onboarding.engagement?.profile?.filename ||
        onboarding.engagement_decision,
    ],
    ["cadence", "Refresh", onboarding.cadence],
    ["success_metrics", "Success", profile?.success_metrics?.join(", ")],
    ["guardrails", "Guardrails", profile?.guardrails?.join(", ")],
    ["operating_mode", "Operating mode", profile?.operating_mode],
    ["response_style", "Response style", profile?.response_style],
  ];
  return (
    <div className={styles.reviewRows}>
      {rows.map(([field, label, value]) => (
        <div key={field}>
          <span>{label}</span>
          <strong>{humanize(value || "Not set")}</strong>
          <button type="button" onClick={() => onEdit(field)}>
            Edit
          </button>
        </div>
      ))}
    </div>
  );
}

function HomeView({
  workspace,
  activeRuns,
  unreadCount,
  onOpenChannel,
  onOpenPanel,
}: {
  workspace: ManagerWorkspaceResponse;
  activeRuns: number;
  unreadCount: number;
  onOpenChannel: (id: string) => void;
  onOpenPanel: (
    panel: "commerce" | "data" | "memory" | "model" | "activity",
  ) => void;
}) {
  const storeNavigation = useStoreNavigation();
  const onboarding = workspace.onboarding;
  const catalogIndex: CatalogIndex = {
    ...EMPTY_CATALOG_INDEX,
    ...(workspace.catalog_index ?? {}),
  };
  const active = workspace.channels.filter(
    (channel) => channel.status !== "archived",
  );
  const catalogReady = catalogIndex.status === "ready";
  const catalogWorking = ["queued", "running"].includes(catalogIndex.status);
  return (
    <div className={styles.homeScroll}>
      <header className={styles.homeHeader}>
        <p className={styles.kicker}>Workspace home</p>
        <h1 data-workspace-focus tabIndex={-1}>Good to see you.</h1>
        <p>
          Pick up a commerce strategy conversation or review what needs
          attention.
        </p>
      </header>
      <CatalogIndexProgress index={catalogIndex} />
      {onboarding.limited_mode && !catalogReady && !catalogWorking && !catalogIndex.serving_catalog_id && (
        <div className={styles.limitedBanner}>
          <Info size={18} />
          <div>
            <strong>Limited exploration mode</strong>
            <span>
              Catalog indexing, model building, activation, and measurement are
              unavailable until catalog data is connected.
            </span>
          </div>
          <button type="button" onClick={() => storeNavigation
            ? storeNavigation.openProducts() : onOpenPanel("data")}>
            Connect data
          </button>
        </div>
      )}
      <section className={styles.homeStats} aria-label="Workspace summary">
        <button type="button" onClick={() => onOpenPanel("data")}>
          <span>Data readiness</span>
          <strong>
            {catalogReady
              ? `${catalogIndex.indexed_product_count} products ready`
              : catalogIndex.status === "queued"
                ? "Index queued"
                : catalogIndex.status === "running"
                  ? "Indexing catalog"
                  : catalogIndex.status === "failed"
                    ? "Index needs attention"
                    : "Needs catalog"}
          </strong>
          <small>
            {onboarding.engagement_decision === "provide"
              ? "Engagement planned"
              : "Engagement optional"}
          </small>
        </button>
        <button type="button" onClick={() => onOpenPanel("activity")}>
          <span>Active agent runs</span>
          <strong>{activeRuns}</strong>
          <small>
            {activeRuns ? "Agents working in parallel" : "No runs in progress"}
          </small>
        </button>
        <button type="button" onClick={() => onOpenPanel("model")}>
          <span>Discovery drafts</span>
          <strong>
            {active.filter((item) => item.working_memory?.objective).length}
          </strong>
          <small>Typed, reviewable objectives</small>
        </button>
        <button type="button" onClick={() => onOpenPanel("activity")}>
          <span>Unread activity</span>
          <strong>{unreadCount}</strong>
          <small>Stored in this browser</small>
        </button>
      </section>
      <section className={styles.homeSection}>
        <div className={styles.sectionTitle}>
          <div>
            <h2>Recent agents</h2>
            <p>
              Independent conversations keep strategy work moving in parallel.
            </p>
          </div>
        </div>
        <div className={styles.recentChannels}>
          {active.slice(0, 5).map((channel) => (
            <button
              key={channel.id}
              type="button"
              onClick={() => onOpenChannel(channel.id)}
            >
              <Hash size={17} />
              <div>
                <strong>{channel.slug}</strong>
                <span>{channel.description}</span>
              </div>
              <small>{formatRelative(channel.updated_at)}</small>
            </button>
          ))}
        </div>
      </section>
      <section className={styles.homeSection}>
        <div className={styles.sectionTitle}>
          <div>
            <h2>Operating boundaries</h2>
            <p>
              {humanize(
                onboarding.workspace_profile?.operating_mode || "draft_only",
              )}{" "}
              with validated objectives and simulated complex tools.
            </p>
          </div>
          <button
            type="button"
            onClick={() =>
              onOpenChannel(
                active.find((item) => item.channel_kind === "onboarding")?.id ||
                  active[0]?.id,
              )
            }
          >
            Review setup
          </button>
        </div>
      </section>
    </div>
  );
}

function MessageRow({
  message,
  onReply,
  replyLoading,
  compact = false,
}: {
  message: ManagerMessage;
  onReply?: () => void;
  replyLoading?: boolean;
  compact?: boolean;
}) {
  const optimistic = message.id.startsWith("pending-");
  const attached =
    message.content.startsWith("Attached ") &&
    message.content.includes(" CSV:");
  return (
    <article
      className={`${styles.messageRow} ${compact ? styles.compactMessage : ""}`}
    >
      <span
        className={
          message.role === "assistant"
            ? styles.agentAvatar
            : styles.managerAvatar
        }
      >
        {message.role === "assistant" ? <Bot size={18} /> : <User size={18} />}
      </span>
      <div className={styles.messageBody}>
        <div className={styles.messageMeta}>
          <strong>
            {message.role === "assistant" ? "GoodAgent" : "You"}
          </strong>
          {message.role === "assistant" && (
            <span className={styles.botBadge}>APP</span>
          )}
          <time>{formatTime(message.created_at)}</time>
          {optimistic && (
            <span className={styles.deliveryState} role="status">
              <Clock3 size={10} /> Sending
            </span>
          )}
        </div>
        {attached ? (
          <div className={styles.attachment}>
            <FileText size={19} />
            <div>
              <strong>{message.content.split(": ")[1]}</strong>
              <span>{message.content.split(":")[0]}</span>
            </div>
          </div>
        ) : (
          message.role === "assistant" ? <ChatMarkdown>{message.content}</ChatMarkdown> : <p>{message.content}</p>
        )}
        {message.steps && message.steps.length > 0 && (
          <details className={styles.activitySummary}>
            <summary>
              <Activity size={14} /> {message.steps.length} safe activity{" "}
              {message.steps.length === 1 ? "step" : "steps"}
            </summary>
            {message.steps.map((step, index) => (
              <div key={`${step.stage}-${index}`}>
                <span data-status={step.status}>{step.stage}</span>
                <div>
                  <strong>{step.title}</strong>
                  <p>{step.detail}</p>
                </div>
              </div>
            ))}
          </details>
        )}
        {message.reply_count ? (
          <button className={styles.replyCount} type="button" onClick={onReply}>
            <MessageSquare size={15} /> {message.reply_count}{" "}
            {message.reply_count === 1 ? "reply" : "replies"}
          </button>
        ) : null}
      </div>
      {onReply && (
        <div className={styles.messageActions}>
          <button
            type="button"
            title="Reply"
            aria-label={`Reply to ${message.role} message`}
            disabled={replyLoading}
            onClick={onReply}
          >
            <MessageSquare size={16} />
          </button>
        </div>
      )}
    </article>
  );
}

function AgentWorking({ agentName = "GoodAgent", run, events, onStop }: {
  agentName?: string; run?: ManagerRun; events?: ManagerRunEvent[]; onStop?: () => void;
}) {
  const [elapsed, setElapsed] = useState(0);
  useEffect(() => {
    const started = Date.now();
    const timer = window.setInterval(
      () => setElapsed(Math.floor((Date.now() - started) / 1000)),
      1000,
    );
    return () => window.clearInterval(timer);
  }, []);
  const phase = events?.at(-1)?.title ?? run?.phase ?? "Waiting for the agent";
  return (
    <div className={styles.agentWorking} role="status" aria-live="polite">
      <span className={styles.agentAvatar}>
        <Bot size={18} />
      </span>
      <div>
        <strong>{agentName.startsWith("Thread:") ? "Reply" : humanize(agentName)} agent is working</strong>
        <p>
          <i />
          <i />
          <i />
          <span>
            {phase} for {elapsed}s
          </span>
        </p>
        {events?.length ? <details><summary>Activity</summary>
          {events.map((event) => <p key={event.sequence}>{event.title}: {event.detail}</p>)}
        </details> : null}
      </div>
      {run && onStop && <button type="button" onClick={onStop} title="Stop agent" aria-label="Stop agent"><Square size={14} /></button>}
    </div>
  );
}

function Composer({
  threadId,
  channelSlug,
  draft,
  pending,
  notice,
  onChange,
  onSend,
  onUpload,
}: {
  threadId: string;
  channelSlug: string;
  draft: string;
  pending: boolean;
  notice?: string;
  onChange: (id: string, value: string) => void;
  onSend: () => void;
  onUpload: () => void;
}) {
  return (
    <div className={styles.composerWrap}>
      {notice && <div className={styles.composerNotice}>{notice}</div>}
      <div className={styles.composer}>
        <textarea
          aria-label="Message the commerce agent"
          value={draft}
          rows={2}
          disabled={pending}
          placeholder={`Message agent #${channelSlug}`}
          onChange={(event) => onChange(threadId, event.target.value)}
          onKeyDown={(event) => submitWithShortcut(event, onSend)}
        />
        <div className={styles.composerTools}>
          <button
            type="button"
            title="Attach catalog CSV"
            aria-label="Attach catalog CSV"
            disabled={pending}
            onClick={onUpload}
          >
            <Plus size={18} />
          </button>
          <span>Draft only</span>
          <button
            className={styles.sendButton}
            type="button"
            title="Send"
            aria-label="Send"
            disabled={pending || !draft.trim()}
            onClick={onSend}
          >
            <Send size={17} />
          </button>
        </div>
      </div>
    </div>
  );
}

function WorkspaceDrawer({
  drawer,
  detail,
  onboarding,
  catalogIndex,
  commerceOverview,
  runtimeStatus,
  loading,
  draft,
  pending,
  notice,
  composerRef,
  onClose,
  onPanel,
  onDraft,
  onSend,
  onUpload,
  onForget,
  run,
  events,
  onStop,
}: {
  drawer: Exclude<Drawer, null>;
  detail: ManagerThreadDetail | null;
  onboarding: ManagerDataOnboarding;
  catalogIndex: CatalogIndex;
  commerceOverview: CommerceOverview | null;
  runtimeStatus: ManagerRuntimeStatus | null;
  loading: boolean;
  draft: string;
  pending: boolean;
  notice?: string;
  composerRef: RefObject<HTMLTextAreaElement | null>;
  onClose: () => void;
  onPanel: (
    panel: "commerce" | "data" | "memory" | "model" | "activity",
  ) => void;
  onDraft: (id: string, value: string) => void;
  onSend: () => void;
  onUpload: (kind: "catalog" | "engagement", threadId?: string) => void;
  onForget: (memory: ManagerMemory) => void;
  run?: ManagerRun;
  events?: ManagerRunEvent[];
  onStop?: () => void;
}) {
  if (drawer.kind === "reply") {
    return (
      <aside className={styles.drawer}>
        <header className={styles.drawerHeader}>
          <div>
            <strong>Thread</strong>
            <span>
              {detail ? `${detail.messages.length} replies` : "Opening thread"}
            </span>
          </div>
          <button
            type="button"
            aria-label="Close thread"
            title="Close"
            onClick={onClose}
          >
            <X size={18} />
          </button>
        </header>
        <div id="reply-scroll" className={styles.replyScroll}>
          {loading && (
            <div className={styles.inlineLoading}>Opening thread...</div>
          )}
          {detail?.root_message && (
            <>
              <p className={styles.threadLabel}>Original message</p>
              <MessageRow message={detail.root_message} compact />
              <div className={styles.replyDivider}>
                <span>{detail.messages.length} replies</span>
              </div>
            </>
          )}
          {detail?.messages.map((message) => (
            <MessageRow key={message.id} message={message} compact />
          ))}
          {pending && <AgentWorking agentName={detail?.thread.title} run={run} events={events} onStop={onStop} />}
        </div>
        {detail && (
          <div className={styles.replyComposer}>
            {notice && <div className={styles.composerNotice}>{notice}</div>}
            <textarea
              ref={composerRef}
              aria-label="Reply to thread"
              value={draft}
              rows={3}
              disabled={pending}
              placeholder="Reply..."
              onChange={(event) =>
                onDraft(detail.thread.id, event.target.value)
              }
              onKeyDown={(event) => submitWithShortcut(event, onSend)}
            />
            <button
              type="button"
              aria-label="Send reply"
              title="Send reply"
              disabled={pending || !draft.trim()}
              onClick={onSend}
            >
              <Send size={17} />
            </button>
          </div>
        )}
      </aside>
    );
  }
  return (
    <aside className={styles.drawer}>
      <header className={styles.drawerHeader}>
        <div>
          <strong>Workspace details</strong>
          <span>Safe operational context</span>
        </div>
        <button
          type="button"
          aria-label="Close details"
          title="Close"
          onClick={onClose}
        >
          <X size={18} />
        </button>
      </header>
      <div className={styles.drawerTabs} role="tablist">
        {(["commerce", "data", "memory", "model", "activity"] as const).map((panel) => (
          <button
            key={panel}
            type="button"
            role="tab"
            aria-selected={drawer.panel === panel}
            onClick={() => onPanel(panel)}
          >
            {panel === "commerce" ? (
              <ShoppingCart size={16} />
            ) : panel === "data" ? (
              <Database size={16} />
            ) : panel === "memory" ? (
              <Brain size={16} />
            ) : panel === "model" ? (
              <Sparkles size={16} />
            ) : (
              <Activity size={16} />
            )}
            <span>{humanize(panel)}</span>
          </button>
        ))}
      </div>
      <div className={styles.drawerScroll} role="tabpanel">
        <PanelContent
          panel={drawer.panel}
          detail={detail}
          onboarding={onboarding}
          catalogIndex={catalogIndex}
          commerceOverview={commerceOverview}
          runtimeStatus={runtimeStatus}
          onUpload={onUpload}
          onForget={onForget}
        />
      </div>
    </aside>
  );
}

function PanelContent({
  panel,
  detail,
  onboarding,
  catalogIndex,
  commerceOverview,
  runtimeStatus,
  onUpload,
  onForget,
}: {
  panel: "commerce" | "data" | "memory" | "model" | "activity";
  detail: ManagerThreadDetail | null;
  onboarding: ManagerDataOnboarding;
  catalogIndex: CatalogIndex;
  commerceOverview: CommerceOverview | null;
  runtimeStatus: ManagerRuntimeStatus | null;
  onUpload: (kind: "catalog" | "engagement", threadId?: string) => void;
  onForget: (memory: ManagerMemory) => void;
}) {
  const storeNavigation = useStoreNavigation();
  if (panel === "commerce") return <CommercePanel overview={commerceOverview} />;
  if (panel === "data")
    return (
      <>
        {!storeNavigation && <ShopifyPanel />}
        <PanelHeading
          icon={<Database size={18} />}
          title="Data sources"
          detail={
            catalogIndex.status === "queued" ? "Catalog queued"
              : catalogIndex.status === "running" ? "Indexing catalog"
                : catalogIndex.status === "ready" || catalogIndex.serving_catalog_id ? "Catalog available"
                  : onboarding.limited_mode ? "Limited exploration" : "Onboarding profile"
          }
        />
        <CatalogIndexProgress index={catalogIndex} />
        {storeNavigation ? (
          <section className={styles.dataSource}>
            <div><h3>Catalog</h3><p>CSV import and product review</p></div>
            <button type="button" onClick={storeNavigation.openProducts}>
              <FileText size={15} /> Upload or review catalog
            </button>
          </section>
        ) : <DataSource
          label="Catalog"
          source={onboarding.catalog}
          required
          onUpload={() => onUpload("catalog", detail?.thread.id)}
        />}
        <DataSource
          label="Engagement"
          source={onboarding.engagement}
          onUpload={() => onUpload("engagement", detail?.thread.id)}
        />
        <div className={styles.datasetSamples}>
          <a href="/manager/catalog"><Database size={13} /> Browse published catalog</a>
          <span>Image-backed demo data</span>
          <a href="/abo-catalog.csv" download>
            <FileText size={13} /> Catalog CSV
          </a>
          <a href="/abo-engagement.csv" download>
            <FileText size={13} /> Engagement CSV
          </a>
        </div>
        <div className={styles.factRows}>
          <div>
            <span>Search index</span>
            <strong>{humanize(catalogIndex.status)}</strong>
          </div>
          {catalogIndex.product_count > 0 && (
            <div>
              <span>Products</span>
              <strong>
                {catalogIndex.indexed_product_count} /{" "}
                {catalogIndex.product_count}
              </strong>
            </div>
          )}
          <div>
            <span>Refresh</span>
            <strong>{humanize(onboarding.cadence || "not scheduled")}</strong>
          </div>
          <div>
            <span>Scheduled loads</span>
            <strong>Inactive</strong>
          </div>
          <div>
            <span>Ranking models</span>
            <strong>Review in Model panel</strong>
          </div>
        </div>
      </>
    );
  if (panel === "memory") {
    const memories = detail?.memories ?? [];
    return (
      <>
        <PanelHeading
          icon={<Brain size={18} />}
          title="Agent memory"
          detail="Three bounded layers"
        />
        <h3>Long-term preferences</h3>
        {memories
          .filter((item) => item.layer === "long_term")
          .map((memory) => (
            <div className={styles.memoryRow} key={memory.id}>
              <div>
                <strong>{memory.title}</strong>
                <p>{memory.content}</p>
              </div>
              <button
                type="button"
                aria-label={`Forget ${memory.title}`}
                onClick={() => onForget(memory)}
              >
                Forget
              </button>
            </div>
          ))}
        {memories.filter((item) => item.layer === "long_term").length === 0 && (
          <EmptyLine>No saved preferences</EmptyLine>
        )}
        <h3>Working memory</h3>
        <div className={styles.memoryRow}>
          <div>
            <strong>
              {detail?.thread.working_memory?.current_topic ||
                "No active topic"}
            </strong>
            <p>
              {detail?.thread.working_memory?.open_question ||
                "No open question"}
            </p>
          </div>
        </div>
        <h3>Periodic memory</h3>
        {memories
          .filter((item) => item.layer === "periodic")
          .map((memory) => (
            <div className={styles.memoryRow} key={memory.id}>
              <div>
                <strong>{memory.title}</strong>
                <p>{memory.content}</p>
              </div>
            </div>
          ))}
        {memories.filter((item) => item.layer === "periodic").length === 0 && (
          <EmptyLine>No checkpoints yet</EmptyLine>
        )}
      </>
    );
  }
  if (panel === "model") {
    const objective = detail?.thread.working_memory?.objective;
    const connection = runtimeStatus?.components.find((item) => item.key === "manager_agent");
    return (
      <>
        <PanelHeading
          icon={<Sparkles size={18} />}
          title="Conversation model"
          detail={
            detail?.capabilities.model_backed
              ? `${detail.capabilities.conversation_provider} / ${detail.capabilities.conversation_model}`
              : "Deterministic local agent"
          }
        />
        <div className={styles.factRows}>
          <div><span>Connection</span><strong>{connection?.state === "green" ? "Response verified" : connection?.state === "red" ? "Unavailable" : "Unchecked"}</strong></div>
          {connection?.observed_at && <div><span>Last observed</span><strong>{formatTime(connection.observed_at)}</strong></div>}
        </div>
        {connection && <p>{connection.detail}</p>}
        <RankingPanel />
        <h3>Discovery objective</h3>
        {objective ? (
          <div className={styles.factRows}>
            <div>
              <span>Surface</span>
              <strong>{humanize(objective.surface || "collecting")}</strong>
            </div>
            <div>
              <span>Retrieval</span>
              <strong>
                {humanize(objective.retrieval_mode || "collecting")}
              </strong>
            </div>
            <div>
              <span>Signals</span>
              <strong>
                {objective.ranking_signals?.join(" / ") || "Collecting"}
              </strong>
            </div>
            <div>
              <span>Status</span>
              <strong>{humanize(objective.status || "collecting")}</strong>
            </div>
          </div>
        ) : (
          <EmptyLine>No typed objective in this channel yet</EmptyLine>
        )}
        <div className={styles.boundaryNote}>
          <Info size={16} />
          <p>
            Local ranking builds require evaluation and explicit approval before serving.
            Live payment, fulfillment, and source inventory writes remain unavailable.
          </p>
        </div>
      </>
    );
  }
  const steps: AgentStep[] = (detail?.messages ?? [])
    .flatMap((message) => message.steps ?? [])
    .reverse();
  return (
    <>
      <ActivityPanel />
      <PanelHeading
        icon={<Activity size={18} />}
        title="Safe activity"
        detail="Operational summaries, not hidden reasoning"
      />
      {steps.map((step, index) => (
        <div className={styles.activityRow} key={`${step.stage}-${index}`}>
          <span data-status={step.status}>{step.stage}</span>
          <div>
            <strong>{step.title}</strong>
            <p>{step.detail}</p>
            {step.tool && <code>{step.tool}</code>}
          </div>
        </div>
      ))}
      {steps.length === 0 && <EmptyLine>No agent activity yet</EmptyLine>}
    </>
  );
}

function CommercePanel({ overview }: { overview: CommerceOverview | null }) {
  if (!overview)
    return (
      <>
        <PanelHeading
          icon={<ShoppingCart size={18} />}
          title="Commerce operations"
          detail="Loading current state"
        />
        <EmptyLine>Reading inventory, reservations, and orders...</EmptyLine>
      </>
    );
  const lowStock = (overview.inventory ?? []).filter(
    (item) => item.state === "low" || item.state === "out",
  ).length;
  const activeReservations = (overview.reservations ?? []).filter(
    (item) => item.status === "active",
  );
  return (
    <>
      <PanelHeading
        icon={<ShoppingCart size={18} />}
        title="Commerce operations"
        detail="Local checkout and observed inventory"
      />
      <div className={styles.commerceSummary}>
        <div><span>Sellable SKUs</span><strong>{overview.inventory?.length ?? 0}</strong></div>
        <div><span>Low or out</span><strong>{lowStock}</strong></div>
        <div><span>Orders</span><strong>{overview.orders?.length ?? 0}</strong></div>
      </div>
      <div className={styles.boundaryNote}>
        <Info size={16} />
        <p>
          Inventory is observed and reserved locally only. Payments are deterministic
          tests; no real money, fulfillment, or stock mutation occurs.
        </p>
      </div>
      <h3>Inventory</h3>
      <div className={styles.inventoryRows}>
        {(overview.inventory ?? []).slice(0, 16).map((item) => (
          <div key={`${item.product_id}-${item.variant_id}`}>
            <i data-state={item.state} />
            <span><strong>{item.title}</strong><small>{item.sku || item.variant_id}</small></span>
            <b>{item.sellable_quantity ?? "?"}</b>
          </div>
        ))}
        {(overview.inventory?.length ?? 0) === 0 && (
          <EmptyLine>No active catalog inventory</EmptyLine>
        )}
      </div>
      <h3>Active reservations</h3>
      <div className={styles.commerceRows}>
        {activeReservations.slice(0, 8).map((item) => (
          <div key={item.id}>
            <span><strong>{item.product_id}</strong><small>{item.quantity} units held</small></span>
            <b>{formatShortTime(item.expires_at)}</b>
          </div>
        ))}
        {activeReservations.length === 0 && <EmptyLine>No active holds</EmptyLine>}
      </div>
      <h3>Recent orders</h3>
      <div className={styles.commerceRows}>
        {(overview.orders ?? []).slice(0, 8).map((order) => (
          <div key={order.id}>
            <span><strong>{order.order_number}</strong><small>{humanize(order.status)}</small></span>
            <b>{formatCommerceMoney(order.total)}</b>
          </div>
        ))}
        {(overview.orders?.length ?? 0) === 0 && <EmptyLine>No orders yet</EmptyLine>}
      </div>
      <h3>Payment attempts</h3>
      <div className={styles.commerceRows}>
        {(overview.payments ?? []).slice(0, 8).map((payment) => (
          <div key={payment.id}>
            <span><strong>{humanize(payment.status)}</strong><small>{payment.provider}</small></span>
            <b>{formatCommerceMoney(payment.total)}</b>
          </div>
        ))}
        {(overview.payments?.length ?? 0) === 0 && (
          <EmptyLine>No payment attempts yet</EmptyLine>
        )}
      </div>
    </>
  );
}

function DataSource({
  label,
  source,
  required = false,
  onUpload,
}: {
  label: string;
  source: ManagerDataOnboarding["catalog"];
  required?: boolean;
  onUpload: () => void;
}) {
  return (
    <section className={styles.dataSource}>
      <div>
        <h3>
          {label}
          {required && <span>Required</span>}
        </h3>
        {source?.profile ? (
          <>
            <strong>{source.profile.filename}</strong>
            <p>
              {source.profile.row_count} rows, {source.profile.columns.length}{" "}
              columns
            </p>
          </>
        ) : source ? (
          <>
            <strong>{humanize(source.source_kind)}</strong>
            <p>Connection details drafted, not connected.</p>
          </>
        ) : (
          <p>No source provided.</p>
        )}
      </div>
      <button type="button" onClick={onUpload}>
        <FileText size={15} /> {source ? "Replace CSV" : "Attach CSV"}
      </button>
    </section>
  );
}

function PanelHeading({
  icon,
  title,
  detail,
}: {
  icon: ReactNode;
  title: string;
  detail: string;
}) {
  return (
    <div className={styles.panelHeading}>
      <span>{icon}</span>
      <div>
        <h2>{title}</h2>
        <p>{detail}</p>
      </div>
    </div>
  );
}

function EmptyLine({ children }: { children: ReactNode }) {
  return <p className={styles.emptyLine}>{children}</p>;
}

function CatalogCurrencyDialog({ onClose }: { onClose: (value: "USD" | "EUR" | "GBP" | "CAD" | "AUD" | null) => void }) {
  const [currency, setCurrency] = useState<"USD" | "EUR" | "GBP" | "CAD" | "AUD" | "">("");
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => { dialog.current?.showModal(); }, []);
  return <dialog ref={dialog} className={styles.channelDialog} aria-labelledby="catalog-currency-title" onCancel={(event) => { event.preventDefault(); onClose(null); }}>
    <form onSubmit={(event) => { event.preventDefault(); if (currency) onClose(currency); }}>
      <header><h2 id="catalog-currency-title">Shopify catalog currency</h2><button type="button" aria-label="Cancel currency selection" onClick={() => onClose(null)}><X size={18} /></button></header>
      <p>Which currency does this export use? Prices will be imported in that currency.</p>
      <label>Currency<select value={currency} onChange={(event) => setCurrency(event.target.value as typeof currency)} required><option value="">Select currency</option>{["USD", "EUR", "GBP", "CAD", "AUD"].map((value) => <option key={value}>{value}</option>)}</select></label>
      <button type="submit" disabled={!currency} className={styles.primaryButton}>Import catalog</button>
    </form>
  </dialog>;
}

function ChannelDialog({
  modal,
  pending,
  error,
  attempt,
  onClose,
  onSave,
}: {
  modal: Exclude<ChannelModal, null>;
  pending: boolean;
  error: string | null;
  attempt: ChannelAttempt | null;
  onClose: () => void;
  onSave: (name: string, purpose: string) => void;
}) {
  const [draftName, setName] = useState(modal.channel?.title ?? "");
  const [draftPurpose, setPurpose] = useState(modal.channel?.description ?? "");
  const name = attempt?.body.title ?? draftName;
  const purpose = attempt ? attempt.body.description ?? "" : draftPurpose;
  const saved = attempt?.saved ?? false;
  function submit(event: FormEvent) {
    event.preventDefault();
    if (!pending && name.trim()) onSave(name.trim(), purpose.trim());
  }
  return (
    <WorkspaceDialog labelledBy="channel-dialog-title" pending={pending} onDismiss={onClose}>
      <form
        className={styles.channelDialog}
        onSubmit={submit}
      >
        <header>
          <div>
            <p className={styles.kicker}>
              {modal.mode === "create" ? "New specialist" : "Agent settings"}
            </p>
            <h2 id="channel-dialog-title" data-dialog-heading tabIndex={-1}>
              {modal.mode === "create" ? "Create an agent" : "Rename agent"}
            </h2>
          </div>
          <button type="button" data-dialog-initial={!!attempt || undefined} aria-label="Close dialog" disabled={pending} onClick={onClose}>
            <X size={18} />
          </button>
        </header>
        <label>
          Agent name
          <input
            data-dialog-initial={!attempt || undefined}
            disabled={pending || !!attempt}
            value={name}
            maxLength={120}
            placeholder="seasonal-search"
            onChange={(event) => { if (!attempt) setName(event.target.value); }}
          />
        </label>
        <label>
          Purpose
          <textarea
            disabled={pending || !!attempt}
            value={purpose}
            maxLength={240}
            rows={3}
            placeholder="What should this agent focus on?"
            onChange={(event) => { if (!attempt) setPurpose(event.target.value); }}
          />
        </label>
        {error && <p role="alert" className={styles.notice}>{error}</p>}
        <footer>
          <button type="button" disabled={pending} onClick={onClose}>
            Cancel
          </button>
          <button
            className={styles.primaryButton}
            type="submit"
            disabled={pending || !name.trim()}
          >
            {pending ? (saved ? "Refreshing..." : "Saving...") : saved ? "Refresh workspace" : attempt ? "Retry save" : modal.mode === "create" ? "Create agent" : "Save changes"}
          </button>
        </footer>
      </form>
    </WorkspaceDialog>
  );
}

function ClearHistoryDialog({
  agent,
  pending,
  onClose,
  onConfirm,
}: {
  agent: ManagerThread;
  pending: boolean;
  onClose: () => void;
  onConfirm: () => void;
}) {
  return (
    <WorkspaceDialog labelledBy="clear-history-title" pending={pending} onDismiss={onClose}>
      <section
        className={`${styles.channelDialog} ${styles.storeDialog}`}
      >
        <header>
          <div>
            <p className={styles.kicker}>Fresh context</p>
            <h2 id="clear-history-title" data-dialog-heading tabIndex={-1}>Clear {agent.title} history?</h2>
          </div>
          <button
            type="button"
            aria-label="Close dialog"
            data-dialog-initial
            disabled={pending}
            onClick={onClose}
          >
            <X size={18} />
          </button>
        </header>
        <MerchantStoreIdentity />
        <p className={styles.dialogCopy}>
          Messages, replies, working memory, and periodic summaries in this
          agent will be removed. Store-level preferences and onboarding answers
          will be kept.
        </p>
        <footer>
          <button type="button" disabled={pending} onClick={onClose}>
            Cancel
          </button>
          <button
            className={styles.dangerButton}
            type="button"
            disabled={pending}
            onClick={onConfirm}
          >
            <Trash2 size={15} /> {pending ? "Clearing..." : "Clear history"}
          </button>
        </footer>
      </section>
    </WorkspaceDialog>
  );
}

function WorkspaceSettingsDialog({
  onClose,
  onReset,
}: {
  onClose: () => void;
  onReset: () => void;
}) {
  const authenticated = useContext(MerchantTransportContext) !== null;
  return (
    <WorkspaceDialog labelledBy="workspace-settings-title" onDismiss={onClose}>
      <section
        className={`${styles.channelDialog} ${styles.storeDialog}`}
      >
        <header>
          <div>
            <p className={styles.kicker}>{authenticated ? "Store workspace" : "Local workspace"}</p>
            <h2 id="workspace-settings-title" data-dialog-heading tabIndex={-1}>Workspace settings</h2>
          </div>
          <button type="button" data-dialog-initial aria-label="Close settings" onClick={onClose}>
            <X size={18} />
          </button>
        </header>
        <MerchantStoreIdentity />
        <div className={styles.settingsSummary}>
          <span>Access</span>
          <strong>{authenticated ? "Signed-in store owner" : "Store operator"}</strong>
          <p>{authenticated
            ? "This workspace uses your signed-in store account."
            : "This local demo does not use a separate manager login."}</p>
        </div>
        <div className={styles.settingsSummary}>
          <span>Cleanup</span>
          <strong>Manager workspace</strong>
          <p>
            Remove manager conversations, memory, and onboarding while retaining
            the active catalog, search index, and shopper data.
          </p>
        </div>
        <footer>
          <button type="button" onClick={onClose}>
            Close
          </button>
          <button
            className={styles.dangerButton}
            type="button"
            onClick={onReset}
          >
            <Trash2 size={15} /> Reset and clean up
          </button>
        </footer>
      </section>
    </WorkspaceDialog>
  );
}

function ResetWorkspaceDialog({
  pending,
  phase,
  error,
  onClose,
  onConfirm,
}: {
  pending: boolean;
  phase: "idle" | "unknown" | "confirmed";
  error: string | null;
  onClose: () => void;
  onConfirm: () => void;
}) {
  const authenticated = useContext(MerchantTransportContext) !== null;
  return (
    <WorkspaceDialog labelledBy="reset-workspace-title" pending={pending} onDismiss={onClose}>
      <section
        className={`${styles.channelDialog} ${styles.storeDialog}`}
      >
        <header>
          <div>
            <p className={styles.kicker}>{authenticated ? "Store workspace cleanup" : "Local demo cleanup"}</p>
            <h2 id="reset-workspace-title" data-dialog-heading tabIndex={-1}>
              {phase === "confirmed" ? "Workspace reset" : "Reset manager workspace?"}
            </h2>
          </div>
          <button
            type="button"
            aria-label="Close dialog"
            data-dialog-initial
            disabled={pending}
            onClick={onClose}
          >
            <X size={18} />
          </button>
        </header>
        <MerchantStoreIdentity />
        <p className={styles.dialogCopy}>
          {phase === "confirmed" ? "This removed" : "This removes"} manager channels, messages, working memory, saved
          preferences, and onboarding answers. The active catalog, search index,
          shopper accounts, and shopper conversations are retained.
        </p>
        {error && <p role="alert" className={styles.notice}>{error}</p>}
        <footer>
          <button type="button" disabled={pending} onClick={onClose}>
            {phase === "confirmed" ? "Close" : "Cancel"}
          </button>
          <button
            className={phase === "confirmed" ? styles.primaryButton : styles.dangerButton}
            type="button"
            disabled={pending}
            onClick={onConfirm}
          >
            {phase === "confirmed" ? <RefreshCw size={15} /> : <Trash2 size={15} />} {pending
              ? (phase === "confirmed" ? "Refreshing..." : "Resetting...")
              : phase === "confirmed" ? "Refresh workspace" : phase === "unknown" ? "Retry reset" : "Reset workspace"}
          </button>
        </footer>
      </section>
    </WorkspaceDialog>
  );
}

function WorkspaceLoading() {
  return (
    <main className={styles.loadingShell}>
      <span className={styles.brandGlyph}>GA</span>
      <div>
        <strong>Opening operator workspace</strong>
        <p>Loading agents and memory...</p>
      </div>
    </main>
  );
}

function setMembership(current: Set<string>, id: string, value: boolean) {
  const next = new Set(current);
  if (value) next.add(id);
  else next.delete(id);
  return next;
}

function submitWithShortcut(
  event: KeyboardEvent<HTMLTextAreaElement>,
  submit: () => void,
) {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    submit();
  }
}

function humanize(value: string) {
  return value
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function formatTime(value: string) {
  return new Intl.DateTimeFormat("en", {
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));
}

function formatShortTime(value: string) {
  return new Intl.DateTimeFormat("en", {
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));
}

function formatCommerceMoney(value: { amount_minor: number; currency: string }) {
  return `${value.currency} ${(value.amount_minor / 100).toFixed(2)}`;
}

function formatRelative(value: string) {
  const minutes = Math.max(
    0,
    Math.round((Date.now() - new Date(value).getTime()) / 60000),
  );
  if (minutes < 1) return "now";
  if (minutes < 60) return `${minutes}m`;
  if (minutes < 1440) return `${Math.floor(minutes / 60)}h`;
  return `${Math.floor(minutes / 1440)}d`;
}
