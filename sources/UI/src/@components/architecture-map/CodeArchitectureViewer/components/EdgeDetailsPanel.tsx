import React, { useEffect, useRef, useState } from "react";
import type { ArchitectureChatMessage } from "../../../../services/api";
import FormattedDetailValue from "./FormattedDetailValue";

interface EdgeDetailsPanelProps {
  selectedEdge: any;
  onClose: () => void;
  edgeDescription: string;
  isEdgeLoading: boolean;
  chatMessages: ArchitectureChatMessage[];
  isChatLoading: boolean;
  onSendChat: (message: string) => Promise<void>;
}

export default function EdgeDetailsPanel({
  selectedEdge,
  onClose,
  edgeDescription,
  isEdgeLoading,
  chatMessages,
  isChatLoading,
  onSendChat,
}: EdgeDetailsPanelProps) {
  const [chatInput, setChatInput] = useState("");
  const chatEndRef = useRef<HTMLDivElement | null>(null);
  const lastChatMessage = chatMessages[chatMessages.length - 1];
  const chatStatusLabel = isChatLoading ? "Preparing a response..." : null;
  const chatStatus = chatStatusLabel ? (
    <div className="chat-status" role="status" aria-live="polite">
      <span className="chat-status-indicator" aria-hidden="true">
        <span />
        <span />
        <span />
      </span>
      <span>{chatStatusLabel}</span>
    </div>
  ) : null;

  useEffect(() => {
    if (typeof chatEndRef.current?.scrollIntoView === "function") {
      chatEndRef.current.scrollIntoView({ block: "end" });
    }
  }, [
    chatMessages.length,
    isChatLoading,
    lastChatMessage?.content,
    lastChatMessage?.streaming,
  ]);

  const handleSendChat = async () => {
    const nextMessage = chatInput.trim();
    if (!nextMessage) return;
    setChatInput("");
    await onSendChat(nextMessage);
  };

  const handleKeyDown = (event: React.KeyboardEvent) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      handleSendChat();
    }
  };

  return (
    <aside className="node-details-panel chat-style">
      <div className="chat-header">
        <div className="chat-avatar node-type-edge">{"->"}</div>
        <div className="chat-title">
          <h3>
            {selectedEdge.label ||
              selectedEdge?.data?.relationship_type ||
              "Relationship"}
          </h3>
          <span className="chat-subtitle">Edge details</span>
        </div>
        <button className="close-btn" onClick={onClose}>
          ×
        </button>
      </div>

      <div className="chat-messages">
        <div className="detail-row description-row">
          <FormattedDetailValue
            value={
              isEdgeLoading
                ? "Generating description..."
                : edgeDescription ||
                  selectedEdge?.data?.description ||
                  "No description available"
            }
            className="description-text"
            preserveWhitespace
          />
        </div>

        {selectedEdge?.data?.relationship_type && (
          <div className="detail-row">
            <span className="detail-label">Relationship type</span>
            <FormattedDetailValue value={selectedEdge.data.relationship_type} />
          </div>
        )}

        {selectedEdge?.data?.protocol && (
          <div className="detail-row">
            <span className="detail-label">Protocol</span>
            <FormattedDetailValue value={selectedEdge.data.protocol} />
          </div>
        )}

        <div className="detail-row">
          <span className="detail-label">From</span>
          <FormattedDetailValue value={selectedEdge.source} />
        </div>
        <div className="detail-row">
          <span className="detail-label">To</span>
          <FormattedDetailValue value={selectedEdge.target} />
        </div>

        {selectedEdge?.data && (
          <div className="detail-row">
            <span className="detail-label">Metadata</span>
            <FormattedDetailValue value={selectedEdge.data} />
          </div>
        )}
        {chatMessages.map((message, index) => (
          <div
            key={`${message.role}-${index}`}
            className={`chat-message ${message.role}${message.streaming ? " streaming" : ""}`}
          >
            <div className="message-content">
              <FormattedDetailValue
                value={message.content}
                preserveWhitespace
              />
            </div>
          </div>
        ))}
        <div ref={chatEndRef} aria-hidden="true" />
      </div>

      <div className="chat-input-container">
        {chatStatus}
        <div className="chat-input-wrapper">
          <textarea
            placeholder="Ask about this relationship..."
            value={chatInput}
            onChange={(event) => setChatInput(event.target.value)}
            onKeyDown={handleKeyDown}
            rows={1}
          />
          <button
            className="send-btn"
            aria-label="Send chat message"
            onClick={handleSendChat}
            disabled={!chatInput.trim() || isChatLoading}
          >
            <svg
              width="18"
              height="18"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
            >
              <path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z" />
            </svg>
          </button>
        </div>
      </div>
    </aside>
  );
}
