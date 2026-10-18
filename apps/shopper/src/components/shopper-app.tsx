"use client";

import { ChatMarkdown } from "./chat-markdown";

import type {
  Cart,
  CheckoutConfirmation,
  CheckoutPreview,
  CheckoutRecovery,
  ShopperAccount,
  ShopperAuthResponse,
  ShopperConversation,
  ShopperConversationDetail,
  ShopperDiscoveryResponse,
  ShopperGuestResponse,
  ShopperMemory,
  ShopperMessage,
  ShopperProductCard,
  ShopperRecovery,
  Storefront,
  CatalogBrowseProduct,
} from "@open-commerce/sdk-typescript";
import {
  AlertTriangle,
  ArrowUp,
  Bot,
  Brain,
  ChevronDown,
  CheckCircle2,
  CreditCard,
  LogOut,
  Menu,
  MessageSquarePlus,
  Minus,
  Package,
  Plus,
  RefreshCw,
  ReceiptText,
  Search,
  ShoppingBag,
  ShoppingCart,
  Sparkles,
  Trash2,
  User,
  X,
} from "lucide-react";
import Image from "next/image";
import { CatalogArtwork } from "./catalog-artwork";
import { ShopperWelcome } from "./shopper-welcome";
import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { createShopperClient, shopperErrorMessage } from "@/lib/api";
import { CatalogBrowser } from "./catalog-browser";
import { ActivityPanel } from "./activity-panel";
import { Activity } from "lucide-react";
import { AccountControls } from "./account-controls";
import { OrderHistory } from "./order-history";
import { ShopperTransportContext, useShopperTransport } from "@/lib/shopper-transport";
import { loadAttempt, saveAttempt, type CheckoutAttempt } from "@/lib/checkout-attempt";
import { loadMemoryChange, saveMemoryChange, type MemoryChange } from "@/lib/memory-change";
import { isSessionExpired, ShopperSessionErrors } from "@/lib/session-errors";
import { SessionRecovery, SessionRecoveryError } from "./session-recovery";

type ShopperClient = Pick<
  ReturnType<typeof createShopperClient>,
  | "chatWithShopper"
  | "addShopperCartItem"
  | "confirmShopperCheckout"
  | "deleteShopperCartItem"
  | "deleteShopperMemory"
  | "loginShopper"
  | "logoutShopper"
  | "registerShopper"
  | "previewShopperCheckout"
  | "shopperAccount"
  | "shopperCart"
  | "shopperCheckout"
  | "shopperOrders"
  | "shopperCatalog"
  | "shopperConversation"
  | "shopperConversations"
  | "shopperDiscovery"
  | "shopperMemories"
  | "updateShopperCartItem"
>;

type CartState = Cart & {
  lines: NonNullable<Cart["lines"]>;
  subtotal: NonNullable<Cart["subtotal"]>;
  total: NonNullable<Cart["total"]>;
  item_count: number;
  version: number;
};
type WorkspaceSection = "history" | "memory" | "suggestions" | "cart";
const workspaceSections: WorkspaceSection[] = ["history", "memory", "suggestions", "cart"];

type ChatAttempt = {
  key: string;
  accountId: string;
  navigation: number;
  content: string;
  conversationId: string | null;
  message: ShopperMessage;
};
type SuspendedSession = {
  accountId: string;
  store: string;
  guest: boolean;
  draft: string;
  failedChat: ChatAttempt | null;
  resumeAttempt: boolean;
  memoryRemovals: MemoryRemoval[];
};

type MemoryRemoval = {
  memoryId: string;
  accountId: string;
  store: string;
  key: string;
  state: "pending" | "uncertain";
};

type RecoveredAccount = {
  accountId: string;
  store: string;
  epoch: number;
  code: string | null;
  verified: boolean;
};

export function ShopperApp({
  client: suppliedClient,
  initialView = "chat",
  store,
}: {
  client?: ShopperClient;
  initialView?: "chat" | "catalog";
  store?: Storefront;
}) {
  const baseTransport = useShopperTransport(store?.slug);
  const baseClient = suppliedClient ?? baseTransport.client;
  const [checked, setChecked] = useState(false);
  const [authError, setAuthError] = useState(false);
  const [authAttempt, setAuthAttempt] = useState(0);
  const [loggingOut, setLoggingOut] = useState(false);
  const [logoutFailed, setLogoutFailed] = useState(false);
  const [workspaceErrors, setWorkspaceErrors] = useState<WorkspaceSection[]>([]);
  const [workspaceLoading, setWorkspaceLoading] = useState(false);
  const [cartLoaded, setCartLoaded] = useState(false);
  const [memoryLoaded, setMemoryLoaded] = useState(false);
  const [memoryUpdating, setMemoryUpdating] = useState(false);
  const [memoryUncertain, setMemoryUncertain] = useState(false);
  const [accountUpdating, setAccountUpdating] = useState(false);
  const [account, setAccount] = useState<ShopperAccount | null>(null);
  const transport = useMemo(
    () => account ? baseTransport.forAccount(account.id) : baseTransport,
    [baseTransport, account?.id],
  );
  const client = suppliedClient ?? transport.client;
  const shopperRequest = transport.request;
  const [conversations, setConversations] = useState<ShopperConversation[]>([]);
  const [detail, setDetail] = useState<ShopperConversationDetail | null>(null);
  const [memories, setMemories] = useState<ShopperMemory[]>([]);
  const [memoryRemovals, setMemoryRemovals] = useState<MemoryRemoval[]>([]);
  const removalReceipts = useRef(new Map<string, MemoryRemoval>());
  const [discovery, setDiscovery] = useState<ShopperDiscoveryResponse | null>(
    null,
  );
  const [cart, setCart] = useState<CartState>(emptyCart());
  const [checkout, setCheckout] = useState<CheckoutPreview | null>(null);
  const [confirmation, setConfirmation] = useState<CheckoutConfirmation | null>(
    null,
  );
  const [recovery, setRecovery] = useState<CheckoutRecovery | null>(null);
  const [uncertain, setUncertain] = useState(false);
  const attempt = useRef<CheckoutAttempt | null>(null);
  const recoveryRequest = useRef(0);
  const discoveredCheckout = useRef<string | undefined>(undefined);
  const [checkingCheckout, setCheckingCheckout] = useState(false);
  const recoveryScope = account ? `${store?.slug ?? "legacy"}:${account.id}` : null;
  const [optimisticMessage, setOptimisticMessage] =
    useState<ShopperMessage | null>(null);
  const [draft, setDraft] = useState("");
  const draftValue = useRef("");
  const draftRevision = useRef(0);
  const [failedChat, setFailedChat] = useState<ChatAttempt | null>(null);
  const failedAttempt = useRef<ChatAttempt | null>(null);
  const activeChat = useRef<ChatAttempt | null>(null);
  const suspendedSession = useRef<SuspendedSession | null>(null);
  const [sessionExpired, setSessionExpired] = useState(false);
  const [recoveryRequested, setRecoveryRequested] = useState(false);
  const [recoveredAccount, setRecoveredAccount] = useState<RecoveredAccount | null>(null);
  const recoveredReceipt = useRef<RecoveredAccount | null>(null);
  const [pending, setPending] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [drawer, setDrawer] = useState<
    "memory" | "cart" | "activity" | "account" | "product" | "orders" | null
  >(null);
  const [productDetail, setProductDetail] =
    useState<CatalogBrowseProduct | null>(null);
  const [selectedVariant, setSelectedVariant] = useState("");
  const [commercePending, setCommercePending] = useState<string | null>(null);
  const [mobileNav, setMobileNav] = useState(false);
  const [view, setView] = useState(initialView);
  const scrollRef = useRef<HTMLDivElement>(null);
  const sessionEpoch = useRef(0);
  const accountId = useRef<string | null>(null);
  const accountSnapshot = useRef<ShopperAccount | null>(null);
  const accountStore = useRef<string | null>(null);
  const conversationRequest = useRef(0);
  const memoryRequest = useRef(0);
  const memoryMutation = useRef(false);
  const memoryChange = useRef<MemoryChange | null>(null);
  const accountAction = useRef(false);
  const currentSession = sessionEpoch.current;
  const storeScope = store?.slug ?? "legacy";
  const renderedStore = useRef(storeScope);
  renderedStore.current = storeScope;
  const sessionError = useMemo(
    () => (error: unknown) => expireSession(error, currentSession),
    [currentSession, storeScope],
  );

  function changeDraft(value: string) {
    draftValue.current = value;
    draftRevision.current += 1;
    setDraft(value);
  }

  function keepFailedAttempt(value: ChatAttempt | null) {
    failedAttempt.current = value;
    setFailedChat(value);
  }

  function expireSession(error: unknown, epoch: number): boolean {
    return isSessionExpired(error) && suspendAccount(epoch);
  }

  function suspendAccount(epoch: number, requested = false): boolean {
    if (epoch !== sessionEpoch.current || !accountSnapshot.current) return false;
    const attempted = activeChat.current ?? failedAttempt.current;
    const saved: SuspendedSession = {
      accountId: accountSnapshot.current.id,
      store: accountStore.current ?? storeScope,
      guest: Boolean(accountSnapshot.current.is_guest),
      draft: draftValue.current,
      failedChat: attempted,
      resumeAttempt: attempted?.navigation === conversationRequest.current,
      memoryRemovals: [...removalReceipts.current.values()].map(removal => ({ ...removal, state: "uncertain" })),
    };
    clearAccountView(true);
    suspendedSession.current = saved;
    accountId.current = null;
    accountSnapshot.current = null;
    accountStore.current = null;
    setAccount(null);
    setSessionExpired(true);
    setRecoveryRequested(requested);
    return true;
  }

  useEffect(() => {
    let active = true;
    const previousStore = accountStore.current ?? suspendedSession.current?.store;
    if (previousStore && previousStore !== storeScope) {
      clearAccountView(true);
      accountId.current = null;
      accountSnapshot.current = null;
      accountStore.current = null;
      setAccount(null);
    }
    const epoch = sessionEpoch.current;
    setChecked(false);
    setAuthError(false);
    void baseClient
      .shopperAccount()
      .then(async (result) => {
        if (!active || epoch !== sessionEpoch.current) return;
        acceptAccount(result.account);
        setChecked(true);
        await loadWorkspace(workspaceSections, clientForAccount(result.account.id));
      })
      .catch((cause) => {
        if (!active || epoch !== sessionEpoch.current) return;
        if (!expireSession(cause, epoch) && !isSessionExpired(cause)) setAuthError(true);
      })
      .finally(() => active && setChecked(true));
    return () => {
      active = false;
      sessionEpoch.current += 1;
    };
  }, [baseClient, authAttempt, storeScope]);

  useEffect(() => {
    if (!detail) return;
    window.requestAnimationFrame(() => {
      if (scrollRef.current)
        scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    });
  }, [detail, optimisticMessage, pending, failedChat]);

  useEffect(() => {
    if (!recoveryScope) return;
    attempt.current = loadAttempt(recoveryScope);
    void checkCheckout(true);
    return () => { recoveryRequest.current += 1; };
  }, [recoveryScope, client]);

  function clearAttempt() {
    if (recoveryScope) saveAttempt(recoveryScope, null);
    attempt.current = null;
    discoveredCheckout.current = undefined;
  }

  async function checkCheckout(initial = false) {
    const epoch = sessionEpoch.current;
    const request = ++recoveryRequest.current;
    const saved = attempt.current;
    setCheckingCheckout(true);
    try {
      const result = await client.shopperCheckout(saved?.checkoutId ?? discoveredCheckout.current);
      if (epoch !== sessionEpoch.current || request !== recoveryRequest.current) return;
      if (result?.status === "processing") discoveredCheckout.current = result.checkout_id;
      setRecovery(result);
      setUncertain(result?.status === "processing" || Boolean(saved && result?.status === "requires_confirmation"));
      if (result?.preview) setCheckout(result.preview);
      else if (result) setCheckout(null);
      if (result?.confirmation) {
        if (!initial || saved) setConfirmation(result.confirmation);
        await loadWorkspace(["cart"]);
      }
      if (epoch !== sessionEpoch.current || request !== recoveryRequest.current) return;
      if (saved || result?.status === "processing") setDrawer("cart");
      if (!result || ["succeeded", "cancelled", "expired", "requires_payment_method"].includes(result.status))
        clearAttempt();
      if (result?.status === "expired" || result?.status === "cancelled") setNotice(result.message);
    } catch (error) {
      if (epoch !== sessionEpoch.current || request !== recoveryRequest.current) return;
      if (expireSession(error, epoch)) return;
      setUncertain(true);
      setNotice("Checkout status could not be verified. Check again before another payment.");
    } finally {
      if (epoch === sessionEpoch.current && request === recoveryRequest.current) setCheckingCheckout(false);
    }
  }

  useEffect(() => {
    if (!account) return;
    let active = true;
    const refreshDiscovery = () => {
      const epoch = sessionEpoch.current;
      void client
        .shopperDiscovery()
        .then((result) => active && epoch === sessionEpoch.current && setDiscovery(result))
        .catch((error) => { if (active) expireSession(error, epoch); });
    };
    const intervalMs = discovery?.catalog_status === "ready" ? 30000 : 5000;
    const timer = window.setInterval(refreshDiscovery, intervalMs);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, [account, client, discovery?.catalog_status]);

  function clientForAccount(id: string): ShopperClient {
    return suppliedClient ?? baseTransport.forAccount(id).client;
  }

  async function loadWorkspace(sections = workspaceSections, workspaceClient = client) {
    const epoch = sessionEpoch.current;
    setWorkspaceLoading(true);
    // Commit each independent response without waiting for slower sections.
    await Promise.all(sections.map(async (section) => {
      try {
        switch (section) {
          case "history": {
            const result = await workspaceClient.shopperConversations();
            if (epoch === sessionEpoch.current) setConversations(result.items);
            break;
          }
          case "memory": {
            const request = ++memoryRequest.current;
            const result = await workspaceClient.shopperMemories();
            if (epoch === sessionEpoch.current && request === memoryRequest.current) {
              setMemories(result.items); setMemoryLoaded(true);
            }
            break;
          }
          case "suggestions": {
            const result = await workspaceClient.shopperDiscovery();
            if (epoch === sessionEpoch.current) setDiscovery(result);
            break;
          }
          case "cart": {
            const result = await workspaceClient.shopperCart();
            if (epoch === sessionEpoch.current) { setCart(normalizeCart(result)); setCartLoaded(true); }
            break;
          }
        }
        if (epoch === sessionEpoch.current)
          setWorkspaceErrors((items) => items.filter((item) => item !== section));
      } catch (error) {
        if (expireSession(error, epoch)) return;
        if (epoch === sessionEpoch.current)
          setWorkspaceErrors((items) => items.includes(section) ? items : [...items, section]);
      }
    }));
    if (epoch === sessionEpoch.current) setWorkspaceLoading(false);
  }

  async function authenticated(result: ShopperAuthResponse) {
    const saved = suspendedSession.current;
    acceptAccount(result.account);
    suspendedSession.current = null;
    setSessionExpired(false);
    setRecoveryRequested(false);
    if (saved?.accountId === result.account.id && saved.store === storeScope) {
      changeDraft(saved.draft);
      keepFailedAttempt(saved.failedChat && saved.resumeAttempt
        ? { ...saved.failedChat, navigation: conversationRequest.current }
        : saved.failedChat);
      for (const removal of saved.memoryRemovals) {
        if (removal.accountId === result.account.id && removal.store === storeScope)
          removalReceipts.current.set(removal.memoryId, removal);
      }
      setMemoryRemovals([...removalReceipts.current.values()]);
    }
    setNotice(null);
    await loadWorkspace(workspaceSections, clientForAccount(result.account.id));
  }

  async function recoverSession(work: () => Promise<ShopperAuthResponse>) {
    const epoch = sessionEpoch.current;
    const result = await work();
    if (epoch !== sessionEpoch.current || !suspendedSession.current) return;
    await authenticated(result);
  }

  function keepRecoveredAccount(value: RecoveredAccount | null) {
    recoveredReceipt.current = value;
    setRecoveredAccount(value);
  }

  function recoveryIsCurrent(epoch: number, scope: string) {
    return epoch === sessionEpoch.current && scope === renderedStore.current && suspendedSession.current?.store === scope;
  }

  async function verifyRecoveredAccount(receipt: RecoveredAccount) {
    const current = () => recoveryIsCurrent(receipt.epoch, receipt.store) && recoveredReceipt.current === receipt;
    if (!current()) throw new Error("Recovery no longer active");
    try {
      const verified = await clientForAccount(receipt.accountId).shopperAccount();
      if (!current()) throw new Error("Recovery no longer active");
      if (verified.account.id !== receipt.accountId || verified.account.is_guest)
        throw new SessionRecoveryError("identity_changed");
      if (!receipt.verified) keepRecoveredAccount({ ...receipt, verified: true });
      return verified;
    } catch (error) {
      if (current() && (isSessionExpired(error) || error instanceof SessionRecoveryError)) {
        keepRecoveredAccount(null);
        throw new SessionRecoveryError("identity_changed");
      }
      throw error;
    }
  }

  async function recoverAccount(credentials: ShopperRecovery) {
    const epoch = sessionEpoch.current;
    if (!recoveryIsCurrent(epoch, storeScope) || recoveredReceipt.current) return;
    const result = await baseTransport.forAccount(null).request<ShopperAuthResponse>("/v1/shopper/auth/recover", "POST", credentials);
    if (!recoveryIsCurrent(epoch, storeScope)) return;
    if (!result.account?.id || result.account.is_guest) throw new SessionRecoveryError("identity_changed");
    // Keep the rotated code before the read: a transient verification failure must not lose it or repeat recovery.
    const receipt: RecoveredAccount = {
      accountId: result.account.id, store: storeScope, epoch, verified: false,
      code: typeof result.recovery_code === "string" && result.recovery_code.trim() ? result.recovery_code : null,
    };
    keepRecoveredAccount(receipt);
    try {
      await verifyRecoveredAccount(receipt);
    } catch (error) {
      if (recoveryIsCurrent(epoch, storeScope) && recoveredReceipt.current === receipt)
        throw new SessionRecoveryError("verification_pending");
      throw error;
    }
  }

  async function acknowledgeRecoveredAccount() {
    const receipt = recoveredReceipt.current;
    if (!receipt?.verified) return;
    const verified = await verifyRecoveredAccount(receipt);
    if (!recoveryIsCurrent(receipt.epoch, receipt.store) || recoveredReceipt.current !== receipt) return;
    await authenticated(verified);
  }

  async function startGuestVisit() {
    const epoch = sessionEpoch.current;
    const saved = suspendedSession.current;
    if (!saved) return;
    let discovered: ShopperAuthResponse | null = null;
    try {
      discovered = await baseClient.shopperAccount();
    } catch (error) {
      if (!isSessionExpired(error)) throw error;
    }
    if (epoch !== sessionEpoch.current || !suspendedSession.current) return;
    if (discovered) {
      if (discovered.account.id !== saved.accountId)
        throw new SessionRecoveryError("guest_conflict");
      await clientForAccount(saved.accountId).logoutShopper();
    }
    if (epoch !== sessionEpoch.current || !suspendedSession.current) return;
    const result = await baseTransport.request<ShopperGuestResponse>("/v1/shopper/auth/guest", "POST");
    if (epoch !== sessionEpoch.current || !suspendedSession.current) return;
    // Bootstrap may reuse a guest; this explicit fresh start requires server-attested creation.
    if (result.created !== true || !result.account.is_guest)
      throw new SessionRecoveryError("guest_conflict");
    suspendedSession.current = null;
    await authenticated(result);
  }

  async function updateMemory(enabled: boolean) {
    if (memoryMutation.current || !account) return;
    const epoch = sessionEpoch.current;
    const scope = `${store?.slug ?? "legacy"}:${account.id}`;
    const change = memoryChange.current ?? { key: crypto.randomUUID(), enabled };
    if (!saveMemoryChange(scope, change)) {
      setNotice("Allow tab storage before changing shopping memory so interrupted changes can be recovered.");
      return;
    }
    memoryChange.current = change;
    memoryMutation.current = true;
    setMemoryUpdating(true);
    setNotice(null);
    try {
      const result = await shopperRequest<ShopperAuthResponse>(
        "/v1/shopper/preferences", "PATCH", { enabled: change.enabled }, change.key,
      );
      if (epoch !== sessionEpoch.current) return;
      acceptAccount(result.account);
      saveMemoryChange(scope, null);
      memoryChange.current = null;
      setMemoryUncertain(false);
      await loadWorkspace(["memory"]);
    } catch (error) {
      if (expireSession(error, epoch)) throw error;
      if (epoch === sessionEpoch.current) {
        setMemoryUncertain(true);
        setNotice(shopperErrorMessage(error));
      }
      throw error;
    } finally {
      if (epoch === sessionEpoch.current) {
        memoryMutation.current = false;
        setMemoryUpdating(false);
      }
    }
  }

  async function openConversation(conversationId: string) {
    const request = ++conversationRequest.current;
    const epoch = sessionEpoch.current;
    changeView("chat");
    setNotice(null);
    setMobileNav(false);
    try {
      const next = await client.shopperConversation(conversationId);
      if (request === conversationRequest.current && epoch === sessionEpoch.current) setDetail(next);
    } catch (error) {
      if (expireSession(error, epoch)) return;
      if (request === conversationRequest.current && epoch === sessionEpoch.current)
        setNotice(shopperErrorMessage(error));
    }
  }

  async function send(contentOverride?: string, retry?: ChatAttempt) {
    const content = retry?.content ?? (contentOverride ?? draftValue.current).trim();
    if (!content || !accountSnapshot.current || activeChat.current || pending || loggingOut || memoryMutation.current || memoryChange.current || accountAction.current) return;
    if (failedAttempt.current && retry !== failedAttempt.current) return;
    const epoch = sessionEpoch.current;
    const sent = retry ?? {
      key: crypto.randomUUID(), accountId: accountSnapshot.current.id,
      navigation: conversationRequest.current,
      content, conversationId: detail?.conversation.id ?? null,
      message: {
      id: crypto.randomUUID(),
      conversation_id: detail?.conversation.id ?? crypto.randomUUID(),
      role: "user",
      content,
      steps: [],
      products: [],
      created_at: new Date().toISOString(),
      },
    } satisfies ChatAttempt;
    activeChat.current = sent;
    setOptimisticMessage(sent.message);
    setPending(true);
    setNotice(null);
    if (!retry || draftValue.current === content) changeDraft("");
    const revision = draftRevision.current;
    try {
      const response = await clientForAccount(sent.accountId).chatWithShopper(
        {
          content,
          conversation_id: sent.conversationId,
          expected_account_id: sent.accountId,
        },
        sent.key,
      );
      if (epoch !== sessionEpoch.current) return;
      if (sent.navigation === conversationRequest.current) setDetail((current) => ({
        conversation: response.conversation,
        messages: [
          ...(current?.conversation.id === response.conversation.id
            ? current.messages.filter((message) => message.id !== response.user_message.id && message.id !== response.assistant_message.id)
            : []),
          response.user_message,
          response.assistant_message,
        ],
      }));
      setConversations((items) => [
        response.conversation,
        ...items.filter((item) => item.id !== response.conversation.id),
      ]);
      // Chat receipts describe a past save; deletion or opt-out may have won since.
      void loadWorkspace(["memory"]);
      setOptimisticMessage(null);
      keepFailedAttempt(null);
    } catch (error) {
      if (epoch !== sessionEpoch.current) return;
      if (draftRevision.current === revision && !draftValue.current) changeDraft(content);
      if (expireSession(error, epoch)) return;
      keepFailedAttempt(sent);
      setOptimisticMessage(null);
      setNotice(shopperErrorMessage(error));
    } finally {
      if (epoch === sessionEpoch.current) {
        activeChat.current = null;
        setPending(false);
      }
    }
  }

  async function logout() {
    if (loggingOut || pending || commercePending || memoryMutation.current || accountAction.current) return;
    const epoch = sessionEpoch.current;
    setLoggingOut(true);
    setLogoutFailed(false);
    try {
      await client.logoutShopper();
    } catch (error) {
      if (epoch !== sessionEpoch.current) return;
      if (expireSession(error, epoch)) return;
      setLogoutFailed(true);
      setLoggingOut(false);
      return;
    }
    if (epoch !== sessionEpoch.current) return;
    clearAccountView();
    accountId.current = null;
    accountSnapshot.current = null;
    accountStore.current = null;
    setAccount(null);
    setLoggingOut(false);
    if (store) location.reload();
  }

  function acceptAccount(next: ShopperAccount) {
    if (accountId.current !== next.id || accountStore.current !== storeScope) {
      clearAccountView();
      memoryChange.current = loadMemoryChange(`${store?.slug ?? "legacy"}:${next.id}`);
      setMemoryUncertain(Boolean(memoryChange.current));
    }
    accountId.current = next.id;
    accountSnapshot.current = next;
    accountStore.current = storeScope;
    setAccount(next);
  }

  function clearAccountView(preserveReceipts = false) {
    // Never retain another account's cached data if its replacement fails to load.
    sessionEpoch.current += 1;
    keepRecoveredAccount(null);
    if (accountId.current && !preserveReceipts) saveAttempt(`${accountStore.current ?? storeScope}:${accountId.current}`, null);
    attempt.current = null;
    discoveredCheckout.current = undefined;
    recoveryRequest.current += 1;
    setRecovery(null);
    setUncertain(false);
    setCheckingCheckout(false);
    conversationRequest.current += 1;
    memoryRequest.current += 1;
    memoryMutation.current = false;
    memoryChange.current = null;
    accountAction.current = false;
    setAccountUpdating(false);
    setMemoryUpdating(false);
    setMemoryUncertain(false);
    setConversations([]);
    setDetail(null);
    setMemories([]);
    removalReceipts.current.clear();
    setMemoryRemovals([]);
    setDiscovery(null);
    setCart(emptyCart());
    setCheckout(null);
    setConfirmation(null);
    setOptimisticMessage(null);
    setDrawer(null);
    changeDraft("");
    activeChat.current = null;
    keepFailedAttempt(null);
    suspendedSession.current = null;
    setSessionExpired(false);
    setNotice(null);
    setRecoveryRequested(false);
    setCartLoaded(false);
    setMemoryLoaded(false);
    setWorkspaceErrors([]);
    setWorkspaceLoading(false);
    setPending(false);
    setCommercePending(null);
    setProductDetail(null);
    setSelectedVariant("");
    setMobileNav(false);
    setLoggingOut(false);
    setLogoutFailed(false);
  }

  function changeView(next: "chat" | "catalog") {
    setView(next);
    setMobileNav(false);
    if (!store)
      window.history.replaceState(
        null,
        "",
        next === "catalog" ? "/catalog" : "/",
      );
  }

  async function addToCart(
    product: Pick<ShopperProductCard, "product_id"> & { variant_id?: string },
  ) {
    if (commercePending || loggingOut) return;
    if (!cartLoaded) {
      setDrawer("cart");
      return;
    }
    const epoch = sessionEpoch.current;
    setCommercePending(product.product_id);
    setNotice(null);
    try {
      if (!product.variant_id) {
        const catalog = await client.shopperCatalog({
          product_id: product.product_id,
          limit: 1,
        });
        if (epoch !== sessionEpoch.current) return;
        const item = catalog.items[0];
        if ((item?.variants?.length ?? 0) > 1) {
          setProductDetail(item);
          setSelectedVariant("");
          setDrawer("product");
          return;
        }
      }
      const result = await client.addShopperCartItem(
        {
          product_id: product.product_id,
          quantity: 1,
          ...(product.variant_id ? { variant_id: product.variant_id } : {}),
        },
        crypto.randomUUID(),
      );
      if (epoch !== sessionEpoch.current) return;
      setCart(normalizeCart(result));
      setCheckout(null);
      setConfirmation(null);
      setDrawer("cart");
    } catch (error) {
      if (expireSession(error, epoch)) return;
      if (epoch === sessionEpoch.current) setNotice(shopperErrorMessage(error));
    } finally {
      if (epoch === sessionEpoch.current) setCommercePending(null);
    }
  }

  async function changeQuantity(lineId: string, quantity: number) {
    if (commercePending || loggingOut || !cartLoaded) return;
    const epoch = sessionEpoch.current;
    setCommercePending(lineId);
    setNotice(null);
    try {
      const result =
        quantity <= 0
          ? await client.deleteShopperCartItem(lineId, crypto.randomUUID())
          : await client.updateShopperCartItem(
              lineId,
              { quantity },
              crypto.randomUUID(),
            );
      if (epoch !== sessionEpoch.current) return;
      setCart(normalizeCart(result));
      setCheckout(null);
      setConfirmation(null);
    } catch (error) {
      if (expireSession(error, epoch)) return;
      if (epoch === sessionEpoch.current) setNotice(shopperErrorMessage(error));
    } finally {
      if (epoch === sessionEpoch.current) setCommercePending(null);
    }
  }

  async function reviewCheckout() {
    if (!cartLoaded || !cart.id || cart.item_count === 0 || commercePending || loggingOut || uncertain || checkingCheckout) return;
    const epoch = sessionEpoch.current;
    setCommercePending("checkout-preview");
    setNotice(null);
    try {
      const result = await client.previewShopperCheckout(
          { cart_version: cart.version },
          crypto.randomUUID(),
        );
      if (epoch !== sessionEpoch.current) return;
      setCheckout(result);
      clearAttempt();
      setRecovery(null);
      setUncertain(false);
      setConfirmation(null);
    } catch (error) {
      if (expireSession(error, epoch)) return;
      if (epoch === sessionEpoch.current) setNotice(shopperErrorMessage(error));
    } finally {
      if (epoch === sessionEpoch.current) setCommercePending(null);
    }
  }

  async function confirmCheckout(
    paymentMethod: "test_success" | "test_decline",
  ) {
    if (!checkout || commercePending || loggingOut || checkingCheckout || !recoveryScope) return;
    if (uncertain && (!attempt.current || attempt.current.checkoutId !== checkout.checkout_id)) return;
    const epoch = sessionEpoch.current;
    recoveryRequest.current += 1;
    setCommercePending("checkout-confirm");
    setNotice(null);
    const saved = attempt.current ?? {
      checkoutId: checkout.checkout_id, cartVersion: checkout.cart_version,
      expiresAt: checkout.reservation_expires_at, key: crypto.randomUUID(), method: paymentMethod,
    };
    attempt.current = saved;
    saveAttempt(recoveryScope, saved);
    setUncertain(true);
    try {
      const result = await client.confirmShopperCheckout(
        { checkout_id: saved.checkoutId, payment_method: saved.method }, saved.key,
      );
      if (epoch !== sessionEpoch.current) return;
      setUncertain(false);
      setRecovery(null);
      clearAttempt();
      setConfirmation(result);
      if (result.status === "succeeded") {
        setCart(emptyCart());
        setCheckout(null);
      } else if (result.status === "cancelled") {
        setCheckout(null);
        setNotice(result.message);
        await loadWorkspace(["cart"]);
      }
    } catch (error) {
      if (expireSession(error, epoch)) return;
      if (epoch === sessionEpoch.current) {
        setNotice(shopperErrorMessage(error));
        await checkCheckout();
      }
    } finally {
      if (epoch === sessionEpoch.current) setCommercePending(null);
    }
  }

  async function forgetMemory(memoryId: string) {
    const identity = accountSnapshot.current;
    if (!identity || accountStore.current !== renderedStore.current || accountAction.current || loggingOut) return;
    const previous = removalReceipts.current.get(memoryId);
    if (previous?.state === "pending") return;
    if (previous && (previous.accountId !== identity.id || previous.store !== storeScope)) return;
    const removal: MemoryRemoval = { memoryId, accountId: identity.id, store: storeScope,
      key: previous?.key ?? crypto.randomUUID(), state: "pending" };
    const epoch = sessionEpoch.current;
    const current = () => epoch === sessionEpoch.current && renderedStore.current === removal.store
      && accountId.current === removal.accountId && removalReceipts.current.get(memoryId) === removal;
    removalReceipts.current.set(memoryId, removal);
    setMemoryRemovals([...removalReceipts.current.values()]);
    memoryRequest.current += 1;
    setNotice(null);
    try {
      await clientForAccount(removal.accountId).deleteShopperMemory(memoryId, removal.key);
      if (!current()) return;
      memoryRequest.current += 1;
      removalReceipts.current.delete(memoryId);
      setMemoryRemovals([...removalReceipts.current.values()]);
      setMemories((items) => items.filter((item) => item.id !== memoryId));
    } catch (error) {
      if (!current()) return;
      if (expireSession(error, epoch)) return;
      removalReceipts.current.set(memoryId, { ...removal, state: "uncertain" });
      setMemoryRemovals([...removalReceipts.current.values()]);
      setNotice(shopperErrorMessage(error));
    }
  }

  if (sessionExpired && suspendedSession.current) {
    if (suspendedSession.current.store !== storeScope) return <Loading />;
    return <SessionRecovery
      storeName={store?.name}
      reason={recoveryRequested ? "requested" : "expired"}
      guest={suspendedSession.current.guest}
      onRecover={store && !store.preview ? recoverAccount : undefined}
      recoveryReceipt={recoveredAccount}
      onVerifyRecovery={async () => { if (recoveredReceipt.current) await verifyRecoveredAccount(recoveredReceipt.current); }}
      onAcknowledgeRecovery={acknowledgeRecoveredAccount}
      onCheckSession={() => recoverSession(() => baseClient.shopperAccount())}
      onSignIn={(credentials) => recoverSession(async () => {
        const result = await baseClient.loginShopper(credentials);
        if (result.merge_token) throw new Error("This guest visit needs a cart choice. Check the session to return to its account controls.");
        const verified = await clientForAccount(result.account.id).shopperAccount();
        if (verified.account.id !== result.account.id)
          throw new Error("Your sign-in changed. Check the session again.");
        return verified;
      })}
      onStartGuest={store && !store.preview ? startGuestVisit : undefined}
    />;
  }
  if (!checked || (account && accountStore.current !== storeScope)) return <Loading />;
  if (authError)
    return (
      <main className="shop-loading">
        <span>GA</span>
        <h1>We could not open your shopping session</h1>
        <p role="alert">The store connection is unavailable. Your account and shopping data have not been reset.</p>
        <button onClick={() => setAuthAttempt((value) => value + 1)}>
          <RefreshCw size={16} /> Retry connection
        </button>
      </main>
    );
  if (!account)
    return (
      <AuthScreen
        client={baseClient}
        notice={notice}
        onNotice={setNotice}
        onAuthenticated={(result) => void authenticated(result)}
      />
    );

  return (
    <ShopperTransportContext.Provider value={transport}>
    <ShopperSessionErrors.Provider value={sessionError}>
    <main className="shop-shell">
      <header className="shop-topbar">
        <button
          className="mobile-menu"
          type="button"
          aria-label="Open conversations"
          onClick={() => setMobileNav(true)}
        >
          <Menu size={20} />
        </button>
        <div className="shop-brand">
          <span>
            {store?.name
              .split(/\s+/)
              .slice(0, 2)
              .map((word) => word[0])
              .join("")
              .toUpperCase() ?? "GA"}
          </span>
          <div className="store-identity">
            <strong>{store?.name ?? "GoodAgent Shop"}</strong>
            {store?.preview && <small>Private preview</small>}
            {store?.sample_data && <small>Sample products</small>}
          </div>
        </div>
        <div className="shop-account">
          <span>{account.display_name}</span>
          {store && (
            <button
              onClick={() => setDrawer("account")}
              title="Shopping account"
              aria-label={account.is_guest ? "Save your progress" : "Account"}
              disabled={loggingOut}
            >
              <User size={16} />
              <span className="account-action-label">
                {account.is_guest ? "Save your progress" : "Account"}
              </span>
            </button>
          )}
          <button
            className="cart-button"
            type="button"
            aria-label={cartLoaded ? `Open cart with ${cart.item_count} items` : "Open cart"}
            disabled={loggingOut}
            title="Cart"
            onClick={() => setDrawer("cart")}
          >
            <ShoppingCart size={17} />
            {cart.item_count > 0 && <b>{cart.item_count}</b>}
          </button>
          <button
            type="button"
            aria-label="Sign out"
            title="Sign out"
            disabled={loggingOut || pending || memoryUpdating || accountUpdating || Boolean(commercePending)}
            onClick={() => void logout()}
          >
            <LogOut size={17} />
          </button>
        </div>
      </header>
      {logoutFailed && <div className="shop-recovery" role="alert">
        <span>Sign-out not confirmed. Your session may still be active.</span>
        <button disabled={loggingOut || pending || memoryUpdating || accountUpdating || Boolean(commercePending)} onClick={() => void logout()}>
          <LogOut size={16} /> Retry sign-out
        </button>
      </div>}
      {workspaceErrors.length > 0 && <div className="shop-recovery" role="alert">
        <span>Could not load {workspaceErrors.join(", ")}. Other sections are still available.</span>
        <button disabled={workspaceLoading || loggingOut} onClick={() => void loadWorkspace(workspaceErrors)}>
          <RefreshCw size={16} /> Retry unavailable sections
        </button>
      </div>}
      {memoryUpdating && <div className="shop-recovery" role="status">Updating shopping memory settings...</div>}
      {accountUpdating && !memoryUpdating && <div className="shop-recovery" role="status">Updating your account...</div>}
      {memoryUncertain && <div className="shop-recovery" role="alert">
        <span>Memory setting is unverified. Browsing is available; chat is paused until the change is confirmed.</span>
        <button disabled={memoryUpdating} onClick={() => void updateMemory(memoryChange.current?.enabled ?? false).catch(() => undefined)}>
          <RefreshCw size={16} /> Retry memory change
        </button>
      </div>}
      <div className="shop-workspace" data-drawer-open={drawer !== null} inert={loggingOut}>
        <aside className="conversation-nav" data-open={mobileNav}>
          <div className="nav-heading">
            <strong>Conversations</strong>
            <button
              type="button"
              aria-label="New conversation"
              title="New conversation"
              onClick={() => {
                conversationRequest.current += 1;
                setDetail(null);
                changeView("chat");
                setMobileNav(false);
              }}
            >
              <MessageSquarePlus size={17} />
            </button>
            <button
              className="close-nav"
              type="button"
              aria-label="Close conversations"
              onClick={() => setMobileNav(false)}
            >
              <X size={17} />
            </button>
          </div>
          <div className="conversation-list">
            <button
              className={view === "catalog" ? "selected" : ""}
              type="button"
              onClick={() => changeView("catalog")}
            >
              <Package size={15} />
              <span>Browse catalog</span>
            </button>
            <button
              className={!detail && view === "chat" ? "selected" : ""}
              type="button"
              onClick={() => {
                conversationRequest.current += 1;
                setDetail(null);
                changeView("chat");
              }}
            >
              <Sparkles size={15} /> <span>Start something new</span>
            </button>
            {conversations.map((conversation) => (
              <button
                className={
                  view === "chat" && detail?.conversation.id === conversation.id
                    ? "selected"
                    : ""
                }
                type="button"
                key={conversation.id}
                onClick={() => void openConversation(conversation.id)}
              >
                <Search size={15} /> <span>{conversation.title}</span>
              </button>
            ))}
          </div>
          <button
            className="memory-button"
            type="button"
            onClick={() => { setDrawer("orders"); setMobileNav(false); }}
          >
            <ReceiptText size={16} /> <span>Demo orders</span>
          </button>
          <button
            className="memory-button"
            type="button"
            onClick={() => {
              setDrawer("activity");
              setMobileNav(false);
            }}
          >
            <Activity size={16} />
            <span>Shopping activity</span>
          </button>
          <button
            className="memory-button"
            type="button"
            onClick={() => { setDrawer("memory"); void loadWorkspace(["memory"]); }}
          >
            <Brain size={16} />
            <span>Shopping memory</span>
            {memoryLoaded && <b>{memories.length}</b>}
          </button>
        </aside>

        {view === "catalog" ? (
          <div className="catalog-main">
            {notice && (
              <p className="catalog-notice" role="alert">
                {notice}
              </p>
            )}
            <CatalogBrowser
              client={client}
              pendingProduct={commercePending}
              storeName={store?.name}
              onInspect={(product) => {
                if (store)
                  void shopperRequest(
                    "/v1/shopper/product-selections",
                    "POST",
                    { product_id: product.product_id, quantity: 1 },
                  ).catch(sessionError);
                setProductDetail(product);
                setSelectedVariant("");
                setDrawer("product");
              }}
              onAdd={addToCart}
              onAsk={(query) => {
                changeView("chat");
                void send(query);
              }}
            />
          </div>
        ) : (
          <section className="conversation-main">
            <header className="conversation-header">
              <div>
                <strong>
                  {detail?.conversation.title ?? "What can I help you find?"}
                </strong>
                <span>
                  {discovery?.catalog_status === "ready"
                    ? store ? `${discovery.product_count} products at ${store.name}` : `${discovery.product_count} products from ${discovery.catalog_name ?? "the store catalog"}`
                    : "Waiting for the store catalog"}
                </span>
                <span aria-label="Conversation mode">{conversationCopy(discovery).label}</span>
              </div>
              <span
                className="read-only"
                data-ready={discovery?.catalog_status === "ready"}
              >
                <i />{" "}
                {discovery?.catalog_status === "ready"
                  ? "Catalog available"
                  : "Catalog pending"}
              </span>
            </header>
            <div className="message-history" ref={scrollRef}>
              {!detail?.messages.length && !optimisticMessage && !failedChat ? (
                <ShopperWelcome
                  key={`${storeScope}:${account.id}`}
                  store={store}
                  discovery={discovery}
                  welcome={conversationCopy(discovery).welcome}
                  disabled={pending || Boolean(failedChat)}
                  onPrompt={(prompt) => void send(prompt)}
                />
              ) : null}
              {detail?.messages.map((message) => (
                <ShopperMessageRow
                  key={message.id}
                  message={message}
                  pendingProduct={commercePending}
                  onAdd={addToCart}
                />
              ))}
              {optimisticMessage && (
                <ShopperMessageRow
                  message={optimisticMessage}
                  pendingProduct={commercePending}
                  onAdd={addToCart}
                />
              )}
              {pending && <ShopperAgentWorking />}
              {failedChat && !pending && <div className="failed-request" role="alert">
                <strong>Request not confirmed</strong>
                <p>{failedChat.content}</p>
                <span>It may already have been received. Retrying uses the same request.</span>
                <div>
                  <button type="button" disabled={memoryUpdating || memoryUncertain || accountUpdating} onClick={() => void send(undefined, failedChat)}>
                    <RefreshCw size={16} /> Retry same request
                  </button>
                  <button type="button" onClick={() => keepFailedAttempt(null)}>
                    <X size={16} /> Dismiss failed request
                  </button>
                </div>
              </div>}
            </div>
            <div className="composer-area">
              {notice && <p className="composer-notice" role="alert">{notice}</p>}
              <div className="composer-box">
                <textarea
                  aria-label="Shopping request"
                  value={draft}
                  maxLength={2000}
                  rows={2}
                  placeholder={conversationCopy(discovery).placeholder}
                  onChange={(event) => changeDraft(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" && !event.shiftKey) {
                      event.preventDefault();
                      void send();
                    }
                  }}
                />
                <button
                  type="button"
                  aria-label="Send request"
                  title="Send"
                  disabled={!draft.trim() || pending || Boolean(failedChat) || memoryUpdating || memoryUncertain || accountUpdating}
                  onClick={() => void send()}
                >
                  <ArrowUp size={18} />
                </button>
              </div>
              <small>
                Cart and demo checkout require your explicit action.
              </small>
            </div>
          </section>
        )}

        {drawer === "orders" && <OrderHistory key={account.id} client={client} guest={Boolean(account.is_guest)} onClose={() => setDrawer(null)} />}
        {drawer === "account" && (
          <AccountControls
            account={account}
            onRecoveryStart={store && !store.preview ? () => {
              if (accountAction.current || activeChat.current || loggingOut || pending || commercePending || memoryMutation.current || memoryChange.current || accountStore.current !== renderedStore.current) return;
              suspendAccount(currentSession, true);
            } : undefined}
            memoryUpdating={memoryUpdating || memoryUncertain}
            memoryUncertain={memoryUncertain}
            onMemoryChange={updateMemory}
            pending={accountUpdating || pending || Boolean(commercePending) || loggingOut}
            onActionStart={() => {
              if (currentSession !== sessionEpoch.current || accountAction.current) return false;
              accountAction.current = true;
              setAccountUpdating(true);
              return true;
            }}
            onActionEnd={() => {
              if (currentSession !== sessionEpoch.current) return;
              accountAction.current = false;
              setAccountUpdating(false);
            }}
            onAccount={(result) => {
              if (currentSession === sessionEpoch.current) void authenticated(result);
            }}
            onClose={() => setDrawer(null)}
            onDeleted={() => {
              if (currentSession !== sessionEpoch.current) return;
              const unresolved = memoryChange.current ?? loadMemoryChange(`${store?.slug ?? "legacy"}:${account.id}`);
              clearAccountView();
              memoryChange.current = unresolved;
              setMemoryUncertain(Boolean(unresolved));
              void loadWorkspace();
            }}
          />
        )}
        {drawer === "product" && productDetail && (
          <aside
            className="memory-drawer account-controls"
            aria-label="Product details"
          >
            <header>
              <strong>{productDetail.title}</strong>
              <button
                aria-label="Close product"
                title="Close product"
                onClick={() => setDrawer(null)}
              >
                <X size={18} />
              </button>
            </header>
            <section>
              {productDetail.image_url && (
                <Image
                  src={productDetail.image_url}
                  width={280}
                  height={240}
                  style={{ objectFit: "contain", maxWidth: "100%" }}
                  unoptimized
                  alt={productDetail.title}
                />
              )}
              <p>{productDetail.description}</p>
              <label>
                Choose a variant
                <select
                  value={selectedVariant}
                  onChange={(e) => setSelectedVariant(e.target.value)}
                >
                  <option value="">Select an option</option>
                  {productDetail.variants?.map((variant) => (
                    <option
                      key={variant.id}
                      value={variant.id}
                      disabled={!variant.available}
                    >
                      {Object.values(variant.options).join(" / ") ||
                        variant.title}{" "}
                      · {variant.price.currency}{" "}
                      {(variant.price.amount_minor / 100).toFixed(2)}
                      {!variant.available ? " · Unavailable" : ""}
                    </option>
                  ))}
                </select>
              </label>
              <button
                disabled={!selectedVariant || commercePending !== null}
                onClick={() =>
                  void addToCart({
                    product_id: productDetail.product_id,
                    variant_id: selectedVariant,
                  })
                }
              >
                <Plus size={16} />
                Add to cart
              </button>
            </section>
          </aside>
        )}
        {drawer === "activity" && (
          <aside className="memory-drawer">
            <header>
              <strong>Activity & monitors</strong>
              <button
                type="button"
                className="icon-button"
                aria-label="Close activity"
                onClick={() => setDrawer(null)}
              >
                <X size={18} />
              </button>
            </header>
            <ActivityPanel />
          </aside>
        )}
        {drawer === "memory" && (
          <aside className="memory-drawer">
            <header>
              <div>
                <Brain size={17} />
                <strong>Shopping memory</strong>
              </div>
              <button
                type="button"
                aria-label="Close memory"
                onClick={() => setDrawer(null)}
              >
                <X size={17} />
              </button>
            </header>
            <p className="memory-intro">
              {account.is_guest
                ? "Preferences for this visit. They expire after 24 hours unless you save your progress."
                : "Your saved shopping preferences. Remove any you no longer want remembered."}
            </p>
            {account.memory_enabled === false && <p className="memory-intro" role="status">
              Shopping memory is off. Saving and recall are paused. Previously saved preferences remain until you remove them.
            </p>}
            {memoryRemovals.filter(removal => removal.state === "uncertain").map(removal => (
              <section className="memory-removal-recovery" key={removal.memoryId} aria-label="Unconfirmed preference removal">
                <p>Preference removal could not be confirmed.</p>
                <button type="button" disabled={accountUpdating || loggingOut}
                  aria-label={`Retry removing ${memories.find(memory => memory.id === removal.memoryId)?.content ?? "preference"}`}
                  onClick={() => void forgetMemory(removal.memoryId)}><RefreshCw size={14} /> Retry removal</button>
              </section>
            ))}
            <div className="memory-list">
              {memories.length ? (
                memories.map((memory) => (
                  <div key={memory.id}>
                    <Sparkles size={14} />
                    <span>{memory.content}</span>
                    <button
                      type="button"
                      aria-label={`Forget ${memory.content}`}
                      title="Forget preference"
                      disabled={memoryRemovals.some(removal => removal.memoryId === memory.id) || accountUpdating || loggingOut}
                      onClick={() => void forgetMemory(memory.id)}
                    >
                      {memoryRemovals.some(removal => removal.memoryId === memory.id && removal.state === "pending")
                        ? <RefreshCw size={14} aria-label="Removing preference" /> : <Trash2 size={14} />}
                    </button>
                  </div>
                ))
              ) : !memoryLoaded ? (
                <p>{workspaceErrors.includes("memory") ? "Shopping memory is unavailable. Retry the connection above." : "Loading shopping memory..."}</p>
              ) : (
                <p>No saved preferences yet.</p>
              )}
            </div>
          </aside>
        )}
        {drawer === "cart" && !cartLoaded && (
          <aside className="memory-drawer" aria-label="Cart">
            <header><strong>Your cart</strong>
              <button aria-label="Close cart" onClick={() => setDrawer(null)}><X size={17} /></button>
            </header>
            <p className="memory-intro" role="status">
              {workspaceErrors.includes("cart") ? "Your cart is unavailable, not empty. Retry the connection above." : "Loading your cart..."}
            </p>
          </aside>
        )}
        {drawer === "cart" && cartLoaded && (
          <CartDrawer
            cart={cart}
            checkout={checkout}
            confirmation={confirmation}
            pending={commercePending}
            notice={notice}
            recovery={uncertain ? recovery?.message ?? "The confirmation outcome is not yet known." : null}
            checking={checkingCheckout}
            onCheck={() => void checkCheckout()}
            onRetry={uncertain && recovery?.preview && attempt.current &&
              Date.parse(attempt.current.expiresAt) > Date.now()
              ? () => void confirmCheckout(attempt.current!.method) : undefined}
            onClose={() => setDrawer(null)}
            onQuantity={changeQuantity}
            onReview={reviewCheckout}
            onConfirm={confirmCheckout}
            onBack={() => {
              setCheckout(null);
              setConfirmation(null);
            }}
          />
        )}
      </div>
    </main>
    </ShopperSessionErrors.Provider>
    </ShopperTransportContext.Provider>
  );
}

function AuthScreen({
  client,
  notice,
  onNotice,
  onAuthenticated,
}: {
  client: ShopperClient;
  notice: string | null;
  onNotice: (value: string | null) => void;
  onAuthenticated: (result: ShopperAuthResponse) => void;
}) {
  const [mode, setMode] = useState<"login" | "register">("register");
  const [username, setUsername] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [password, setPassword] = useState("");
  const [pending, setPending] = useState(false);
  async function submit(event: FormEvent) {
    event.preventDefault();
    setPending(true);
    onNotice(null);
    try {
      const result =
        mode === "register"
          ? await client.registerShopper({
              username,
              display_name: displayName,
              password,
            })
          : await client.loginShopper({ username, password });
      onAuthenticated(result);
    } catch (error) {
      onNotice(shopperErrorMessage(error));
    } finally {
      setPending(false);
    }
  }
  return (
    <main className="auth-shell">
      <CatalogArtwork />
      <div className="auth-overlay">
        <div className="auth-copy">
          <span className="auth-mark">GA</span>
          <h1>Your store, in conversation.</h1>
          <p>
            Ask naturally. Compare clearly. Pick from products that are actually
            in the catalog.
          </p>
        </div>
        <form className="auth-form" onSubmit={(event) => void submit(event)}>
          <div className="auth-tabs" role="tablist">
            <button
              type="button"
              data-active={mode === "register"}
              onClick={() => setMode("register")}
            >
              Create account
            </button>
            <button
              type="button"
              data-active={mode === "login"}
              onClick={() => setMode("login")}
            >
              Sign in
            </button>
          </div>
          <h2>{mode === "register" ? "Start shopping" : "Welcome back"}</h2>
          {mode === "register" && (
            <label>
              Display name
              <input
                value={displayName}
                maxLength={80}
                required
                onChange={(event) => setDisplayName(event.target.value)}
              />
            </label>
          )}
          <label>
            Username
            <input
              value={username}
              minLength={3}
              maxLength={40}
              required
              autoComplete="username"
              onChange={(event) => setUsername(event.target.value)}
            />
          </label>
          <label>
            Password
            <input
              type="password"
              value={password}
              minLength={mode === "register" ? 10 : 1}
              maxLength={128}
              required
              autoComplete={
                mode === "register" ? "new-password" : "current-password"
              }
              onChange={(event) => setPassword(event.target.value)}
            />
          </label>
          {notice && <p className="auth-notice">{notice}</p>}
          <button className="auth-submit" type="submit" disabled={pending}>
            {pending
              ? "Opening the shop..."
              : mode === "register"
                ? "Create account"
                : "Sign in"}
          </button>
        </form>
      </div>
    </main>
  );
}

function conversationCopy(discovery: ShopperDiscoveryResponse | null) {
  if (discovery?.conversation_mode === "basic") return {
    label: "Basic mode: AI chat is not connected.",
    welcome: "Search for a product or browse the catalog. Basic mode uses limited catalog matching, not conversational AI.",
    placeholder: "Search for a product or category...",
  };
  if (discovery?.conversation_mode === "model_configured") return {
    label: "AI mode: connection not checked.",
    welcome: "Describe what you need, including budget and preferences. AI replies depend on the configured provider being available.",
    placeholder: "Ask for a product, a gift, or a comparison...",
  };
  return {
    label: "Search the store catalog.",
    welcome: "Search for products or explore the catalog. Conversation availability has not been reported.",
    placeholder: "Search the store catalog...",
  };
}

function ShopperMessageRow({
  message,
  pendingProduct,
  onAdd,
}: {
  message: ShopperMessage;
  pendingProduct: string | null;
  onAdd: (product: ShopperProductCard) => void;
}) {
  return (
    <article className="shop-message" data-role={message.role}>
      <div className="message-avatar">
        {message.role === "assistant" ? <Bot size={18} /> : <User size={17} />}
      </div>
      <div className="message-content">
        <header>
          <strong>
            {message.role === "assistant" ? "Shop assistant" : "You"}
          </strong>
          <time>{formatTime(message.created_at)}</time>
        </header>
        {message.role === "assistant" ? (
          <ChatMarkdown>{message.content}</ChatMarkdown>
        ) : (
          <p>{message.content}</p>
        )}
        {message.steps?.some(
          (step) => step.stage === "remember" && step.status === "completed",
        ) && (
          <p className="memory-saved">
            <Brain size={14} /> Saved to shopping memory
          </p>
        )}
        {(message.products?.length ?? 0) > 0 && (
          <ProductStrip
            products={message.products ?? []}
            pendingProduct={pendingProduct}
            onAdd={onAdd}
          />
        )}
        {(message.steps?.length ?? 0) > 0 && (
          <details className="search-steps">
            <summary>
              <ChevronDown size={14} /> How I searched
            </summary>
            {(message.steps ?? []).map((step, index) => (
              <div key={`${step.stage}-${index}`}>
                <i data-status={step.status} />
                <span>
                  <strong>{step.title}</strong>
                  {step.detail}
                </span>
              </div>
            ))}
          </details>
        )}
      </div>
    </article>
  );
}

function ProductStrip({
  products,
  pendingProduct,
  onAdd,
}: {
  products: ShopperProductCard[];
  pendingProduct: string | null;
  onAdd: (product: ShopperProductCard) => void;
}) {
  return (
    <div className="product-strip">
      {products.slice(0, 8).map((product) => (
        <article className="product-card" key={product.product_id}>
          <div className="product-visual">
            {product.image_url ? (
              <Image
                src={product.image_url}
                alt={product.title}
                fill
                sizes="180px"
                unoptimized
              />
            ) : (
              <>
                <Package size={26} />
                <span>{product.category?.split(" > ")[0] || "Product"}</span>
              </>
            )}
          </div>
          <div className="product-info">
            <span>{product.brand || product.category || "In stock"}</span>
            <strong>{product.title}</strong>
            <b>
              {product.currency} {(product.price_minor / 100).toFixed(2)}
            </b>
            <button
              type="button"
              disabled={pendingProduct !== null}
              onClick={() => onAdd(product)}
            >
              <Plus size={13} />
              {pendingProduct === product.product_id ? "Adding" : "Add"}
            </button>
          </div>
        </article>
      ))}
    </div>
  );
}

function CartDrawer({
  cart,
  checkout,
  confirmation,
  pending,
  notice,
  onClose,
  onQuantity,
  onReview,
  onConfirm,
  onBack,
  recovery,
  checking,
  onCheck,
  onRetry,
}: {
  cart: CartState;
  checkout: CheckoutPreview | null;
  confirmation: CheckoutConfirmation | null;
  pending: string | null;
  notice: string | null;
  onClose: () => void;
  onQuantity: (lineId: string, quantity: number) => void;
  onReview: () => void;
  onConfirm: (method: "test_success" | "test_decline") => void;
  onBack: () => void;
  recovery: string | null;
  checking: boolean;
  onCheck: () => void;
  onRetry?: () => void;
}) {
  return (
    <aside className="cart-drawer">
      <header>
        <div>
          <ShoppingCart size={17} />
          <span>
            <strong>Your cart</strong>
            <small>{cart.item_count} items</small>
          </span>
        </div>
        <button type="button" aria-label="Close cart" onClick={onClose}>
          <X size={17} />
        </button>
      </header>
      <div className="cart-scroll">
        {recovery ? (
          <section className="checkout-review" role="status">
            <h2>Checking your checkout</h2>
            <p>{recovery}</p>
            {notice && <p>{notice}</p>}
            <div className="payment-actions">
              <button disabled={checking || pending !== null} onClick={onCheck}>
                <RefreshCw size={16} /> {checking ? "Checking" : "Check status"}
              </button>
              {onRetry && <button disabled={checking || pending !== null} onClick={onRetry}>
                Retry same test payment
              </button>}
            </div>
          </section>
        ) : confirmation?.status === "succeeded" && confirmation.order ? (
          <section className="order-confirmation">
            <CheckCircle2 size={34} />
            <h2>Order confirmed</h2>
            <p>{confirmation.message}</p>
            <dl>
              <div>
                <dt>Order</dt>
                <dd>{confirmation.order.order_number}</dd>
              </div>
              <div>
                <dt>Total</dt>
                <dd>{formatMoney(confirmation.order.total)}</dd>
              </div>
              <div>
                <dt>Payment</dt>
                <dd>Local test only</dd>
              </div>
            </dl>
            <button type="button" onClick={onBack}>
              Back to cart
            </button>
          </section>
        ) : checkout ? (
          <section className="checkout-review">
            <button className="checkout-back" type="button" onClick={onBack}>
              Back to cart
            </button>
            <div className="checkout-heading">
              <CreditCard size={21} />
              <div>
                <h2>Review checkout</h2>
                <p>Inventory is held for 15 minutes.</p>
              </div>
            </div>
            <div className="checkout-lines">
              {checkout.lines.map((line) => (
                <div key={line.variant_id}>
                  <span>
                    {line.quantity} x {line.title}
                  </span>
                  <strong>{formatMoney(line.line_total)}</strong>
                </div>
              ))}
            </div>
            <div className="cart-total">
              <span>Total</span>
              <strong>{formatMoney(checkout.total)}</strong>
            </div>
            <div className="demo-payment-note">
              <AlertTriangle size={16} />
              <p>
                <strong>Demo payment</strong>No card is charged or stored. Pick
                an outcome to test the flow.
              </p>
            </div>
            {confirmation?.status === "requires_payment_method" && (
              <p className="payment-declined">
                Payment declined as requested. The inventory hold remains
                active.
              </p>
            )}
            {notice && <p className="cart-notice">{notice}</p>}
            <div className="payment-actions">
              <button
                type="button"
                disabled={pending !== null || checking}
                onClick={() => onConfirm("test_success")}
              >
                <CheckCircle2 size={16} />
                {pending === "checkout-confirm"
                  ? "Processing"
                  : "Approve test payment"}
              </button>
              <button
                type="button"
                disabled={pending !== null || checking}
                onClick={() => onConfirm("test_decline")}
              >
                Test decline
              </button>
            </div>
          </section>
        ) : cart.lines.length ? (
          <>
            <div className="cart-lines">
              {cart.lines.map((line) => (
                <article key={line.id}>
                  <div className="cart-line-image">
                    {line.image_url ? (
                      <Image
                        src={line.image_url}
                        alt=""
                        fill
                        sizes="56px"
                        unoptimized
                      />
                    ) : (
                      <Package size={21} />
                    )}
                  </div>
                  <div className="cart-line-copy">
                    <strong>{line.title}</strong>
                    <span>{formatMoney(line.unit_price)}</span>
                    <div className="quantity-control">
                      <button
                        type="button"
                        aria-label={`Decrease ${line.title}`}
                        disabled={pending !== null}
                        onClick={() => onQuantity(line.id, line.quantity - 1)}
                      >
                        <Minus size={13} />
                      </button>
                      <b>{line.quantity}</b>
                      <button
                        type="button"
                        aria-label={`Increase ${line.title}`}
                        disabled={pending !== null || line.quantity >= 20}
                        onClick={() => onQuantity(line.id, line.quantity + 1)}
                      >
                        <Plus size={13} />
                      </button>
                    </div>
                  </div>
                  <strong className="cart-line-total">
                    {formatMoney(line.line_total)}
                  </strong>
                </article>
              ))}
            </div>
            {notice && <p className="cart-notice">{notice}</p>}
          </>
        ) : (
          <div className="empty-cart">
            <ShoppingBag size={28} />
            <h2>Your cart is empty</h2>
            <p>
              Ask the shopping agent for ideas, then add a product from its
              results.
            </p>
          </div>
        )}
      </div>
      {!recovery && !checkout && !confirmation && cart.lines.length > 0 && (
        <footer className="cart-footer">
          <div>
            <span>Subtotal</span>
            <strong>{formatMoney(cart.subtotal)}</strong>
          </div>
          <button type="button" disabled={pending !== null || checking} onClick={onReview}>
            {pending === "checkout-preview"
              ? "Checking stock"
              : "Review checkout"}
          </button>
          <small>
            Taxes, shipping, fulfillment, and real payment are not part of this
            local MVP.
          </small>
        </footer>
      )}
    </aside>
  );
}

function ShopperAgentWorking() {
  const [elapsed, setElapsed] = useState(0);
  useEffect(() => {
    const started = Date.now();
    const timer = window.setInterval(
      () => setElapsed(Math.floor((Date.now() - started) / 1000)),
      1000,
    );
    return () => window.clearInterval(timer);
  }, []);
  return (
    <div className="shopper-working" role="status" aria-live="polite">
      <span className="message-avatar">
        <Bot size={18} />
      </span>
      <div>
        <strong>Shop assistant is working</strong>
        <p>
          <i />
          <i />
          <i />
          <span>
            Waiting for a reply · {elapsed}s
          </span>
        </p>
        <small>
          Private reasoning stays private; validated search activity appears
          with the reply.
        </small>
      </div>
    </div>
  );
}

function Loading() {
  return (
    <main className="shop-loading">
      <span>GA</span>
      <p>Opening the store...</p>
    </main>
  );
}

function formatTime(value: string) {
  return new Intl.DateTimeFormat("en", {
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));
}

function formatMoney(value: NonNullable<Cart["total"]>) {
  return `${value.currency} ${(value.amount_minor / 100).toFixed(2)}`;
}

function emptyCart(): CartState {
  return {
    id: null,
    status: "open",
    lines: [],
    subtotal: { amount_minor: 0, currency: "USD" },
    total: { amount_minor: 0, currency: "USD" },
    item_count: 0,
    version: 0,
    updated_at: null,
  };
}

function normalizeCart(value: Cart): CartState {
  const fallback = emptyCart();
  return {
    ...value,
    lines: value.lines ?? fallback.lines,
    subtotal: value.subtotal ?? fallback.subtotal,
    total: value.total ?? fallback.total,
    item_count: value.item_count ?? 0,
    version: value.version ?? 0,
  };
}
