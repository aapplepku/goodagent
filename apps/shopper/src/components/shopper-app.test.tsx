import type { Cart, CatalogBrowseResponse, CheckoutConfirmation, CheckoutRecovery, ShopperAccount, ShopperChatResponse, ShopperConversation, ShopperMemory } from "@open-commerce/sdk-typescript";
import { OpenCommerceApiError } from "@open-commerce/sdk-typescript";
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ShopperApp } from "./shopper-app";
import { saveAttempt } from "@/lib/checkout-attempt";
import { loadMemoryChange, saveMemoryChange } from "@/lib/memory-change";

const accountRequest = vi.hoisted(() => vi.fn());
vi.mock("@/lib/shopper-transport", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/shopper-transport")>();
  return { ...actual, useShopperTransport: (slug?: string) => {
    const transport = { ...actual.useShopperTransport(slug), request: accountRequest, forAccount: () => transport };
    return transport;
  } };
});

const account: ShopperAccount = {
  id: "80000000-0000-0000-0000-000000000001",
  username: "alex",
  display_name: "Alex",
  created_at: "2026-09-09T12:00:00Z",
};

function fakeClient() {
  const emptyCart = {
    id: null,
    status: "open" as const,
    lines: [],
    subtotal: { amount_minor: 0, currency: "USD" },
    total: { amount_minor: 0, currency: "USD" },
    item_count: 0,
    version: 0,
    updated_at: null,
  };
  const cart = {
    ...emptyCart,
    id: "83000000-0000-0000-0000-000000000001",
    lines: [
      {
        id: "84000000-0000-0000-0000-000000000001",
        product_id: "pasta-kit",
        variant_id: "pasta-kit-default",
        title: "Weeknight Pasta Kit",
        variant_title: "Default",
        image_url: null,
        quantity: 1,
        unit_price: { amount_minor: 1899, currency: "USD" },
        line_total: { amount_minor: 1899, currency: "USD" },
        available_quantity: 12,
        sellable_quantity: 12,
      },
    ],
    subtotal: { amount_minor: 1899, currency: "USD" },
    total: { amount_minor: 1899, currency: "USD" },
    item_count: 1,
    version: 2,
    updated_at: "2026-09-09T12:02:00Z",
  };
  const response: ShopperChatResponse = {
    conversation: {
      id: "81000000-0000-0000-0000-000000000001",
      title: "Dinner for four",
      created_at: "2026-09-09T12:01:00Z",
      updated_at: "2026-09-09T12:01:00Z",
      version: 1,
    },
    user_message: {
      id: "82000000-0000-0000-0000-000000000001",
      conversation_id: "81000000-0000-0000-0000-000000000001",
      role: "user",
      content: "Dinner for four under $35",
      steps: [],
      products: [],
      created_at: "2026-09-09T12:01:00Z",
    },
    assistant_message: {
      id: "82000000-0000-0000-0000-000000000002",
      conversation_id: "81000000-0000-0000-0000-000000000001",
      role: "assistant",
      content: "I found a strong pantry option.",
      created_at: "2026-09-09T12:01:01Z",
      products: [
        {
          product_id: "pasta-kit",
          title: "Weeknight Pasta Kit",
          brand: "Northstar",
          category: "Pantry",
          price_minor: 1899,
          currency: "USD",
          score: "0.91",
          highlights: ["quick dinner"],
          image_url: null,
          url: null,
        },
      ],
      steps: [
        {
          stage: "search",
          title: "Search the store catalog",
          detail: "Ran bounded hybrid retrieval.",
          status: "completed",
        },
      ],
    },
    memory_created: null,
  };
  return {
    shopperAccount: vi.fn(async (): Promise<{ account: typeof account }> => {
      throw new OpenCommerceApiError(401, null);
    }),
    registerShopper: vi.fn(async () => ({ account })),
    loginShopper: vi.fn(async () => ({ account })),
    logoutShopper: vi.fn(async () => undefined),
    shopperConversations: vi.fn(async (): Promise<{ items: ShopperConversation[] }> => ({ items: [] })),
    shopperConversation: vi.fn(),
    shopperMemories: vi.fn(async (): Promise<{ items: ShopperMemory[] }> => ({ items: [] })),
    shopperDiscovery: vi.fn(async () => ({
      catalog_status: "ready" as const,
      catalog_name: "abo-catalog.csv",
      product_count: 48,
      suggestions: [
        {
          label: "Explore Grocery",
          query: "Dinner for four under $35",
          category: "Grocery",
          image_url: "/abo-images/B07QCR35JF.jpg",
        },
      ],
    })),
    shopperCart: vi.fn(async (): Promise<Cart> => emptyCart),
    shopperCheckout: vi.fn(async (): Promise<CheckoutRecovery | null> => null),
    shopperOrders: vi.fn(async () => ({ items: [], next_offset: null, payment_mode: "local_test" as const })),
    shopperCatalog: vi.fn(async (): Promise<CatalogBrowseResponse> => ({ catalog: null, indexing: { status: "not_configured" as const }, categories: [], items: [], total: 0, offset: 0, limit: 24 })),
    addShopperCartItem: vi.fn(async () => cart),
    updateShopperCartItem: vi.fn(async () => cart),
    deleteShopperCartItem: vi.fn(async () => emptyCart),
    previewShopperCheckout: vi.fn(async () => ({
      checkout_id: "85000000-0000-0000-0000-000000000001",
      cart_id: cart.id,
      cart_version: cart.version,
      status: "requires_confirmation" as const,
      lines: [
        {
          product_id: "pasta-kit",
          variant_id: "pasta-kit-default",
          title: "Weeknight Pasta Kit",
          quantity: 1,
          unit_price: { amount_minor: 1899, currency: "USD" },
          line_total: { amount_minor: 1899, currency: "USD" },
        },
      ],
      subtotal: { amount_minor: 1899, currency: "USD" },
      total: { amount_minor: 1899, currency: "USD" },
      reservation_expires_at: "2026-09-09T12:17:00Z",
      payment_mode: "local_test" as const,
      policy: {
        allowed: true,
        code: "LOCAL_TEST_CHECKOUT_ALLOWED",
        reason: "Preconditions passed.",
        preconditions: ["stock"],
        rollback_strategy: "Release reservations.",
      },
    })),
    confirmShopperCheckout: vi.fn(async (): Promise<CheckoutConfirmation> => ({
      checkout_id: "85000000-0000-0000-0000-000000000001",
      status: "succeeded" as const,
      order: {
        id: "86000000-0000-0000-0000-000000000001",
        order_number: "OC-1234ABCD",
        status: "paid" as const,
        lines: [],
        total: { amount_minor: 1899, currency: "USD" },
        created_at: "2026-09-09T12:03:00Z",
      },
      failure_code: null,
      message: "Demo payment approved and order created.",
    })),
    deleteShopperMemory: vi.fn(async () => ({ memory_id: "", deleted: true })),
    chatWithShopper: vi.fn(async () => response),
  };
}

describe("ShopperApp", () => {
  it("preserves a newer composer draft when an earlier send fails", async () => {
    const client = fakeClient();
    client.shopperAccount.mockResolvedValue({ account });
    let rejectChat!: (error: Error) => void;
    client.chatWithShopper.mockImplementationOnce(() => new Promise((_, reject) => { rejectChat = reject; }));
    render(<ShopperApp client={client} />);
    const composer = await screen.findByLabelText("Shopping request");
    fireEvent.change(composer, { target: { value: "First submitted request" } });
    fireEvent.click(screen.getByRole("button", { name: "Send request" }));
    fireEvent.change(composer, { target: { value: "Newer unsent detail" } });
    await act(async () => rejectChat(new Error("Connection interrupted")));
    expect(composer).toHaveValue("Newer unsent detail");
    expect(screen.getByText("First submitted request")).toBeVisible();
    expect(screen.getByRole("button", { name: "Retry same request" })).toBeEnabled();
  });

  it("hides cached account data and offers recovery after a runtime 401", async () => {
    const client = fakeClient();
    client.shopperAccount.mockResolvedValue({ account });
    client.shopperCart.mockResolvedValue(await client.addShopperCartItem());
    client.chatWithShopper.mockRejectedValue(new OpenCommerceApiError(401, null));
    render(<ShopperApp client={client} />);
    await screen.findByRole("button", { name: "Open cart with 1 items" });
    fireEvent.change(screen.getByLabelText("Shopping request"), { target: { value: "My private unsent question" } });
    fireEvent.click(screen.getByRole("button", { name: "Send request" }));
    expect(await screen.findByRole("heading", { name: "Your shopping session expired" })).toBeVisible();
    expect(screen.queryByText("Alex")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Open cart/ })).not.toBeInTheDocument();
    expect(screen.queryByText("My private unsent question")).not.toBeInTheDocument();
    expect(screen.getByLabelText("Username")).toBeVisible();
    expect(client.chatWithShopper).toHaveBeenCalledTimes(1);
  });
  it("retries only the original chat receipt while preserving a newer draft", async () => {
    const client = fakeClient();
    client.shopperAccount.mockResolvedValue({ account });
    client.chatWithShopper.mockRejectedValueOnce(new Error("Response lost"));
    render(<ShopperApp client={client} />);
    const composer = await screen.findByLabelText("Shopping request");
    fireEvent.change(composer, { target: { value: "Original question" } });
    fireEvent.click(screen.getByRole("button", { name: "Send request" }));
    await screen.findByRole("button", { name: "Retry same request" });
    fireEvent.change(composer, { target: { value: "Newer unsent question" } });
    expect(screen.getByRole("button", { name: "Send request" })).toBeDisabled();
    fireEvent.keyDown(composer, { key: "Enter" });
    expect(client.chatWithShopper).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByRole("button", { name: "Retry same request" }));
    await screen.findByText("I found a strong pantry option.");
    expect(client.chatWithShopper.mock.calls[1]).toEqual(client.chatWithShopper.mock.calls[0]);
    expect(composer).toHaveValue("Newer unsent question");
    expect(screen.queryByRole("button", { name: "Retry same request" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Send request" })).toBeEnabled();
  });

  it("does not restore sent text over a draft the shopper intentionally cleared", async () => {
    const client = fakeClient();
    client.shopperAccount.mockResolvedValue({ account });
    let reject!: (error: Error) => void;
    client.chatWithShopper.mockImplementationOnce(() => new Promise((_, fail) => { reject = fail; }));
    render(<ShopperApp client={client} />);
    const composer = await screen.findByLabelText("Shopping request");
    fireEvent.change(composer, { target: { value: "Earlier question" } });
    fireEvent.click(screen.getByRole("button", { name: "Send request" }));
    fireEvent.change(composer, { target: { value: "Do not retain this draft" } });
    fireEvent.change(composer, { target: { value: "" } });
    await act(async () => reject(new Error("Response lost")));
    expect(composer).toHaveValue("");
    expect(screen.getByText("Earlier question")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Dismiss failed request" }));
    expect(screen.queryByText("Earlier question")).not.toBeInTheDocument();
    expect(client.chatWithShopper).toHaveBeenCalledTimes(1);
  });

  it("does not duplicate committed messages when replay follows a history refresh", async () => {
    const client = fakeClient();
    const response = await client.chatWithShopper();
    client.chatWithShopper.mockClear().mockRejectedValueOnce(new Error("Response lost"));
    client.shopperAccount.mockResolvedValue({ account });
    client.shopperConversations.mockResolvedValue({ items: [response.conversation] });
    client.shopperConversation.mockResolvedValueOnce({ conversation: response.conversation, messages: [] })
      .mockResolvedValue({ conversation: response.conversation, messages: [response.user_message, response.assistant_message] });
    render(<ShopperApp client={client} />);
    fireEvent.click(await screen.findByRole("button", { name: "Dinner for four" }));
    await waitFor(() => expect(client.shopperConversation).toHaveBeenCalledTimes(1));
    fireEvent.change(screen.getByLabelText("Shopping request"), { target: { value: response.user_message.content } });
    fireEvent.click(screen.getByRole("button", { name: "Send request" }));
    await screen.findByRole("button", { name: "Retry same request" });
    fireEvent.click(screen.getByRole("button", { name: "Dinner for four" }));
    await screen.findByText(response.assistant_message.content);
    fireEvent.click(screen.getByRole("button", { name: "Retry same request" }));
    await waitFor(() => expect(screen.queryByRole("button", { name: "Retry same request" })).not.toBeInTheDocument());
    expect(screen.getAllByText(response.assistant_message.content)).toHaveLength(1);
    expect(screen.getAllByText(response.user_message.content)).toHaveLength(1);
    expect(client.chatWithShopper.mock.calls[1]).toEqual(client.chatWithShopper.mock.calls[0]);
  });

  it("keeps a newly selected conversation when an older chat finishes", async () => {
    const client = fakeClient();
    const response = await client.chatWithShopper();
    client.chatWithShopper.mockClear();
    client.shopperAccount.mockResolvedValue({ account });
    render(<ShopperApp client={client} />);
    fireEvent.click(await screen.findByRole("button", { name: "Explore Grocery" }));
    await screen.findByText(response.assistant_message.content);
    let finish!: (result: ShopperChatResponse) => void;
    client.chatWithShopper.mockImplementationOnce(() => new Promise((resolve) => { finish = resolve; }));
    fireEvent.change(screen.getByLabelText("Shopping request"), { target: { value: "Old conversation follow-up" } });
    fireEvent.click(screen.getByRole("button", { name: "Send request" }));
    fireEvent.click(screen.getByRole("button", { name: "New conversation" }));
    fireEvent.change(screen.getByLabelText("Shopping request"), { target: { value: "Entirely new topic" } });
    await act(async () => finish(response));
    expect(screen.getByText("What can I help you find?")).toBeVisible();
    expect(screen.getByLabelText("Shopping request")).toHaveValue("Entirely new topic");
    fireEvent.click(screen.getByRole("button", { name: "Send request" }));
    await waitFor(() => expect(client.chatWithShopper).toHaveBeenLastCalledWith(
      { content: "Entirely new topic", conversation_id: null, expected_account_id: account.id }, expect.any(String),
    ));
  });

  it("keeps the issuing account bound when a failed request is retried", async () => {
    const client = fakeClient();
    client.shopperAccount.mockResolvedValue({ account });
    client.chatWithShopper.mockRejectedValueOnce(new Error("Response lost"))
      .mockRejectedValueOnce(new OpenCommerceApiError(401, null));
    render(<ShopperApp client={client} />);
    fireEvent.change(await screen.findByLabelText("Shopping request"), { target: { value: "Private account A request" } });
    fireEvent.click(screen.getByRole("button", { name: "Send request" }));
    await screen.findByRole("button", { name: "Retry same request" });
    // Another tab changed the cookie: the server rejects A's binding under B.
    client.shopperAccount.mockResolvedValue({ account: { ...account, id: "another-account", display_name: "Blake" } });
    fireEvent.click(screen.getByRole("button", { name: "Retry same request" }));
    await screen.findByRole("heading", { name: "Your shopping session expired" });
    expect(client.chatWithShopper).toHaveBeenCalledWith(
      { content: "Private account A request", conversation_id: null, expected_account_id: account.id }, expect.any(String),
    );
    expect(client.chatWithShopper.mock.calls[1]).toEqual(client.chatWithShopper.mock.calls[0]);
    fireEvent.click(screen.getByRole("button", { name: "Check session" }));
    await screen.findByText("Blake");
    expect(screen.getByLabelText("Shopping request")).toHaveValue("");
    expect(screen.queryByText("Private account A request")).not.toBeInTheDocument();
  });

  it.each([false, true])("does not redirect a new draft when an old retry finishes (recovery=%s)", async (recover) => {
    const client = fakeClient();
    client.shopperAccount.mockResolvedValue({ account });
    render(<ShopperApp client={client} />);
    fireEvent.click(await screen.findByRole("button", { name: "Explore Grocery" }));
    await screen.findByText("I found a strong pantry option.");
    client.chatWithShopper.mockRejectedValueOnce(new Error("Response lost"));
    fireEvent.change(screen.getByLabelText("Shopping request"), { target: { value: "Old follow-up" } });
    fireEvent.click(screen.getByRole("button", { name: "Send request" }));
    await screen.findByRole("button", { name: "Retry same request" });
    fireEvent.click(screen.getByRole("button", { name: "New conversation" }));
    fireEvent.change(screen.getByLabelText("Shopping request"), { target: { value: "Entirely new draft" } });
    if (recover) {
      client.shopperOrders.mockRejectedValueOnce(new OpenCommerceApiError(401, null));
      fireEvent.click(screen.getByRole("button", { name: "Demo orders" }));
      fireEvent.click(await screen.findByRole("button", { name: "Check session" }));
      await screen.findByLabelText("Shopping request");
    }
    fireEvent.click(screen.getByRole("button", { name: "Retry same request" }));
    await waitFor(() => expect(screen.queryByRole("button", { name: "Retry same request" })).not.toBeInTheDocument());
    expect(client.chatWithShopper.mock.calls[2]).toEqual(client.chatWithShopper.mock.calls[1]);
    expect(screen.getByText("What can I help you find?")).toBeVisible();
    expect(screen.getByLabelText("Shopping request")).toHaveValue("Entirely new draft");
    fireEvent.click(screen.getByRole("button", { name: "Send request" }));
    await waitFor(() => expect(client.chatWithShopper).toHaveBeenLastCalledWith(
      { content: "Entirely new draft", conversation_id: null, expected_account_id: account.id }, expect.any(String),
    ));
  });

  it("hides an expired guest visit when registration requires reauthentication", async () => {
    accountRequest.mockReset();
    const client = fakeClient();
    client.shopperAccount.mockResolvedValue({ account: { ...account, is_guest: true } });
    accountRequest.mockRejectedValueOnce(new OpenCommerceApiError(401, null));
    render(<ShopperApp client={client} store={{ slug: "fixture", name: "Fixture", description: "Test", currency: "USD" }} />);
    fireEvent.change(await screen.findByLabelText("Shopping request"), { target: { value: "Private guest draft" } });
    fireEvent.click(screen.getByRole("button", { name: "Save your progress" }));
    fireEvent.submit(screen.getByLabelText("Username").closest("form")!);
    await screen.findByRole("heading", { name: "Your shopping session expired" });
    expect(screen.queryByLabelText("Shopping request")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Check session" }));
    expect(await screen.findByLabelText("Shopping request")).toHaveValue("Private guest draft");
    expect(accountRequest).toHaveBeenCalledTimes(1);
  });

  it("restores the draft and exact failed receipt only after checking the same account", async () => {
    const client = fakeClient();
    client.shopperAccount.mockResolvedValue({ account });
    client.chatWithShopper.mockRejectedValueOnce(new OpenCommerceApiError(401, null));
    render(<ShopperApp client={client} />);
    fireEvent.change(await screen.findByLabelText("Shopping request"), { target: { value: "Private question" } });
    fireEvent.click(screen.getByRole("button", { name: "Send request" }));
    await screen.findByRole("heading", { name: "Your shopping session expired" });
    expect(JSON.stringify(sessionStorage)).not.toContain("Private question");
    fireEvent.click(screen.getByRole("button", { name: "Check session" }));
    expect(await screen.findByLabelText("Shopping request")).toHaveValue("Private question");
    expect(client.shopperAccount).toHaveBeenCalledTimes(2);
    expect(client.chatWithShopper).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByRole("button", { name: "Retry same request" }));
    await screen.findByText("I found a strong pantry option.");
    expect(client.chatWithShopper.mock.calls[1]).toEqual(client.chatWithShopper.mock.calls[0]);
  });

  it("discards private drafts and failed receipts after recovery into a different account", async () => {
    const client = fakeClient();
    client.shopperAccount.mockResolvedValueOnce({ account }).mockResolvedValue({ account: { ...account, id: "another-account", display_name: "Blake" } });
    client.chatWithShopper.mockRejectedValueOnce(new OpenCommerceApiError(401, null));
    render(<ShopperApp client={client} />);
    fireEvent.change(await screen.findByLabelText("Shopping request"), { target: { value: "Private question" } });
    fireEvent.click(screen.getByRole("button", { name: "Send request" }));
    fireEvent.click(await screen.findByRole("button", { name: "Check session" }));
    expect(await screen.findByText("Blake")).toBeVisible();
    expect(screen.getByLabelText("Shopping request")).toHaveValue("");
    expect(screen.queryByText("Private question")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Retry same request" })).not.toBeInTheDocument();
    expect(client.chatWithShopper).toHaveBeenCalledTimes(1);
  });

  it("requires a matching server session after sign-in before restoring the draft", async () => {
    const client = fakeClient();
    client.shopperAccount.mockResolvedValueOnce({ account }).mockResolvedValueOnce({ account: { ...account, id: "unexpected-account" } }).mockResolvedValue({ account });
    client.chatWithShopper.mockRejectedValueOnce(new OpenCommerceApiError(401, null));
    render(<ShopperApp client={client} />);
    fireEvent.change(await screen.findByLabelText("Shopping request"), { target: { value: "Private question" } });
    fireEvent.click(screen.getByRole("button", { name: "Send request" }));
    fireEvent.change(await screen.findByLabelText("Username"), { target: { value: "alex" } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "synthetic-test-password" } });
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
    await screen.findByText(/We couldn't sign you in/);
    expect(screen.queryByLabelText("Shopping request")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByLabelText("Shopping request")).toHaveValue("Private question");
    expect(client.chatWithShopper).toHaveBeenCalledTimes(1);
  });

  it.each([403, 503])("does not mistake HTTP %s for an expired session", async (status) => {
    const client = fakeClient();
    client.shopperAccount.mockResolvedValue({ account });
    client.chatWithShopper.mockRejectedValueOnce(new OpenCommerceApiError(status, null));
    render(<ShopperApp client={client} />);
    fireEvent.change(await screen.findByLabelText("Shopping request"), { target: { value: "Question" } });
    fireEvent.click(screen.getByRole("button", { name: "Send request" }));
    await screen.findByRole("button", { name: "Retry same request" });
    expect(screen.getByText("Alex")).toBeVisible();
    expect(screen.queryByRole("heading", { name: "Your shopping session expired" })).not.toBeInTheDocument();
  });

  it("ignores an earlier account's delayed 401 after the account has changed", async () => {
    const client = fakeClient();
    client.shopperAccount.mockResolvedValue({ account });
    let reject!: (error: Error) => void;
    client.chatWithShopper.mockImplementationOnce(() => new Promise((_, fail) => { reject = fail; }));
    const { rerender } = render(<ShopperApp client={client} />);
    fireEvent.change(await screen.findByLabelText("Shopping request"), { target: { value: "Private question" } });
    fireEvent.click(screen.getByRole("button", { name: "Send request" }));
    const next = fakeClient();
    next.shopperAccount.mockResolvedValue({ account: { ...account, id: "another-account", display_name: "Blake" } });
    rerender(<ShopperApp client={next} />);
    await screen.findByText("Blake");
    await act(async () => reject(new OpenCommerceApiError(401, null)));
    expect(screen.getByText("Blake")).toBeVisible();
    expect(screen.getByLabelText("Shopping request")).toHaveValue("");
    expect(screen.queryByRole("heading", { name: "Your shopping session expired" })).not.toBeInTheDocument();
  });

  it("retains an interrupted memory command through same-account recovery without replay", async () => {
    accountRequest.mockReset();
    const client = fakeClient();
    client.shopperAccount.mockResolvedValue({ account });
    accountRequest.mockRejectedValueOnce(new OpenCommerceApiError(401, null));
    render(<ShopperApp client={client} store={{ slug: "fixture", name: "Fixture", description: "Test", currency: "USD" }} />);
    fireEvent.click(await screen.findByRole("button", { name: "Account" }));
    fireEvent.click(screen.getByLabelText("Remember shopping preferences"));
    await screen.findByRole("heading", { name: "Your shopping session expired" });
    const saved = loadMemoryChange(`fixture:${account.id}`);
    expect(saved).not.toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Check session" }));
    await screen.findByText(/Memory setting is unverified/);
    expect(accountRequest).toHaveBeenCalledTimes(1);
    accountRequest.mockResolvedValueOnce({ account: { ...account, memory_enabled: false } });
    fireEvent.click(screen.getByRole("button", { name: "Retry memory change" }));
    await waitFor(() => expect(loadMemoryChange(`fixture:${account.id}`)).toBeNull());
    expect(accountRequest.mock.calls[1]).toEqual(accountRequest.mock.calls[0]);
  });

  it("retains an interrupted checkout receipt and checks status without repeating payment", async () => {
    const client = fakeClient();
    client.shopperAccount.mockResolvedValue({ account });
    client.shopperCart.mockResolvedValue(await client.addShopperCartItem());
    const preview = await client.previewShopperCheckout();
    preview.reservation_expires_at = "2099-01-01T00:00:00Z";
    client.previewShopperCheckout.mockResolvedValue(preview);
    client.confirmShopperCheckout.mockRejectedValueOnce(new OpenCommerceApiError(401, null));
    render(<ShopperApp client={client} />);
    fireEvent.click(await screen.findByRole("button", { name: "Open cart with 1 items" }));
    fireEvent.click(screen.getByRole("button", { name: "Review checkout" }));
    fireEvent.click(await screen.findByRole("button", { name: "Approve test payment" }));
    await screen.findByRole("heading", { name: "Your shopping session expired" });
    const saved = sessionStorage.getItem(`checkout:legacy:${account.id}`);
    expect(saved).not.toBeNull();
    client.shopperCheckout.mockResolvedValue({ checkout_id: preview.checkout_id, status: "processing", preview, message: "Processing" });
    fireEvent.click(screen.getByRole("button", { name: "Check session" }));
    await screen.findByText("Checking your checkout");
    expect(client.confirmShopperCheckout).toHaveBeenCalledTimes(1);
    expect(sessionStorage.getItem(`checkout:legacy:${account.id}`)).toBe(saved);
    expect(client.shopperCheckout).toHaveBeenLastCalledWith(preview.checkout_id);
  });

  it("starts a new guest only explicitly and never transfers the prior draft", async () => {
    accountRequest.mockReset();
    const client = fakeClient();
    client.shopperAccount.mockResolvedValue({ account: { ...account, is_guest: true } });
    client.chatWithShopper.mockRejectedValueOnce(new OpenCommerceApiError(401, null));
    client.logoutShopper.mockRejectedValueOnce(new Error("Offline"));
    accountRequest.mockResolvedValueOnce({ account: { ...account, id: "new-guest", display_name: "Guest", is_guest: true }, created: true });
    render(<ShopperApp client={client} store={{ slug: "fixture", name: "Fixture", description: "Test", currency: "USD" }} />);
    fireEvent.change(await screen.findByLabelText("Shopping request"), { target: { value: "Private question" } });
    fireEvent.click(screen.getByRole("button", { name: "Send request" }));
    await screen.findByRole("heading", { name: "Your shopping session expired" });
    expect(accountRequest).not.toHaveBeenCalled();
    expect(client.logoutShopper).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Start a new guest visit" }));
    await screen.findByText(/We couldn't start a new guest visit/);
    expect(accountRequest).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Start a new guest visit" }));
    await screen.findByText("Guest");
    expect(accountRequest).toHaveBeenCalledExactlyOnceWith("/v1/shopper/auth/guest", "POST");
    expect(screen.getByLabelText("Shopping request")).toHaveValue("");
    expect(screen.queryByText("Private question")).not.toBeInTheDocument();
  });

  it("does not offer a new public guest visit from a private preview", async () => {
    const client = fakeClient();
    client.shopperAccount.mockResolvedValue({ account });
    client.chatWithShopper.mockRejectedValueOnce(new OpenCommerceApiError(401, null));
    render(<ShopperApp client={client} store={{ slug: "fixture", name: "Fixture", description: "Test", currency: "USD", preview: true }} />);
    fireEvent.change(await screen.findByLabelText("Shopping request"), { target: { value: "Question" } });
    fireEvent.click(screen.getByRole("button", { name: "Send request" }));
    await screen.findByRole("heading", { name: "Your shopping session expired" });
    expect(screen.queryByRole("button", { name: "Start a new guest visit" })).not.toBeInTheDocument();
  });

  it("drops a suspended draft when navigating to a different store without a session", async () => {
    const client = fakeClient();
    client.shopperAccount.mockResolvedValueOnce({ account }).mockRejectedValue(new OpenCommerceApiError(401, null));
    client.chatWithShopper.mockRejectedValueOnce(new OpenCommerceApiError(401, null));
    const store = { slug: "first", name: "First", description: "Test", currency: "USD" };
    const { rerender } = render(<ShopperApp client={client} store={store} />);
    fireEvent.change(await screen.findByLabelText("Shopping request"), { target: { value: "Private question" } });
    fireEvent.click(screen.getByRole("button", { name: "Send request" }));
    await screen.findByRole("heading", { name: "Your shopping session expired" });
    rerender(<ShopperApp client={client} store={{ ...store, slug: "second", name: "Second" }} />);
    expect(await screen.findByLabelText("Username")).toBeVisible();
    expect(screen.queryByText("Private question")).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Your shopping session expired" })).not.toBeInTheDocument();
  });
  it("uses GoodAgent Shop and GA when no merchant store is provided", async () => {
    const client = fakeClient();
    client.shopperAccount.mockResolvedValue({ account });
    render(<ShopperApp client={client} />);
    const brand = await screen.findByText("GoodAgent Shop");
    const header = within(brand.closest("header")!);
    expect(header.getByText("GoodAgent Shop")).toBeVisible();
    expect(header.getByText("GA")).toBeVisible();
  });

  it.each([
    ["Northstar Goods", "NG"],
    ["Open Commerce Shop", "OC"],
  ])("preserves merchant store name %s and initials %s", async (name, initials) => {
    const client = fakeClient();
    client.shopperAccount.mockResolvedValue({ account });
    render(<ShopperApp client={client} store={{ slug: "fixture", name, description: "Test", currency: "USD" }} />);
    const brand = await screen.findByText(name);
    const header = within(brand.closest("header")!);
    expect(header.getByText(name)).toBeVisible();
    expect(header.getByText(initials)).toBeVisible();
    expect(header.queryByText("GoodAgent Shop")).not.toBeInTheDocument();
  });

  it("cannot overlap a pending deletion with settings changes after reopening Account", async () => {
    accountRequest.mockReset();
    const client = fakeClient();
    client.shopperAccount.mockResolvedValue({ account: { ...account, memory_enabled: false } });
    let resolveDeletion!: (value: unknown) => void;
    accountRequest.mockImplementationOnce(() => new Promise((resolve) => { resolveDeletion = resolve; }));
    render(<ShopperApp client={client} store={{ slug: "fixture", name: "Fixture", description: "Test", currency: "USD" }} />);
    fireEvent.click(await screen.findByRole("button", { name: "Account" }));
    fireEvent.click(screen.getByRole("button", { name: "Delete shopping data" }));
    fireEvent.click(screen.getByRole("button", { name: "Confirm deletion" }));
    fireEvent.click(screen.getByRole("button", { name: "Close account" }));
    fireEvent.click(screen.getByRole("button", { name: "Account" }));
    expect(screen.getByLabelText("Remember shopping preferences")).toBeDisabled();
    fireEvent.click(screen.getByLabelText("Remember shopping preferences"));
    expect(accountRequest).toHaveBeenCalledTimes(1);
    fireEvent.change(screen.getByLabelText("Shopping request"), { target: { value: "I prefer organic tea" } });
    fireEvent.keyDown(screen.getByLabelText("Shopping request"), { key: "Enter" });
    expect(client.chatWithShopper).not.toHaveBeenCalled();
    await act(async () => resolveDeletion(null));
    fireEvent.click(screen.getByRole("button", { name: "Account" }));
    expect(screen.getByLabelText("Remember shopping preferences")).not.toBeChecked();
    expect(screen.getByLabelText("Remember shopping preferences")).toBeEnabled();
  });
  it("keeps a pending memory change serialized when Account is closed and reopened", async () => {
    accountRequest.mockReset();
    const client = fakeClient();
    client.shopperAccount.mockResolvedValue({ account });
    let resolveSetting!: (value: unknown) => void;
    accountRequest.mockImplementationOnce(() => new Promise((resolve) => { resolveSetting = resolve; }));
    render(<ShopperApp client={client} store={{ slug: "fixture", name: "Fixture", description: "Test", currency: "USD" }} />);
    fireEvent.click(await screen.findByRole("button", { name: "Account" }));
    fireEvent.click(screen.getByLabelText("Remember shopping preferences"));
    expect(accountRequest).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByRole("button", { name: "Close account" }));
    fireEvent.click(screen.getByRole("button", { name: "Account" }));
    expect(screen.getByLabelText("Remember shopping preferences")).toBeDisabled();
    fireEvent.click(screen.getByLabelText("Remember shopping preferences"));
    expect(accountRequest).toHaveBeenCalledTimes(1);
    fireEvent.change(screen.getByLabelText("Shopping request"), { target: { value: "Find me a snack" } });
    expect(screen.getByRole("button", { name: "Send request" })).toBeDisabled();
    await act(async () => resolveSetting({ account: { ...account, memory_enabled: false } }));
    expect(screen.getByLabelText("Remember shopping preferences")).not.toBeChecked();
    expect(screen.getByLabelText("Remember shopping preferences")).toBeEnabled();
    expect(screen.getByRole("button", { name: "Send request" })).toBeEnabled();
    accountRequest.mockResolvedValueOnce({ account: { ...account, memory_enabled: true } });
    fireEvent.click(screen.getByLabelText("Remember shopping preferences"));
    await waitFor(() => expect(screen.getByLabelText("Remember shopping preferences")).toBeChecked());
    expect(accountRequest).toHaveBeenCalledTimes(2);
    expect(accountRequest).toHaveBeenLastCalledWith("/v1/shopper/preferences", "PATCH", { enabled: true }, expect.any(String));
  });
  it("keeps chat paused after a lost settings response and retries the same command after reload", async () => {
    accountRequest.mockReset();
    const client = fakeClient();
    const off = { ...account, memory_enabled: false };
    client.shopperAccount.mockResolvedValue({ account: off });
    accountRequest.mockRejectedValueOnce(new Error("Response lost"));
    const props = { client, store: { slug: "fixture", name: "Fixture", description: "Test", currency: "USD" } };
    const first = render(<ShopperApp {...props} />);
    fireEvent.click(await screen.findByRole("button", { name: "Account" }));
    fireEvent.click(screen.getByLabelText("Remember shopping preferences"));
    await screen.findByText(/Memory setting is unverified/);
    fireEvent.change(screen.getByLabelText("Shopping request"), { target: { value: "I prefer organic tea" } });
    expect(screen.getByRole("button", { name: "Send request" })).toBeDisabled();
    fireEvent.keyDown(screen.getByLabelText("Shopping request"), { key: "Enter" });
    expect(client.chatWithShopper).not.toHaveBeenCalled();
    const saved = loadMemoryChange(`fixture:${account.id}`)!;
    expect(saved.enabled).toBe(true);
    first.unmount();
    render(<ShopperApp {...props} />);
    await screen.findByText(/Memory setting is unverified/);
    accountRequest.mockResolvedValueOnce({ account: { ...account, memory_enabled: true } });
    fireEvent.click(screen.getByRole("button", { name: "Retry memory change" }));
    await waitFor(() => expect(screen.queryByText(/Memory setting is unverified/)).not.toBeInTheDocument());
    expect(accountRequest).toHaveBeenCalledTimes(2);
    expect(accountRequest.mock.calls[1]).toEqual(accountRequest.mock.calls[0]);
    expect(accountRequest).toHaveBeenLastCalledWith("/v1/shopper/preferences", "PATCH", { enabled: true }, saved.key);
    expect(loadMemoryChange(`fixture:${account.id}`)).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Account" }));
    expect(screen.getByLabelText("Remember shopping preferences")).toBeChecked();
  });
  it("does not apply another account's pending memory change", async () => {
    accountRequest.mockReset();
    const client = fakeClient();
    client.shopperAccount.mockResolvedValue({ account });
    saveMemoryChange("fixture:another-account", { key: crypto.randomUUID(), enabled: false });
    render(<ShopperApp client={client} store={{ slug: "fixture", name: "Fixture", description: "Test", currency: "USD" }} />);
    await screen.findByRole("button", { name: "Account" });
    expect(screen.queryByText(/Memory setting is unverified/)).not.toBeInTheDocument();
    expect(accountRequest).not.toHaveBeenCalled();
  });
  it("returns an expired demo confirmation to a fresh cart review without automatic retry", async () => {
    const client = fakeClient();
    client.shopperAccount.mockResolvedValue({ account });
    const preview = await client.previewShopperCheckout();
    preview.reservation_expires_at = "2099-01-01T00:00:00Z";
    const key = "12345678-1234-1234-1234-123456789013";
    saveAttempt(`legacy:${account.id}`, { checkoutId: preview.checkout_id,
      cartVersion: preview.cart_version, expiresAt: preview.reservation_expires_at,
      key, method: "test_success" });
    client.shopperCheckout.mockResolvedValue({ checkout_id: preview.checkout_id,
      status: "processing", preview, message: "Still processing" });
    client.confirmShopperCheckout.mockResolvedValue({ checkout_id: preview.checkout_id,
      status: "cancelled", order: null, failure_code: "checkout_changed_during_confirmation",
      message: "Demo checkout expired. Review the current cart." });
    render(<ShopperApp client={client} />);
    fireEvent.click(await screen.findByRole("button", { name: "Retry same test payment" }));
    expect(await screen.findByText("Demo checkout expired. Review the current cart.")).toBeVisible();
    expect(screen.queryByText("Checking your checkout")).not.toBeInTheDocument();
    expect(client.confirmShopperCheckout).toHaveBeenCalledTimes(1);
    expect(sessionStorage.getItem(`checkout:legacy:${account.id}`)).toBeNull();
  });
  it("restores processing checkout after reload and retries only the persisted key and method", async () => {
    const client = fakeClient();
    client.shopperAccount.mockResolvedValue({ account });
    const preview = await client.previewShopperCheckout();
    preview.reservation_expires_at = "2099-01-01T00:00:00Z";
    const scope = `legacy:${account.id}`;
    const key = "12345678-1234-1234-1234-123456789012";
    saveAttempt(scope, { checkoutId: preview.checkout_id, cartVersion: preview.cart_version,
      expiresAt: preview.reservation_expires_at, key, method: "test_success" });
    client.shopperCheckout.mockResolvedValue({ checkout_id: preview.checkout_id, status: "processing",
      preview, message: "Confirmation is still processing." });
    render(<ShopperApp client={client} />);
    expect(await screen.findByText("Checking your checkout")).toBeVisible();
    expect(client.confirmShopperCheckout).not.toHaveBeenCalled();
    expect(screen.queryByRole("button", { name: "Approve test payment" })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Retry same test payment" }));
    expect(await screen.findByText("Order confirmed")).toBeVisible();
    expect(client.confirmShopperCheckout).toHaveBeenCalledWith({ checkout_id: preview.checkout_id, payment_method: "test_success" }, key);
    expect(sessionStorage.getItem(`checkout:${scope}`)).toBeNull();
  });

  it("recovers completed payment through status without repeating confirmation", async () => {
    const client = fakeClient();
    client.shopperAccount.mockResolvedValue({ account });
    const preview = await client.previewShopperCheckout();
    client.shopperCheckout.mockResolvedValueOnce({ checkout_id: preview.checkout_id, status: "processing",
      preview, message: "Still processing." });
    render(<ShopperApp client={client} />);
    expect(await screen.findByText("Checking your checkout")).toBeVisible();
    expect(screen.queryByText("Retry same test payment")).not.toBeInTheDocument();
    const confirmation = await client.confirmShopperCheckout();
    client.confirmShopperCheckout.mockClear();
    client.shopperCheckout.mockResolvedValue({ checkout_id: preview.checkout_id, status: "succeeded", confirmation, message: "Confirmed" });
    fireEvent.click(screen.getByRole("button", { name: "Check status" }));
    expect(await screen.findByText("Order confirmed")).toBeVisible();
    expect(client.confirmShopperCheckout).not.toHaveBeenCalled();
    expect(client.shopperCheckout).toHaveBeenLastCalledWith(preview.checkout_id);
  });
  it("requires an explicit variant for chat products without a storefront prop", async () => {
    const client = fakeClient();
    client.shopperAccount.mockResolvedValue({ account });
    client.shopperCatalog.mockResolvedValue({
      catalog: null, indexing: { status: "ready" }, categories: [], total: 1, offset: 0, limit: 1,
      items: [{
        product_id: "pasta-kit", title: "Weeknight Pasta Kit", brand: "Northstar",
        category: "Pantry", description: "Pick a size", image_url: null,
        variant_id: "small", price: { amount_minor: 1899, currency: "USD" },
        availability: "available", provenance: null,
        variants: [
          { id: "small", title: "Small", options: {}, price: { amount_minor: 1899, currency: "USD" }, available: true },
          { id: "large", title: "Large", options: {}, price: { amount_minor: 2499, currency: "USD" }, available: true },
        ],
      }],
    });
    render(<ShopperApp client={client} />);
    fireEvent.click(await screen.findByRole("button", { name: "Explore Grocery" }));
    fireEvent.click(await screen.findByRole("button", { name: "Add" }));
    expect(await screen.findByLabelText("Choose a variant")).toHaveValue("");
    expect(client.addShopperCartItem).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Add to cart" })).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Choose a variant"), { target: { value: "large" } });
    fireEvent.click(screen.getByRole("button", { name: "Add to cart" }));
    await waitFor(() => expect(client.addShopperCartItem).toHaveBeenCalledWith(
      { product_id: "pasta-kit", quantity: 1, variant_id: "large" }, expect.any(String),
    ));
  });

  it("does not carry a previous account's cart into an unavailable new session", async () => {
    const previous = fakeClient();
    previous.shopperAccount.mockResolvedValue({ account });
    previous.shopperCart.mockResolvedValue(await previous.addShopperCartItem());
    const { rerender } = render(<ShopperApp client={previous} />);
    await screen.findByRole("button", { name: "Open cart with 1 items" });
    const next = fakeClient();
    next.shopperAccount.mockResolvedValue({ account: { ...account, id: "different-account", display_name: "Blake" } });
    next.shopperCart.mockRejectedValue(new Error("offline"));
    rerender(<ShopperApp client={next} />);
    await screen.findByRole("alert");
    expect(screen.getByText("Blake")).toBeVisible();
    expect(screen.queryByRole("button", { name: "Open cart with 1 items" })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Open cart" }));
    expect(screen.getByRole("status")).toHaveTextContent("unavailable, not empty");
  });
  it("discards an old account's delayed chat response after identity changes", async () => {
    const previous = fakeClient();
    previous.shopperAccount.mockResolvedValue({ account });
    const response = await previous.chatWithShopper();
    let resolveChat!: (value: ShopperChatResponse) => void;
    previous.chatWithShopper.mockImplementationOnce(() => new Promise((resolve) => { resolveChat = resolve; }));
    const { rerender } = render(<ShopperApp client={previous} />);
    await screen.findByLabelText("Shopping request");
    fireEvent.change(screen.getByLabelText("Shopping request"), { target: { value: "Dinner for four under $35" } });
    fireEvent.click(screen.getByRole("button", { name: "Send request" }));
    expect(screen.getByRole("status")).toHaveTextContent("Shop assistant is working");
    const next = fakeClient();
    next.shopperAccount.mockResolvedValue({ account: { ...account, id: "different-account", display_name: "Blake" } });
    rerender(<ShopperApp client={next} />);
    await screen.findByText("Blake");
    await act(async () => resolveChat(response));
    expect(screen.queryByText("I found a strong pantry option.")).not.toBeInTheDocument();
    expect(screen.queryByText("Dinner for four under $35")).not.toBeInTheDocument();
    expect(screen.getByLabelText("Shopping request")).toHaveValue("");
  });
  it("retries an unavailable session without presenting registration", async () => {
    const client = fakeClient();
    client.shopperAccount.mockRejectedValueOnce(new OpenCommerceApiError(503, null));
    client.shopperAccount.mockResolvedValue({ account });
    render(<ShopperApp client={client} />);
    expect(await screen.findByRole("alert")).toHaveTextContent("have not been reset");
    expect(screen.queryByLabelText("Username")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Retry connection" }));
    expect(await screen.findByText("What are we shopping for?")).toBeVisible();
  });

  it("keeps the account, draft and cart when sign-out fails; retries server revocation", async () => {
    const client = fakeClient();
    client.shopperAccount.mockResolvedValue({ account });
    client.shopperCart.mockResolvedValue(await client.addShopperCartItem());
    client.logoutShopper.mockRejectedValueOnce(new Error("offline"));
    render(<ShopperApp client={client} />);
    await screen.findByRole("button", { name: "Open cart with 1 items" });
    fireEvent.change(screen.getByLabelText("Shopping request"), { target: { value: "My unsent request" } });
    fireEvent.click(screen.getByRole("button", { name: "Sign out" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("may still be active");
    expect(screen.getByLabelText("Shopping request")).toHaveValue("My unsent request");
    expect(screen.getByRole("button", { name: "Open cart with 1 items" })).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Retry sign-out" }));
    expect(await screen.findByLabelText("Username")).toBeVisible();
    expect(screen.queryByText("Alex")).not.toBeInTheDocument();
    expect(client.logoutShopper).toHaveBeenCalledTimes(2);
  });

  it("loads the cart and suggestions even while memory is slow, then retries memory alone", async () => {
    const client = fakeClient();
    client.shopperAccount.mockResolvedValue({ account });
    client.shopperCart.mockResolvedValue(await client.addShopperCartItem());
    let rejectMemory!: (reason: Error) => void;
    client.shopperMemories.mockImplementationOnce(() => new Promise((_, reject) => { rejectMemory = reject; }));
    render(<ShopperApp client={client} />);
    expect(await screen.findByRole("button", { name: "Open cart with 1 items" })).toBeVisible();
    expect(screen.getByRole("button", { name: "Explore Grocery" })).toBeVisible();
    await act(async () => rejectMemory(new Error("unavailable")));
    expect(screen.getByRole("alert")).toHaveTextContent("Could not load memory");
    fireEvent.click(screen.getByRole("button", { name: /Shopping memory/ }));
    expect(screen.queryByText("No saved preferences yet.")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Retry unavailable sections" }));
    expect(await screen.findByText("No saved preferences yet.")).toBeVisible();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(client.shopperCart).toHaveBeenCalledTimes(1);
    expect(client.shopperMemories).toHaveBeenCalledTimes(2);
  });

  it("does not show a failed cart load as an empty cart", async () => {
    const client = fakeClient();
    client.shopperAccount.mockResolvedValue({ account });
    client.shopperCart.mockRejectedValueOnce(new Error("offline"));
    client.shopperCart.mockResolvedValue(await client.addShopperCartItem());
    render(<ShopperApp client={client} />);
    await screen.findByRole("alert");
    fireEvent.click(screen.getByRole("button", { name: "Open cart" }));
    expect(screen.getByRole("status")).toHaveTextContent("unavailable, not empty");
    expect(screen.queryByText("Your cart is empty")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Review checkout" })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Retry unavailable sections" }));
    expect(await screen.findByRole("button", { name: "Review checkout" })).toBeEnabled();
    expect(screen.getByText("Weeknight Pasta Kit")).toBeVisible();
  });

  it("discards workspace reads that finish after sign-out", async () => {
    const client = fakeClient();
    client.shopperAccount.mockResolvedValue({ account });
    let resolveCart!: (value: Cart) => void;
    client.shopperCart.mockImplementationOnce(() => new Promise((resolve) => { resolveCart = resolve; }));
    render(<ShopperApp client={client} />);
    await screen.findByRole("button", { name: "Sign out" });
    fireEvent.click(screen.getByRole("button", { name: "Sign out" }));
    await screen.findByLabelText("Username");
    await act(async () => resolveCart(await client.addShopperCartItem()));
    expect(screen.queryByRole("button", { name: /Open cart with/ })).not.toBeInTheDocument();
    expect(screen.getByLabelText("Username")).toBeVisible();
  });
  it("refreshes committed memories from their current authoritative state", async () => {
    const client = fakeClient();
    client.shopperAccount.mockResolvedValue({ account });
    const response = await client.chatWithShopper();
    const memory = { id: "saved-1", content: "i am into organic stuffs", created_at: account.created_at };
    response.memory_created = memory;
    response.memories_saved = [memory, { ...memory, id: "saved-2", content: "Premium is my usual choice" }];
    client.shopperMemories.mockResolvedValueOnce({ items: [] }).mockResolvedValue({ items: response.memories_saved });
    response.assistant_message.content = "Saved your shopping preferences.";
    response.assistant_message.steps = [{ stage: "remember", title: "Saved", detail: memory.content, status: "completed" }];
    render(<ShopperApp client={client} />);
    await screen.findByText("What are we shopping for?");
    fireEvent.change(screen.getByLabelText("Shopping request"), { target: { value: memory.content } });
    fireEvent.click(screen.getByRole("button", { name: "Send request" }));
    expect(await screen.findByText("Saved to shopping memory")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: /Shopping memory/ }));
    const drawer = screen.getByText("Your saved shopping preferences. Remove any you no longer want remembered.").closest("aside")!;
    expect(within(drawer).getByText(memory.content)).toBeVisible();
    expect(screen.getByText("Premium is my usual choice")).toBeVisible();
  });
  it("does not restore a deleted preference from a late chat receipt", async () => {
    const client = fakeClient();
    client.shopperAccount.mockResolvedValue({ account });
    const memory = { id: "saved-1", content: "Organic is my preference", created_at: account.created_at };
    let removed = false;
    client.shopperMemories.mockImplementation(async () => ({ items: removed ? [] : [memory] }));
    client.deleteShopperMemory.mockImplementation(async () => { removed = true; return { deleted: true, memory_id: memory.id }; });
    const response = await client.chatWithShopper();
    response.memory_created = memory;
    response.memories_saved = [memory];
    let resolveChat!: (value: ShopperChatResponse) => void;
    client.chatWithShopper.mockImplementationOnce(() => new Promise((resolve) => { resolveChat = resolve; }));
    render(<ShopperApp client={client} />);
    await screen.findByText("What are we shopping for?");
    fireEvent.change(screen.getByLabelText("Shopping request"), { target: { value: "Find me a snack" } });
    fireEvent.click(screen.getByRole("button", { name: "Send request" }));
    fireEvent.click(screen.getByRole("button", { name: /Shopping memory/ }));
    fireEvent.click(await screen.findByRole("button", { name: `Forget ${memory.content}` }));
    await screen.findByText("No saved preferences yet.");
    await act(async () => resolveChat(response));
    await waitFor(() => expect(client.shopperMemories).toHaveBeenCalledTimes(3));
    expect(screen.queryByRole("button", { name: `Forget ${memory.content}` })).not.toBeInTheDocument();
    expect(screen.getByText("No saved preferences yet.")).toBeVisible();
  });
  it("ignores a memory refresh that started before deletion was confirmed", async () => {
    const client = fakeClient();
    client.shopperAccount.mockResolvedValue({ account });
    const memory = { id: "saved-1", content: "Organic is my preference", created_at: account.created_at };
    let resolveMemory!: (value: { items: ShopperMemory[] }) => void;
    client.shopperMemories.mockResolvedValueOnce({ items: [memory] }).mockImplementationOnce(() => new Promise((resolve) => { resolveMemory = resolve; }));
    render(<ShopperApp client={client} />);
    await screen.findByText("What are we shopping for?");
    fireEvent.change(screen.getByLabelText("Shopping request"), { target: { value: "Find me a snack" } });
    fireEvent.click(screen.getByRole("button", { name: "Send request" }));
    await waitFor(() => expect(client.shopperMemories).toHaveBeenCalledTimes(2));
    fireEvent.click(screen.getByRole("button", { name: /Shopping memory/ }));
    fireEvent.click(await screen.findByRole("button", { name: `Forget ${memory.content}` }));
    await screen.findByText("No saved preferences yet.");
    await act(async () => resolveMemory({ items: [memory] }));
    expect(screen.queryByRole("button", { name: `Forget ${memory.content}` })).not.toBeInTheDocument();
    expect(screen.getByText("No saved preferences yet.")).toBeVisible();
  });
  it("does not show a saved-memory badge for an unsuccessful tool step", async () => {
    const client = fakeClient();
    client.shopperAccount.mockResolvedValue({ account });
    const response = await client.chatWithShopper();
    response.assistant_message.content = "Your preference was not saved.";
    response.assistant_message.steps = [{ stage: "remember", title: "Save failed", detail: "Storage unavailable", status: "needs_input" }];
    render(<ShopperApp client={client} />);
    await screen.findByText("What are we shopping for?");
    fireEvent.change(screen.getByLabelText("Shopping request"), { target: { value: "i am into organic stuffs" } });
    fireEvent.click(screen.getByRole("button", { name: "Send request" }));
    expect(await screen.findByText("Your preference was not saved.")).toBeVisible();
    expect(screen.queryByText("Saved to shopping memory")).not.toBeInTheDocument();
  });
  it("creates an account and runs a grounded shopping conversation", async () => {
    const client = fakeClient();
    render(<ShopperApp client={client} />);

    expect(await screen.findByText("Your store, in conversation.")).toBeVisible();
    fireEvent.change(screen.getByLabelText("Display name"), {
      target: { value: "Alex" },
    });
    fireEvent.change(screen.getByLabelText("Username"), {
      target: { value: "alex" },
    });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "local-demo-password" },
    });
    const form = screen.getByRole("heading", { name: "Start shopping" }).closest("form");
    expect(form).not.toBeNull();
    fireEvent.click(
      within(form!).getAllByRole("button", { name: "Create account" })[1],
    );

    expect(await screen.findByText("What are we shopping for?")).toBeVisible();
    expect(screen.getByText("48 products from abo-catalog.csv")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Explore Grocery" }));

    expect(screen.getByText("Dinner for four under $35")).toBeVisible();
    expect(screen.getByRole("status")).toHaveTextContent("Shop assistant is working");

    expect(await screen.findByText("I found a strong pantry option.")).toBeVisible();
    expect(screen.getByText("Weeknight Pasta Kit")).toBeVisible();
    expect(screen.getByText("USD 18.99")).toBeVisible();
    fireEvent.click(screen.getByText("How I searched"));
    expect(screen.getByText("Ran bounded hybrid retrieval.")).toBeVisible();
    await waitFor(() =>
      expect(client.chatWithShopper).toHaveBeenCalledWith(
        { content: "Dinner for four under $35", conversation_id: null, expected_account_id: account.id },
        expect.any(String),
      ),
    );

    fireEvent.click(screen.getByRole("button", { name: "Add" }));
    expect(await screen.findByText("Your cart")).toBeVisible();
    expect(screen.getByText("1 items")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Review checkout" }));
    expect(await screen.findByText("Demo payment")).toBeVisible();
    fireEvent.click(
      screen.getByRole("button", { name: "Approve test payment" }),
    );
    expect(await screen.findByText("Order confirmed")).toBeVisible();
    expect(screen.getByText("OC-1234ABCD")).toBeVisible();
    expect(client.addShopperCartItem).toHaveBeenCalledWith(
      { product_id: "pasta-kit", quantity: 1 },
      expect.any(String),
    );
    expect(client.confirmShopperCheckout).toHaveBeenCalledWith(
      {
        checkout_id: "85000000-0000-0000-0000-000000000001",
        payment_method: "test_success",
      },
      expect.any(String),
    );
  });
});
