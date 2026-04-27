const STORAGE_KEY = "stayease_conversation_id";
const chatLog = document.getElementById("chat-log");
const chatForm = document.getElementById("chat-form");
const messageInput = document.getElementById("message-input");
const sendButton = document.getElementById("send-button");
const loadingIndicator = document.getElementById("loading-indicator");
const emptyState = document.getElementById("empty-state");
const errorBanner = document.getElementById("error-banner");
const conversationIdText = document.getElementById("conversation-id");
const newChatButton = document.getElementById("new-chat-button");

const state = {
  conversationId: loadConversationId(),
  messages: [],
  isLoading: false,
  error: null,
};

conversationIdText.textContent = state.conversationId;

chatForm.addEventListener("submit", onSubmit);
newChatButton.addEventListener("click", resetConversation);
messageInput.addEventListener("input", autoResizeTextarea);

void initializeChat();

function loadConversationId() {
  const existingId = localStorage.getItem(STORAGE_KEY);
  if (existingId) {
    return existingId;
  }

  const freshId = crypto.randomUUID();
  localStorage.setItem(STORAGE_KEY, freshId);
  return freshId;
}

async function initializeChat() {
  setLoading(true);
  clearError();

  try {
    const response = await fetch(`/api/chat/${encodeURIComponent(state.conversationId)}/history`);
    if (response.status === 404) {
      state.messages = [];
      renderMessages();
      return;
    }

    if (!response.ok) {
      throw new Error("Unable to load previous messages right now.");
    }

    const data = await response.json();
    state.messages = data.messages.map((item) => ({
      role: item.role,
      messageText: item.message_text,
      createdAt: item.created_at,
    }));
    renderMessages();
  } catch (error) {
    showError(error.message || "Unable to load chat history.");
    renderMessages();
  } finally {
    setLoading(false);
  }
}

async function onSubmit(event) {
  event.preventDefault();
  const rawMessage = messageInput.value.trim();
  if (!rawMessage || state.isLoading) {
    return;
  }

  clearError();
  const optimisticMessage = {
    role: "user",
    messageText: rawMessage,
    createdAt: new Date().toISOString(),
  };
  state.messages.push(optimisticMessage);
  renderMessages();

  messageInput.value = "";
  autoResizeTextarea();
  setLoading(true);

  try {
    const response = await fetch(`/api/chat/${encodeURIComponent(state.conversationId)}/message`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        message: rawMessage,
        guest_id: "web-guest",
      }),
    });

    if (!response.ok) {
      const errorPayload = await safeJson(response);
      const errorMessage = errorPayload?.detail || "Unable to send your message right now.";
      throw new Error(errorMessage);
    }

    const data = await response.json();
    state.messages.push({
      role: "assistant",
      messageText: data.reply,
      createdAt: new Date().toISOString(),
      intent: data.intent,
      toolResult: data.tool_result,
      escalated: data.escalated,
    });
    renderMessages();
  } catch (error) {
    state.messages.pop();
    renderMessages();
    messageInput.value = rawMessage;
    autoResizeTextarea();
    showError(error.message || "Unable to send your message right now.");
  } finally {
    setLoading(false);
    messageInput.focus();
  }
}

function renderMessages() {
  const hasMessages = state.messages.length > 0;
  emptyState.classList.toggle("hidden", hasMessages);

  const existingMessages = chatLog.querySelectorAll(".message");
  existingMessages.forEach((node) => node.remove());

  state.messages.forEach((message) => {
    const wrapper = document.createElement("article");
    wrapper.className = `message ${message.role}${message.escalated ? " escalate" : ""}`;

    const bubble = document.createElement("div");
    bubble.className = "bubble";
    bubble.textContent = message.messageText;
    wrapper.appendChild(bubble);

    if (message.toolResult) {
      const toolNode = buildToolResult(message.toolResult, message.intent);
      if (toolNode) {
        wrapper.appendChild(toolNode);
      }
    }

    const meta = document.createElement("div");
    meta.className = "message-meta";
    meta.textContent = formatMeta(message);
    wrapper.appendChild(meta);

    chatLog.appendChild(wrapper);
  });

  chatLog.scrollTop = chatLog.scrollHeight;
}

function buildToolResult(toolResult, intent) {
  if (intent === "search" && Array.isArray(toolResult.properties) && toolResult.properties.length > 0) {
    const container = document.createElement("div");
    container.className = "tool-cards";

    toolResult.properties.forEach((property) => {
      const card = document.createElement("section");
      card.className = "tool-card";
      card.innerHTML = `
        <h4>${escapeHtml(property.title)}</h4>
        <p>${escapeHtml(property.area)}, ${escapeHtml(property.location)}</p>
        <p>Fits up to ${property.max_guests} guests</p>
        <span class="tool-pill">BDT ${property.price_bdt}/night · ${escapeHtml(property.listing_id)}</span>
      `;
      container.appendChild(card);
    });
    return container;
  }

  if (intent === "book" && toolResult.booking_id) {
    const card = document.createElement("section");
    card.className = "tool-card";
    card.innerHTML = `
      <h4>Booking Confirmed</h4>
      <p>Booking ID: ${escapeHtml(toolResult.booking_id)}</p>
      <p>Total: BDT ${toolResult.total_price_bdt}</p>
      <span class="tool-pill">${escapeHtml(toolResult.status || "confirmed")}</span>
    `;
    return card;
  }

  if (intent === "details" && toolResult.listing_id) {
    const card = document.createElement("section");
    card.className = "tool-card";
    const amenities = Array.isArray(toolResult.amenities) ? toolResult.amenities.join(", ") : "";
    card.innerHTML = `
      <h4>${escapeHtml(toolResult.title || "Listing Details")}</h4>
      <p>${escapeHtml(toolResult.area || "")}${toolResult.area ? ", " : ""}${escapeHtml(toolResult.location || "")}</p>
      <p>BDT ${toolResult.nightly_price_bdt}/night · Max ${toolResult.max_guests} guests</p>
      ${amenities ? `<p>Amenities: ${escapeHtml(amenities)}</p>` : ""}
      <span class="tool-pill">${escapeHtml(toolResult.listing_id)}</span>
    `;
    return card;
  }

  return null;
}

function formatMeta(message) {
  const roleLabel = message.role === "user" ? "You" : "StayEase";
  if (!message.createdAt) {
    return roleLabel;
  }

  const formattedTime = new Date(message.createdAt).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  });
  return `${roleLabel} · ${formattedTime}`;
}

function setLoading(isLoading) {
  state.isLoading = isLoading;
  loadingIndicator.classList.toggle("hidden", !isLoading);
  sendButton.disabled = isLoading;
  messageInput.disabled = isLoading;
  newChatButton.disabled = isLoading;
}

function showError(message) {
  state.error = message;
  errorBanner.textContent = message;
  errorBanner.classList.remove("hidden");
}

function clearError() {
  state.error = null;
  errorBanner.textContent = "";
  errorBanner.classList.add("hidden");
}

function resetConversation() {
  if (state.isLoading) {
    return;
  }

  const freshId = crypto.randomUUID();
  localStorage.setItem(STORAGE_KEY, freshId);
  state.conversationId = freshId;
  state.messages = [];
  clearError();
  conversationIdText.textContent = freshId;
  renderMessages();
}

function autoResizeTextarea() {
  messageInput.style.height = "auto";
  messageInput.style.height = `${Math.min(messageInput.scrollHeight, 180)}px`;
}

async function safeJson(response) {
  try {
    return await response.json();
  } catch {
    return null;
  }
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}
